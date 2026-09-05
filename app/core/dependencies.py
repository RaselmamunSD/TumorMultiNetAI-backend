import uuid
from typing import List, Optional
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.config import settings
from app.core.database import get_db
from app.core.security import decode_token
from app.core.exceptions import ForbiddenException, RateLimitException, UnauthorizedException
from app.core.redis import check_rate_limit
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Dependency that authenticates the user via JWT Bearer token."""
    payload = decode_token(token)
    if not payload:
        raise UnauthorizedException("Invalid or expired authentication token.")
    
    token_type = payload.get("type")
    if token_type != "access":
        raise UnauthorizedException("Invalid token type. Access token required.")

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise UnauthorizedException("Malformed token claims.")

    try:
        user_uuid = uuid.UUID(user_id_str)
    except ValueError:
        raise UnauthorizedException("Invalid user identifier in token.")

    query = select(User).where(User.id == user_uuid)
    result = await db.execute(query)
    user = result.scalars().first()

    if not user:
        raise UnauthorizedException("User no longer exists.")
    
    if not user.is_active:
        raise ForbiddenException("User account is inactive.")

    return user


async def get_current_active_verified_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Ensure user is active and optionally verified."""
    if not current_user.is_active:
        raise ForbiddenException("Inactive user account.")
    return current_user


class RoleChecker:
    """Dependency for Role-Based Access Control (RBAC)."""
    def __init__(self, allowed_roles: List[str]):
        self.allowed_roles = [r.lower() for r in allowed_roles]

    async def __call__(self, current_user: User = Depends(get_current_user)) -> User:
        user_roles = [role.name.lower() for role in current_user.roles]
        
        # Superuser / Admin always bypasses specific role restrictions
        if "admin" in user_roles:
            return current_user

        has_permission = any(role in self.allowed_roles for role in user_roles)
        if not has_permission:
            raise ForbiddenException(
                f"Access denied. Requires one of roles: {', '.join(self.allowed_roles)}"
            )
        return current_user


async def rate_limit_dependency(request: Request) -> None:
    """Rate limit per client IP."""
    client_ip = request.client.host if request.client else "unknown"
    key = f"rate_limit:{client_ip}"
    allowed = await check_rate_limit(key, max_requests=settings.RATE_LIMIT_PER_MINUTE, window_seconds=60)
    if not allowed:
        raise RateLimitException()
