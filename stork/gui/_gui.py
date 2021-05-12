from __future__ import annotations

import asyncio
import json
import logging
import traceback
from contextlib import suppress
from functools import partial
from pathlib import Path
from types import TracebackType
from typing import Any, AsyncContextManager, Optional, Type

import PySimpleGUI as sg

from .. import commands
from ..branding import Branding
from ..hardware import Hardware, raise_if_bad_hostname

_CONFIG = Path("./.stork.json").absolute()

_LOGGER = logging.getLogger(__name__)


def _layout() -> list[Any]:
    sg.theme("SystemDefaultForReal")

    try:
        with _CONFIG.open("r") as f:
            defaults = json.load(f)
    except OSError:
        defaults = {}

    swu_layout = [
        [
            sg.Input(key="swu_file", default_text=defaults.get("swu_file")),
            sg.FileBrowse(file_types=(("SWUpdate files", "*.swu"),)),
        ],
    ]

    hardware_layout = [
        [
            sg.Combo(
                key="hardware",
                values=[hw.name for hw in Hardware],
                default_value=defaults.get("hardware"),
                size=(20, None),
            ),
        ],
    ]

    branding_layout = [
        [
            sg.Combo(
                key="branding",
                values=[hw.name for hw in Branding],
                default_value=defaults.get("branding"),
                size=(20, None),
            ),
        ],
    ]

    hostname_layout = [
        [sg.Input(key="hostname", default_text=defaults.get("hostname"))],
    ]

    fsbl_layout = [
        [
            sg.Input(key="fsbl_elf", default_text=defaults.get("fsbl_elf")),
            sg.FileBrowse(file_types=(("ELF files", "*.elf"),)),
        ],
    ]

    parameter_layout = [
        [
            sg.Frame("SWUpdate file", swu_layout),
            sg.Frame("First-stage boot loader (FSBL)", fsbl_layout),
        ],
        [
            sg.Frame("Hardware", hardware_layout),
            sg.Frame("Branding", branding_layout),
            sg.Frame("Hostname", hostname_layout),
        ],
    ]

    # All the stuff inside your window.
    return [
        [sg.Column(parameter_layout)],
        [
            sg.Multiline(
                key="messages",
                size=(80, 30),
                font=("Monospace", 8),
                disabled=True,
            ),
            sg.Multiline(
                key="output",
                size=(80, 30),
                font=("Monospace", 8),
                disabled=True,
            ),
        ],
        [
            sg.Button("Start"),
            sg.Button("Continue", disabled=True),
            sg.Button("Stop", disabled=True),
            sg.StatusBar(text="", key="status", size=(80, 1)),
        ],
    ]


