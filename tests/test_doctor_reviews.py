import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_doctor_can_submit_review(
    client: AsyncClient, patient_token, doctor_token, sample_mri_png_bytes
):
    # Patient uploads scan
    files = {"file": ("scan_review.png", sample_mri_png_bytes, "image/png")}
    upload_res = await client.post(
        "/api/v1/analysis/upload",
        files=files,
        headers={"Authorization": f"Bearer {patient_token}"},
    )
    analysis_id = upload_res.json()["data"]["analysis_id"]

    # Doctor submits clinical review
    review_res = await client.post(
        f"/api/v1/doctors/analysis/{analysis_id}/review",
        json={
            "status": "confirmed_normal",
            "clinical_notes": "No signs of intracranial mass effect or acute ischemic infarction.",
            "recommendations": "Routine follow-up in 12 months.",
        },
        headers={"Authorization": f"Bearer {doctor_token}"},
    )
    assert review_res.status_code == 200
    data = review_res.json()
    assert data["success"] is True
    assert data["data"]["status"] == "confirmed_normal"
    assert "No signs of intracranial mass" in data["data"]["clinical_notes"]


@pytest.mark.asyncio
async def test_patient_cannot_submit_doctor_review(
    client: AsyncClient, patient_token, sample_mri_png_bytes
):
    # Patient uploads scan
    files = {"file": ("scan_perm.png", sample_mri_png_bytes, "image/png")}
    upload_res = await client.post(
        "/api/v1/analysis/upload",
        files=files,
        headers={"Authorization": f"Bearer {patient_token}"},
    )
    analysis_id = upload_res.json()["data"]["analysis_id"]

    # Patient tries to submit review
    review_res = await client.post(
        f"/api/v1/doctors/analysis/{analysis_id}/review",
        json={
            "status": "confirmed_normal",
            "clinical_notes": "Attempting patient self review.",
        },
        headers={"Authorization": f"Bearer {patient_token}"},
    )
    assert review_res.status_code == 403
