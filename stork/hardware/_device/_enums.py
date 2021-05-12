from enum import Enum, auto


class DeviceStatus(Enum):
    UNKNOWN = auto()
    POWER_OFF = auto()
    IDLE = auto()
    BUSY = auto()
