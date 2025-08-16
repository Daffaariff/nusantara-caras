# services/runner.py
from __future__ import annotations
from typing import Iterator, Dict, Any, List
from datetime import datetime
from agent.orchestrator import ConversationState
from agent.openai_client import extractor_propose, questioner_stream

# --- minimal core list for "ready to evaluate" (tune with your lead if needed)
CORE_FIELDS = [
    "consent_terms_agreed", "consent_is_emergency", "consent_acknowledges_ai",
    "demographics_age", "demographics_sex_assigned_at_birth",
    "demographics_city", "demographics_province",
    "chief_complaint",
    "hpi_onset", "hpi_duration", "hpi_character", "hpi_timing", "hpi_severity",
    "allergies", "current_medications",
]

def _count_completed_core(slots: Dict[str, Any]) -> int:
    def filled(v):
        if v is None: return False
        if isinstance(v, str): return v.strip() != ""
        if isinstance(v, list): return True  # [] means explicitly none (acceptable)
        if isinstance(v, dict): return True
        return True
    return sum(1 for k in CORE_FIELDS if filled(slots.get(k)))

def _compact_memory(slots: Dict[str, Any]) -> str:
    # Small summary for the LLM; include only scalars
    pairs = []
    for k, v in slots.items():
        if v is None: 
            continue
        if isinstance(v, (list, dict)): 
            continue
        pairs.append(f"{k}={v}")
    return "; ".join(pairs) if pairs else "(none)"

def handle_user_turn(state: ConversationState, user_text: str) -> Iterator[dict]:
    """
    Pure agentic: LLM decides safety (interrupt) and follow-ups.
    Yields streaming tokens and stage change events for the UI.
    """
    # 0) record user
    state.turn_count += 1
    state.messages.append({"role": "user", "content": user_text, "ts": datetime.utcnow().isoformat()})

    # 1) extractor proposes updates (including language + safety)
    try:
        proposals = extractor_propose(messages=state.messages, memory_blob=_compact_memory(state.slots))
    except Exception as e:
        # Fail soft: show a brief apology and stop this turn
        err_msg = "Maaf, terjadi kendala teknis. Coba ketik ulang atau kirim pesan lagi ya."
        for ch in err_msg:
            yield {"type": "token", "content": ch}
        state.messages.append({"role": "assistant", "content": err_msg})
        return

    # 1a) language (can be dict or str)
    lang_prop = proposals.get("language")
    if isinstance(lang_prop, dict):
        lang_val = lang_prop.get("value")
        if lang_val: 
            state.language = lang_val
    elif isinstance(lang_prop, str):
        state.language = lang_prop

    # 1b) safety — normalize defensively
    raw_safety = proposals.get("safety")
    safety_obj = None
    if isinstance(raw_safety, dict):
        val = raw_safety.get("value")
        if isinstance(val, dict):
            safety_obj = val
        elif any(k in raw_safety for k in ("interrupt", "message", "reason")):
            safety_obj = raw_safety

    if safety_obj and bool(safety_obj.get("interrupt")):
        state.safety_interrupt = True
        msg = safety_obj.get("message") or "Segera hubungi dokter atau rumah sakit terdekat."
        for ch in msg:
            yield {"type": "token", "content": ch}
        state.messages.append({"role": "assistant", "content": msg})
        return

    # 2) merge field proposals (schema-agnostic, flat slots)
    for key, payload in proposals.items():
        if key in ("language", "safety"):
            continue
        if not isinstance(payload, dict):
            continue
        val = payload.get("value", None)
        if val is not None:
            state.slots[key] = val

    # 3) compute completion & decide to evaluate
    state.completed_core = _count_completed_core(state.slots)
    if state.completed_core >= getattr(state, "completion_target", 14) and state.turn_count >= 4:
        # tell UI to mute input & start "thinking"
        yield {"type": "event", "name": "stage_changed", "payload": {"stage": "EVALUATING"}}
        return

    # 4) otherwise, ask next best follow-up — streamed
    def is_missing(k: str) -> bool:
        v = state.slots.get(k)
        if v is None: 
            return True
        if isinstance(v, str) and v.strip() == "":
            return True
        # empty list is considered explicitly none => not missing
        return False

    ctx = {
        "memory": _compact_memory(state.slots),
        "missing": [k for k in CORE_FIELDS if is_missing(k)],
        "safety": "",
        "turns_left": max(0, 10 - state.turn_count),
        "dialog": state.messages[-8:],
    }
    for tok in questioner_stream(ctx):
        yield {"type": "token", "content": tok}
