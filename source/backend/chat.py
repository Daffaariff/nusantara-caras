import os
from typing import Optional
import asyncio
import json
from loguru import logger
from datetime import date

from .tasks import process_doctor_report
from .wsocket import ws_manager
import re
from agents import SCA, SPA
from utils import get_conn, require_user, validate_uuid, decode_jwt_token
from schemas import StartChat, SendMessage

from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi import (
    APIRouter, HTTPException, Header, Depends, status,
    WebSocket, WebSocketDisconnect, BackgroundTasks
)


security = HTTPBearer()
router = APIRouter()


@router.post("/start-with-message")
async def start_chat_with_message(
    body: dict,  # {"content": "user message"}
    user_id: str = Depends(require_user)
):
    content = body.get("content", "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="Message content is required")

    conn = get_conn()
    cur = conn.cursor()
    try:
        conn.autocommit = False
        cur.execute(
            """
            INSERT INTO chat_sessions (user_id, topic, started_at)
            VALUES (%s::uuid, %s, NOW())
            RETURNING id
            """,
            (user_id, "New Chat"),
        )
        chat_id = cur.fetchone()[0]
        chat_uuid = str(chat_id)
        logger.info(f"Created chat session {chat_uuid} for user {user_id}")

        # Insert user message
        cur.execute(
            """INSERT INTO chat_messages (chat_id, sender, content)
               VALUES (%s,'user',%s) RETURNING id, created_at""",
            (chat_uuid, content),
        )
        user_msg_id, user_msg_ts = cur.fetchone()
        logger.debug(f"Saved user_msg_id={user_msg_id}")

        # Get user profile data
        cur.execute(
            "SELECT display_name, gender, date_of_birth, province FROM users WHERE id = %s::uuid",
            (user_id,),
        )
        user_row = cur.fetchone()
        display_name, gender, dob, province = user_row if user_row else ("User", None, None, None)

        age = None
        if dob:
            today = date.today()
            age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

        history_text = f"{display_name}: {content}\nAssistant:"

        try:
            sca_output = await SCA.arun(
                content=history_text,
                display_name=display_name,
                age=age,
                gender=gender,
                province=province,
            )
            reply = sca_output["answer"]
            report = sca_output["report_done"]
            translation = sca_output['translation']

            if translation and f"({translation})" in reply:
                reply = reply.replace(f"({translation})", "").strip()
            else:
                reply = re.sub(r"\([^)]*\)", "", reply).strip()


        except Exception as e:
            logger.error(f"LLM Intake: {str(e)}")
            conn.rollback()
            raise HTTPException(status_code=500, detail="Failed to get response from Intake LLM")

        # If parser/doctor report is needed
        if report:
            try:
                parsed = await SPA.arun(content=history_text)
                parsed["gender"] = gender
                parsed["age"] = age
                parsed["province"] = province
                logger.debug(f"Parsed output: {parsed}")
            except Exception as e:
                logger.error(f"LLM intake Parser: {str(e)}")
                raise HTTPException(status_code=500, detail="Failed to get response from Parser intake LLM")

        # Insert bot message
        cur.execute(
            """INSERT INTO chat_messages (chat_id, sender, content)
               VALUES (%s,'bot',%s) RETURNING id, created_at""",
            (chat_uuid, reply),
        )
        bot_msg_id, bot_msg_ts = cur.fetchone()

        conn.commit()

        # Construct response
        messages = [
            {"id": str(user_msg_id), "sender": "user", "content": content, "created_at": user_msg_ts},
            {"id": str(bot_msg_id), "sender": "bot", "content": reply, "created_at": bot_msg_ts},
        ]

        return {"chat_id": chat_uuid, "messages": messages}

    except Exception as e:
        conn.rollback()
        logger.error(f"Error in start_chat_with_message: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create chat and send message")
    finally:
        cur.close()
        conn.close()

@router.post("/start")
async def start_chat(user_id: str = Depends(require_user)):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO chat_sessions (user_id, topic, started_at)
            VALUES (%s::uuid, %s, NOW())
            RETURNING id
            """,
            (user_id, "New Chat"),
        )
        chat_id = cur.fetchone()[0]
        conn.commit()
        logger.info(f"New empty chat session {chat_id} created for user {user_id}")
        return {"chat_id": str(chat_id), "messages": []}
    except Exception as e:
        logger.error(f"Error creating empty chat session: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create chat session")
    finally:
        cur.close()
        conn.close()


@router.post("/send")
async def send_message(
    body: SendMessage,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(require_user),
):
    chat_uuid = str(body.chat_id)
    logger.debug(f"[SEND] user_id={user_id} chat_id={chat_uuid} content={body.content!r}")

    try:
        result = await process_chat_message_logic(user_id, chat_uuid, body.content)

        if ws_manager.has_connections(chat_uuid):
            await ws_manager.broadcast_to_chat(chat_uuid, {
                "type": "new_message",
                "message": {
                    "id": result["user_message"]["id"],
                    "sender": "user",
                    "content": result["user_message"]["content"],
                    "created_at": result["user_message"]["created_at"].isoformat()
                }
            })

            await ws_manager.broadcast_to_chat(chat_uuid, {
                "type": "new_message",
                "message": {
                    "id": result["bot_message"]["id"],
                    "sender": "bot",
                    "content": result["bot_message"]["content"],
                    "created_at": result["bot_message"]["created_at"].isoformat()
                }
            })

        # Handle doctor report
        if result["needs_doctor_report"]:
            if ws_manager.has_connections(chat_uuid):
                # WebSocket clients get real-time processing
                background_tasks.add_task(
                    process_doctor_report_with_websocket_notification,
                    user_id, chat_uuid, result["history_text"]
                )
                reply = result["bot_message"]["content"]  # Keep original response
            else:
                # REST-only clients get the old behavior
                background_tasks.add_task(process_doctor_report, user_id, chat_uuid, result["history_text"])
                reply = result["bot_message"]["content"]
        else:
            reply = result["bot_message"]["content"]

        return {
            "reply": reply,
            "user_msg_id": result["user_message"]["id"],
            "bot_msg_id": result["bot_message"]["id"]
        }

    except Exception as e:
        logger.error(f"[SEND] Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")



@router.get("/list")
def list_chats(user_id: str = Depends(require_user)):
    conn = get_conn(); cur = conn.cursor()
    try:
        cur.execute("""
            DELETE FROM chat_sessions
            WHERE user_id=%s::uuid
              AND id NOT IN (SELECT DISTINCT chat_id FROM chat_messages)
              AND started_at < NOW() - INTERVAL '5 minutes'
        """, (user_id,))

        logger.debug(f"[LIST] Deleted {cur.rowcount} old empty sessions for user_id={user_id}")
        conn.commit()

        # fetch sessions
        cur.execute("""
            SELECT id, topic, started_at, ended_at
            FROM chat_sessions
            WHERE user_id=%s::uuid
            ORDER BY started_at DESC
        """, (user_id,))
        rows = cur.fetchall()
        return {"chats": [
            {
                "chat_id": str(r[0]),
                "topic": r[1] or "Untitled chat",
                "created_at": r[2],
                "updated_at": r[3]
            }
            for r in rows
        ]}
    finally:
        cur.close(); conn.close()

@router.get("/{chat_id}")
def get_messages(chat_id: str, user_id: str = Depends(require_user)):
    validate_uuid(chat_id)
    logger.debug(f"[GET] user_id={user_id} requesting chat_id={chat_id}")
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT 1 FROM chat_sessions WHERE id=%s::uuid AND user_id=%s::uuid",
            (chat_id, user_id),
        )
        if not cur.fetchone():
            logger.warning(f"[GET] Forbidden or Not Found: User {user_id} tried to access chat {chat_id}")
            raise HTTPException(status_code=404, detail="Chat not found")

        cur.execute("""SELECT id, sender, content, created_at
                       FROM chat_messages
                       WHERE chat_id=%s ORDER BY created_at ASC""",
                    (chat_id,))

        messages = []
        for row in cur.fetchall():
            messages.append({
                "id": str(row[0]),
                "sender": row[1],
                "content": row[2],
                "created_at": row[3]
            })

        logger.debug(f"[GET] Retrieved and processed {len(messages)} messages for chat_id={chat_id}")
        return {"messages": messages}
    finally:
        cur.close()
        conn.close()

@router.delete("/clear")
def clear_user_chats(user_id: str = Depends(require_user)):
    conn = get_conn()
    cur = conn.cursor()
    try:
        logger.debug(f"[CLEAR] user_id={user_id} requested chat reset")

        cur.execute("""
            DELETE FROM chat_messages
            WHERE chat_id IN (
                SELECT id FROM chat_sessions WHERE user_id = %s::uuid
            )
        """, (user_id,))
        logger.debug(f"[CLEAR] Deleted {cur.rowcount} messages for user_id={user_id}")

        cur.execute("DELETE FROM chat_sessions WHERE user_id = %s::uuid", (user_id,))
        logger.debug(f"[CLEAR] Deleted {cur.rowcount} chats for user_id={user_id}")

        conn.commit()
        return {"status": "ok", "msg": "Chat history cleared for this user"}
    finally:
        cur.close()
        conn.close()

async def verify_chat_access(user_id: str, chat_id: str) -> bool:
    """Verify that user has access to the specified chat"""
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT 1 FROM chat_sessions WHERE id=%s::uuid AND user_id=%s::uuid",
            (chat_id, user_id),
        )
        return bool(cur.fetchone())
    except Exception as e:
        logger.error(f"Error verifying chat access: {str(e)}")
        return False
    finally:
        cur.close()
        conn.close()

@router.websocket("/ws/{chat_id}")
async def websocket_endpoint(websocket: WebSocket, chat_id: str):
    """Enhanced WebSocket endpoint with JWT authentication"""
    validate_uuid(chat_id)

    # Try to get user_id from connection
    user_id = await get_user_from_websocket(websocket)

    # Connect to WebSocket manager
    await ws_manager.connect(chat_id, websocket, user_id)

    # If no authentication, inform client they need to authenticate
    if not user_id:
        try:
            await websocket.send_json({
                "type": "auth_required",
                "message": "Please authenticate by sending your token"
            })
        except:
            # Connection might be closed
            pass

    try:
        while True:
            try:
                raw_data = await websocket.receive_text()
                data = json.loads(raw_data)
            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "message": "Invalid JSON format"
                })
                continue
            except Exception as e:
                logger.error(f"WebSocket receive error: {str(e)}")
                break

            message_type = data.get("type")

            # Handle authentication first
            if message_type == "auth":
                new_user_id = await handle_websocket_auth(data)
                if new_user_id:
                    # Update connection with authenticated user
                    ws_manager.disconnect(chat_id, websocket, user_id)
                    user_id = new_user_id
                    await ws_manager.connect(chat_id, websocket, user_id)

                    # Verify user has access to this chat
                    if await verify_chat_access(user_id, chat_id):
                        await websocket.send_json({
                            "type": "auth_success",
                            "message": "Authentication successful"
                        })
                    else:
                        await websocket.send_json({
                            "type": "auth_error",
                            "message": "You don't have access to this chat"
                        })
                        break
                else:
                    await websocket.send_json({
                        "type": "auth_error",
                        "message": "Authentication failed - invalid token"
                    })
                continue

            # All other message types require authentication
            if not user_id:
                await websocket.send_json({
                    "type": "auth_required",
                    "message": "Please authenticate first"
                })
                continue

            # Handle authenticated messages
            if message_type == "send_message":
                await handle_websocket_message(websocket, chat_id, data, user_id)
            elif message_type == "typing":
                await handle_typing_indicator(chat_id, data, user_id)
            elif message_type == "ping":
                await websocket.send_json({"type": "pong"})
            else:
                await websocket.send_json({
                    "type": "error",
                    "message": f"Unknown message type: {message_type}"
                })

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected from chat {chat_id} for user {user_id}")
    except Exception as e:
        logger.error(f"WebSocket error in chat {chat_id}: {str(e)}")
    finally:
        ws_manager.disconnect(chat_id, websocket, user_id)

locks = {}

# define this once, outside the function
locks: dict[str, asyncio.Lock] = {}

async def process_chat_message_logic(user_id: str, chat_uuid: str, content: str):
    conn = get_conn()
    cur = conn.cursor()
    lock = locks.setdefault(chat_uuid, asyncio.Lock())

    async with lock:
        try:
            # Ownership check
            cur.execute(
                "SELECT 1 FROM chat_sessions WHERE id=%s::uuid AND user_id=%s::uuid",
                (chat_uuid, user_id),
            )
            if not cur.fetchone():
                raise ValueError("Chat not found or access denied")

            # Insert user message + commit early
            cur.execute(
                """INSERT INTO chat_messages (chat_id, sender, content)
                   VALUES (%s,'user',%s) RETURNING id, created_at""",
                (chat_uuid, content),
            )
            user_msg_id, user_msg_ts = cur.fetchone()
            conn.commit()

            # Fetch chat history (now includes the latest user message)
            cur.execute("""
                SELECT cm.sender, cm.content, u.display_name
                FROM chat_messages cm
                JOIN chat_sessions cs ON cm.chat_id = cs.id
                JOIN users u ON cs.user_id = u.id
                WHERE cm.chat_id = %s
                ORDER BY cm.created_at ASC
            """, (chat_uuid,))
            history = cur.fetchall()
            history_text = ""
            for sender, msg_content, display_name in history:
                prefix = display_name if sender == "user" else "Assistant"
                history_text += f"{prefix}: {msg_content}\n"

            # Fetch user profile
            cur.execute(
                "SELECT display_name, gender, date_of_birth, province FROM users WHERE id=%s::uuid",
                (user_id,),
            )
            user_row = cur.fetchone()
            display_name, gender, dob, province = user_row if user_row else ("User", None, None, None)

            # Compute age
            age = None
            if dob:
                today = date.today()
                age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

            # Get LLM response
            sca_output = await SCA.arun(
                content=history_text,
                display_name=display_name,
                age=age,
                gender=gender,
                province=province,
            )
            reply = sca_output["answer"]
            report = sca_output['report_done']
            translation = sca_output['translation']

            if translation and f"({translation})" in reply:
                reply = reply.replace(f"({translation})", "").strip()
            else:
                reply = re.sub(r"\([^)]*\)", "", reply).strip()

            # Dedup safeguard
            if history and reply.strip() == history[-1][1].strip():
                reply += " (sanes pangulangan, punten diparios deui)"

            needs_doctor_report = bool(report)

            # Insert bot reply
            cur.execute(
                """INSERT INTO chat_messages (chat_id, sender, content)
                   VALUES (%s,'bot',%s) RETURNING id, created_at""",
                (chat_uuid, reply),
            )
            bot_msg_id, bot_msg_ts = cur.fetchone()
            conn.commit()

            return {
                "user_message": {
                    "id": str(user_msg_id),
                    "sender": "user",
                    "content": content,
                    "created_at": user_msg_ts
                },
                "bot_message": {
                    "id": str(bot_msg_id),
                    "sender": "bot",
                    "content": reply,
                    "created_at": bot_msg_ts
                },
                "needs_doctor_report": needs_doctor_report,
                "history_text": history_text
            }

        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cur.close()
            conn.close()


async def get_user_from_websocket(websocket: WebSocket) -> Optional[str]:
    """Extract user_id from WebSocket connection via query param or header"""
    query_params = dict(websocket.query_params)
    token = query_params.get("token")

    if token:
        user_id = decode_jwt_token(token)
        logger.debug(f"[get_user_from_websocket] token={token} -> user_id={user_id}")
        if user_id:
            return user_id

    # fallback to Authorization header
    auth_header = websocket.headers.get("authorization")
    if auth_header:
        user_id = decode_jwt_token(auth_header)
        if user_id:
            return user_id

    return None

async def handle_websocket_message(websocket: WebSocket, chat_id: str, data: dict, user_id: str):
    """Handle incoming chat message via WebSocket (now requires user_id)"""
    content = data.get("content", "").strip()
    if not content:
        await websocket.send_json({
            "type": "error",
            "message": "Message content is required"
        })
        return

    try:
        # Verify user still has access
        if not await verify_chat_access(user_id, chat_id):
            await websocket.send_json({
                "type": "error",
                "message": "Access denied to this chat"
            })
            return

        # Send typing indicator
        await ws_manager.broadcast_to_chat(chat_id, {
            "type": "typing",
            "sender": "bot",
            "is_typing": True
        }, exclude_websocket=websocket)

        # Process message ONCE
        result = await process_chat_message_logic(user_id, chat_id, content)

        # Stop typing indicator
        await ws_manager.broadcast_to_chat(chat_id, {
            "type": "typing",
            "sender": "bot",
            "is_typing": False
        })

        # Send confirmation + broadcast
        await websocket.send_json({
            "type": "message_sent",
            "message": {
                "id": result["user_message"]["id"],
                "sender": "user",
                "content": result["user_message"]["content"],
                "created_at": result["user_message"]["created_at"].isoformat()
            }
        })

        await ws_manager.broadcast_to_chat(chat_id, {
            "type": "new_message",
            "message": {
                "id": result["user_message"]["id"],
                "sender": "user",
                "content": result["user_message"]["content"],
                "created_at": result["user_message"]["created_at"].isoformat()
            }
        }, exclude_websocket=websocket)

        await ws_manager.broadcast_to_chat(chat_id, {
            "type": "new_message",
            "message": {
                "id": result["bot_message"]["id"],
                "sender": "bot",
                "content": result["bot_message"]["content"],
                "created_at": result["bot_message"]["created_at"].isoformat()
            }
        })

        # Doctor report
        if result["needs_doctor_report"]:
            asyncio.create_task(
                process_doctor_report_with_websocket_notification(
                    user_id, chat_id, result["history_text"]
                )
            )
            await ws_manager.send_to_user(user_id, chat_id, {
                "type": "doctor_report_processing",
                "message": "Your data is being processed by our doctor. You'll be notified when ready."
            })

    except Exception as e:
        logger.error(f"Error processing WebSocket message: {str(e)}")
        await websocket.send_json({
            "type": "error",
            "message": "Failed to process message"
        })


async def handle_typing_indicator(chat_id: str, data: dict, user_id: Optional[str]):
    """Handle typing indicator"""
    if not user_id:
        return

    await ws_manager.broadcast_to_chat(chat_id, {
        "type": "typing",
        "sender": "user",
        "user_id": user_id,
        "is_typing": data.get("is_typing", False)
    })

async def handle_websocket_auth(data: dict) -> Optional[str]:
    """Handle WebSocket authentication via message"""
    token = data.get("token")
    if not token:
        logger.warning("WebSocket auth message missing token")
        return None

    user_id = decode_jwt_token(token)
    if user_id:
        logger.info(f"WebSocket authenticated via message for user: {user_id}")
        return user_id
    else:
        logger.warning("WebSocket auth failed - invalid token")
        return None

async def process_doctor_report_with_websocket_notification(user_id: str, chat_id: str, history_text: str):
    """Process doctor report and notify via WebSocket when complete"""
    try:

        await process_doctor_report(user_id, chat_id, history_text)

        await ws_manager.send_to_user(user_id, chat_id, {
            "type": "doctor_report_ready",
            "message": "Your doctor report is now available.",
            "action": "reload_chat"
        })

        logger.info(f"Doctor report completed and user {user_id} notified via WebSocket")

    except Exception as e:
        logger.error(f"Doctor report processing error: {str(e)}")
        await ws_manager.send_to_user(user_id, chat_id, {
            "type": "doctor_report_error",
            "message": "Failed to process doctor report. Please try again."
        })

