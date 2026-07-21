from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from project_paths import data_dir  # noqa: E402


@dataclass(frozen=True)
class Config:
    data_path: Path = data_dir() / "sales_raw.csv"
    output_dir: Path = Path(__file__).resolve().parent / "output"
    template_dir: Path = Path(__file__).resolve().parent / "templates"
    title: str = "SKALA 일일 매출 운영 리포트"
    top_n: int = 5


CONFIG = Config()
