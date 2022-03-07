from __future__ import annotations

import json
import logging
from datetime import datetime
from math import inf
from pathlib import Path
from traceback import format_exc
from typing import Any, Optional

import anyio
import PySimpleGUI as sg
from anyio.abc import TaskGroup, TaskStatus
from anyio.streams.memory import MemoryObjectReceiveStream

from ..commands import (
    RESET_DEVICE_STATUS_MAP,
    ResetDeviceSettings,
    StepSettings,
    reset_device,
)
from ..config.branding import Branding
from ..device import DeviceDescription, DeviceType
from ..logging import set_logging_defaults
from ..progress import (
    Cancelled,
    Completed,
    Failed,
    Idle,
    Skipped,
    StatusMap,
    StatusStream,
)
from ._command_log import CommandLog, CommandStatus
from ._config import COMMAND_LOG_PATH, GUI_CONFIG_PATH, LowLevelConfig
from ._layout import create_layout
from ._logging import GuiFormatter, GuiHandler

ResetParams = tuple[DeviceDescription, Path, Branding]

_LOGGER = logging.getLogger()  # root logger


class WindowEventLoop:
    """Event loop for the GUI."""

    def __init__(self, tg: TaskGroup) -> None:
        self._tg = tg
        self._cancel_scope: Optional[anyio.CancelScope] = None
        self._done: Optional[anyio.Event] = None
        # Load low-level config
        self._low_level_config = LowLevelConfig.try_from_config_file()
        # Create the Window
        self._window = sg.Window(
            "Reset Device", create_layout(), enable_close_attempted_event=True
        )
        # Widgets
        self._hostname_device_abbr: sg.Input = self._window["hostname_device_abbr"]
        self._hostname_id: sg.Input = self._window["hostname_id"]
        self._command_log_output: sg.Multiline = self._window["command_log"]
        self._output: sg.Multiline = self._window["output"]
        self._submit: sg.Button = self._window["submit"]
        # Progress
        self._progress_send_stream: StatusStream
        self._progress_receive_stream: MemoryObjectReceiveStream[StatusMap]
        (
            self._progress_send_stream,
            self._progress_receive_stream,
        ) = anyio.create_memory_object_stream(inf)
        self._status_map = RESET_DEVICE_STATUS_MAP
        self._tg.start_soon(self._receive_steps)
        # Command log
        self._command_log = CommandLog(COMMAND_LOG_PATH)
        # Logging
        handler = GuiHandler(self._output)
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(GuiFormatter())
        _LOGGER.addHandler(handler)

    async def run_forever(self) -> None:
        """Iterate this event loop indefinitely."""
        params: Optional[ResetParams] = None
        prev_values: Optional[dict[str, Any]] = None

        initial_iteration = True

        with self._command_log:
            # Event Loop to process "events" and get the "values" of the inputs
            while True:
                # This is a very crude and CPU-intensive way to integrate
                # an async event loop with PySimpleGUI.
                await anyio.sleep(0.1)
                event, values = self._window.read(0)

                if event == sg.WINDOW_CLOSE_ATTEMPTED_EVENT:
                    self._tg.cancel_scope.cancel()
                    if self._done is not None:
                        await self._done.wait()
                    break

                if initial_iteration is True:
                    self._update_command_log()
                    initial_iteration = False

                # Persist GUI state
                filtered_values = {
                    k: v
                    for k, v in values.items()
                    if not k.endswith("_status")
                    and k != "output"
                    and k != "command_log"
                    and k != "Browse"
                }
                values_changed = prev_values != filtered_values
                prev_values = filtered_values
                if values_changed:
                    with GUI_CONFIG_PATH.open("w") as config_file:
                        json.dump(filtered_values, config_file)

                    self._output.update(value="", background_color="white")

                    hostname = _get_hostname(values)
                    if self._command_log.contains(
                        status=CommandStatus.COMPLETED,
                        hostname=hostname,
                    ):
                        self._output.print(
                            f'\n  Warning: A previous run already used the hostname "{hostname}".\n',
                            background_color="yellow",
                        )
                        # Print an empty line for separation
                        self._output.print()
                    self._output.print('Press "Start" to reset the device')

                self._validate_forms(values)
                self._update_progress()
                self._update_hostname_device_abbr(values)

                # Check parameters when the task doesn't run. Otherwise, we may erroneously
                # clear `_output`. E.g., while we power cycle the USB port, the TTY is not
                # available, which raises a `ValidationError`.
                if self._cancel_scope is None:
                    try:
                        params = _get_parameters(self._low_level_config, values)
                    # Catch broad `Exception` as we want to handle all the general errors
                    except Exception as exc:  # pylint: disable=broad-except
                        self._output.update(
                            value=str(exc),
                            text_color="black",
                            background_color="lightgrey",
                        )
                        params = None
                        self._submit.update(disabled=True)
                    else:
                        self._submit.update(disabled=False)

                if event == "submit":
                    if self._cancel_scope is None:
                        # The quick user can invalidate the params and press start
                        # almost at the same time. Therefore, we have a `None` check
                        # here.
                        if params is not None:
                            settings = _get_reset_device_settings(values)
                            self._tg.start_soon(self._start_task_ui, params, settings)
                    else:
                        self._tg.start_soon(self._cancel_task_ui)

    async def _start_task_ui(
        self, params: ResetParams, settings: ResetDeviceSettings
    ) -> None:
        # Early out if the task already runs. We need this check even though
        # we disable the "Start" button. This is because it is possible
        # to quickly trigger the "Start" button twice before we disable it.
        if self._cancel_scope is not None:
            return

        async def _reset_device(task_status: TaskStatus) -> None:
            assert self._cancel_scope is not None
            assert self._done is not None
            hostname = params[0].link.communication.hostname
            with self._cancel_scope:
                try:
                    task_status.started()
                    await reset_device(
                        *params,
                        settings=settings,
                        progress_stream=self._progress_send_stream,
                        logger=_LOGGER,
                    )
                # Catch broad `Exception` as we want to handle all the general errors
                except (
                    anyio.ExceptionGroup,
                    Exception,
                ):  # pylint: disable=broad-except
                    self._command_log.add(
                        status=CommandStatus.FAILED, hostname=hostname
                    )
                    self._output.print(format_exc(), background_color="red")
                else:
                    # Increment hostname ID if we changed it
                    if settings.reset_config.enabled:
                        self._increment_hostname_id()
                    self._command_log.add(
                        status=CommandStatus.COMPLETED, hostname=hostname
                    )
                    self._output.print(
                        "\n\n\n    Done\n\n\n",
                        text_color="white",
                        background_color="green",
                    )
                finally:
                    self._update_command_log()
                    self._disable_parameters(False)
                    self._submit.update(text="Start")
                    self._done.set()
            self._cancel_scope = None

        self._disable_parameters(True)
        self._output.update(value="")
        self._submit.update(text="Stop", disabled=True)

        self._cancel_scope = anyio.CancelScope()
        self._done = anyio.Event()
        await self._tg.start(_reset_device)

        self._submit.update(disabled=False)

    async def _cancel_task_ui(self) -> None:
        # Early out if the task is done. We need this check even though
        # we disable the "Stop" button. This is because it is possible
        # to quickly trigger the "Stop" button twice before we disable it.
        if self._cancel_scope is None:
            return

        self._submit.update(disabled=True)
        await self._cancel_task()
        self._submit.update(disabled=False)

    async def _cancel_task(self) -> None:
        assert self._cancel_scope is not None
        assert self._done is not None
        self._cancel_scope.cancel()
        await self._done.wait()
        self._cancel_scope = None

    async def _receive_steps(self) -> None:
        async with self._progress_receive_stream:
            async for status_map in self._progress_receive_stream:
                self._status_map = status_map

    def _update_progress(self) -> None:
        now = datetime.now()
        for name, status in self._status_map.items():
            progress_bar: sg.ProgressBar = self._window[name]
            status_bar: sg.StatusBar = self._window[f"{name}_status"]
            if isinstance(status, Idle):
                progress_bar.update(0)
                status_bar.update("Pending")
                continue
            if isinstance(status, Skipped):
                progress_bar.update(0)
                status_bar.update("Skipped")
                continue
            if isinstance(status, Completed):
                progress_bar.update(100)
                text = "Completed"
                if status.tries > 1:
                    text += f" (tries: {status.tries})"
                status_bar.update(text)
                continue
            if isinstance(status, Failed):
                status_bar.update("Failed")
                continue
            if isinstance(status, Cancelled):
                status_bar.update("Cancelled")
                continue
            elapsed = now - status.begin_at
            remaining = status.expected_duration - elapsed
            ratio = elapsed / status.expected_duration * 100
            progress_bar.update(ratio)
            text = f"Max {int(remaining.total_seconds())} seconds left"
            if status.tries > 1:
                text += f" (tries: {status.tries})"
            status_bar.update(text)

    def _validate_forms(self, values: dict[str, Any]) -> None:
        self._validate_form(values, "hostname_year", max_length=2)
        self._validate_form(values, "hostname_week", max_length=2)
        self._validate_form(values, "hostname_id", max_length=3)

    def _validate_form(
        self, values: dict[str, Any], key: str, *, max_length: Optional[int] = None
    ) -> None:
        widget: sg.Input = self._window[key]
        value = values[key]
        # Max length
        if max_length is not None and len(value) > max_length:
            widget.update(value[:max_length])

    def _update_hostname_device_abbr(self, values: dict[str, Any]) -> None:
        device_type = values["device_type"]
        abbrs = {
            "BACTOBOX": "bb",
            "ZEUS": "zs",
        }
        abbr = abbrs.get(device_type, "")
        self._hostname_device_abbr.update(value=abbr)

    def _update_command_log(self) -> None:
        self._command_log_output.update("")
        for row in self._command_log.rows:
            if row.status is CommandStatus.COMPLETED:
                text_color = "white"
                background_color = "green"
            elif row.status is CommandStatus.FAILED:
                text_color = "white"
                background_color = "red"
            else:
                text_color = "black"
                background_color = "white"
            self._command_log_output.print(
                row.hostname, text_color=text_color, background_color=background_color
            )

    def _increment_hostname_id(self) -> None:
        try:
            current_id = int(self._hostname_id.get())
        except ValueError:
            return
        next_id = (current_id + 1) % 1000
        value = f"{next_id:03d}"
        self._hostname_id.update(value)

    def _disable_parameters(self, flag: bool) -> None:
        parameter_elements = (
            e
            for e in self._window.element_list()
            if isinstance(e, (sg.Listbox, sg.Combo))
            or (isinstance(e, sg.Input) and not e.Key == "hostname_device_abbr")
            or (
                isinstance(e, (sg.Checkbox, sg.Spin))
                and not e.Key.startswith("prepare")
            )
            or (isinstance(e, sg.Button) and e.ButtonText == "Browse")
        )
        for element in parameter_elements:
            element.update(disabled=flag)


