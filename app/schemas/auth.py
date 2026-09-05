from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field


class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, description="Password must be at least 8 characters.")
    full_name: str = Field(..., min_length=2, max_length=255)
    role: Optional[str] = Field("Patient", description="Patient, Doctor, Radiologist, or Admin")
    # Optional Doctor fields
    license_number: Optional[str] = None
    specialty: Optional[str] = None
    hospital_affiliation: Optional[str] = None
    # Optional Patient fields
    date_of_birth: Optional[str] = None
    gender: Optional[str] = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user_id: str
    email: str
    roles: List[str]


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8)


class EmailVerificationRequest(BaseModel):
    token: str
