DOCTOR_PROMPT_TEMPLATE = """Patient data:
- Age: {age}
- Gender : {gender}
- Chief Complaint: {chief_complaint}
- history of present illness: {history_present_illness}
- review of systems: {review_of_systems}
- Past Medical History: {past_medical_history}
- Medcation: {medications_and_allergies[current_medications]}
- Allergies: {medications_and_allergies[allergies]}

Please provide the complete output in the required JSON format."""

FINAL_REPORT_TEMPLATE = """
- Diagnosis: {diagnosis}
- History and Examination Findings: {history_and_examination_findings}
- Investigation Plan: {investigation_plan}
- Management Plan: {management_plan}
- Prognosis: {prognosis}
- Doctor’s Prescription: {doctors_prescription}
- Patient Summary: {summary}
"""