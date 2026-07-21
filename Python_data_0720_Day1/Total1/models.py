"""=============================================================================
파일명: models.py
작성자: 채수아
작성일: 2026-07-20
작성 목적: 비동기 ETL 파이프라인의 상품 데이터 검증 모델을 정의

입력:
    수집 단계에서 전달되는 상품 및 판매자 딕셔너리

검증 항목:
    양수 ID와 가격, 필수 문자열, 카테고리 소문자 정규화,
    판매자 중첩 스키마

실행:
    pipeline.py에서 Product 모델을 가져와 사용
=============================================================================
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class Seller(BaseModel):
    """상품 판매자의 식별자와 지역 정보를 검증합니다."""

    seller_id: int = Field(gt=0)
    region: str = Field(min_length=2)

    @field_validator("region")
    @classmethod
    def normalize_region(cls, value: str) -> str:
        """지역명의 앞뒤 공백을 제거합니다."""
        normalized = value.strip()
        if len(normalized) < 2:
            raise ValueError("지역명은 공백 제외 2자 이상이어야 합니다")
        return normalized


class Product(BaseModel):
    """상품 한 건의 필드 타입과 업무 규칙을 검증합니다."""

    id: int = Field(gt=0)
    name: str = Field(min_length=1)
    category: str = Field(min_length=2)
    price: float = Field(gt=0)
    seller: Seller

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        """상품명의 앞뒤 공백을 제거합니다."""
        normalized = value.strip()
        if not normalized:
            raise ValueError("상품명은 비어 있을 수 없습니다")
        return normalized

    @field_validator("category")
    @classmethod
    def normalize_category(cls, value: str) -> str:
        """카테고리의 공백을 제거하고 소문자로 통일합니다."""
        normalized = value.strip().lower()
        if len(normalized) < 2:
            raise ValueError("카테고리는 공백 제외 2자 이상이어야 합니다")
        return normalized
