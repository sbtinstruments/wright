from stork.console import Console, Mode

from ..._command import StepByStepCommand


async def boot_to_os(
    console: Console,
) -> StepByStepCommand:
    yield "Reset hardware and boot to Linux"
    await console.reset()
    await console.force_prompt()
    # Disable kernel logging as it messes with the serial output.
    # That is, sometimes the kernel will spam the serial line with
    # driver info messages. Said messages interfere with how we parse
    # the serial line.
    await console.cmd("setenv bootargs loglevel=0")
    await console.cmd("boot", wait_for_prompt=False)

    # Switch to Linux mode
    await console.set_mode(Mode.LINUX)
    await console.wait_for_prompt()
    yield 'Kill any "sleep"-delayed startup scripts'
    # We stop all the services that may be using the /media/data path.
    # Kill any delayed scripts first.
    await console.cmd("kill `ps | awk '/[s]leep/ {print $1}'`")
    yield "Stop all processes that may use the data partition"
    await console.cmd("/etc/init.d/Amonit stop")
    await console.cmd("/etc/init.d/Adash stop")
    await console.cmd("/etc/init.d/Acellmate stop")
    await console.cmd("/etc/init.d/Abaxter stop")
    await console.cmd("/etc/init.d/Amester stop")
    await console.cmd("/etc/init.d/Amaskin stop")
    await console.cmd("/etc/init.d/S01rsyslogd stop")
    await console.cmd("/etc/init.d/S70swupdate stop")
    # We use an 'awk'-based kill command to make sure that even
    # launching processes are killed as well.
    await console.cmd("kill `ps | awk '/[t]elegraf/ {print $1}'`")
    await console.cmd("kill `ps | awk '/[i]nfluxd/ {print $1}'`")
