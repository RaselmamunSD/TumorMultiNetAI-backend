import io
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_upload_and_analyze_sync(
    client: AsyncClient, patient_token, sample_mri_png_bytes
):
    files = {"file": ("brain_mri_scan.png", sample_mri_png_bytes, "image/png")}
    response = await client.post(
        "/api/v1/analysis/upload",
        files=files,
        headers={"Authorization": f"Bearer {patient_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["status"] == "completed"
    assert "prediction" in data["data"]
    assert "disclaimer" in data["data"]
    assert data["data"]["prediction"]["predicted_class"] in [
        "no_tumor",
        "glioma",
        "meningioma",
        "pituitary",
    ]


@pytest.mark.asyncio
async def test_get_analysis_history(
    client: AsyncClient, patient_token, sample_mri_png_bytes
):
    # First upload an image
    files = {"file": ("scan1.png", sample_mri_png_bytes, "image/png")}
    upload_res = await client.post(
        "/api/v1/analysis/upload",
        files=files,
        headers={"Authorization": f"Bearer {patient_token}"},
    )
    analysis_id = upload_res.json()["data"]["analysis_id"]

    # Fetch history
    history_res = await client.get(
        "/api/v1/analysis/history",
        headers={"Authorization": f"Bearer {patient_token}"},
    )
    assert history_res.status_code == 200
    history_data = history_res.json()
    assert history_data["success"] is True
    assert len(history_data["data"]["items"]) >= 1
    assert any(item["id"] == analysis_id for item in history_data["data"]["items"])


@pytest.mark.asyncio
async def test_generate_gradcam_explainability(
    client: AsyncClient, patient_token, sample_mri_png_bytes
):
    # Upload first
    files = {"file": ("scan_gradcam.png", sample_mri_png_bytes, "image/png")}
    upload_res = await client.post(
        "/api/v1/analysis/upload",
        files=files,
        headers={"Authorization": f"Bearer {patient_token}"},
    )
    analysis_id = upload_res.json()["data"]["analysis_id"]

    # Request Grad-CAM
    explain_res = await client.post(
        f"/api/v1/analysis/{analysis_id}/explain",
        headers={"Authorization": f"Bearer {patient_token}"},
    )
    assert explain_res.status_code == 200
    data = explain_res.json()
    assert data["success"] is True
    assert "gradcam_url" in data["data"]
    assert "overlay_url" in data["data"]
    assert "explanation_note" in data["data"]
