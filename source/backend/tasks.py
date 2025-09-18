import asyncio
from datetime import date
from utils import get_conn, format_user_prompt
from loguru import logger
from .wsocket import ws_manager
from agents import MDA, SPA, FRA, LDA
from tools import NearestFacilityFinder
from prompts import DOCTOR_PROMPT_TEMPLATE, FINAL_REPORT_TEMPLATE

nearest_place = NearestFacilityFinder()

map_lang = {
    "id-id" : "bahasa indonesia",
    "id-su" : "sundanese",
    "id-jv" : "javanese"
}

async def process_doctor_report(user_id: str, chat_uuid: str, history_text: str):
    conn = get_conn(); cur = conn.cursor()
    try:
        cur.execute("SELECT gender, date_of_birth, address_line1, city, display_name FROM users WHERE id=%s::uuid", (user_id,))
        user_data = cur.fetchone()
        gender, dob, address, city, display_name = user_data if user_data else (None, None, None, None, None)
        age = None
        if dob:
            today = date.today()
            age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

        address_combined = f"{address}, {city}"

        apotek, hospital, tandlang, parsed = await asyncio.gather(
            nearest_place.search(facility_type="apotek", radius_m="16000", limit=2, address=address_combined),
            nearest_place.search(facility_type="hospital", radius_m="16000", limit=2, address=address_combined),
            LDA.arun(content=history_text, display_name=display_name),
            SPA.arun(content=history_text)
        )

        if apotek or hospital:
            parts = []
            if apotek:
                parts.append("\n".join(apotek).strip())
            if hospital:
                parts.append("\n".join(hospital).strip())
            combined = "\n".join(parts)
        else:
            combined = "apotek atau rumah sakit terdekat tidak dapat ditemukan"

        title = tandlang.get("title", None)
        language = tandlang.get("language", None)
        lang = map_lang.get(language, "unknown")

        parsed["gender"], parsed["age"] = gender, age

        doctor_prompt = format_user_prompt(DOCTOR_PROMPT_TEMPLATE, parsed)
        doctor_process = await MDA.arun(content=doctor_prompt)

        doctor_process['display_name'], doctor_process['lang'], doctor_process['hospital'] = display_name, lang, combined
        final_report_prompt = format_user_prompt(FINAL_REPORT_TEMPLATE, doctor_process)
        final_report = await FRA.arun(content=final_report_prompt)

        cur.execute("""INSERT INTO chat_messages (chat_id, sender, content)
                       VALUES (%s,'bot',%s)""",
                    (chat_uuid, final_report))
        conn.commit()

        await ws_manager.broadcast_to_chat(chat_uuid, {
            "chat_id": chat_uuid,
            "sender": "bot",
            "content": final_report
        })

        logger.info(f"Inserted + pushed doctor result for chat {chat_uuid}")
    except Exception as e:
        logger.error(f"Doctor pipeline failed: {str(e)}")
    finally:
        cur.close(); conn.close()
