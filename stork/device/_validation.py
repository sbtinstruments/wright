from ._device_type import DeviceType


def raise_if_bad_hostname(hostname: str, device_type: DeviceType) -> None:
    """Raise `ValueError` if the hostname doesn't fit the device type."""
    if len(hostname) != 9:
        raise ValueError("Hostname must be exactly 9 characters long.")
    hostname_prefixes = {
        DeviceType.ZEUS: "zs",
        DeviceType.BACTOBOX: "bb",
    }
    prefix = hostname_prefixes[device_type]
    if not hostname.startswith(prefix):
        raise ValueError(
            f'Hostname must start with "{prefix}" when targeting '
            f"a {device_type.value} device."
        )
