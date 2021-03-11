from ...hardware import Hardware


def raise_if_bad_hostname(hostname: str, hardware: Hardware):
    if len(hostname) != 9:
        raise ValueError("Hostname must be exactly 9 characters long.")
    hostname_prefixes = {
        Hardware.ZEUS: "zs",
        Hardware.BACTOBOX: "bb",
    }
    prefix = hostname_prefixes[hardware]
    if not hostname.startswith(prefix):
        raise ValueError(
            f'Hostname must start with "{prefix}" when targeting '
            f"the {hardware.value} hardware."
        )
