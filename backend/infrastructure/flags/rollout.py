"""Deterministic per-user rollout bucketing.

A user lands in the rollout iff the first 32 bits of
``md5(flag_name + ':' + user_id)`` mod 100 fall below the configured
percentage. Hashing both flag name and user id keeps buckets independent
across flags so two 50% flags don't allocate the same population.
"""
from __future__ import annotations

import hashlib


def in_rollout(user_id: str, flag_name: str, pct: int) -> bool:
    if pct <= 0:
        return False
    if pct >= 100:
        return True
    digest = hashlib.md5(f"{flag_name}:{user_id}".encode()).hexdigest()
    bucket = int(digest[:8], 16) % 100
    return bucket < pct
