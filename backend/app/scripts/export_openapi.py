"""将 FastAPI OpenAPI 契约导出为确定性 JSON。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.main import app


def export_openapi(output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(app.openapi(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="导出 FastAPI OpenAPI JSON")
    parser.add_argument("output", type=Path, help="OpenAPI JSON 输出路径")
    arguments = parser.parse_args()
    export_openapi(arguments.output)


if __name__ == "__main__":
    main()
