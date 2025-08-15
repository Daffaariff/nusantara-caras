from __future__ import annotations
import uuid, json, time
import streamlit as st

from agent.orchestrator import ConversationState, finalize_to_json
from services.runner import handle_user_turn

from dotenv import load_dotenv
load_dotenv()

st.set_page_config(page_title="Nusantara CaRas", page_icon="🇮🇩", layout="centered")
st.title("🇮🇩 Nusantara CaRas — Medical Intake")

if "session_id" not in st.session_state:
    st.session_state.session_id = "sess_" + uuid.uuid4().hex[:10]
if "state" not in st.session_state:
    st.session_state.state = ConversationState(
        session_id=st.session_state.session_id,
        user_id="webuser",
        tz="Asia/Jakarta",
        eval_seconds=60
    )
if "log" not in st.session_state:
    st.session_state.log = []

state: ConversationState = st.session_state.state
is_thinking = getattr(state, "is_thinking", False)

for m in st.session_state.log:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

prompt = st.chat_input(
    "Tulis pesan Anda…",
    disabled=is_thinking
)

if prompt and not is_thinking:
    st.session_state.log.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        placeholder = st.empty()
        buf = []

        for ev in handle_user_turn(state, prompt):
            t = ev.get("type")
            if t == "token":
                buf.append(ev.get("content", ""))
                placeholder.markdown("".join(buf))
            elif t == "event":
                name = ev.get("name")
                if name == "stage_changed" and ev.get("payload", {}).get("stage") == "EVALUATING":
                    state.is_thinking = True
                    break
        final_text = "".join(buf).strip()
        if final_text:
            st.session_state.log.append({"role": "assistant", "content": final_text})

    if getattr(state, "is_thinking", False):
        st.experimental_rerun()

# --- thinking state (mute input, show spinner) ---
if getattr(state, "is_thinking", False):
    with st.chat_message("assistant"):
        with st.spinner("…"):
            # simulate/perform evaluation
            time.sleep(getattr(state, "eval_seconds", 60))
            # produce final JSON-only message
            doc = finalize_to_json(state)  # must return dict with lead-spec shape
            json_text = json.dumps(doc, ensure_ascii=False)
    # append JSON as normal assistant message
    st.session_state.log.append({"role": "assistant", "content": json_text})
    state.is_thinking = False
    # Optionally mark conversation closed if you don’t want more input after JSON:
    state.conversation_closed = True
    st.experimental_rerun()

# optional: lock input after final JSON
if getattr(state, "conversation_closed", False):
    st.chat_input("Sesi selesai.", disabled=True)
