import asyncio
import sys

import anyio
import qasync
from PyQt5.QtWidgets import QApplication

from ..logging import set_logging_defaults
from .widgets import MainWidget


async def _show_main_window() -> None:
    async with anyio.create_task_group() as tg:
        main_widget = MainWidget(tg)
        main_widget.setWindowTitle("Shipyard")
        main_widget.show()
        tg.start_soon(main_widget.waitClosed)


def gui() -> None:
    """Start the GUI."""
    set_logging_defaults()
    app = QApplication(sys.argv)
    # Default behaviour is to exit (like `sys.exit`) immediately.
    # We don't want that. We want to close the event loop gracefully.
    app.setQuitOnLastWindowClosed(False)

    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)
    loop.run_until_complete(_show_main_window())
