from logging import Formatter, LogRecord


class CliFormatter(Formatter):
    """Log formatter for the CLI."""

    def __init__(self) -> None:
        self._root_formatter = Formatter("\033[7m>>> %(message)s\033[0m")
        super().__init__("%(levelname)s [%(name)s] %(message)s")

    def format(self, record: LogRecord) -> str:
        """Return the formatted version of the given record."""
        if record.name == "root":
            return self._root_formatter.format(record)
        return super().format(record)