def _get_parameters(
    low_level_config: LowLevelConfig, values: dict[str, Any]
) -> ResetParams:
    # SWU
    swu = Path(values["swu_file"])
    if not swu.is_file():
        raise ValueError(f"The SWU path {swu} is not a file")
    # Device description
    device_type = next(dt for dt in DeviceType if dt.name == values["device_type"])
    device_version = values["device_version"]
    hostname = _get_hostname(values)
    desc = DeviceDescription.from_raw_args(
        device_type=device_type,
        device_version=device_version,
        hostname=hostname,
        tty=low_level_config.tty,
        jtag_usb_serial=low_level_config.jtag_usb_serial,
        power_relay=low_level_config.power_relay,
        boot_mode_gpio=low_level_config.boot_mode_gpio,
    )
    # Branding
    branding = next(br for br in Branding if br.name == values["branding"])
    return (desc, swu, branding)


def _get_hostname(values: dict[str, Any]) -> str:
    device_abbr = values["hostname_device_abbr"]
    year = values["hostname_year"]
    week = values["hostname_week"]
    id_ = values["hostname_id"]
    return f"{device_abbr}{year}{week}{id_}"


def _get_reset_device_settings(values: dict[str, Any]) -> ResetDeviceSettings:
    args = (
        StepSettings(
            values[f"{name}_enabled"],
            values[f"{name}_max_tries"],
        )
        for name in RESET_DEVICE_STATUS_MAP
        if name != "prepare"
    )
    return ResetDeviceSettings(*args)


async def _gui_async() -> None:
    async with anyio.create_task_group() as tg:
        wel = WindowEventLoop(tg)
        tg.start_soon(wel.run_forever)


def gui() -> None:
    """Start the GUI."""
    set_logging_defaults()
    anyio.run(_gui_async)
