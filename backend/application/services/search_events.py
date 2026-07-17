from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit, urlunsplit


_SENSITIVE_KEYS = {
    "api_key",
    "authorization",
    "headers",
    "raw_payload",
    "token",
}


def _is_sensitive_key(key: object) -> bool:
    normalized = str(key).lower().replace("-", "_")
    return (
        normalized in _SENSITIVE_KEYS
        or normalized.endswith("_api_key")
        or normalized.endswith("apikey")
        or normalized.endswith("_headers")
    )


def _safe_event_value(value: Any, *, key: str = "") -> Any:
    if isinstance(value, Mapping):
        return {
            str(item_key): _safe_event_value(item_value, key=str(item_key))
            for item_key, item_value in value.items()
            if not _is_sensitive_key(item_key)
        }
    if isinstance(value, (list, tuple)):
        return [_safe_event_value(item) for item in value]
    if isinstance(value, str) and key.lower().endswith("url"):
        parsed = urlsplit(value)
        if parsed.scheme in {"http", "https"} and parsed.netloc:
            return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
    return value


@dataclass
class SearchEventEmitter:
    search_id: str
    sink: Callable[[dict], None]
    sequence: int = field(default=0, init=False)

    def emit(self, event_type: str, payload: dict) -> None:
        self.sequence += 1
        self.sink(
            {
                "type": event_type,
                "search_id": self.search_id,
                "sequence": self.sequence,
                "payload": _safe_event_value(payload),
            }
        )


_EMITTER: ContextVar[SearchEventEmitter | None] = ContextVar(
    "search_event_emitter", default=None
)


@contextmanager
def bind_search_event_emitter(
    emitter: SearchEventEmitter,
) -> Iterator[SearchEventEmitter]:
    token = _EMITTER.set(emitter)
    try:
        yield emitter
    finally:
        _EMITTER.reset(token)


def emit_search_event(event_type: str, payload: dict) -> None:
    emitter = _EMITTER.get()
    if emitter is not None:
        emitter.emit(event_type, payload)
