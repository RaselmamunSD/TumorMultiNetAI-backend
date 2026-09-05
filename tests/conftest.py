import io
import os
import uuid
import pytest
import pytest_asyncio
from typing import AsyncGenerator
from httpx import AsyncClient, ASGITransport
from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.database import Base, get_db
from app.core.security import create_access_token, get_password_hash
from app.main import app
from app.models.user import User, Role
from app.ml.predictor import model_service

# Use in-memory SQLite for high-speed, isolated unit and integration testing
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provides a fresh, isolated database session per test with tables created."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestingSessionLocal() as session:
        yield session

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """FastAPI Async test client with overridden database dependency."""
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def patient_user(db_session: AsyncSession) -> User:
    role = Role(name="Patient", description="Patient role")
    db_session.add(role)
    user = User(
        email="patient@example.com",
        hashed_password=get_password_hash("StrongPass123!"),
        full_name="John Doe",
        is_active=True,
        is_verified=True,
        roles=[role],
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def doctor_user(db_session: AsyncSession) -> User:
    role = Role(name="Doctor", description="Doctor role")
    db_session.add(role)
    user = User(
        email="doctor@hospital.org",
        hashed_password=get_password_hash("StrongDoc123!"),
        full_name="Dr. Sarah Connor",
        is_active=True,
        is_verified=True,
        roles=[role],
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession) -> User:
    role = Role(name="Admin", description="Admin role")
    db_session.add(role)
    user = User(
        email="admin@brainscan.ai",
        hashed_password=get_password_hash("AdminSecret123!"),
        full_name="System Administrator",
        is_active=True,
        is_verified=True,
        roles=[role],
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
def patient_token(patient_user: User) -> str:
    return create_access_token(
        subject=str(patient_user.id),
        extra_claims={"email": patient_user.email, "roles": ["Patient"]},
    )


@pytest.fixture
def doctor_token(doctor_user: User) -> str:
    return create_access_token(
        subject=str(doctor_user.id),
        extra_claims={"email": doctor_user.email, "roles": ["Doctor"]},
    )


@pytest.fixture
def admin_token(admin_user: User) -> str:
    return create_access_token(
        subject=str(admin_user.id),
        extra_claims={"email": admin_user.email, "roles": ["Admin"]},
    )


@pytest.fixture
def sample_mri_png_bytes() -> bytes:
    """Creates a sample 256x256 grayscale/RGB PNG image in memory for testing."""
    img = Image.new("RGB", (256, 256), color=(128, 128, 128))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def sample_mri_jpeg_bytes() -> bytes:
    """Creates a sample 256x256 JPEG image in memory for testing."""
    img = Image.new("RGB", (256, 256), color=(100, 100, 100))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()
