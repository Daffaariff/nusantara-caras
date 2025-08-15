# agent/orchestrator.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime
from zoneinfo import ZoneInfo

# --- Conversation state (minimal & explicit) ---

@dataclass
class ConversationState:
    session_id: str
    user_id: str
    tz: str = "Asia/Jakarta"
    eval_seconds: int = 60

    # chat + flow
    messages: List[Dict[str, Any]] = field(default_factory=list)  # [{role, content}]
    turn_count: int = 0
    is_thinking: bool = False
    conversation_closed: bool = False

    # working slots (flat; finalizer assembles nested JSON)
    slots: Dict[str, Any] = field(default_factory=dict)           # {slot_name: value}
    completed_core: int = 0
    completion_target: int = 14     # per lead: at least 14 fields completed before eval trigger

    # language & safety as decided by LLM
    language: Optional[str] = None  # "id"|"su"|"jv"|"en"
    safety_interrupt: bool = False
    safety_message: Optional[str] = None

# --- Helper: WIB ISO8601 timestamp (+07:00) ---

def iso_wib_now() -> str:
    tz = ZoneInfo("Asia/Jakarta")
    return datetime.now(tz).isoformat(timespec="seconds")

# --- Final JSON assembly (exactly per lead’s spec) ---

def finalize_to_json(state: ConversationState) -> Dict[str, Any]:
    """
    Build the exact JSON object required by the lead's spec.
    Rule: all keys present, null for missing, arrays as [] (or null where allowed).
    Output language: English field names + values; culture-specific (e.g., 'jamu') may remain.
    """
    s = state.slots  # convenience

    # helper getters with null default
    def g(key, default=None):
        return s.get(key, default)

    # medication items normalization
    meds = g("current_medications", None)
    if meds is None:
        meds_out = None  # unknown
    elif isinstance(meds, list):
        # normalize each item to {name, type}
        meds_out = []
        for m in meds:
            if isinstance(m, dict):
                meds_out.append({
                    "name": m.get("name"),
                    "type": m.get("type")  # "prescription" | "over_the_counter" | "herbal"
                })
            elif isinstance(m, str):
                meds_out.append({"name": m, "type": None})
            else:
                meds_out.append({"name": None, "type": None})
    else:
        meds_out = None

    doc = {
      "session_id": state.session_id,
      "timestamp": iso_wib_now(),
      "consent": {
        "terms_agreed": g("consent_terms_agreed", None),
        "is_emergency": g("consent_is_emergency", None),
        "acknowledges_ai": g("consent_acknowledges_ai", None)
      },
      "patient_demographics": {
        "age": g("demographics_age", None),
        "sex_assigned_at_birth": g("demographics_sex_assigned_at_birth", None),
        "location": {
          "city": g("demographics_city", None),
          "province": g("demographics_province", None)
        }
      },
      "chief_complaint": g("chief_complaint", None),
      "history_present_illness": {
        "onset": g("hpi_onset", None),
        "location": g("hpi_location", None),
        "duration": g("hpi_duration", None),
        "character": g("hpi_character", None),
        "aggravating_factors": g("hpi_aggravating", None),
        "alleviating_factors": g("hpi_alleviating", None),
        "radiation": g("hpi_radiation", None),
        "timing": g("hpi_timing", None),
        "severity": g("hpi_severity", None),  # int 1-10 or null
      },
      "review_of_systems": {
        "general": g("ros_general", [] if "ros_general" in s else None),
        "heent": g("ros_heent", [] if "ros_heent" in s else None),
        "respiratory": g("ros_respiratory", [] if "ros_respiratory" in s else None),
        "gastrointestinal": g("ros_gastrointestinal", [] if "ros_gastrointestinal" in s else None),
        "musculoskeletal": g("ros_musculoskeletal", [] if "ros_musculoskeletal" in s else None),
      },
      "past_medical_history": {
        "chronic_illnesses": g("pmh_chronic_illnesses", [] if "pmh_chronic_illnesses" in s else None),
        "past_surgeries": g("pmh_past_surgeries", None),         # [] if explicitly none, null if unknown
        "hospitalizations": g("pmh_hospitalizations", None)       # [] if explicitly none, null if unknown
      },
      "medications_and_allergies": {
        "current_medications": meds_out,
        "allergies": g("allergies", [] if "allergies" in s else None)
      }
    }
    return doc
