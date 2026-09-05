import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_endpoints(client: AsyncClient):
    # General health check
    res = await client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert "status" in data
    assert "database" in data

    # Database health
    db_res = await client.get("/health/database")
    assert db_res.status_code == 200

    # ML Model health
    ml_res = await client.get("/health/ml-model")
    assert ml_res.status_code == 200
