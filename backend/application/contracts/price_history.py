from pydantic import BaseModel, Field


class PricePoint(BaseModel):
    at: str
    price: int


class PriceHistoryDto(BaseModel):
    route: str
    points: list[PricePoint] = Field(default_factory=list)
