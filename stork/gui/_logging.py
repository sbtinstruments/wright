from logging import Formatter, Handler, LogRecord
from typing import Optional

import PySimpleGUI as sg


class GuiHandler(Handler):
    """Log handler that outputs to a PySimpleGUI Multiline element."""

    def __init__(self, multiline: sg.Multiline) -> None:
        super().__init__()
        self._multiline = multiline

    def emit(self, record: LogRecord) -> None:
        """Emit the given record to the GUI element."""
        text_color: Optional[str] = None
        background_color: Optional[str] = None
        if record.name == "root":
            text_color = "white"
            background_color = "black"
        self._multiline.print(
            self.format(record),
            text_color=text_color,
            background_color=background_color,
        )


class GuiFormatter(Formatter):
    """Log formatter for the GUI."""

    def __init__(self) -> None:
        super().__init__("%(levelname)s [%(name)s] %(message)s")
