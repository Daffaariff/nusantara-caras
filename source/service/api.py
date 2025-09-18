import os
import json
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
from litellm import completion


class MedicalDiagnosticAssistant:
    def __init__(self, env_path: str = "/home/ec2-user/projects/nusantara-caras/source/.env"):
        load_dotenv(dotenv_path=env_path)
        os.environ["AWS_ACCESS_KEY_ID"] = os.getenv("AWS_ACCESS_KEY_ID", "")
        os.environ["AWS_SECRET_ACCESS_KEY"] = os.getenv("AWS_SECRET_ACCESS_KEY", "")
        os.environ["AWS_REGION_NAME"] = os.getenv("AWS_REGION_NAME", "us-west-2")
        os.environ["AWS_SESSION_TOKEN"] = os.getenv("AWS_SESSION_TOKEN", "")

        self.system_prompt = os.getenv("SYSTEM_PROMPT", "You are a helpful assistant specialized in healthcare.")
        self.user_prompt_template = os.getenv("USER_PROMPT_TEMPLATE", "Patient complaint: {chief_complaint}")

        self.model = os.getenv("SAGEMAKER_MODEL", "sagemaker/medgemma-27b-it-250908-1209")

    def format_user_prompt(self, patient_data: dict) -> str:
        """Fill user prompt template with patient data"""
        return self.user_prompt_template.format(**patient_data)

    def get_diagnosis(self, patient_data: dict) -> dict:
        user_prompt = self.format_user_prompt(patient_data)

        try:
            response = completion(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,
                max_tokens=512
            )
            result = response["choices"][0]["message"]["content"]

            try:
                return json.loads(result)  # if model outputs JSON
            except json.JSONDecodeError:
                return {"raw_output": result}

        except Exception as e:
            raise RuntimeError(f"SageMaker request failed: {str(e)}")


app = FastAPI(title="Medical Diagnostic API (SageMaker)")

assistant = MedicalDiagnosticAssistant()


class PatientData(BaseModel):
    chief_complaint: str
    onset: str
    location: str
    duration: str
    character: str
    aggravating_factors: str
    alleviating_factors: str
    radiation: str
    timing: str
    severity: str


@app.post("/diagnosis")
def get_diagnosis(patient: PatientData):
    try:
        result = assistant.get_diagnosis(patient.dict())
        return {"success": True, "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))