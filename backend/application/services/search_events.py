from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import SplitResult, urlsplit, urlunsplit


_SENSITIVE_KEY_SUFFIXES = (
    "apikey",
    "authorization",
    "authorizationheader",
    "headers",
    "rawpayload",
    "token",
)


def _canonical_key(key: object) -> str:
    return "".join(
        character
        for character in str(key).casefold()
        if character.isalnum()
    )


def _is_sensitive_key(key: object) -> bool:
    return _canonical_key(key).endswith(_SENSITIVE_KEY_SUFFIXES)


def _is_recognized_uri_reference(value: str, parsed: SplitResult) -> bool:
    if any(character.isspace() for character in value):
        return False
    if parsed.scheme in {"http", "https"}:
        return bool(parsed.netloc)
    if parsed.scheme or not value.startswith("/"):
        return False
    if value.startswith("//"):
        try:
            return bool(parsed.netloc and parsed.hostname)
        except ValueError:
            return False
    return not parsed.netloc


def _safe_uri_reference(value: str) -> str:
    try:
        parsed = urlsplit(value)
    except ValueError:
        return value
    if not _is_recognized_uri_reference(value, parsed):
        return value
    if not parsed.query and not parsed.fragment:
        return value
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))


def _safe_event_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(item_key): _safe_event_value(item_value)
            for item_key, item_value in value.items()
            if not _is_sensitive_key(item_key)
        }
    if isinstance(value, (list, tuple)):
        return [_safe_event_value(item) for item in value]
    if isinstance(value, str):
        return _safe_uri_reference(value)
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
