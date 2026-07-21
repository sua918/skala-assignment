from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent


def data_dir() -> Path:
    """Return the first directory containing the supplied assignment data."""
    candidates = (PROJECT_ROOT / "data", PROJECT_ROOT.parent / "data")
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError("data 폴더를 찾을 수 없습니다.")


def output_dir(module_file: str) -> Path:
    path = Path(module_file).resolve().parent / "output"
    path.mkdir(parents=True, exist_ok=True)
    return path
