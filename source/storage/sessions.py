from __future__ import annotations
from typing import Dict, Any

_SESS: Dict[str, Dict[str, Any]] = {}

def get(session_id: str) -> Dict[str, Any]:
    return _SESS.setdefault(session_id, {})

def save_payload(session_id: str, payload: dict) -> None:
    _SESS.setdefault(session_id, {})["latest_payload"] = payload
