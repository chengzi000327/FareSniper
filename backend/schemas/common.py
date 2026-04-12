from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


ApiConfidence = Literal["high", "medium", "low"]


class ApiMeta(BaseModel):
    generated_at: str
    source: Optional[str] = None
    request_id: Optional[str] = None
    result_count: Optional[int] = None
    fallback_mode: Optional[bool] = None


class DealCardDto(BaseModel):
    id: str
    system_id: str
    platform: str
    origin_city: str
    origin_code: str
    destination_city: str
    destination_code: str
    depart_date: str
    airline: str
    depart_time: str
    arrive_time: str
    price: int
    original_price: Optional[int] = None
    discount_rate: Optional[float] = None
    cabin: Optional[str] = None
    signals: list[str] = Field(default_factory=list)
    confidence: ApiConfidence = "medium"
    verdict: str
    booking_url: Optional[str] = None


class RecommendationCardDto(BaseModel):
    id: str
    title: str
    reason: str
    query_hint: str
    tags: list[str] = Field(default_factory=list)
    preview_deal: Optional[DealCardDto] = None


# ── 向后兼容别名（旧代码引用，Step 8 删除）────────────────────────────────

class HealthResponse(BaseModel):
    status: str = "ok"
    app: str
