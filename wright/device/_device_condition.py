from __future__ import annotations

from enum import Enum


class DeviceCondition(Enum):
    """How used the device is from a software perspective.

    This is *not* the hardware condition. Instead, it's how far the device's
    data, config, etc. are from the factory defaults,
    """

    # Any of the other states
    UNKNOWN = "unknown"
    # Fresh from the factory
    MINT = "mint"
    # We have observed the device (non-mutating operations)
    AS_NEW = "as-new"
    # We have stored data or configured the device (mutating operations)
    USED = "used"
    # The device is unusable (e.g., unable to boot)
    BRICKED = "bricked"

    def to_int(self) -> int:
        """Return the integer value of this condition."""
        return _INTEGER_VALUE[self]

    def is_as_new_or_better(self) -> bool:
        """Return true if the device is in mint or as-new condition."""
        return self is DeviceCondition.MINT or self is DeviceCondition.AS_NEW

    def __lt__(self, rhs: DeviceCondition) -> bool:
        lhs_value = self.to_int()
        rhs_value = rhs.to_int
        return lhs_value < rhs_value


_INTEGER_VALUE = {
    DeviceCondition.UNKNOWN: 0,
    DeviceCondition.BRICKED: 1,
    DeviceCondition.USED: 2,
    DeviceCondition.AS_NEW: 3,
    DeviceCondition.MINT: 4,
}