class WindowEventLoop(AsyncContextManager["WindowEventLoop"]):
    def __init__(self) -> None:
        self._task: Optional[asyncio.Task] = None
        self._continue_event = asyncio.Event()
        # Create the Window
        self._window = sg.Window("Stork", _layout())
        # Widgets
        self._start_button: sg.Button = self._window["Start"]
        self._continue_button: sg.Button = self._window["Continue"]
        self._stop_button: sg.Button = self._window["Stop"]
        self._messages: sg.Multiline = self._window["messages"]
        self._output: sg.Multiline = self._window["output"]
        self._status: sg.Text = self._window["status"]

    async def run_forever(self) -> None:
        prev_params = None
        # Event Loop to process "events" and get the "values" of the inputs
        while True:
            # This is a very crude and CPU-intensive way to integrate
            # asyncio with PySimpleGUI.
            await asyncio.sleep(0.01)
            event, values = self._window.read(0)
            # Persist values
            if values is not None:
                with _CONFIG.open("w") as f:
                    json.dump(values, f)

            if event == sg.WIN_CLOSED:
                break

            try:
                params = _get_parameters(values)
            except Exception as exc:
                self._messages.update(value=str(exc), background_color="lightgrey")
                self._start_button.update(disabled=True)
                params = None
            params_changed = prev_params != params
            prev_params = params
            if params is not None and params_changed:
                self._messages.update(
                    value='Press "Start" to program the device',
                    background_color="white",
                )
                self._start_button.update(disabled=False)

            if event == "Start":
                self._start_task_ui(params)
            elif event == "Continue":
                self._continue_button.update(disabled=True)
                self._continue_event.set()
                self._messages.update(value="")
            elif event == "Stop":
                await self._cancel_task_ui()

    def _start_task_ui(self, params) -> None:
        # We disable the start button while the task runs. Therefore,
        # it shouldn't be possible to start two tasks in parallel.
        if self._task is not None:
            assert self._task.done()
        self._start_button.update(disabled=True)
        self._disable_parameters(True)

        output_cb = partial(self._output.print, end="")

        async def _reset_hw() -> None:

            try:
                steps = commands.reset_hw(
                    *params[0],
                    **params[1],
                    output_cb=output_cb,
                )

                async for step in steps:
                    # Always clear messages when we receive a new step.
                    # This way, outdated instructions won't linger.
                    self._messages.update(value="", background_color="white")
                    # Switch on the step type
                    if isinstance(step, command_steps.StatusUpdate):
                        self._status.update(value=step)
                    elif isinstance(step, command_steps.Instruction):
                        self._messages.update(
                            value=step.text, background_color="yellow"
                        )
                    elif isinstance(step, command_steps.RequestConfirmation):
                        self._continue_event.clear()
                        self._continue_button.update(disabled=False)
                        self._messages.update(
                            value=step.text, background_color="yellow"
                        )
                        await self._continue_event.wait()
                    else:
                        raise RuntimeError("Unknown step")

            except Exception as exc:  # [1]
                tb = traceback.format_exc()
                self._messages.update(value=tb, background_color="red")
                _LOGGER.error("Error:", exc_info=exc)
                raise
            else:
                self._start_button.update(disabled=False)
                self._disable_parameters(False)
                self._stop_button.update(disabled=True)
                self._messages.update(value="Done", background_color="green")
            finally:
                await steps.aclose()

        self._task = asyncio.create_task(_reset_hw())
        self._stop_button.update(disabled=False)

    async def _cancel_task_ui(self):
        self._stop_button.update(disabled=True)
        await self._cancel_task()
        self._messages.update(value="", background_color="white")
        self._output.update(value="")
        self._status.update(value="")
        self._disable_parameters(False)
        self._start_button.update(disabled=False)
        self._continue_button.update(disabled=True)

    async def _cancel_task(self):
        if self._task is None:
            return
        self._task.cancel()
        # We also suppress the general `Exception` because we don't
        # care if the task raised. We already displayed/logged any error
        # at [1].
        with suppress(Exception, asyncio.CancelledError):
            await self._task

    def _disable_parameters(self, flag: bool) -> None:
        parameter_elements = (
            e
            for e in self._window.element_list()
            if isinstance(
                e,
                (sg.Listbox, sg.Combo, sg.Input),
            )
            or (isinstance(e, sg.Button) and e.ButtonText == "Browse")
        )
        for element in parameter_elements:
            element.update(disabled=flag)

    async def __aenter__(self) -> WindowEventLoop:
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> None:
        await self._cancel_task()
        self._window.close()


def _get_parameters(values: dict[str, Any]) -> Optional[tuple]:
    swu = Path(values["swu_file"])
    hardware = next(hw for hw in Hardware if hw.name == values["hardware"])
    branding = next(br for br in Branding if br.name == values["branding"])
    hostname = values["hostname"]
    fsbl_elf = Path(values["fsbl_elf"])
    raise_if_bad_hostname(hostname, hardware)
    args = (swu,)
    kwargs = {
        "hardware": hardware,
        "branding": branding,
        "hostname": hostname,
        "fsbl_elf": fsbl_elf,
    }
    return (args, kwargs)


async def gui_async() -> None:
    async with WindowEventLoop() as wel:
        await wel.run_forever()


def gui() -> None:
    asyncio.run(gui_async())
