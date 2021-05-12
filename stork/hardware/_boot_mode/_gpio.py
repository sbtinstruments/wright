from __future__ import annotations

from dataclasses import dataclass

import RPi.GPIO as GPIO

from ._abc import AbstractBootModeControl
from ._boot_mode import BootMode

GPIO.setmode(GPIO.BOARD)


@dataclass(frozen=True)
class GpioBootModeControl(AbstractBootModeControl):
    """GPIO-based boot mode control."""

    gpio_id: int
    default_mode: BootMode = BootMode.QSPI

    def get_mode(self) -> BootMode:
        """Return the current boot mode."""
        if GPIO.input(self.gpio_id):
            return BootMode.QSPI
        return BootMode.JTAG

    def set_mode(self, value: BootMode) -> None:
        """Set the boot mode."""
        if value is BootMode.JTAG:
            gpio_value = GPIO.LOW
        elif value is BootMode.QSPI:
            gpio_value = GPIO.HIGH
        else:
            raise ValueError("Could not set boot mode")
        GPIO.output(self.gpio_id, gpio_value)

    def __enter__(self) -> GpioBootModeControl:
        GPIO.setup(self.gpio_id, GPIO.OUT)
        super().__enter__()
        return self
