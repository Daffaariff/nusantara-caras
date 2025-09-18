import uuid
from uuid import UUID
from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from .db import get_conn
from loguru import logger
import jwt
from datetime import datetime, timezone
from config import settings
from typing import Optional

security = HTTPBearer()

def require_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> UUID:
    token = credentials.credentials
    user_id = decode_jwt_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return user_id


def validate_uuid(chat_id: str):
    try:
        uuid.UUID(chat_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid chat_id")

def decode_jwt_token(token: str) -> Optional[str]:
    """Decode either session UUID token or JWT token, return user_id"""
    if token.startswith("Bearer "):
        token = token[7:]

    # Case 1: session token (UUID-like)
    try:
        uuid.UUID(token)  # ensure it's valid UUID format
        conn = get_conn(); cur = conn.cursor()
        try:
            cur.execute(
                """
                SELECT user_id
                FROM user_sessions
                WHERE session_token_hash = digest(%s, 'sha256')
                  AND revoked_at IS NULL
                  AND expires_at > now()
                LIMIT 1
                """,
                (token,),
            )
            row = cur.fetchone()
            if row:
                logger.debug(f"[decode_jwt_token] Found user_id={row[0]} for session token")
                return str(row[0])   # ✅ return immediately
        finally:
            cur.close(); conn.close()
    except ValueError:
        # not a UUID, fall through to JWT
        pass

    # Case 2: JWT
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        user_id = payload.get("user_id") or payload.get("sub")
        logger.debug(f"[decode_jwt_token] JWT decoded -> {user_id}")
        return str(user_id)
    except Exception as e:
        logger.debug(f"[decode_jwt_token] Failed -> {e}")
        return None
