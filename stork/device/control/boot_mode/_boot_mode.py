from enum import Enum, auto


class BootMode(Enum):
    """Device boot mode."""

    JTAG = auto()
    QSPI = auto()
