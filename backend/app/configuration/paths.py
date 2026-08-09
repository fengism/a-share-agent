from pathlib import Path

from app.configuration.runtime import get_settings

DATA_DIR: Path = get_settings().app_data_dir
