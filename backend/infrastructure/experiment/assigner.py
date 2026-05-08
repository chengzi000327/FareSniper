from __future__ import annotations

import hashlib


def assign_arm(user_id: str, experiment_name: str) -> str:
    h = hashlib.md5(f"{experiment_name}:{user_id}".encode()).hexdigest()
    return "treatment" if int(h[:8], 16) % 2 == 0 else "control"
