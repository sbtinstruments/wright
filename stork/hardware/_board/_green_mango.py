from __future__ import annotations

import asyncio
from contextlib import AsyncExitStack
from functools import partial
from types import TracebackType
from typing import Callable, Optional, Type

from ...console import Console
from .._boot_mode import BootMode
from .._hardware import Hardware
from .._power import PowerControl
from ._board_definition import BoardDefinition
from ._console_mode import ConsoleMode
from . import commands


class GreenMango:
    def __init__(
        self,
        bd: BoardDefinition,
        *,
        output_cb: Optional[Callable[[str], None]] = None,
    ) -> None:
        # Private
        self._stack = AsyncExitStack()
        self._console_mode: ConsoleMode = ConsoleMode.UBOOT
        # Public
        self.bd = bd
        self.power_control = bd.power_control.copy()
        self.boot_mode_control = bd.boot_mode_control.copy()
        self.console = Console(
            bd.tty,
            prompt=self._get_console_prompt(),
            output_cb=partial(output_cb, source="console"),
        )
        self.output_cb = output_cb
        # Commands
        class Commands:
            """Board-specific commands."""

            boot_to_os = partial(commands.boot_to_os, self)
            erase_data = partial(commands.erase_data, self)
            install_firmware = partial(commands.install_firmware, self)
            install_software = partial(commands.install_software, self)
            jtag_boot_to_uboot = partial(commands.jtag_boot_to_uboot, self)

        self.commands = Commands

    async def hard_reset(self) -> None:
        if self.power_control.on:
            self.power_control.on = False
            # Wait a bit for the system to loose power. E.g., it may
            # take some time for the capacitors to fully drain.
            await asyncio.sleep(0.1)
        self.power_control.on = True

    async def reset_and_wait_for_prompt(self) -> None:
        """Reset the board and wait for the prompt."""
        await self.hard_reset()
        await self.console.force_prompt()

    async def boot_to_jtag(self) -> None:
        with self.boot_mode_control.scoped(BootMode.JTAG):
            await self.hard_reset()
            # The Zynq chip does its boot mode check within the first 100 ms.
            # Therefore, wait wait 100 ms before we switch back to the default
            # boot mode.
            await asyncio.sleep(0.1)

    async def initialize_network(self) -> None:
        # Early out if not in U-boot
        if self._console_mode is not ConsoleMode.UBOOT:
            # Async checkpoint
            await asyncio.sleep(0)
            return
        await self.console.cmd("usb start")
        await self.console.cmd("dhcp", check_error_code=False)
        await self.console.cmd(f"setenv serverip {self.bd.tftp_host}")
        await self.console.cmd(f"setenv tftpdstp {self.bd.tftp_port}")
        await self.console.cmd(f"setenv tftpblocksize 1468")
        await self.console.cmd(f"setenv tftpwindowsize 256")
        await self.console.cmd("setenv autostart no")

    async def set_console_mode(self, value: ConsoleMode) -> None:
        self._console_mode = value
        await self._update_console_prompt()

    async def _update_console_prompt(self) -> None:
        await self.console.set_prompt(self._get_console_prompt())

    def _get_console_prompt(self) -> None:
        prompts = _prompts(self.bd.hardware, self.bd.hostname)
        return prompts[self._console_mode]

    async def __aenter__(self) -> PowerControl:
        self._stack.__aenter__()
        self._stack.enter_context(self.power_control)
        self._stack.enter_context(self.boot_mode_control)
        await self._stack.enter_async_context(self.console)
        return self

    async def __aexit__(
        self,
        exc_type: Type[BaseException],
        exc_value: BaseException,
        traceback: TracebackType,
    ) -> None:
        await self._stack.__aexit__(exc_type, exc_value, traceback)


def _prompts(hardware: Hardware, hostname: str):
    return {
        ConsoleMode.UBOOT: f"\r\n{hardware.value}> ",
        ConsoleMode.LINUX: f"\r\n\x1b[1;34mroot@{hostname}\x1b[m$ ",
    }
