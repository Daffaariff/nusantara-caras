
import time
import asyncio
from typing import Dict, Any, List, Literal
from openai import OpenAI, AsyncOpenAI
from loguru import logger


class BaseAgent:
    def __init__(
        self,
        system_prompt: str,
        human_prompt: str,
        provider: Literal["openai", "sealion"] = "openai",
        agent_name: str = "",
        max_retries: int = 3,
        multiagent_name: str = "",
        **model_kwargs: Any,
    ):
        self.system_prompt : str = system_prompt
        self.human_prompt : str = human_prompt
        self.provider : Literal["openai", "sealion"] = provider
        self.agent_name : str = agent_name
        self.max_retries : int = max_retries
        self.multiagent_name : str = multiagent_name

        self.model_name : str = model_kwargs.get("model_name", "gemini-1.5-flash")
        self.base_url : str = model_kwargs.get(
            "base_url", "https://generativelanguage.sealionapis.com/v1beta/openai/"
        )
        self.api_key : str = model_kwargs.get("api_key") or ""

        self._validate_model_kwargs(model_kwargs)

    def _validate_model_kwargs(self, model_kwargs: Dict[str, Any]):
        # Remove parameters that shouldn't be passed to the model
        model_kwargs.pop("model_name", None)
        model_kwargs.pop("base_url", None)
        model_kwargs.pop("api_key", None)
        model_kwargs.pop("max_new_token", None)
        model_kwargs.pop("multiagent_name", None)

        # Set default timeout if not provided
        if "timeout" not in model_kwargs:
            model_kwargs["timeout"] = 180

        self.model_kwargs = model_kwargs

    def chat_prompt(self, **kwargs):
        """
        Initializes the chat prompt by combining the system and human prompts.
        """
        system_content = (
            self.system_prompt.format(**kwargs) if kwargs else self.system_prompt
        )
        user_content = (
            self.human_prompt.format(**kwargs) if kwargs else self.human_prompt
        )
        return [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_content},
        ]

    def _llm(self):
        return OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
        )

    def _allm(self):
        return AsyncOpenAI(

            api_key=self.api_key,
            base_url=self.base_url,

        )

    def analyze(self, **kwargs: Any) -> str:
        """
        Synchronous analysis method.
        """
        start_time = time.time()
        tries = 0
        logger.debug(self.model_kwargs)
        while tries < self.max_retries:
            try:
                with self._llm() as llm:
                    response: Any = llm.chat.completions.create(
                        model=self.model_name,
                        messages=self.chat_prompt(**kwargs),
                        **self.model_kwargs,
                    ) # type: ignore

                if response.choices[0].finish_reason == "stop":
                    process_time = time.time() - start_time
                    logger.success(f"Analysis completed in {process_time:.2f}s")
                    return response.choices[0].message.content

                tries += 1
                logger.warning(
                    f"Attempt {tries} failed, finish_reason: {response.choices[0].finish_reason}"
                )

            except Exception as e:
                tries += 1
                logger.error(f"Attempt {tries} failed with error: {str(e)}")
                if tries >= self.max_retries:
                    raise e
                time.sleep(1)

        raise Exception(f"Max retries exceeded after {self.max_retries} attempts")

    async def aanalyze(self, **kwargs: Any) -> str:
        """
        Asynchronous analysis method.
        """
        start_time = time.time()
        tries = 0
        logger.debug(self.model_kwargs)
        while tries < self.max_retries:
            try:
                async with self._allm() as llm:
                    response = await llm.chat.completions.create(
                        model=self.model_name,
                        messages=self.chat_prompt(**kwargs),
                        **self.model_kwargs,
                    ) # type: ignore

                if response.choices[0].finish_reason == "stop":
                    process_time = time.time() - start_time
                    logger.success(f"Async analysis completed in {process_time:.2f}s")
                    return response.choices[0].message.content

                tries += 1
                logger.warning(
                    f"Attempt {tries} failed, finish_reason: {response.choices[0].finish_reason}"
                )

            except Exception as e:
                tries += 1
                logger.error(f"Attempt {tries} failed with error: {str(e)}")
                if tries >= self.max_retries:
                    raise e
                await asyncio.sleep(1)  # Brief delay before retry

        raise Exception(f"Max retries exceeded after {self.max_retries} attempts")


async def main():
    """Example usage with async method"""
    agent = BaseAgent(
        agent_name="simplified_agent",
        system_prompt="You are an AI assistant specialized in processing and analyzing text data with characteristics such as {persona}. Please analyze the following content.",
        human_prompt="Here is the content: {input_text}",
        api_key="AIzaSyD2kY8qdrsUgVTk0kzKDTMS9xiB-X-T-zg",  # Replace with your actual API key
        model_name="gemini-1.5-flash",
        max_retries=3,
        timeout=180,
        temperature=0.7,
    )

    input_text = "Analyze the sentiment either positive, neutral or negative of this sentence: Gold has reached an all-time high!"
    persona = "Data is concise and clear, in English. The data is a sentence with positive, neutral or negative sentiment."

    try:
        response = await agent.aanalyze(persona=persona, input_text=input_text)
        logger.success(f"Async Agent response:\n{response}")
    except Exception as e:
        logger.error(f"Error in async analysis: {e}")


if __name__ == "__main__":
    # Example with synchronous method
    agent = BaseAgent(
        agent_name="simplified_agent",
        system_prompt="{persona}",
        human_prompt="Here is the user query: {input_text}",
        api_key="sk-xx",  # Replace with your actual API key
        model_name="aisingapore/Gemma-SEA-LION-v3.5-8B-R",
        max_retries=3,
        timeout=180,
        temperature=0.7,
        base_url="https://api.sea-lion.ai/v1",
    )

    input_text = "abdi nyeri beteung tos 3 poe, tiasa bantuan ngubarana teu?"
    persona = "you must answer user query in sundanese"

    try:
        response = agent.analyze(persona=persona, input_text=input_text)
        logger.success(f"Agent response:\n{response}")
    except Exception as e:
        logger.error(f"Error in analysis: {e}")

    # Run async example
    # asyncio.run(main())
