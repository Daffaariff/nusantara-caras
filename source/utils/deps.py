import uuid
from uuid import UUID
from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from .db import get_conn
from loguru import logger

security = HTTPBearer()

def require_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> UUID:
    token = credentials.credentials
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
        logger.debug(f"_require_user: token={token}, row={row}")
        if not row:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        return row[0]  # psycopg2 already returns a UUID
    finally:
        cur.close(); conn.close()

def validate_uuid(chat_id: str):
    try:
        uuid.UUID(chat_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid chat_id")