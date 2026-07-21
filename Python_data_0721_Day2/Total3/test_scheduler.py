from __future__ import annotations

import logging
from pathlib import Path

from .run_scheduler import execute_safely


def test_execute_safely_returns_success_result() -> None:
    expected = Path("report.html")
    assert execute_safely(lambda: expected) == expected


def test_execute_safely_logs_failure_and_keeps_running(caplog) -> None:
    def fail() -> None:
        raise OSError("temporary")

    with caplog.at_level(logging.ERROR):
        result = execute_safely(fail)

    assert result is None
    assert "다음 실행 주기" in caplog.text
