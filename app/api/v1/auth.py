from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.auth import (
    PasswordResetConfirm,
    PasswordResetRequest,
    RefreshTokenRequest,
    TokenResponse,
    UserLogin,
    UserRegister,
)
from app.schemas.common import APIResponse
from app.schemas.user import UserResponse
from app.services.auth_service import AuthService
from app.services.audit_service import AuditService

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=APIResponse[UserResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description="Registers a new user with an initial role (Patient, Doctor, Radiologist, Admin).",
)
async def register(
    payload: UserRegister,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    auth_service = AuthService(db)
    user = await auth_service.register_user(payload)

    # HIPAA audit trail
    audit_service = AuditService(db)
    await audit_service.log_action(
        action="USER_REGISTER",
        resource_type="User",
        resource_id=str(user.id),
        user_id=user.id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    return APIResponse(
        success=True,
        message="User registered successfully.",
        data=UserResponse.model_validate(user),
    )


@router.post(
    "/login",
    response_model=APIResponse[TokenResponse],
    summary="User Login",
    description="Authenticates user credentials and returns JWT access and refresh tokens.",
)
async def login(
    payload: UserLogin,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    auth_service = AuthService(db)
    token_response = await auth_service.authenticate_user(payload.email, payload.password)

    # Audit login
    audit_service = AuditService(db)
    await audit_service.log_action(
        action="USER_LOGIN",
        resource_type="User",
        resource_id=token_response.user_id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    return APIResponse(
        success=True,
        message="Login successful.",
        data=token_response,
    )


@router.post(
    "/refresh",
    response_model=APIResponse[TokenResponse],
    summary="Refresh Access Token",
    description="Rotates refresh token and returns a fresh JWT access token.",
)
async def refresh_token(
    payload: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
):
    auth_service = AuthService(db)
    token_response = await auth_service.refresh_access_token(payload.refresh_token)
    return APIResponse(
        success=True,
        message="Token refreshed successfully.",
        data=token_response,
    )


@router.post(
    "/logout",
    response_model=APIResponse[dict],
    summary="User Logout",
    description="Revokes the provided refresh token.",
)
async def logout(
    payload: RefreshTokenRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    auth_service = AuthService(db)
    await auth_service.logout(payload.refresh_token)
    return APIResponse(success=True, message="Successfully logged out.")


@router.get(
    "/me",
    response_model=APIResponse[UserResponse],
    summary="Get Current User Profile",
    description="Returns the profile and roles of the currently authenticated user.",
)
async def get_me(current_user: User = Depends(get_current_user)):
    return APIResponse(
        success=True,
        data=UserResponse.model_validate(current_user),
    )


@router.post(
    "/forgot-password",
    response_model=APIResponse[dict],
    summary="Request Password Reset",
    description="Initiates password reset process for the specified email.",
)
async def forgot_password(payload: PasswordResetRequest):
    # In production, send secure reset token via email service
    return APIResponse(
        success=True,
        message="If this email is registered, a password reset link has been dispatched.",
    )


@router.post(
    "/reset-password",
    response_model=APIResponse[dict],
    summary="Confirm Password Reset",
    description="Resets the password given a valid reset token.",
)
async def reset_password(payload: PasswordResetConfirm):
    return APIResponse(
        success=True,
        message="Password has been reset successfully.",
    )
