
import os
from typing import List, Dict, Generator, Optional
try:
    from openai import OpenAI
except ImportError as e:
    raise SystemExit(
        "The 'openai' package is required. Install with: pip install openai>=1.0.0"
    ) from e


DEFAULT_SYSTEM_PROMPT = "You are a helpful assistant."


class ChatBackbone:
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4o-mini",
        temperature: float = 0.2,
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
    ):
        if api_key:
            os.environ["OPENAI_API_KEY"] = api_key
        elif not os.getenv("OPENAI_API_KEY"):
            raise ValueError("OpenAI API key not provided. Set OPENAI_API_KEY or pass api_key.")
        self.client = OpenAI()
        self.model = model
        self.temperature = temperature
        self._system_prompt = system_prompt
        self.messages: List[Dict[str, str]] = [{"role": "system", "content": self._system_prompt}]

    def set_system_prompt(self, prompt: str):
        self._system_prompt = prompt
        self.reset()

    def reset(self):
        self.messages = [{"role": "system", "content": self._system_prompt}]

    def history(self) -> List[Dict[str, str]]:
        return list(self.messages)

    def complete(self, user_content: str) -> str:
        self.messages.append({"role": "user", "content": user_content})
        res = self.client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            messages=self.messages,
            stream=False,
        )
        reply = res.choices[0].message.content or ""
        self.messages.append({"role": "assistant", "content": reply})
        return reply

    def stream(self, user_content: str) -> Generator[str, None, None]:
        self.messages.append({"role": "user", "content": user_content})
        acc = []
        stream = self.client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            messages=self.messages,
            stream=True,
        )
        for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            part = getattr(delta, "content", None) or ""
            if part:
                acc.append(part)
                yield part
        if acc:
            self.messages.append({"role": "assistant", "content": "".join(acc)})
