from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import date

class UserBase(BaseModel):
    email: EmailStr
    display_name: str
    date_of_birth: Optional[date] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    province: Optional[str] = None
    postal_code: Optional[str] = None
    gender: Optional[str] = None
    status: Optional[str] = "active"
    locale: Optional[str] = "id-ID"

class UserOut(UserBase):
    id: str

class UserUpdate(BaseModel):
    display_name: Optional[str] = None
    date_of_birth: Optional[date] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    province: Optional[str] = None
    postal_code: Optional[str] = None
    gender: Optional[str] = None
    status: Optional[str] = None
    locale: Optional[str] = None