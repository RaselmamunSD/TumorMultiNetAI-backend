import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_admin_stats(client: AsyncClient, admin_token):
    response = await client.get(
        "/api/v1/admin/stats",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "total_users" in data["data"]
    assert "total_analyses" in data["data"]
    assert "class_distribution" in data["data"]


@pytest.mark.asyncio
async def test_admin_register_model(client: AsyncClient, admin_token):
    response = await client.post(
        "/api/v1/admin/models",
        json={
            "name": "brain-tumor-resnet50-v2",
            "version": "2.0.0",
            "architecture": "ResNet50",
            "weights_path": "./models/resnet50_v2.pt",
            "description": "Upgraded ResNet50 with high sensitivity.",
            "accuracy": 0.965,
            "f1_score": 0.958,
            "auc_roc": 0.982,
            "supported_classes": ["no_tumor", "glioma", "meningioma", "pituitary"],
            "is_active": True,
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["success"] is True
    assert data["data"]["name"] == "brain-tumor-resnet50-v2"
