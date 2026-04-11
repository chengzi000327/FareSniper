from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = "ok"
    app: str


class RecommendationModel(BaseModel):
    recommendation: str
    signals: List[str] = Field(default_factory=list)
    confidence: str = "medium"


class FlightResultModel(BaseModel):
    id: str
    platform: str
    origin: str
    destination: str
    depart_date: str
    airline: str
    depart_time: str
    arrive_time: str
    price: int
    cabin: Optional[str] = None
    signals: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RecommendationCardModel(BaseModel):
    title: str
    reason: str
    query_hint: str
    price: Optional[int] = None
    destination: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
