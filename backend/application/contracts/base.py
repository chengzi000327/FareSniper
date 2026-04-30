"""Base classes for workflow contract models."""

from pydantic import BaseModel, ConfigDict


class BaseContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=False)
