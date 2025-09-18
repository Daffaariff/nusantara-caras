from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import date

class Signup(BaseModel):
    email: EmailStr
    display_name: str
    password: str
    date_of_birth: date
    address_line1: str
    address_line2: str | None = None
    city: str
    province: str
    postal_code: str
    gender: str

class Login(BaseModel):
    email: EmailStr
    password: str