from __future__ import annotations
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field, validator
from dataclasses import dataclass

Provenance = Literal["explicit", "implicit", "inferred"]

class FieldState(BaseModel):
    value: Optional[Any] = None
    completeness: int = 0               # 0 or 1 (backend-validated)
    weight: float = 0.0                 # 0..1 (fuzzy certainty)
    provenance: Provenance = "inferred"
    candidate: Optional[Dict[str, Any]] = None  # {"value":..., "weight":..., "provenance":...}

    @validator("completeness")
    def _check_completeness(cls, v):
        if v not in (0, 1):
            raise ValueError("completeness must be 0 or 1")
        return v

class Params(BaseModel):
    # NOTE: keep schema-agnostic: you can expand these to your lead's 20 fields.
    primary_concern: FieldState = Field(default_factory=FieldState)
    concern_onset: FieldState = Field(default_factory=FieldState)
    severity: FieldState = Field(default_factory=FieldState)           # 0–10 ordinal expected
    location_of_pain: FieldState = Field(default_factory=FieldState)   # enum/list allowed
    pain_character: FieldState = Field(default_factory=FieldState)
    associated_symptoms: FieldState = Field(default_factory=FieldState)  # list
    triggers: FieldState = Field(default_factory=FieldState)             # list
    relievers: FieldState = Field(default_factory=FieldState)            # list
    duration: FieldState = Field(default_factory=FieldState)             # number + unit
    medical_history: FieldState = Field(default_factory=FieldState)      # list
    current_meds: FieldState = Field(default_factory=FieldState)         # list
    allergies: FieldState = Field(default_factory=FieldState)            # list
    red_flags: FieldState = Field(default_factory=FieldState)            # list
    user_intent: FieldState = Field(default_factory=FieldState)          # enum
    # add more to reach ~20…

    def dict_flat(self) -> Dict[str, FieldState]:
        return {name: getattr(self, name) for name in self.__fields__}

@dataclass(frozen=True)
class ParamMeta:
    name: str
    prio: int = 5
    type: str = "str"                  # "str"|"enum"|"ordinal"|"list"|"duration"|"datetime"
    choices: Optional[List[str]] = None
    required: bool = False
    safety_tag: bool = False

# Default metadata (tune priorities later)
DEFAULT_SCHEMA: List[ParamMeta] = [
    ParamMeta("primary_concern", prio=10, required=True),
    ParamMeta("concern_onset", prio=9),
    ParamMeta("severity", prio=9, type="ordinal"),
    ParamMeta("location_of_pain", prio=8, type="enum"),
    ParamMeta("pain_character", prio=8, type="enum"),
    ParamMeta("associated_symptoms", prio=8, type="list"),
    ParamMeta("triggers", prio=7, type="list"),
    ParamMeta("relievers", prio=6, type="list"),
    ParamMeta("duration", prio=7, type="duration"),
    ParamMeta("medical_history", prio=6, type="list"),
    ParamMeta("current_meds", prio=6, type="list"),
    ParamMeta("allergies", prio=6, type="list"),
    ParamMeta("red_flags", prio=10, type="list", safety_tag=True),
    ParamMeta("user_intent", prio=8, type="enum"),
]

# --- Validators (acceptance rules) ---
def accept(meta: ParamMeta, proposal: Dict[str, Any]) -> bool:
    """Return True iff proposal is minimally valid for this field type."""
    if proposal is None:
        return False
    val = proposal.get("value", None)
    if val is None:
        return False

    t = meta.type
    if t == "str":
        return isinstance(val, str) and val.strip() not in ("", "idk", "maybe", "kinda")
    if t == "enum":
        if isinstance(val, str) and meta.choices:
            return val in meta.choices
        return isinstance(val, str) and len(val.strip()) > 0
    if t == "ordinal":
        try:
            n = float(val)
            return 0.0 <= n <= 10.0
        except Exception:
            return False
    if t == "list":
        return isinstance(val, list) and len(val) > 0
    if t == "duration":
        # naive check: contains a number and a unit
        if isinstance(val, str):
            import re
            return bool(re.search(r"\b\d+(\.\d+)?\s*(h|hr|hour|hours|d|day|days|m|min|mins|minute|minutes)\b", val.lower()))
        return False
    if t == "datetime":
        try:
            from dateutil import parser
            parser.parse(str(val))
            return True
        except Exception:
            return False
    return True  # default: accept if not sure

def completed_count(p: Params) -> int:
    return sum(1 for f in p.dict_flat().values() if f.completeness == 1)

def weighted_coverage(p: Params) -> float:
    fields = list(p.dict_flat().values())
    if not fields:
        return 0.0
    return sum(f.weight for f in fields if f.completeness == 1) / len(fields)
