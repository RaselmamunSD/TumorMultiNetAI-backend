from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.common import APIResponse
from app.schemas.user import UserResponse, UserUpdate
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["Users"])


@router.get(
    "/profile",
    response_model=APIResponse[UserResponse],
    summary="Get user profile",
)
async def get_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user_service = UserService(db)
    user = await user_service.get_user_profile(current_user.id)
    return APIResponse(success=True, data=UserResponse.model_validate(user))


@router.put(
    "/profile",
    response_model=APIResponse[UserResponse],
    summary="Update user profile",
)
async def update_profile(
    update_data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user_service = UserService(db)
    updated_user = await user_service.update_user_profile(current_user.id, update_data)
    return APIResponse(
        success=True,
        message="Profile updated successfully.",
        data=UserResponse.model_validate(updated_user),
    )
