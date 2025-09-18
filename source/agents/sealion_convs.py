import asyncio
import json
import os
import sys
import re
import json_repair
from loguru import logger
from pydantic import BaseModel, Field, ValidationError
from typing import Dict, Any, List, Literal

# path_this = os.path.dirname(os.path.abspath(__file__))
# path_project = os.path.dirname(os.path.join(path_this, ".."))
# path_root = os.path.dirname(os.path.join(path_this, "../.."))
# sys.path.append(path_root)
# sys.path.append(path_project)
# sys.path.append(path_this)

from .base_agent import BaseAgent
from config import settings

class SealionConvs(BaseAgent):

    def __init__(
        self,
        agent_name: str = "Nusantara CaRas",
        multiagent_name : str ="Chatbot Agent",
        temperature: float = 0.3,
        max_retries: int = 2,
        timeout: int = 130,
        model_name: str = "",
        base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/",
        api_key: str = "",
        system_prompt: str = "",
        human_prompt: str = "",
        provider: Literal["openai", "google"]= "openai",
        max_tokens: int=2048,
        output_type: str = "json",
        extra_body: Dict[str, Any] = {},
        **kwargs,
    ) -> None:
        super().__init__(
            agent_name=agent_name,
            temperature=temperature,
            max_retries=max_retries,
            timeout=timeout,
            model_name=model_name,
            base_url=base_url,
            api_key=api_key,
            system_prompt=system_prompt,
            human_prompt=human_prompt,
            provider=provider,
            multiagent_name=multiagent_name,
            max_tokens=max_tokens,
            **kwargs,
        )
        self.max_retries = max_retries
        self.output_type = output_type
        self.muliagent_name = multiagent_name
        self.fallback_base_url = settings.MEDGEMMA_BASE_URL
        self.fallback_model_name = settings.MEDGEMMA_MODEL_NAME

    async def arun(self, **kwargs):
        logger.debug(f"Running agent {self.muliagent_name}")
        retries = 0
        logger.debug(kwargs.get("content"))
        while retries < self.max_retries:
            try:
                main = await super().aanalyze(**kwargs)
                logger.debug(main)
                if self.output_type == "str":
                    if "</think>" in main:
                        main = main.split("</think>")[-1].strip()
                    return main

                main = json_repair.repair_json(main)
                main = json.loads(main)
                if "</think>" in main.get("answer", ""):
                    main = main.split("</think>")[-1].strip()
                return main

            except (json.JSONDecodeError, ValidationError) as e:
                logger.warning(f"[Retry {retries+1}] Invalid format: {str(e)}")
                retries += 1
            except Exception as e:
                logger.exception(f"Unexpected error in SealionConvs.arun: {str(e)}")
                break

        if self.fallback_base_url and self.fallback_model_name:
            logger.warning("Primary failed. Falling back to MedGEMMA...")
            self.base_url = self.fallback_base_url
            self.model_name = self.fallback_model_name
            try:
                main = await super().aanalyze(**kwargs)

                if self.output_type == "str":
                    if "</think>" in main:
                        main = main.split("</think>")[-1].strip()
                    return main

                main = json_repair.repair_json(main)
                main = json.loads(main)

                return main
            except Exception as e:
                logger.error(f"Fallback to MedGEMMA failed: {e}")

        return None

    def run(self, content: str):
        retries = 0
        while retries < self.max_retries:
            try:
                main = super().analyze(content=content)
                main = json_repair.repair_json(main)
                main = json.loads(main)
                return main
            except (json.JSONDecodeError, ValidationError) as e:
                logger.warning(f"[Retry {retries+1}] Invalid format: {str(e)}")
                retries += 1
            except Exception as e:
                logger.exception(f"Unexpected error in SealionConvs.run: {str(e)}")
                break

        if self.fallback_agent:
            logger.warning(f"Falling back from {self.muliagent_name} to {self.fallback_agent.muliagent_name}")
            return self.fallback_agent.run(content)

        return None


