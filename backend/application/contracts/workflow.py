"""Graph entry contracts."""

from __future__ import annotations

from enum import Enum

from .base import BaseContract


class WorkflowErrorCode(str, Enum):
    parse_failed = "parse_failed"
    intent_incomplete = "intent_incomplete"
    clarify_exceeded = "clarify_exceeded"
    datasource_timeout = "datasource_timeout"
    schema_validation = "schema_validation"
    llm_timeout = "llm_timeout"
    memory_write_error = "memory_write_error"
    unknown = "unknown"


class WorkflowRequest(BaseContract):
    user_id: str
    session_id: str | None = None
    message: str


class WorkflowError(BaseContract):
    code: WorkflowErrorCode
    message: str
    node: str | None = None
    retryable: bool = False
