from __future__ import annotations

from pathlib import Path
from typing import Optional

from ...model import FrozenModel

_BASE_PATH = Path("/media/data/shipyard")
_LOW_LEVEL_CONFIG_PATH = _BASE_PATH / "low-level-config.json"


class LowLevelConfig(FrozenModel):
    tty: Optional[Path] = None
    jtag_usb_serial: Optional[str] = None
    power_relay: Optional[int] = None
    boot_mode_gpio: Optional[int] = None

    @classmethod
    def from_config_file(cls, path: Optional[Path] = None) -> LowLevelConfig:
        """Return instance created from the given config file.

        If you don't specify a config file, we look for one in a default location.
        """
        if path is None:
            path = _LOW_LEVEL_CONFIG_PATH
        return cls.parse_file(path)

    @classmethod
    def try_from_config_file(cls, path: Optional[Path] = None) -> LowLevelConfig:
        """Try to create an instance based on the given config file.

        Returns a default-constructed instance if something goes wrong.
        """
        try:
            return cls.from_config_file(path)
        except Exception:
            return cls()
