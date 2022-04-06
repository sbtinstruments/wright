from html import escape as escape_html
from logging import Formatter, Handler, LogRecord
from typing import Optional

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QTextBlockFormat, QTextOption
from PyQt5.QtWidgets import QTextEdit, QVBoxLayout, QWidget


class LogWidget(QWidget):
    """Log (messages) of a run."""

    htmlAppended = pyqtSignal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._layout = QVBoxLayout()
        self.setLayout(self._layout)

        self._log = QTextEdit(self)
        self._log.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._log.setMinimumWidth(650)  # Space enough for around 88 chararacters
        self._log.setWordWrapMode(QTextOption.WrapMode.NoWrap)
        self._log.setReadOnly(True)
        self._log_style = self._log.style()
        self._log_format = self._log.currentCharFormat()
        self._layout.addWidget(self._log)

        # We use the `messageAppended` signal as a thread-safe layer of indirection.
        # This way, we can append to the log from non-GUI threads.
        self.htmlAppended.connect(self._append)

    def setHtml(self, html: str) -> None:
        self._log.setHtml(html)
        # Wait 0.1 seconds before we scroll. Otherwise, it doesn't actually
        # scroll to the bottom. Maybe the scroll happens before the UI
        # refreshes?
        QTimer.singleShot(100, self._scroll_to_bottom)

    def _scroll_to_bottom(self) -> None:
        scroll_bar = self._log.verticalScrollBar()
        scroll_bar.setValue(scroll_bar.maximum())

    def appendHtml(self, html: str) -> None:
        """Append given HTML to the log.

        Thread-safe. You may call this in a non-GUI thread.
        """
        self.htmlAppended.emit(html)

    def _append(self, html: str) -> None:
        # Per default, the text cursor remembers the block format (styling).
        # This causes styles from the current block to spill over into the next
        # block. We don't want that. Therefore, we reset the block format before
        # each append.
        # For example, if the current block has black background color then a
        # call to `append` inserts a new block that also has black background color.
        # This behaviour makes sense for a text editor but not for a log viewer.
        self._log.textCursor().setBlockFormat(QTextBlockFormat())
        # Note that Qt does not simply add the given HTML to the text document.
        # It parses the given HTML and inserts it as a new "block" in the document.
        # A subsequent call to `toHtml()` converts the "block" back into HTML. The
        # latter is surprisingly different compared to original HTML given to `append`.
        # For example, if we `append` the following to the document:
        #
        #     <pre>text</pre>
        #
        # Then we get the following back from `toHtml`:
        #
        #     <p><span style=" font-family:'monospace';">text</span></p>
        #
        # I (FPA) guess this is because HTML is just one format supported by the
        # "block" model. Markdown is another such format.
        self._log.append(html)

    def toHtml(self) -> str:
        return self._log.toHtml()


class GuiHandler(Handler):
    """Log handler that outputs to a `LogWidget`."""

    def __init__(self, log_widget: LogWidget) -> None:
        super().__init__()
        self._log_widget = log_widget

    def emit(self, record: LogRecord) -> None:
        """Emit the given record to the GUI element."""
        style_lines = ["display: block", "margin: 0"]
        if record.name == "root":
            style_lines += ("color: white", "background-color: black")
        style = "; ".join(style_lines)
        message = self.format(record)
        message_html = escape_html(message)
        html = f'<pre style="{style}">{message_html}</pre>'
        self._log_widget.htmlAppended.emit(html)


class GuiFormatter(Formatter):
    """Log formatter for the GUI."""

    def __init__(self) -> None:
        super().__init__("%(levelname)s [%(name)s] %(message)s")
