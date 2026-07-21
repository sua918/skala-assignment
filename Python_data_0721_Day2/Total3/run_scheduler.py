"""종합실습 3의 실행 시점만 조율하는 스케줄러 진입점.

1회 실행:
    python Total3/run_scheduler.py

60초 간격 반복:
    python Total3/run_scheduler.py --interval 60

운영 환경에서는 같은 명령을 Windows 작업 스케줄러나 cron에 등록한다.
"""

from __future__ import annotations

import argparse
import logging
import time
from datetime import datetime

try:
    from .report import run_once
except ImportError:  # 스크립트 직접 실행 지원
    from report import run_once


LOGGER = logging.getLogger(__name__)


def execute_safely(task=run_once):
    """일시적인 실행 오류를 기록하고 다음 스케줄을 계속 진행한다."""
    try:
        return task()
    except Exception:
        LOGGER.exception("리포트 생성 실패; 다음 실행 주기에 다시 시도합니다.")
        return None


def run_interval(interval: int) -> None:
    if interval <= 0:
        raise ValueError("반복 간격은 1초 이상이어야 합니다.")
    print(f"{interval}초 간격으로 실행합니다. 종료: Ctrl+C")
    while True:
        result = execute_safely()
        if result is not None:
            print(f"[{datetime.now():%H:%M:%S}] {result}")
        time.sleep(interval)


def run_daily(at_time: str) -> None:
    try:
        import schedule
    except ModuleNotFoundError as error:
        raise RuntimeError(
            "daily 모드에는 schedule 패키지가 필요합니다: pip install schedule"
        ) from error

    schedule.every().day.at(at_time).do(execute_safely)
    print(f"매일 {at_time}에 실행합니다. 종료: Ctrl+C")
    while True:
        schedule.run_pending()
        time.sleep(1)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    parser = argparse.ArgumentParser(description="매출 리포트 실행 주기 조율")
    parser.add_argument(
        "--mode",
        choices=["once", "interval", "daily"],
        default="once",
    )
    parser.add_argument("--interval", type=int, default=60, help="반복 실행 간격(초)")
    parser.add_argument("--at", default="09:00", help="daily 실행 시각(HH:MM)")
    arguments = parser.parse_args()

    try:
        if arguments.mode == "once":
            print(f"리포트 생성: {run_once()}")
        elif arguments.mode == "interval":
            run_interval(arguments.interval)
        else:
            run_daily(arguments.at)
    except KeyboardInterrupt:
        print("\n스케줄러를 종료했습니다.")


if __name__ == "__main__":
    main()
