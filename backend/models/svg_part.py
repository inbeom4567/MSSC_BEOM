"""SVG 라이브러리 카탈로그 Pydantic 모델.

Task #4 — SVG 부품(Part) 카탈로그 스키마.

정의 모델:
    - ParamType   : 변수 파라미터 타입 리터럴
    - Bbox        : 부품 바운딩 박스
    - ParamDef    : 변수 파라미터 정의
    - AiDraft     : Gemini 초벌 제안 보관용
    - SvgPart     : 개별 SVG 부품 메타데이터
    - Catalog     : 부품 목록 최상위
    - Progress    : 라벨링 진행 상태 (trial/full 범위)

참조:
    - docs/superpowers/specs/2026-04-24-svg-library-trainer-design.md
    - docs/superpowers/plans/2026-04-24-svg-library-trainer.md (Task #4)

Python 3.14, pydantic v2.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# 리터럴 타입
# ---------------------------------------------------------------------------

ParamType = Literal["number", "position", "color", "boolean"]
"""변수 파라미터의 값 타입."""

ScopeType = Literal["trial", "full"]
"""라벨링 범위 — trial(시범 N개) / full(전체)."""


# ---------------------------------------------------------------------------
# 기본 구조체
# ---------------------------------------------------------------------------


def _utcnow() -> datetime:
    """timezone-aware UTC 현재 시각 (datetime.utcnow deprecation 회피)."""
    return datetime.now(timezone.utc)


class Bbox(BaseModel):
    """SVG 부품의 바운딩 박스 (viewBox 기준)."""

    x: float = Field(..., description="좌상단 x")
    y: float = Field(..., description="좌상단 y")
    width: float = Field(..., description="너비")
    height: float = Field(..., description="높이")


class ParamDef(BaseModel):
    """부품의 변수화 가능한 파라미터 정의."""

    name: str = Field(..., description="파라미터 이름 (예: 'radius', 'cx')")
    type: ParamType = Field(..., description="값 타입")
    default: float | int | str | bool = Field(..., description="기본값")
    description: str = Field(default="", description="교사가 읽을 설명")


class AiDraft(BaseModel):
    """Gemini가 제시한 초벌 라벨링 결과 (교사 검증 전)."""

    name: str = ""
    category: str = ""
    subcategory: str = ""
    tags: list[str] = []
    variable_params: list[ParamDef] = []
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    questions_for_teacher: list[str] = []
    gemini_raw: str = Field(default="", description="Gemini 원본 응답 (디버그용)")


# ---------------------------------------------------------------------------
# 카탈로그 엔트리
# ---------------------------------------------------------------------------


class SvgPart(BaseModel):
    """개별 SVG 부품 메타데이터."""

    id: str = Field(..., description="부품 ID (예: '4-001')")
    filename: str = Field(..., description="카탈로그 루트 기준 상대 경로 (parts/...)")

    # 교사 확정 메타 (verified_by_teacher=True면 신뢰)
    name: str = ""
    category: str = ""
    subcategory: str = ""
    tags: list[str] = []
    variable_params: list[ParamDef] = []

    # AI 초벌 (검증 전 보관)
    ai_draft: AiDraft | None = None
    verified_by_teacher: bool = False

    # SVG 기하 정보
    bbox: Bbox
    path_count: int = Field(default=0, ge=0, description="포함된 <path> 개수")

    # 타임스탬프 (UTC, tz-aware)
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class Catalog(BaseModel):
    """카탈로그 전체 — catalog.json 의 최상위 스키마."""

    version: str = "1.0"
    total_count: int = Field(default=0, ge=0)
    parts: list[SvgPart] = []


class Progress(BaseModel):
    """라벨링 진행 상태 — progress.json 의 최상위 스키마.

    scope:
        - 'trial' : 시범 라벨링 (소수 부품) — 갈량 피드백 중 #4 반영
        - 'full'  : 전체 라벨링
    """

    scope: ScopeType = "trial"
    total: int = Field(default=0, ge=0)
    labeled: int = Field(default=0, ge=0)
    skipped: int = Field(default=0, ge=0)
    in_progress_id: str | None = None


__all__ = [
    "ParamType",
    "ScopeType",
    "Bbox",
    "ParamDef",
    "AiDraft",
    "SvgPart",
    "Catalog",
    "Progress",
]
