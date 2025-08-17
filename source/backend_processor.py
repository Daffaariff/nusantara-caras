import os
import json
import gradio as gr
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# =========================
# TAB 1 — SEA-LION Chat
# =========================
SEA_LION_API_KEY = os.getenv("SEA_LION_API_KEY")
SEA_LION_BASE_URL = os.getenv("SEA_LION_BASE_URL")
SEA_LION_MODEL_NAME = os.getenv("SEA_LION_MODEL_NAME")
SEA_LION_SYSTEM_PROMPT = os.getenv("SEA_LION_SYSTEM_PROMPT")

sea_client = OpenAI(api_key=SEA_LION_API_KEY, base_url=SEA_LION_BASE_URL)

sea_history = [{"role": "system", "content": SEA_LION_SYSTEM_PROMPT or ""}]

def sea_chat_with_openai(user_message: str) -> str:
    global sea_history
    sea_history.append({"role": "user", "content": user_message})
    resp = sea_client.chat.completions.create(
        model=SEA_LION_MODEL_NAME,
        messages=sea_history,
        temperature=0.1,
        top_p=1.0,
        max_tokens=150,
        extra_body={"chat_template_kwargs": {"thinking_mode": "off"}},
    )
    bot = resp.choices[0].message.content
    sea_history.append({"role": "assistant", "content": bot})
    return bot

def sea_respond(user_message, chat_history):
    bot_message = sea_chat_with_openai(user_message)
    chat_history.append((user_message, bot_message))
    return "", chat_history

def sea_clear_memory():
    global sea_history
    sea_history = [{"role": "system", "content": SEA_LION_SYSTEM_PROMPT or ""}]
    return []


# =========================
# TAB 2 — Backend Gemma Prototype
# =========================
class MedicalDiagnosticAssistant:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.base_url = os.getenv("OPENAI_BASE_URL")
        self.system_prompt = os.getenv("SYSTEM_PROMPT")
        self.user_prompt_template = os.getenv("USER_PROMPT_TEMPLATE")

        if not all([self.api_key, self.base_url, self.system_prompt, self.user_prompt_template]):
            missing = [k for k, v in {
                "OPENAI_API_KEY": self.api_key,
                "OPENAI_BASE_URL": self.base_url,
                "SYSTEM_PROMPT": self.system_prompt,
                "USER_PROMPT_TEMPLATE": self.user_prompt_template,
            }.items() if not v]
            raise RuntimeError(f"Missing env vars: {', '.join(missing)}")

        self.client = OpenAI(base_url=self.base_url, api_key=self.api_key)

    def format_user_prompt(self, patient_data: dict) -> str:
        return self.user_prompt_template.format(**patient_data)

    def get_diagnosis(self, patient_data: dict, model: str = "gpt-4o-mini"):
        user_prompt = self.format_user_prompt(patient_data)
        resp = self.client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_prompt},
            ]
        )
        text = resp.choices[0].message.content
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"raw_output": text}

gemma_chat_log = []

def run_diagnosis(
    chief_complaint, onset, location, duration, character,
    aggravating_factors, alleviating_factors, radiation, timing, severity,
    chat_log
):
    patient_data = {
        "chief_complaint": chief_complaint or "",
        "onset": onset or "",
        "location": location or "",
        "duration": duration or "",
        "character": character or "",
        "aggravating_factors": aggravating_factors or "",
        "alleviating_factors": alleviating_factors or "",
        "radiation": radiation or "",
        "timing": timing or "",
        "severity": severity if severity is not None else 0,
    }

    assistant = MedicalDiagnosticAssistant()
    result = assistant.get_diagnosis(patient_data, model="gpt-4o-mini")  # 🔒 fixed model

    # Update chat log
    user_summary = (
        f"CC: {patient_data['chief_complaint']}; onset: {patient_data['onset']}; "
        f"loc: {patient_data['location']}; dur: {patient_data['duration']}; "
        f"char: {patient_data['character']}; agg: {patient_data['aggravating_factors']}; "
        f"allv: {patient_data['alleviating_factors']}; rad: {patient_data['radiation']}; "
        f"time: {patient_data['timing']}; sev: {patient_data['severity']}"
    )
    chat_log = chat_log or []
    chat_log.append((user_summary, json.dumps(result, ensure_ascii=False, indent=2)))
    return result, chat_log

def clear_gemma_chat():
    global gemma_chat_log
    gemma_chat_log = []
    return []


# =========================
# Build Gradio UI
# =========================
with gr.Blocks(title="Two-Place Chat: SEA-LION + Backend Gemma Prototype") as demo:
    gr.Markdown("# Two-Place Chat\n**Tab 1:** SEA-LION Chat • **Tab 2:** Backend Gemma Prototype")

    with gr.Tabs():
        # ---- TAB 1: SEA-LION ----
        with gr.Tab("SEA-LION Chat"):
            sea_chatbot = gr.Chatbot(height=420)
            with gr.Row():
                sea_msg = gr.Textbox(placeholder="Type your message here...")
                sea_send = gr.Button("Send", variant="primary")
                sea_clear = gr.Button("Clear")

            sea_msg.submit(sea_respond, [sea_msg, sea_chatbot], [sea_msg, sea_chatbot])
            sea_send.click(sea_respond, [sea_msg, sea_chatbot], [sea_msg, sea_chatbot])
            sea_clear.click(sea_clear_memory, None, sea_chatbot, queue=False)

        # ---- TAB 2: Backend Gemma Prototype ----
        with gr.Tab("Backend Gemma Prototype"):
            gr.Markdown("### Enter patient data → get structured diagnosis (JSON). Right side keeps a chat log.")

            with gr.Row():
                with gr.Column(scale=6):
                    with gr.Row():
                        chief_complaint = gr.Textbox(label="Chief Complaint", placeholder="Toothache")
                        onset = gr.Textbox(label="Onset", placeholder="3 days ago upon waking")
                    with gr.Row():
                        location = gr.Textbox(label="Location", placeholder="Back teeth")
                        duration = gr.Textbox(label="Duration", placeholder="Intermittent, minutes to hours")
                    with gr.Row():
                        character = gr.Textbox(label="Character", placeholder="Pressed, pulsating")
                        aggravating_factors = gr.Textbox(label="Aggravating Factors", placeholder="cold water")
                    with gr.Row():
                        alleviating_factors = gr.Textbox(label="Alleviating Factors", placeholder="warm water")
                        radiation = gr.Textbox(label="Radiation", placeholder="None")
                    with gr.Row():
                        timing = gr.Textbox(label="Timing", placeholder="Worse in the morning")
                        severity = gr.Slider(label="Severity (0-10)", minimum=0, maximum=10, step=1, value=6)

                    run_btn = gr.Button("Generate Diagnosis", variant="primary")
                    result_view = gr.JSON(label="Diagnosis Result (JSON)")

                with gr.Column(scale=6):
                    gemma_chat = gr.Chatbot(label="Diagnosis Chat Log", height=420)
                    gemma_clear = gr.Button("Clear Log")

            run_btn.click(
                run_diagnosis,
                inputs=[
                    chief_complaint, onset, location, duration, character,
                    aggravating_factors, alleviating_factors, radiation, timing, severity,
                    gemma_chat
                ],
                outputs=[result_view, gemma_chat]
            )

            gemma_clear.click(clear_gemma_chat, None, gemma_chat, queue=False)

demo.launch()
