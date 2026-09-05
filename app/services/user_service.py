import uuid
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exceptions import NotFoundException
from app.core.security import get_password_hash
from app.models.user import User
from app.repositories.user_repo import UserRepository
from app.schemas.user import UserUpdate


class UserService:
    def __init__(self, db: AsyncSession):
        self.user_repo = UserRepository(db)

    async def get_user_profile(self, user_id: uuid.UUID) -> User:
        user = await self.user_repo.get_by_id_with_profiles(user_id)
        if not user:
            raise NotFoundException("User profile not found.")
        return user

    async def update_user_profile(self, user_id: uuid.UUID, update_data: UserUpdate) -> User:
        user = await self.get_user_profile(user_id)
        if update_data.full_name:
            user.full_name = update_data.full_name
        if update_data.password:
            user.hashed_password = get_password_hash(update_data.password)
        return await self.user_repo.update(user)
