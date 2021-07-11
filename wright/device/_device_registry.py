from typing import TYPE_CHECKING, Any, Optional, Type

if TYPE_CHECKING:
    from ._device import Device


# Global dict of all registered devices
_DEVICES: dict[str, Type["Device"]] = dict()


def get_device(device_type: str, default: Any = None) -> Optional[Type["Device"]]:
    """Get the device that corresponds to type.

    Returns `default` if there is no such device.
    """
    return _DEVICES.get(device_type, default)


def add_device(device_type: str, device: Type["Device"]) -> None:
    """Add the given device to the global registry."""
    if device_type in _DEVICES:
        raise ValueError(f'There already exists an entry for a "{device_type}" device')
    _DEVICES[device_type] = device
