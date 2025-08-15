from __future__ import annotations
from typing import Dict, Iterator, List
import os, json

# OpenAI SDK (>=1.0)
try:
    from openai import OpenAI
except Exception:
    OpenAI = None

# ---------- client ----------
def _client():
    if OpenAI is None:
        raise RuntimeError("openai package not installed. Run: pip install openai")
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY not set. Put it in .env or your shell.")
    return OpenAI(api_key=key)

# ---------- system prompts (lead-spec aligned, minimal) ----------
EXTRACTOR_SYSTEM = (
    'You are "Nusantara CaRas", an empathetic Indonesian medical intake assistant. '
    "Your job is to read the dialogue and PROPOSE structured field updates for a medical intake JSON. "
    "NEVER provide medical advice or diagnoses. If a medical emergency is suspected (e.g., severe chest pain, "
    "difficulty breathing, uncontrolled bleeding, loss of consciousness), propose a safety interrupt with a short, "
    "polite message in the user's language advising immediate help: "
    '"segera hubungi dokter atau rumah sakit terdekat". '
    "Language handling: detect user language as id (Indonesian), su (Sundanese), jv (Javanese), or en. "
    "Return proposals via the tool `propose_params` ONLY for fields you can justify from the conversation. "
    "For each field: {value, weight: 0..1, provenance: explicit|implicit|inferred}. "
    "Omit fields you are unsure about. Do NOT output the final JSON here."
)

QUESTIONER_SYSTEM = (
    'You are "Nusantara CaRas", a concise, friendly interviewer (ID/Sunda/Jawa/EN depending on the user). '
    "Ask AT MOST TWO short questions that most help complete the medical intake (Consent→Demographics→Chief Complaint→OLDCARTS→ROS→PMH→Meds/Allergies). "
    "Avoid medical advice or diagnosis. Prefer options/scales (e.g., severity 1–10). Keep language simple and polite."
)

# ---------- tool: schema-agnostic proposals ----------
PROPOSE_PARAMS_TOOL = {
    "type": "function",
    "function": {
        "name": "propose_params",
        "description": "Propose field values with fuzzy weight (0..1). Include 'language' and 'safety' if relevant.",
        "parameters": {
            "type": "object",
            "properties": {                           # <-- REQUIRED by OpenAI
                "fields": {
                    "type": "object",
                    "description": "Arbitrary field map for the intake form.",
                    "additionalProperties": {
                        "type": "object",
                        "properties": {
                            "value": {},
                            "weight": {"type": "number", "minimum": 0, "maximum": 1},
                            "provenance": {"type": "string", "enum": ["explicit", "implicit", "inferred"]}
                        },
                        "required": ["value", "weight"],
                        "additionalProperties": True
                    }
                }
            },
            "required": ["fields"]
        }
    }
}

def extractor_propose(messages: List[dict], memory_blob: str) -> Dict[str, dict]:
    """
    Returns dict: { field_name: {value, weight, provenance}, ... }
    Special keys allowed: 'language', 'safety' (see caller for handling).
    """
    c = _client()
    resp = c.chat.completions.create(
        model=os.getenv("MODEL_FAST", "gpt-4o-mini"),
        temperature=0.0,
        tools=[PROPOSE_PARAMS_TOOL],
        tool_choice="auto",
        messages=[
            {"role": "system", "content": EXTRACTOR_SYSTEM},
            {"role": "system", "content": f"Memory (filled so far): {memory_blob}"},
            *messages
        ],
    )
    msg = resp.choices[0].message
    out: Dict[str, dict] = {}

    if getattr(msg, "tool_calls", None):
        for tc in msg.tool_calls:
            if tc.function.name != "propose_params":
                continue
            try:
                args = json.loads(tc.function.arguments or "{}")
            except Exception:
                args = {}

            # Prefer wrapped format { "fields": { ... } }
            fields = args.get("fields")
            if isinstance(fields, dict):
                out.update(fields)
                continue

            # Fallback: support legacy direct map (if model ignores "fields")
            if isinstance(args, dict):
                # Avoid copying "fields" again if present
                for k, v in args.items():
                    if k == "fields":
                        continue
                    if isinstance(v, dict) and "value" in v:
                        out[k] = v

    return out

# ---------- questioner: stream ----------
def questioner_stream(context: dict) -> Iterator[str]:
    """
    Streams 1–2 short follow-up questions. `context` keys expected:
      - memory: compact string of known fields
      - missing: list of top missing core keys (strings)
      - safety: optional cues (unused here; model can infer)
      - turns_left: int
      - dialog: recent message list
    """
    c = _client()
    msgs = [
        {"role": "system", "content": QUESTIONER_SYSTEM},
        {"role": "system", "content": _pack_context(context)},
    ] + context.get("dialog", [])
    stream = c.chat.completions.create(
        model=os.getenv("MODEL_FAST", "gpt-4o-mini"),
        temperature=0.2,
        stream=True,
        messages=msgs,
    )
    for ev in stream:
        if ev.choices and ev.choices[0].delta and ev.choices[0].delta.content:
            yield ev.choices[0].delta.content

def _pack_context(ctx: dict) -> str:
    mem = ctx.get("memory", "(none)")
    missing = ctx.get("missing", [])
    turns_left = ctx.get("turns_left", 0)
    return f"Known: {mem}\nTop missing: {missing}\nTurns left: {turns_left}"
