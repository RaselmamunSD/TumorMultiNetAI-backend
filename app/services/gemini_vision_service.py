import base64
import io
import json
import re
from typing import Any, Dict, Optional, Tuple
import cv2
import httpx
import numpy as np
from PIL import Image

from app.core.config import settings
from app.core.logging import logger
from app.ml.preprocessing import load_image_bytes

VISION_PROMPT = """
You are an expert AI Neuro-Radiology Image Verification & Screening System.
Analyze the provided input image in detail.

STEP 1: RECOGNITION & VERIFICATION
Determine whether this image is genuinely a Brain MRI or Brain CT medical scan (e.g. Axial, Sagittal, Coronal slice of human brain, T1, T2, FLAIR, T1ce, DWI, etc.).

If the image is NOT a brain MRI or brain CT scan (for example: a human photo, selfie, animal, car, nature, document, random object, chest X-ray, or non-brain image):
You MUST immediately reject it by returning JSON with is_brain_mri = false.

STEP 2: TUMOR SCREENING & CLASSIFICATION (Only if is_brain_mri is true)
Examine the brain anatomical structures (cerebrum, ventricles, meninges, pituitary fossa, brainstem, white/gray matter) and pathological patterns:
1. Detect whether an intracranial tumor or abnormal mass lesion is present.
2. Classify into one of these 4 standard classes:
   - "glioma" (Glioma, Glioblastoma, Astrocytoma, Oligodendroglioma)
   - "meningioma" (Meningioma along dural/meningeal borders)
   - "pituitary" (Pituitary Adenoma / Sellar/Suprasellar Neoplasm)
   - "no_tumor" (Normal anatomical brain scan with no detectable mass)

You MUST respond strictly with a valid JSON object in the following format (no extra text, no markdown backticks outside JSON):
{
  "is_brain_mri": true or false,
  "rejection_reason": "Reason if is_brain_mri is false, or null if true",
  "predicted_class": "glioma" | "meningioma" | "pituitary" | "no_tumor",
  "screening_label": "Screening summary label, e.g. 'Suspicious Neoplasm: Glioma' or 'Normal Scan: No Tumor Detected'",
  "confidence": 0.94,
  "is_abnormal": true or false,
  "probabilities": {
    "glioma": 0.02,
    "meningioma": 0.94,
    "pituitary": 0.01,
    "no_tumor": 0.03
  },
  "anatomical_location": "e.g. Parasagittal dura / Right frontal lobe / Sellar region / None",
  "clinical_findings": "Detailed 2-3 sentence clinical observation of the scan features and hyper/hypo-intensities.",
  "recommendation": "Recommended clinical next steps for the attending medical professional."
}
"""


class GeminiVisionService:
    @staticmethod
    def prepare_base64_image(image_bytes: bytes, filename: str) -> Tuple[str, str]:
        """
        Loads image (including DICOM) and converts to standard JPEG base64 string.
        """
        rgb_arr = load_image_bytes(image_bytes, filename)
        pil_img = Image.fromarray(rgb_arr)
        
        # Max dimension 1024 for fast inference
        if max(pil_img.size) > 1024:
            pil_img.thumbnail((1024, 1024), Image.Resampling.LANCZOS)

        buffered = io.BytesIO()
        pil_img.save(buffered, format="JPEG", quality=90)
        img_b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
        return img_b64, "image/jpeg"

    @classmethod
    async def analyze_mri_with_gemini(
        cls, image_bytes: bytes, filename: str
    ) -> Optional[Dict[str, Any]]:
        """
        Sends image to Gemini Vision API for MRI verification and tumor screening.
        Returns parsed dictionary, or None if Gemini is not configured / fails.
        """
        api_key = settings.GEMINI_API_KEY.strip()
        if not api_key:
            return None

        try:
            img_b64, mime_type = cls.prepare_base64_image(image_bytes, filename)

            url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.GEMINI_MODEL}:generateContent?key={api_key}"

            payload = {
                "contents": [
                    {
                        "role": "user",
                        "parts": [
                            {"text": VISION_PROMPT},
                            {
                                "inlineData": {
                                    "mimeType": mime_type,
                                    "data": img_b64,
                                }
                            },
                        ],
                    }
                ],
                "generationConfig": {
                    "temperature": 0.1,
                    "responseMimeType": "application/json",
                    "maxOutputTokens": 1000,
                },
            }

            async with httpx.AsyncClient(timeout=25.0) as client:
                response = await client.post(url, json=payload)
                if response.status_code == 200:
                    data = response.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        text_part = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                        if text_part:
                            # Clean potential markdown formatting
                            cleaned_text = re.sub(r"^```json\s*", "", text_part.strip())
                            cleaned_text = re.sub(r"```$", "", cleaned_text.strip())
                            result = json.loads(cleaned_text)
                            logger.info(f"Gemini Vision MRI Analysis result: {result.get('is_brain_mri')}, class: {result.get('predicted_class')}")
                            return result
                else:
                    logger.warning(f"Gemini Vision API status {response.status_code}: {response.text}")
        except Exception as e:
            logger.error(f"Error during Gemini Vision analysis: {str(e)}")

        return None
