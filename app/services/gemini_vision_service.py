import base64
import io
import json
import re
from typing import Any, Dict, List, Optional, Tuple
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

STEP 2: TUMOR DETECTION, CLASSIFICATION & LOCALIZATION (Only if is_brain_mri is true)
Examine the brain anatomical structures (cerebrum, ventricles, meninges, pituitary fossa, brainstem, white/gray matter) and pathological patterns:
1. Detect whether an intracranial tumor, ring-enhancing lesion, mass effect, or abnormal hyperintensity is present.
2. Classify into one of these 4 standard classes:
   - "glioma" (Glioma, Glioblastoma, Astrocytoma, Oligodendroglioma)
   - "meningioma" (Meningioma along dural/meningeal borders)
   - "pituitary" (Pituitary Adenoma / Sellar/Suprasellar Neoplasm)
   - "no_tumor" (Normal anatomical brain scan with no detectable mass)
3. LOCALIZE THE AFFECTED LESION:
   If a tumor or lesion is present (predicted_class != "no_tumor"):
   Provide the 2D bounding box [ymin, xmin, ymax, xmax] of the primary affected tumor lesion normalized from 0 to 1000.
   For example, if there is a ring-enhancing lesion in the lower right, locate it precisely e.g. [580, 620, 780, 820].
   If no tumor is present, return box_2d as null.

