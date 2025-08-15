from __future__ import annotations
from typing import Dict, List

_FEEDBACK: Dict[str, List[dict]] = {}

def record(session_id: str, rating: str, note: str = "") -> None:
    _FEEDBACK.setdefault(session_id, []).append({"rating": rating, "note": note})
