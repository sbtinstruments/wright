from pathlib import Path

_BASE_PATH = Path("/media/data/shipyard")

CONFIG = (_BASE_PATH / ".reset-board-gui.json").absolute()
COMMAND_LOG_PATH = _BASE_PATH / "command-log.csv"
