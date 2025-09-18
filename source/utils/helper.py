
def format_user_prompt(prompt_template, patient_data: dict) -> str:
        """Fill user prompt template with patient data"""
        return prompt_template.format(**patient_data)