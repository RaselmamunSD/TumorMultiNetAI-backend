import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.exceptions import AppException, UnauthorizedException
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    verify_password,
)
from app.models.user import User, PatientProfile, DoctorProfile, RefreshToken
from app.repositories.user_repo import UserRepository
from app.schemas.auth import TokenResponse, UserRegister


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_repo = UserRepository(db)

    async def register_user(self, payload: UserRegister) -> User:
        # Check if email already registered
        existing = await self.user_repo.get_by_email(payload.email)
        if existing:
            raise AppException(
                status_code=400,
                error_code="EMAIL_ALREADY_EXISTS",
                message="An account with this email address already exists.",
            )

        # Resolve role
        role_name = payload.role.capitalize() if payload.role else "Patient"
        valid_roles = ["Patient", "Doctor", "Radiologist", "Admin"]
        if role_name not in valid_roles:
            role_name = "Patient"

        role = await self.user_repo.create_role_if_not_exists(
            role_name, f"{role_name} system role"
        )

        # Create user
        user = User(
            email=payload.email.lower(),
            hashed_password=get_password_hash(payload.password),
            full_name=payload.full_name,
            is_active=True,
            is_verified=False,
            roles=[role],
        )

        # Role-specific profiles
        if role_name in ["Doctor", "Radiologist"]:
            doctor_profile = DoctorProfile(
                user=user,
                license_number=payload.license_number or f"LIC-{uuid.uuid4().hex[:8].upper()}",
                specialty=payload.specialty or ("Radiology" if role_name == "Radiologist" else "General Medicine"),
                hospital_affiliation=payload.hospital_affiliation,
            )
            user.doctor_profile = doctor_profile
        else:
            patient_profile = PatientProfile(
                user=user,
                gender=payload.gender,
                medical_record_number=f"MRN-{uuid.uuid4().hex[:8].upper()}",
            )
            user.patient_profile = patient_profile

        await self.user_repo.create(user)
        return user

    async def authenticate_user(self, email: str, password: str) -> TokenResponse:
        user = await self.user_repo.get_by_email(email)
        if not user or not verify_password(password, user.hashed_password):
            raise UnauthorizedException("Invalid email or password.")

        if not user.is_active:
            raise AppException(status_code=403, error_code="INACTIVE_USER", message="Account is deactivated.")

        roles_list = [r.name for r in user.roles]
        extra_claims = {"email": user.email, "roles": roles_list}

        access_token = create_access_token(subject=str(user.id), extra_claims=extra_claims)
        refresh_token = create_refresh_token(subject=str(user.id), extra_claims=extra_claims)

        # Persist refresh token in database
        rf_entry = RefreshToken(
            user_id=user.id,
            token=refresh_token,
            expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
            revoked=False,
        )
        await self.user_repo.save_refresh_token(rf_entry)

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user_id=str(user.id),
            email=user.email,
            roles=roles_list,
        )

    async def refresh_access_token(self, refresh_token_str: str) -> TokenResponse:
        payload = decode_token(refresh_token_str)
        if not payload or payload.get("type") != "refresh":
            raise UnauthorizedException("Invalid or expired refresh token.")

        token_entry = await self.user_repo.get_refresh_token(refresh_token_str)
        if not token_entry or token_entry.revoked:
            raise UnauthorizedException("Refresh token has been revoked or is invalid.")

        user = await self.user_repo.get_by_id_with_profiles(token_entry.user_id)
        if not user or not user.is_active:
            raise UnauthorizedException("User no longer active.")

        # Rotate refresh token
        await self.user_repo.revoke_refresh_token(refresh_token_str)

        roles_list = [r.name for r in user.roles]
        extra_claims = {"email": user.email, "roles": roles_list}

        new_access_token = create_access_token(subject=str(user.id), extra_claims=extra_claims)
        new_refresh_token = create_refresh_token(subject=str(user.id), extra_claims=extra_claims)

        new_rf_entry = RefreshToken(
            user_id=user.id,
            token=new_refresh_token,
            expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
            revoked=False,
        )
        await self.user_repo.save_refresh_token(new_rf_entry)

        return TokenResponse(
            access_token=new_access_token,
            refresh_token=new_refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user_id=str(user.id),
            email=user.email,
            roles=roles_list,
        )

    async def logout(self, refresh_token_str: Optional[str]) -> bool:
        if refresh_token_str:
            await self.user_repo.revoke_refresh_token(refresh_token_str)
        return True
