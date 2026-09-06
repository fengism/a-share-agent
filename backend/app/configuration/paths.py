from pathlib import Path

from app.configuration.runtime import get_settings

DATA_DIR: Path = get_settings().app_data_dir
# 种子数据目录：与仓库一起分发的行业库初始数据（csv.gz），用于空库自动播种
SEEDS_DIR: Path = Path(__file__).resolve().parents[2] / "seeds"
