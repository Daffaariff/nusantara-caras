from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr
from passlib.hash import bcrypt
from datetime import datetime, timedelta, date
import uuid
from utils import get_conn
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from utils import require_user
from schemas import Signup, Login

security = HTTPBearer()

router = APIRouter()

def _norm_email(s: str) -> str:
    return s.strip().lower()

def _create_session(user_id: str) -> str:
    conn = get_conn(); cur = conn.cursor()
    try:
        token = str(uuid.uuid4())
        expires_at = datetime.now() + timedelta(days=7)
        cur.execute(
            "INSERT INTO user_sessions (user_id, session_token_hash, expires_at) "
            "VALUES (%s, digest(%s, 'sha256'), %s)",
            (user_id, token, expires_at)
        )
        conn.commit()
        return token
    finally:
        cur.close(); conn.close()

@router.post("/login")
def login(data: Login):
    email = _norm_email(data.email)
    conn = get_conn(); cur = conn.cursor()
    try:
        # find user
        cur.execute("SELECT id, password_hash, status FROM users WHERE email=%s", (email,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=401, detail="Invalid email or password")

        user_id, pwd_hash, status = row
        if status != "active":
            raise HTTPException(status_code=403, detail="Account is not active")

        # verify password
        if not bcrypt.verify(data.password, pwd_hash):
            raise HTTPException(status_code=401, detail="Invalid email or password")

        # create session
        token = _create_session(user_id)
        return {"session_token": token}
    finally:
        cur.close(); conn.close()


@router.post("/signup")
def signup(data: Signup):
    email = _norm_email(data.email)
    conn = get_conn(); cur = conn.cursor()
    try:
        # unique email
        cur.execute("SELECT 1 FROM users WHERE email=%s", (email,))
        if cur.fetchone():
            raise HTTPException(status_code=400, detail="Email already exists")

        # create user with profile fields
        pwd_hash = bcrypt.hash(data.password)
        cur.execute(
            """
            INSERT INTO users (
              email, display_name, password_hash, status, locale,
              date_of_birth, address_line1, address_line2, city, province, postal_code, gender
            )
            VALUES (%s, %s, %s, 'active', 'id-ID',
                    %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                email, data.display_name, pwd_hash,
                data.date_of_birth, data.address_line1, data.address_line2,
                data.city, data.province, data.postal_code, data.gender
            )
        )
        user_id = cur.fetchone()[0]
        conn.commit()
        return {"session_token": _create_session(user_id)}
    except HTTPException:
        raise
    except Exception:
        conn.rollback()
        raise HTTPException(status_code=500, detail="Failed to create account")
    finally:
        cur.close(); conn.close()


@router.get("/me")
def me(user_id: str = Depends(require_user)):
    conn = get_conn(); cur = conn.cursor()
    try:
        cur.execute(
            """SELECT id, email, display_name, date_of_birth, city, province, gender
               FROM users WHERE id=%s""",
            (user_id,)
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="User not found")

        return {
            "id": str(row[0]),
            "email": row[1],
            "display_name": row[2],
            "date_of_birth": row[3],
            "city": row[4],
            "province": row[5],
            "gender": row[6],
        }
    finally:
        cur.close(); conn.close()
