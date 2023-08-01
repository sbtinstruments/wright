from __future__ import annotations

import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any, AsyncIterator, Optional

import anyio
from anyio.abc import TaskGroup

from ....command_line import CommandLine, SerialCommandLine, SshCommandLine
from ..._device_condition import DeviceCondition
from ...models import BbpState, ElecRef, PartialBbpStatus, Process, FrequencySweep
from .._deteriorate import deteriorate
from .._enter_context import enter_context
from .._fw import DeviceUboot
from ._linux import Linux
from ._log_in import force_log_in_over_serial

if TYPE_CHECKING:
    from ..._device import Device


class DeviceLinux(Linux):
    """The Linux distribution installed on the device.

    This depends on the state of device. That is, the operating system (kernel
    and rootfs) installed on the device. Use `WrightLiveLinux` if you want a
    stateless execution context.
    """

    def __init__(
        self, device: "Device", tg: TaskGroup, kernel_log_level: Optional[int] = None
    ) -> None:
        super().__init__(device, tg)
        # Kernel logging messes with the serial output. That is, sometimes the
        # kernel will spam the serial line with driver info messages. Said
        # messages interfere with how we parse the serial line.
        # Use `kernel_log_level=0` to avoid this.
        self._kernel_log_level = kernel_log_level
        # SSH command line
        self._ssh: Optional[SshCommandLine] = None

    @property
    def command_line(self) -> CommandLine:
        """Return the preferred command line.

        We prefer SSH if it is available. Otherwise, we fall back on serial.

        We use this command line for the `run` and `run_parsed` methods.
        """
        if self._ssh is not None:
            return self._ssh
        return self.serial

    @property
    def ssh(self) -> SshCommandLine:
        """Return the SSH-based command line."""
        self._raise_if_not_entered()
        self._raise_if_exited()
        assert self._ssh is not None
        return self._ssh

    @deteriorate(DeviceCondition.AS_NEW)
    async def unbock_data_partition(self) -> None:
        """Stop all processes/mounts that may use the data partition."""
        self.logger.info("Stop all services that may use the data partition")
        await self.run("/etc/init.d/S99monit stop")
        await self.run("/etc/init.d/S97dash stop")
        await self.run("/etc/init.d/S96staten stop")
        await self.run("/etc/init.d/S95mester stop")
        await self.run("/etc/init.d/S94baxter stop")
        await self.run("/etc/init.d/S93maskin stop")
        await self.run("/etc/init.d/S92cellmate stop")
        await self.run("/etc/init.d/S91frog stop")
        await self.run("/etc/init.d/S82telegraf stop")
        await self.run("/etc/init.d/S81influxdb stop")
        await self.run("/etc/init.d/S70swupdate stop")
        # HACK: crond doesn't use the data partition but it causes other issues
        # due to sudden time shifts. Therefore, we also stop crond.
        # Specifically, a time shift during `mkfs.ext4` causes `mkfs.ext4` to
        # not return.
        await self.run("/etc/init.d/S60crond stop")
        # We introduced nginx in SW 4.12.0. Therefore, it won't be there on older
        # systems. Hence the conditional command.
        await self.run("[ -f /etc/init.d/S50nginx ] && /etc/init.d/S50nginx stop")
        await self.run("/etc/init.d/S01rsyslogd stop")

    @deteriorate(DeviceCondition.AS_NEW)
    async def get_processes(self) -> dict[int, Process]:
        """Return overview of the processes that run on the device."""
        return await self.run_py_parsed(_PY_PRINT_PROCESSES, dict[int, Process])

    @deteriorate(DeviceCondition.AS_NEW)
    async def get_host_key(self) -> str:
        """Return the public host key for SSH."""
        # Use the serial command line for this since we need the host
        # key to initialize the SSH command line. I.e., we can't assume
        # that the latter is ready yet.
        return await self.serial.run("cat /etc/ssh/ssh_host_ed25519_key.pub")

    @deteriorate(DeviceCondition.AS_NEW)
    async def set_electronics_reference(self) -> ElecRef:
        """Set the electronics reference data (JSON file).

        Returns the reference data (parsed contents of the JSON file).
        """
        await self._start_bbp(program_name="electronics_reference.bbp")
        with anyio.fail_after(60):
            await self._wait_for_bbp()
        elec_ref_data = await self.read_file_as_json(
            Path("/media/config/individual/etc/electrical_test_reference.json")
        )
        frequency_sweep = FrequencySweep.from_elec_ref_data(elec_ref_data)
        return ElecRef.from_frequency_sweep(
            frequency_sweep,
            device_type=self.device.device_type,
        )

    async def read_file_as_json(self, file: Path, **kwargs: Any) -> dict[str, Any]:
        """Read the given file and parse the contents as JSON."""
        text = await self.read_file_as_text(file)
        result = json.loads(text, **kwargs)
        assert isinstance(result, dict)
        return result

    @deteriorate(DeviceCondition.AS_NEW)
    async def read_file_as_text(self, file: Path) -> str:
        """Read the given file and return its contents as a raw text string."""
        return await self.run(f"cat {file}")

    async def _wait_for_bbp(self) -> None:
        """Wait until the BBP is done.

        Raises `RuntimeError` if the BBP failed or was cancelled.
        """
        while True:
            status = await self.run_py_parsed(_GET_BBP_STATUS, PartialBbpStatus)
            bbp_state = status.state
            if bbp_state is BbpState.CANCELLED:
                raise RuntimeError("User cancelled the BBP")
            if bbp_state is BbpState.FAILED:
                raise RuntimeError("The BBP failed")
            if bbp_state is BbpState.COMPLETED:
                break
            await anyio.sleep(2)

    async def _start_bbp(self, program_name: str) -> None:
        """Start the given BBP.

        Note that this simply starts the BBP in the background. It does not wait
        for it to complete.
        """
        py_code = _RUN_BBP.format(program_name=program_name)
        await self.run_py(py_code)

    async def _boot(self) -> None:
        # We assume that the device uses U-boot and sbtOS. This way, we know how to
        # enter Linux.

        # Enter U-boot first so that we can interrupt the usual boot procedure.
        # Otherwise, U-boot power offs early with the message:
        #
        #  > PMIC woke due to "charging" event'
        #
        # on battery-powered devices like Zeus.
        #
        # We need to set the boot flags for Linux (e.g., "log level") from within
        # U-boot anyhow.
        async with enter_context(DeviceUboot, self.device) as uboot:
            if self._kernel_log_level is not None:
                await uboot.set_boot_args(loglevel="0")
            await uboot.boot_to_device_os()

    @asynccontextmanager
    async def _serial_cm(self) -> AsyncIterator[SerialCommandLine]:
        communication = self.device.link.communication
        # TODO: Remove the path (the "~" part) from the prompt.
        # This is a change to the wright image itself. Otherwise,
        # we fail to recognize the prompt if the user changes the
        # current working directory. For now, we simply don't change the
        # current working directory.
        prompt = f"root@{communication.hostname}:~# "
        async with self._create_serial(prompt) as serial:
            if not self._should_skip_boot():
                # Wait until the serial prompt is just about to appear.
                # We found the length of this sleep empirically.
                await anyio.sleep(80)
                with anyio.fail_after(100):
                    # The authentication is at the default values
                    await force_log_in_over_serial(serial, username="root", password="")
            # Spam `echo` commands until the serial prompt appears
            with anyio.fail_after(160):
                await serial.force_prompt()
            yield serial

    async def __aenter__(self) -> DeviceLinux:
        await super().__aenter__()
        assert self._stack is not None
        host = self.device.link.communication.hostname
        host_key = await self.get_host_key()
        # Logger
        if self.logger is None:
            ssh_logger = None
        else:
            ssh_logger = self.logger.getChild("ssh")
        self._ssh = SshCommandLine(
            host=host, port=7910, host_key=host_key, username="root", logger=ssh_logger
        )
        await self._stack.enter_async_context(self._ssh)
        return self


_PY_PRINT_PROCESSES = """
import psutil
import json

processes = {
    p.pid: p.as_dict(attrs=["name", "cmdline"])
    for p in psutil.process_iter()
}

print(json.dumps(processes))
"""


_RUN_BBP = """
from urllib.request import Request, urlopen
from urllib.error import HTTPError

# Discard previous program (if any)
req = Request(
    url="http://localhost:8082/tasks/program",
    method="DELETE"
)
try:
    with urlopen(req):
        pass
except HTTPError as exc:
    # Discard 404 errors (no previous program)
    if exc.code != 404:
        raise

# Start next program
req = Request(
    url="http://localhost:8082/tasks/program",
    data="{program_name}".encode("utf-8"),
    method="PUT"
)
with urlopen(req):
    pass
"""

_GET_BBP_STATUS = """
from urllib.request import Request, urlopen
from urllib.error import HTTPError

req = Request(
    url="http://localhost:8082/tasks/program",
    method="GET"
)
with urlopen(req) as io:
    data = io.read()

print(data.decode("utf-8"))
"""
