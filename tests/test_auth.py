import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_user_registration(client: AsyncClient):
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "newuser@example.com",
            "password": "Password123!",
            "full_name": "New User",
            "role": "Patient",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["success"] is True
    assert data["data"]["email"] == "newuser@example.com"
    assert any(r["name"] == "Patient" for r in data["data"]["roles"])


@pytest.mark.asyncio
async def test_duplicate_email_registration_fails(client: AsyncClient, patient_user):
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": patient_user.email,
            "password": "AnotherPassword123!",
            "full_name": "Duplicate User",
            "role": "Patient",
        },
    )
    assert response.status_code == 400
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "EMAIL_ALREADY_EXISTS"


@pytest.mark.asyncio
async def test_user_login_success(client: AsyncClient, patient_user):
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": patient_user.email,
            "password": "StrongPass123!",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "access_token" in data["data"]
    assert "refresh_token" in data["data"]


@pytest.mark.asyncio
async def test_user_login_invalid_password(client: AsyncClient, patient_user):
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": patient_user.email,
            "password": "WrongPassword!",
        },
    )
    assert response.status_code == 401
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_get_current_user_profile(client: AsyncClient, patient_token):
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {patient_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["email"] == "patient@example.com"


@pytest.mark.asyncio
async def test_token_refresh(client: AsyncClient, patient_user):
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": patient_user.email, "password": "StrongPass123!"},
    )
    tokens = login_res.json()["data"]

    refresh_res = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert refresh_res.status_code == 200
    new_tokens = refresh_res.json()["data"]
    assert "access_token" in new_tokens
    assert "refresh_token" in new_tokens
    assert new_tokens["refresh_token"] != tokens["refresh_token"]
