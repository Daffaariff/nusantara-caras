# backend/users.py
from fastapi import APIRouter, HTTPException, Depends
from typing import Optional, List
from utils import get_conn, get_cursor, require_user
from schemas import UserOut, UserUpdate

router = APIRouter()

# --------- endpoints ------------------------------------------------------
@router.get("/", response_model=List[UserOut])
def list_users(user_id: str = Depends(require_user)):
    conn = get_conn(); cur = get_cursor(conn)
    try:
        cur.execute("SELECT * FROM users ORDER BY created_at DESC")
        return cur.fetchall()
    finally:
        cur.close(); conn.close()

@router.get("/{user_id}", response_model=UserOut)
def get_user(user_id: str, _: str = Depends(require_user)):
    conn = get_conn(); cur = get_cursor(conn)
    try:
        cur.execute("SELECT * FROM users WHERE id=%s", (user_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="User not found")
        return row
    finally:
        cur.close(); conn.close()

@router.put("/{user_id}", response_model=UserOut)
def update_user(user_id: str, data: UserUpdate, _: str = Depends(require_user)):
    conn = get_conn(); cur = conn.cursor()
    try:
        fields = []
        values = []
        for k, v in data.dict(exclude_unset=True).items():
            fields.append(f"{k}=%s")
            values.append(v)
        if not fields:
            raise HTTPException(status_code=400, detail="No fields to update")

        query = f"UPDATE users SET {', '.join(fields)}, updated_at=now() WHERE id=%s RETURNING *"
        values.append(user_id)
        cur.execute(query, tuple(values))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="User not found")
        conn.commit()
        return row
    finally:
        cur.close(); conn.close()

@router.delete("/{user_id}")
def delete_user(user_id: str, _: str = Depends(require_user)):
    conn = get_conn(); cur = conn.cursor()
    try:
        cur.execute("DELETE FROM users WHERE id=%s RETURNING id", (user_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="User not found")
        conn.commit()
        return {"deleted_user_id": str(row[0])}
    finally:
        cur.close(); conn.close()
