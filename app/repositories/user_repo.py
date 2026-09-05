import uuid
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.user import User, Role, PatientProfile, DoctorProfile, RefreshToken
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    def __init__(self, db: AsyncSession):
        super().__init__(User, db)

    async def get_by_email(self, email: str) -> Optional[User]:
        query = (
            select(User)
            .where(User.email == email.lower())
            .options(
                selectinload(User.roles),
                selectinload(User.patient_profile),
                selectinload(User.doctor_profile),
            )
        )
        result = await self.db.execute(query)
        return result.scalars().first()

    async def get_by_id_with_profiles(self, user_id: uuid.UUID) -> Optional[User]:
        query = (
            select(User)
            .where(User.id == user_id)
            .options(
                selectinload(User.roles),
                selectinload(User.patient_profile),
                selectinload(User.doctor_profile),
            )
        )
        result = await self.db.execute(query)
        return result.scalars().first()

    async def get_role_by_name(self, role_name: str) -> Optional[Role]:
        query = select(Role).where(Role.name.ilike(role_name))
        result = await self.db.execute(query)
        return result.scalars().first()

    async def create_role_if_not_exists(self, role_name: str, description: Optional[str] = None) -> Role:
        role = await self.get_role_by_name(role_name)
        if not role:
            role = Role(name=role_name, description=description)
            self.db.add(role)
            await self.db.commit()
            await self.db.refresh(role)
        return role

    async def save_refresh_token(self, refresh_token: RefreshToken) -> RefreshToken:
        self.db.add(refresh_token)
        await self.db.commit()
        await self.db.refresh(refresh_token)
        return refresh_token

    async def get_refresh_token(self, token_str: str) -> Optional[RefreshToken]:
        query = select(RefreshToken).where(RefreshToken.token == token_str)
        result = await self.db.execute(query)
        return result.scalars().first()

    async def revoke_refresh_token(self, token_str: str) -> bool:
        token = await self.get_refresh_token(token_str)
        if token:
            token.revoked = True
            await self.db.commit()
            return True
        return False
