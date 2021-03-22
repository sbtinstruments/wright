from ....console import Console


async def initialize_network(console: Console, tftp_host: str, tftp_port: int) -> None:
    await console.cmd("usb start")
    await console.cmd("dhcp", check_error_code=False)
    await console.cmd(f"setenv serverip {tftp_host}")
    await console.cmd(f"setenv tftpdstp {tftp_port}")
    await console.cmd(f"setenv tftpblocksize 1468")
    await console.cmd(f"setenv tftpwindowsize 256")
    await console.cmd("setenv autostart no")
