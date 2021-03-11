from __future__ import annotations
import asyncio
from functools import partial
import json
import logging
from pathlib import Path
import traceback
from types import TracebackType
from typing import AsyncContextManager, Optional, Type
from contextlib import suppress

import PySimpleGUI as sg

from .. import commands
from ..branding import Branding
from ..hardware import Hardware

_CONFIG = Path("./.stork.json").absolute()

_LOGGER = logging.getLogger(__name__)


def _layout():
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


class WindowEventLoop(AsyncContextManager):
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

    async def run_forever(self):
        # Event Loop to process "events" and get the "values" of the inputs
        while True:
            await asyncio.sleep(0.01)
            event, values = self._window.read(0)
            # Persist values
            if values is not None:
                with _CONFIG.open("w") as f:
                    json.dump(values, f)
            if event == sg.WIN_CLOSED:
                break
            elif event == "Start":
                self._start_task_ui(values)
            elif event == "Continue":
                self._continue_button.update(disabled=True)
                self._continue_event.set()
                self._messages.update(value="")
            elif event == "Stop":
                await self._cancel_task_ui()

    def _start_task_ui(self, values) -> None:
        # We disable the start button while the task runs. Therefore,
        # it shouldn't be possible to start two tasks in parallel.
        if self._task is not None:
            assert self._task.done()
        self._start_button.update(disabled=True)
        self._disable_parameters(True)

        swu = Path(values["swu_file"])
        hardware = next(hw for hw in Hardware if hw.name == values["hardware"])
        branding = next(br for br in Branding if br.name == values["branding"])
        hostname = values["hostname"]
        fsbl_elf = Path(values["fsbl_elf"])
        output_cb = partial(self._output.print, end="")

        async def _reset_hw():

            try:
                steps = commands.reset_hw(
                    swu,
                    hardware=hardware,
                    branding=branding,
                    hostname=hostname,
                    fsbl_elf=fsbl_elf,
                    output_cb=output_cb,
                )

                async for step in steps:
                    # Always clear messages when we receive a new step.
                    # This way, outdated instructions won't linger.
                    self._messages.update(value="", background_color="white")
                    # Switch on the step type
                    if isinstance(step, commands.StatusUpdate):
                        self._status.update(value=step)
                    elif isinstance(step, commands.Instruction):
                        self._messages.update(
                            value=step.text, background_color="yellow"
                        )
                    elif isinstance(step, commands.RequestConfirmation):
                        self._continue_event.clear()
                        self._continue_button.update(disabled=False)
                        self._messages.update(
                            value=step.text, background_color="yellow"
                        )
                        await self._continue_event.wait()
                    else:
                        raise RuntimeError("Unknown step")

            except Exception as exc:
                tb = traceback.format_exc()
                self._messages.update(value=tb, background_color="red")
                _LOGGER.error("Error:", exc_info=exc)
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
        with suppress(asyncio.CancelledError):
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
        exc_type: Type[BaseException],
        exc_value: BaseException,
        traceback: TracebackType,
    ) -> None:
        await self._cancel_task()
        self._window.close()


async def gui_async():
    async with WindowEventLoop() as wel:
        await wel.run_forever()


def gui():

    asyncio.run(gui_async())
