from __future__ import annotations

import RPi.GPIO as GPIO

GPIO.setmode(GPIO.BCM)

from ._boot_mode import BootMode, BootModeControl


class GpioBootModeControl(BootModeControl):
    def __init__(self, index: int) -> None:
        self._index = index

    @property
    def mode(self) -> BootMode:
        if GPIO.value(self._index):
            return BootMode.QSPI
        else:
            return BootMode.JTAG

    @mode.setter
    def mode(self, value: BootMode) -> None:
        if value is BootMode.JTAG:
            gpio_value = GPIO.LOW
        elif value is BootMode.QSPI:
            gpio_value = GPIO.HIGH
        else:
            raise ValueError("Could not set boot mode")
        GPIO.output(self._index, gpio_value)

    def copy(self) -> GpioBootModeControl:
        return GpioBootModeControl(self._index)

    def __enter__(self) -> GpioBootModeControl:
        GPIO.setup(self._index, GPIO.OUT)
        super().__enter__()
        return self
