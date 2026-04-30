from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class AlertCreateRequest(BaseModel):
    user_id: str
    flight_id: str
    origin_city: str
    destination_city: str
    depart_date: str
    current_price: int
    target_price: int


class AlertItemDto(BaseModel):
    alert_id: str
    origin_city: str
    destination_city: str
    depart_date: str
    current_price: int
    target_price: int
    status: Literal["active", "cancelled"] = "active"
    created_at: str


class AlertCreateResponseDto(BaseModel):
    alert_id: str
    status: Literal["active", "cancelled"] = "active"
    created_at: str


class AlertsListResponseDto(BaseModel):
    user_id: str
    alerts: list[AlertItemDto] = Field(default_factory=list)
