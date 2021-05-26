from ._device_type import DeviceType

_DEVICE_TYPE_ABBREVIATIONS = {
    DeviceType.ZEUS: "zs",
    DeviceType.BACTOBOX: "bb",
}


def raise_if_bad_hostname(hostname: str, device_type: DeviceType) -> None:
    """Raise `ValueError` if the hostname doesn't fit the device type."""
    if len(hostname) != 9:
        raise ValueError("Hostname must be exactly 9 characters long.")

    # Split hostname into parts
    hostname_device_type = hostname[0:2]  # E.g.: "bb" or "zs"
    hostname_year = hostname[2:4]
    hostname_week = hostname[4:6]
    hostname_id = hostname[6:9]

    # Device type
    device_type_abbreviation = _DEVICE_TYPE_ABBREVIATIONS[device_type]
    if hostname_device_type != device_type_abbreviation:
        raise ValueError(
            f'Hostname must start with "{device_type_abbreviation}" when targeting '
            f"a {device_type.value} device."
        )

    # Year
    try:
        year = int(hostname_year)
    except ValueError as exc:
        raise ValueError(
            f"The hostname year must be an integer and not {hostname_year}."
        ) from exc
    if not 19 <= year <= 40:  # Some arbitrary limits to catch common input mistakes
        raise ValueError(f"The hostname year must between 19 and 40 (both inclusive).")

    # Week
    try:
        week = int(hostname_week)
    except ValueError as exc:
        raise ValueError(
            f"The hostname week must be an integer and not {hostname_week}."
        ) from exc
    if not 1 <= week <= 53:  # Some arbitrary limits to catch common input mistakes
        raise ValueError(f"The hostname week must between 1 and 53 (both inclusive).")

    # ID
    try:
        id_ = int(hostname_id)
    except ValueError as exc:
        raise ValueError(
            f"The hostname ID must be an integer and not {hostname_id}."
        ) from exc
    if not 0 <= id_ <= 999:
        raise ValueError(f"The hostname id must between 0 and 999  (both inclusive).")