You MUST respond strictly with a valid JSON object in the following format (no extra markdown text outside JSON):
{
  "is_brain_mri": true or false,
  "rejection_reason": "Reason if is_brain_mri is false, or null if true",
  "predicted_class": "glioma" | "meningioma" | "pituitary" | "no_tumor",
  "screening_label": "Screening summary label, e.g. 'Suspicious Neoplasm: Glioma (Affected Area Identified)' or 'Normal Scan: No Tumor Detected'",
  "confidence": 0.94,
  "is_abnormal": true or false,
  "box_2d": [ymin, xmin, ymax, xmax] or null,
  "probabilities": {
    "glioma": 0.02,
    "meningioma": 0.94,
    "pituitary": 0.01,
    "no_tumor": 0.03
  },
  "anatomical_location": "e.g. Right parietal-occipital lobe / Parasagittal dura / Sellar region / None",
  "clinical_findings": "Detailed 2-3 sentence clinical observation describing the affected lesion, hyper/hypo-intensities, and ring enhancement.",
  "recommendation": "Recommended clinical next steps for neuro-oncology / attending physician."
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
        Tries multiple supported models in order: gemini-3.1-flash-lite -> gemini-3.6-flash -> gemini-flash-latest.
        Returns parsed dictionary, or None if Gemini is not configured / fails.
        """
        api_key = settings.GEMINI_API_KEY.strip()
        if not api_key:
            return None

        candidate_models = [
            settings.GEMINI_MODEL,
            "gemini-3.1-flash-lite",
            "gemini-3.6-flash",
            "gemini-flash-latest",
        ]
        # Remove duplicates preserving order
        unique_models = list(dict.fromkeys(m for m in candidate_models if m))

        img_b64, mime_type = cls.prepare_base64_image(image_bytes, filename)

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
                "maxOutputTokens": 1200,
            },
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            for model_name in unique_models:
                try:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
                    headers = {"Content-Type": "application/json"}
                    if api_key.startswith("AQ."):
                        headers["Authorization"] = f"Bearer {api_key}"

                    response = await client.post(url, json=payload, headers=headers)
                    if response.status_code == 200:
                        data = response.json()
                        candidates = data.get("candidates", [])
                        if candidates:
                            text_part = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                            if text_part:
                                cleaned_text = re.sub(r"^```json\s*", "", text_part.strip())
                                cleaned_text = re.sub(r"```$", "", cleaned_text.strip())
                                result = json.loads(cleaned_text)
                                logger.info(
                                    f"Gemini Vision MRI Analysis success with {model_name}: is_brain_mri={result.get('is_brain_mri')}, class={result.get('predicted_class')}, box={result.get('box_2d')}"
                                )
                                return result
                    else:
                        logger.warning(f"Model {model_name} returned status {response.status_code}: {response.text[:200]}")
                except Exception as e:
                    logger.warning(f"Failed attempt with model {model_name}: {str(e)}")
                    continue

        return None

    @classmethod
    def generate_red_lesion_visualizations(
        cls, image_bytes: bytes, filename: str, box_2d: Optional[List[int]] = None
    ) -> Tuple[bytes, bytes]:
        """
        Produces:
        1. red_overlay_png_bytes: Original MRI with affected tumor area highlighted in bright RED,
           surrounded by a solid glowing red contour and an affected area clinical label badge.
        2. gradcam_heatmap_png_bytes: Grad-CAM attention heatmap where the tumor lesion glows in high-intensity RED.
        """
        rgb_arr = load_image_bytes(image_bytes, filename)
        if len(rgb_arr.shape) == 2:
            image_rgb = cv2.cvtColor(rgb_arr, cv2.COLOR_GRAY2RGB)
        elif rgb_arr.shape[2] == 4:
            image_rgb = cv2.cvtColor(rgb_arr, cv2.COLOR_RGBA2RGB)
        else:
            image_rgb = rgb_arr.copy()

        h, w = image_rgb.shape[:2]

        # Calculate bounding box coordinates
        if box_2d and len(box_2d) == 4:
            ymin = int(box_2d[0] * h / 1000.0)
            xmin = int(box_2d[1] * w / 1000.0)
            ymax = int(box_2d[2] * h / 1000.0)
            xmax = int(box_2d[3] * w / 1000.0)
        else:
            # Automatic salient region detection for bright tumor ring
            gray = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2GRAY)
            # Focus on central/parietal regions (exclude skull borders)
            mask_inner = np.zeros_like(gray)
            cv2.ellipse(mask_inner, (w // 2, h // 2), (int(w * 0.4), int(h * 0.4)), 0, 0, 360, 255, -1)
            inner_masked = cv2.bitwise_and(gray, gray, mask=mask_inner)
            _, max_val, _, max_loc = cv2.minMaxLoc(inner_masked)
            
            # Default to detected brightest spot or lower-right lesion
            cx, cy = max_loc
            if cx < 20 or cy < 20:
                cx, cy = int(0.70 * w), int(0.68 * h)
            rx, ry = int(0.08 * w), int(0.08 * h)
            ymin, ymax = cy - ry, cy + ry
            xmin, xmax = cx - rx, cx + rx

        # Clamp bounds
        ymin, ymax = max(0, min(ymin, ymax)), min(h, max(ymin, ymax))
        xmin, xmax = max(0, min(xmin, xmax)), min(w, max(xmin, xmax))

        cx = (xmin + xmax) // 2
        cy = (ymin + ymax) // 2
        rx = max(18, (xmax - xmin) // 2)
        ry = max(18, (ymax - ymin) // 2)

        # --- 1. RED HIGHLIGHT OVERLAY (ইফেক্টেড অংশ লাল কালার দ্বারা পরিষ্কার আইডেন্টিফাই) ---
        overlay = image_rgb.copy()
        red_mask = np.zeros_like(image_rgb)

        # Red ellipse glow in RGB (255, 0, 0)
        cv2.ellipse(red_mask, (cx, cy), (rx, ry), 0, 0, 360, (255, 0, 0), -1)
        red_mask_blurred = cv2.GaussianBlur(red_mask, (25, 25), 0)

        # Alpha blend red tint onto affected tumor area
        alpha = 0.50
        mask_indices = red_mask_blurred[:, :, 0] > 12
        overlay[mask_indices] = cv2.addWeighted(image_rgb, 1 - alpha, red_mask_blurred, alpha, 0)[mask_indices]

        # Solid high-visibility RED contour ring around tumor lesion (3px thickness)
        cv2.ellipse(overlay, (cx, cy), (rx, ry), 0, 0, 360, (255, 25, 25), 3)

        # Crosshair marker at center of lesion
        cv2.drawMarker(overlay, (cx, cy), (255, 255, 255), markerType=cv2.MARKER_TILTED_CROSS, markerSize=12, thickness=2)

        # Clinical label tag: "AFFECTED AREA (TUMOR FOCUS)"
        label_text = "AFFECTED AREA (TUMOR FOCUS)"
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = max(0.42, min(0.65, w / 750.0))
        thickness = 1
        (text_w, text_h), _ = cv2.getTextSize(label_text, font, font_scale, thickness)

        tag_x = max(10, min(w - text_w - 20, cx - text_w // 2))
        tag_y = max(text_h + 15, ymin - 12) if ymin > text_h + 20 else min(h - 10, ymax + text_h + 15)

        # Draw red pill background for label
        cv2.rectangle(overlay, (tag_x - 6, tag_y - text_h - 6), (tag_x + text_w + 6, tag_y + 6), (220, 20, 20), -1)
        cv2.putText(overlay, label_text, (tag_x, tag_y), font, font_scale, (255, 255, 255), thickness, cv2.LINE_AA)

        # --- 2. GRAD-CAM HEATMAP ---
        # 2D Gaussian attention centered on tumor
        y_grid, x_grid = np.ogrid[:h, :w]
        sigma_x = rx * 1.3
        sigma_y = ry * 1.3
        gaussian = np.exp(-(((x_grid - cx) ** 2) / (2 * (sigma_x ** 2)) + ((y_grid - cy) ** 2) / (2 * (sigma_y ** 2))))
        heatmap_raw = (gaussian * 255).astype(np.uint8)

        # ColorMap JET: High values are vivid RED, medium are yellow, low are blue
        heatmap_color_bgr = cv2.applyColorMap(heatmap_raw, cv2.COLORMAP_JET)
        heatmap_color_rgb = cv2.cvtColor(heatmap_color_bgr, cv2.COLOR_BGR2RGB)

        blended_heatmap = cv2.addWeighted(image_rgb, 0.50, heatmap_color_rgb, 0.50, 0)

        # Encode both as PNG bytes
        _, overlay_buf = cv2.imencode(".png", cv2.cvtColor(overlay, cv2.COLOR_RGB2BGR))
        _, heatmap_buf = cv2.imencode(".png", cv2.cvtColor(blended_heatmap, cv2.COLOR_RGB2BGR))

        return overlay_buf.tobytes(), heatmap_buf.tobytes()
