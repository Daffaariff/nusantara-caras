from .sealion_convs import SealionConvs
from prompts import (
    FINAL_REPORT_PROMPT,
    PARSER_INTAKE_PROMPT,
    DOCTOR_SYSTEM_PROMPT,
    TANDLANG_DETECTOR_PROMPT,
    INTAKE_PROMPT as SYSTEM_PROMPT_LLM_CONVS
)
from config import settings

SCA = SealionConvs(
    system_prompt=SYSTEM_PROMPT_LLM_CONVS,
    multiagent_name="intake_agent",
    human_prompt="\n{content} \n",
    provider="openai",
    temperature=0.1,
    max_retries=2,
    api_key=settings.SEALION_API_KEY,
    model_name=settings.SEALION_MODEL_NAME,
    base_url=settings.SEALION_BASE_URL,
    max_tokens=8092,
)

SPA = SealionConvs(
    system_prompt=PARSER_INTAKE_PROMPT,
    multiagent_name="parser_agent",
    human_prompt="here is the user message\n{content} you strictly must return a json format only",
    provider="openai",
    temperature=0.3,
    max_retries=2,
    api_key=settings.SEALION_API_KEY,
    model_name=settings.SEALION_MODEL_NAME,
    base_url=settings.SEALION_BASE_URL,
    extra_body={
        "chat_template_kwargs": {
            "thinking_mode": "off"
        }
    },
    max_tokens=4096,
)

MDA = SealionConvs(
    system_prompt=DOCTOR_SYSTEM_PROMPT,
    multiagent_name="parser_agent",
    human_prompt="here is the user message\n{content} you strictly must return a json format only",
    provider="openai",
    temperature=0.3,
    max_retries=2,
    api_key=settings.SEALION_API_KEY,
    model_name=settings.MEDGEMMA_MODEL_NAME,
    base_url=settings.MEDGEMMA_BASE_URL,
    extra_body={
        "chat_template_kwargs": {
            "thinking_mode": "off"
        }
    },
    max_tokens=4096,
)

FRA = SealionConvs(
    system_prompt=FINAL_REPORT_PROMPT,
    human_prompt="here is the user message\n{content}",
    provider="openai",
    temperature=0.3,
    output_type="str",
    max_retries=2,
    api_key=settings.SEALION_API_KEY,
    model_name=settings.SEALION_MODEL_NAME,
    base_url=settings.SEALION_BASE_URL,
    max_tokens=8192,
)

LDA = SealionConvs(
    system_prompt=TANDLANG_DETECTOR_PROMPT,
    human_prompt="here is the user message\n{content}",
    provider="openai",
    temperature=0.3,
    max_retries=2,
    api_key=settings.SEALION_API_KEY,
    model_name=settings.SEALION_MODEL_NAME,
    base_url=settings.SEALION_BASE_URL,
    max_tokens=8192,
)
