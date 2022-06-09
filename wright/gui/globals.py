from pathlib import Path

SHIPYARD_DIR = Path("/media/data/shipyard")
STORAGE_DIR = SHIPYARD_DIR / "storage"
STORAGE_DIR.mkdir(exist_ok=True)
