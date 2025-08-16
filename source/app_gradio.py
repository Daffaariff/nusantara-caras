import gradio as gr
from openai import OpenAI
from typing import Optional, List, Dict, Generator
from dotenv import load_dotenv
import os
load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
base_url = os.getenv("BASE_URL")
model_name = os.getenv("MODEL_NAME")
SYSTEM_PROMPT = os.getenv("SYSTEM_PROMPT")

# Initialize OpenAI client
client = OpenAI(api_key=api_key, base_url=base_url)

# Memory (conversation history)
conversation_history = [
    {"role": "system", "content": SYSTEM_PROMPT}
]

def chat_with_openai(user_message):
    global conversation_history

    # Add user message to history
    conversation_history.append({"role": "user", "content": user_message})

    # Call OpenAI API with memory
    response = client.chat.completions.create(
        model=model_name,
        messages=conversation_history,
        temperature=0.1,
        top_p=1.0,
        max_tokens=150,
        extra_body={
        "chat_template_kwargs": {
            "thinking_mode": "off"
        }
    },
    )

    bot_reply = response.choices[0].message.content

    # Add assistant reply to history
    conversation_history.append({"role": "assistant", "content": bot_reply})

    return bot_reply

# Build Gradio UI
with gr.Blocks() as demo:
    chatbot = gr.Chatbot()
    msg = gr.Textbox(placeholder="Type your message here...")
    clear = gr.Button("Clear")

    def respond(user_message, chat_history):
        bot_message = chat_with_openai(user_message)
        chat_history.append((user_message, bot_message))
        return "", chat_history

    def clear_memory():
        global conversation_history
        conversation_history = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]
        return []

    msg.submit(respond, [msg, chatbot], [msg, chatbot])
    clear.click(clear_memory, None, chatbot, queue=False)

demo.launch()