if __name__ == "__main__":

    system_prompt = """
You are a medical information extraction assistant. Your task is to analyze medical conversations (which may be in Indonesian, Sundanese, or Javanese) and extract structured medical information into a standardized JSON format in English.
Instructions:

1. Read through the entire medical conversation carefully
2. Identify and extract the key medical information
3. Translate all medical terms and descriptions to English
4. Format the information according to the specified JSON structure
5. Use medical terminology appropriately in English
6. If information is not provided or mentioned as "tidak ada" (none), use empty arrays or null values as appropriate

```json
{{
  "chief_complaint": "The user's main symptom in their own words.", // string
  "history_present_illness": {{
    "onset": "Description of when and how it started.", // string
    "location": "Where the symptom is located.", // string
    "duration": "How long it lasts, constant or intermittent.", // string
    "character": "Description of the symptom's feeling (e.g., 'seperti ditekan').", // string
    "aggravating_factors": "What makes it worse.", // string
    "alleviating_factors": "What makes it better.", // string
    "radiation": "If the sensation travels elsewhere.", // string
    "timing": "When the symptom occurs (e.g., 'malam hari').", // string
    "severity": 0 // integer from 1-10
  }},
  "review_of_systems": {{
    "general": [], // array of strings (e.g., ["Tootache", "Dizzy"])
    "heent": [], // array of strings
    "respiratory": [], // array of strings
    "gastrointestinal": [], // array of strings
    "musculoskeletal": [] // array of strings
  }},
  "past_medical_history": {{
    "chronic_illnesses": [], // array of strings (e.g., ["Hypertension"])
    "past_surgeries": [], // array of strings or null
    "hospitalizations": [] // array of strings or null
  }},
  "medications_and_allergies": {{
    "current_medications": [
      {{
        "name": "Medication name", // string
        "type": "prescription_or_over_the_counter_or_herbal" // string
      }}
    ],
    "allergies": [] // array of strings
  }}
}}

You must strictly follow these rules and the JSON format above without deviation.
Return in english only without any translation

    """
    agent = SealionConvs(
        system_prompt=system_prompt,
        human_prompt="here is the user message\n{content} you must return in one json format",
        provider="openai",
        temperature=0.0,
        max_retries=2,
        api_key="",
        model_name="medgemma-27b-it",
        base_url="http://0.0.0.0:3997",
        max_tokens=2048,
        extra_body={
        "chat_template_kwargs": {
            "thinking_mode": "off",

        }
    }
    )
    content = """Assistant: Halo! Wilujeng sumping, Budi. Kula Nura, asisten medis ingkang saged mbantu panjenengan. Kados pundi kabaringipun dinten menika? (Hello! Welcome, Budi. I'm Nura, a medical assistant who can help you. How are you feeling today?) Menawi wonten keluhan ingkang saged kula bantu cathet?
budi: hi
budi: saya sakit perut sudah 3 hari, tiduran menambah saya sakit. makan bubur meredekan sakit saya
Assistant: Oh, sakit perut selama 3 hari ya? Kula nuwun, Budi. (Oh, stomach pain for 3 days? I'm sorry to hear that, Budi.) Menawi kersa nyariosaken lokasinipun sakit punika ing ngandhap sirah menapa ing sisih tengen utawi kiwa? Ugi saged dipunwedharaken karakteripun nyeri menapa tajam utawi namung mboten nyaman kemawon?
Assistant: Nyeri tajam ya, Budi. Kula ngertos. (Sharp pain, yes Budi. I understand.) Saged dipunwedharaken menawi nyeri punika wonten ing lokasi ingkang spesifik kemawon? Menawi wonten, ing pundi tepatipun? Ugi kados pundi wekdalipun nyeri punika muncul lan sirna?
budi: tajam
Assistant: Kula nyuwun agunging pangapunten, Budi. Panjenengan ngginakaken basa Jawa. (I apologize, Budi. You are using Javanese.) Menawi kersa dipunwedharaken menawi nyeri punika wonten ing lokasi ingkang spesifik kemawon? Menawi wonten, ing pundi tepatipun? Ugi kados pundi wekdalipun nyeri punika muncul lan sirna?
budi: bahasa apa yang saya gunakan?
budi: kenapa anda menjawa dalam bahasa jawa?
Assistant: Kula nyuwun agunging pangapunten, Budi. Kula namung nyoba ngrawat basa ingkang panjenengan ginakaken. Menawi panjenengan kepengin kula ngginakaken basa Indonesia kemawon, kula saged kok. (I apologize, Budi. I was just trying to match the language you are using. If you would prefer I use Indonesian instead, I can.) Saestu wonten lokasi spesifik ingkang krasa nyeri? Lan menawi dipunertosaken wekdalipun nyeri punika muncul lan sirna?
budi: jawab dalam bahasa indonesia
Assistant: Baik, Budi. Saya akan menjawab dalam bahasa Indonesia. Maaf atas kebingungan sebelumnya. Jadi, Anda merasakan sakit perut selama 3 hari ya? Sakitnya terasa tajam dan bertambah saat berbaring, serta mereda setelah makan bubur. Apakah ada lokasi spesifik di perut Anda yang terasa paling sakit? Dan bisakah Anda ceritakan bagaimana rasa sakit itu datang dan pergi?
budi: sakit itu datang ketika saya berjalan
Assistant: Oh, jadi sakitnya datang ketika Anda berjalan ya, Budi? Terima kasih sudah berbagi. Apakah rasa sakitnya menjalar ke bagian tubuh lain seperti punggung atau dada? Dan apakah ada sesuatu selain makan bubur yang bisa meredakan rasa sakit ini?
budi: tidak ada
Assistant: Baik, Budi. Jadi rasa sakitnya tidak menjalar ke bagian tubuh lain dan hanya mereda dengan makan bubur. Apakah Anda memiliki riwayat penyakit kronis seperti diabetes, hipertensi, atau penyakit jantung? Atau pernah menjalani operasi sebelumnya?
Assistant: Baik, Budi. Jadi Anda tidak memiliki riwayat penyakit kronis atau pernah menjalani operasi sebelumnya. Apakah Anda sedang mengonsumsi obat-obatan tertentu saat ini? Atau apakah Anda memiliki alergi terhadap obat-obatan atau makanan tertentu?
budi: tidak ada
budi: ya saya kadang gatal ketika minum obat paracetamol
Assistant: Baik, Budi. Jadi Anda tidak sedang mengonsumsi obat-obatan tertentu, tetapi kadang mengalami gatal setelah minum paracetamol. Apakah ada anggota keluarga Anda yang memiliki riwayat penyakit serius seperti jantung, kanker, atau diabetes? Informasi ini bisa membantu kami memahami kondisi kesehatan Anda lebih baik.
budi: tidak ada
Assistant: Baik, Budi. Jadi tidak ada anggota keluarga yang memiliki riwayat penyakit serius. Apakah Anda merokok atau mengonsumsi alkohol? Jika ya, seberapa sering?
Assistant: Baik, Budi. Jadi Anda merokok aktif tetapi tidak mengonsumsi alkohol. Apakah ada keluhan lain yang ingin Anda sampaikan? Misalnya, apakah Anda merasa lelah, demam, mual, atau muntah?
budi: ya saya merokok aktif tapi tidak minum alkohol
budi: tidak ada
Assistant: Baik, Budi. Jadi Anda merokok aktif tetapi tidak mengonsumsi alkohol dan tidak ada keluhan lain yang ingin disampaikan. Sekarang, mari kita bahas sedikit tentang gejala umum yang mungkin Anda alami selain sakit perut ini. Apakah Anda pernah mengalami gangguan tidur, perubahan berat badan yang signifikan, atau masalah pencernaan lainnya seperti diare atau sembelit?
Assistant: Baik, Budi. Jadi Anda tidak mengalami gangguan tidur, perubahan berat badan signifikan, atau masalah pencernaan lainnya. Apakah ada keluhan terkait sistem pernapasan seperti batuk atau sesak napas? Atau mungkin masalah pada sistem kemih seperti nyeri saat buang air kecil?
budi: tidak ada
Assistant: Baik, Budi. Jadi Anda tidak mengalami keluhan terkait sistem pernapasan atau kemih. Apakah ada masalah pada otot dan sendi seperti nyeri atau kekakuan? Atau mungkin ada gejala lain yang belum sempat kita bahas?
budi: tidak ada
budi: tidak ada
Assistant: Baik, Budi. Terima kasih atas semua informasinya. Jadi, untuk merangkum:
"""

    # final = asyncio.run_str(agent.arun(content=content))
    final = asyncio.run(agent.arun(content=content))
    print(final)
