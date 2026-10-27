"""
schemas.py - The shape of every JSON body the API accepts.

Pydantic checks types and limits BEFORE our code runs, so bad input
(wrong types, huge strings, unknown roles) is rejected with a clear 422 error.
"""
from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: Literal["admin", "officer", "viewer"] = "officer"


class UserUpdate(BaseModel):
    role: Optional[Literal["admin", "officer", "viewer"]] = None
    is_active: Optional[bool] = None


class PasswordChange(BaseModel):
    old_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class CameraIn(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    location: Optional[str] = Field(None, max_length=200)
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    is_active: bool = True


class ReviewRequest(BaseModel):
    decision: Literal["approved", "rejected"]
    note: Optional[str] = Field(None, max_length=300)
    plate_text: Optional[str] = Field(None, max_length=20)   # officer may correct the OCR


class ProfileUpdate(BaseModel):
    full_name: str = Field(min_length=2, max_length=100)


class AccessRequestIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    organisation: Optional[str] = Field(None, max_length=150)
    reason: Optional[str] = Field(None, max_length=400)
    requested_role: Literal["officer", "viewer"] = "officer"
    website: Optional[str] = Field(None, max_length=100)     # honeypot: hidden in the form, bots fill it


class AccessDecision(BaseModel):
    decision: Literal["approved", "rejected"]
    role: Optional[Literal["admin", "officer", "viewer"]] = None


class CitizenLookup(BaseModel):
    plate: str = Field(min_length=3, max_length=20)
    challan_no: str = Field(min_length=5, max_length=30)


class CitizenAction(BaseModel):
    token: str = Field(min_length=20, max_length=1000)


class AppealIn(CitizenAction):
    reason: str = Field(min_length=10, max_length=1000)
    contact: Optional[str] = Field(None, max_length=100)


class AppealDecision(BaseModel):
    decision: Literal["accepted", "rejected"]
    response: str = Field(min_length=3, max_length=500)


class StreamSettings(BaseModel):
    stream_url: Optional[str] = Field(None, max_length=400)
    stream_enabled: bool = False
