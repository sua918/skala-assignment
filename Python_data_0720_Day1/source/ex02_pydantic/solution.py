"""=============================================================================
파일명: solution.py
작성자: 채수아
작성일: 2026-07-20
작성 목적: JSON API 응답을 Pydantic v2 스키마로 검증하고 정상·오염 데이터 분리

입력:
    data/api_response.json

검증 항목:
    필드 타입, 값의 범위, 필수 필드, 중첩 구조 및 사용자 정의 규칙

실행:
    python ex02_pydantic/solution.py
=============================================================================
"""

import json
import logging
import re
from datetime import date
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError, field_validator

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = PROJECT_ROOT / "data" / "api_response.json"
OUTPUT_DIR = Path(__file__).resolve().parent / "output"

logger = logging.getLogger(__name__)


class Profile(BaseModel):
    """사용자의 국가, 회원 등급과 활동 점수를 검증합니다."""

    country: Literal["KR", "US", "JP", "DE"]
    tier: Literal["free", "pro", "enterprise"]
    score: float = Field(ge=0, le=100)


class UserRecord(BaseModel):
    """API 사용자 한 건의 필드 타입과 값 범위를 검증합니다."""

    id: int = Field(gt=0)
    username: str = Field(min_length=3, max_length=30)
    email: str
    age: int = Field(ge=0, le=120)
    is_active: bool
    signup_date: date
    profile: Profile
    tags: list[str]

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        """이메일을 정규화하고 기본 형식이 올바른지 검사합니다."""
        normalized = value.strip().lower()
        if not EMAIL_PATTERN.fullmatch(normalized):
            raise ValueError("올바른 이메일 형식이 아닙니다")
        return normalized


def load_records(path: Path) -> list[dict[str, Any]]:
    """JSON API 응답을 읽고 사용자 레코드 목록을 반환합니다."""
    if not path.is_file():
        raise FileNotFoundError(f"입력 JSON 파일을 찾을 수 없습니다: {path}")

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(
            f"입력 JSON 형식이 올바르지 않습니다: {error.msg} "
            f"(줄 {error.lineno}, 열 {error.colno})"
        ) from error

    if not isinstance(payload, dict):
        raise ValueError("API 응답의 최상위 값은 객체여야 합니다.")

    records = payload.get("results")
    if not isinstance(records, list):
        raise ValueError("API 응답에 results 목록이 없습니다.")
    if not all(isinstance(record, dict) for record in records):
        raise ValueError("results에는 객체 형식의 데이터만 있어야 합니다.")

    declared_count = payload.get("count")
    if declared_count != len(records):
        raise ValueError(
            f"API 응답의 count({declared_count})와 "
            f"실제 건수({len(records)})가 일치하지 않습니다."
        )

    return records


def validate_records(
    records: list[dict[str, Any]],
) -> tuple[list[UserRecord], list[dict[str, Any]]]:
    """전체 레코드를 검증하여 유효 데이터와 실패 정보를 분리합니다."""
    valid_records: list[UserRecord] = []
    invalid_records: list[dict[str, Any]] = []

    # 한 건의 실패가 나머지 레코드 검증을 중단하지 않도록 개별 처리합니다.
    for row_number, record in enumerate(records, start=1):
        try:
            valid_records.append(UserRecord.model_validate(record))
        except ValidationError as error:
            invalid_records.append(
                {
                    "row": row_number,
                    "id": record.get("id"),
                    "data": record,
                    "errors": error.errors(),
                }
            )

    return valid_records, invalid_records


def save_results(
    valid_records: list[UserRecord],
    invalid_records: list[dict[str, Any]],
    output_dir: Path,
) -> None:
    """유효 데이터와 오염 데이터를 UTF-8 JSON 파일로 각각 저장합니다."""
    output_dir.mkdir(parents=True, exist_ok=True)

    valid_data = [record.model_dump(mode="json") for record in valid_records]
    (output_dir / "valid_records.json").write_text(
        json.dumps(valid_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "invalid_records.json").write_text(
        json.dumps(invalid_records, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )


def print_report(
    total: int,
    valid_records: list[UserRecord],
    invalid_records: list[dict[str, Any]],
) -> None:
    """검증 건수와 각 오염 데이터의 필드별 실패 사유를 출력합니다."""
    print("=" * 72)
    print("실습 2: Pydantic v2 중첩 스키마 검증")
    print("=" * 72)
    print(
        f"전체 {total}건 → 유효 {len(valid_records)}건 / 오염 {len(invalid_records)}건"
    )

    print("\n[오염 데이터 상세]")
    print(f"{'행':<6}{'ID':<8}{'필드':<22}사유")
    print("-" * 72)

    for item in invalid_records:
        for error in item["errors"]:
            field = ".".join(str(part) for part in error["loc"])
            print(f"{item['row']:<6}{item['id']!s:<8}{field:<22}{error['msg']}")


def main() -> int:
    """API 응답을 검증하고 콘솔 리포트와 JSON 결과를 생성합니다."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s | %(message)s",
    )
    logger.info("API 응답 검증을 시작합니다: %s", DATA_PATH)

    try:
        records = load_records(DATA_PATH)
        valid_records, invalid_records = validate_records(records)
        save_results(valid_records, invalid_records, OUTPUT_DIR)
    except (FileNotFoundError, OSError, ValueError) as error:
        logger.error("API 응답 검증에 실패했습니다: %s", error)
        return 1

    print_report(len(records), valid_records, invalid_records)
    logger.info(
        "검증을 완료했습니다: 유효 %d건, 오염 %d건",
        len(valid_records),
        len(invalid_records),
    )
    logger.info("검증 결과를 저장했습니다: %s", OUTPUT_DIR)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
