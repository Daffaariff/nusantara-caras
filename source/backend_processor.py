import os
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

class MedicalDiagnosticAssistant:
    def __init__(self):
        # Load environment variables from the given path

        self.api_key = os.getenv("OPENAI_API_KEY")
        self.base_url = os.getenv("OPENAI_BASE_URL")
        self.system_prompt = os.getenv("SYSTEM_PROMPT")
        self.user_prompt_template = os.getenv("USER_PROMPT_TEMPLATE")

        # Initialize OpenAI client
        self.client = OpenAI(base_url=self.base_url, api_key=self.api_key)

    def format_user_prompt(self, patient_data: dict) -> str:
        """Fill user prompt template with patient data"""
        return self.user_prompt_template.format(**patient_data)

    def get_diagnosis(self, patient_data: dict, model: str = "gpt-4o-mini") -> str:
        """Send request to OpenAI and return diagnosis JSON"""
        user_prompt = self.format_user_prompt(patient_data)

        response = self.client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_prompt},
            ]
        )
        return response.choices[0].message.content

    def save_result(self, result: str, save_path: str = "/Users/daffaarifadilah/multiagent/sea-lionn/nusantara-caras/source/output/result.json"):
        """Save the diagnosis result to a JSON file"""
        try:
            # Try to ensure it's valid JSON before saving
            parsed = json.loads(result)
        except json.JSONDecodeError:
            # If model returns invalid JSON, just save raw string
            parsed = {"raw_output": result}

        os.makedirs(os.path.dirname(save_path), exist_ok=True)

        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(parsed, f, ensure_ascii=False, indent=4)

        print(f"✅ Result saved to {save_path}")


if __name__ == "__main__":
    # Example patient data
    patient_data = {
      "chief_complaint": "Toothache",
      "onset": "3 days ago upon waking",
      "location": "Backteeth",
      "duration": "Intermittent, lasting minutes to hours",
      "character": "Like being pressed with pulsating sensation",
      "aggravating_factors": "cold water",
      "alleviating_factors": "warm water",
      "radiation": "None",
      "timing": "Worse in the morning",
      "severity": 6
    }

    assistant = MedicalDiagnosticAssistant()
    result = assistant.get_diagnosis(patient_data)
    assistant.save_result(result)   # save to result.json
