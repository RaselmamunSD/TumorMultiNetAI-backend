import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, EmailStr


class RoleResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None

    class Config:
        from_attributes = True


class PatientProfileResponse(BaseModel):
    date_of_birth: Optional[datetime] = None
    gender: Optional[str] = None
    medical_record_number: Optional[str] = None

    class Config:
        from_attributes = True


class DoctorProfileResponse(BaseModel):
    license_number: str
    specialty: str
    hospital_affiliation: Optional[str] = None

    class Config:
        from_attributes = True


class UserResponse(BaseModel):
    id: uuid.UUID
    email: EmailStr
    full_name: str
    is_active: bool
    is_verified: bool
    roles: List[RoleResponse]
    patient_profile: Optional[PatientProfileResponse] = None
    doctor_profile: Optional[DoctorProfileResponse] = None
    created_at: datetime

    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    password: Optional[str] = None
