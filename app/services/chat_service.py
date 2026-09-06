from typing import Any, Dict, List, Optional
import httpx
from app.core.config import settings
from app.core.logging import logger

SYSTEM_PROMPT = """
You are the TumorMultiNetAI Medical Intelligence System, an advanced neuro-oncology neural network assistant.
You specialize in Brain MRI neuro-oncology, deep learning screening, multimodal sequences (T1, T2, FLAIR, T1ce), and Grad-CAM explainable AI.
You answer questions accurately, professionally, and empathetically.

STRICT IDENTITY RULES:
1. Under NO circumstances should you disclose, state, or hint that you are powered by Gemini, Google, or any external third-party LLM.
2. If asked what model you are, always state that you are the TumorMultiNetAI Neural Intelligence Engine developed for Brain MRI clinical decision support.
3. Always clarify that AI outputs are screening and decision-support aids, not final medical diagnoses, and advise consulting qualified medical specialists or certified radiologists for clinical confirmation.
"""

OFFLINE_FALLBACKS: Dict[str, str] = {
    "tumor": "A brain tumor is an abnormal mass of cells. Common types detected by our AI include Glioma, Meningioma, and Pituitary tumors. Early screening with MRI is vital.",
    "glioma": "Gliomas originate from glial tissue in the brain. They range from low-grade to high-grade glioblastomas and often show hyperintensity on T2 and FLAIR MRI sequences.",
    "meningioma": "Meningiomas arise from the protective meninges layer. They are typically well-circumscribed and frequently benign.",
    "pituitary": "Pituitary tumors develop in the pituitary gland at the base of the brain, affecting endocrine hormonal functions.",
    "gradcam": "Grad-CAM (Gradient-weighted Class Activation Mapping) visually highlights the exact 2D regions in the brain MRI that influenced the AI prediction with a color-coded heatmap.",
    "mri": "Our system supports T1, T2, FLAIR, and T1ce MRI modalities in DICOM (.dcm), PNG, and JPEG formats.",
}


class ChatService:
    @staticmethod
    async def generate_response(user_message: str, history: Optional[List[Dict[str, str]]] = None) -> str:
        api_key = settings.GEMINI_API_KEY.strip()

        # If API key is configured, call neural completion backend
        if api_key:
            try:
                # Prepare contents for REST API
                contents = []
                if history:
                    for item in history[-6:]:  # Keep recent context
                        role = "user" if item.get("role") == "user" else "model"
                        contents.append({"role": role, "parts": [{"text": item.get("text", "")}]})

                contents.append({"role": "user", "parts": [{"text": user_message}]})

                url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.GEMINI_MODEL}:generateContent"
                headers = {
                    "Content-Type": "application/json",
                    "x-goog-api-key": api_key,
                }
                
                payload = {
                    "contents": contents,
                    "systemInstruction": {
                        "parts": [{"text": SYSTEM_PROMPT}]
                    },
                    "generationConfig": {
                        "temperature": 0.4,
                        "maxOutputTokens": 800,
                    }
                }

                async with httpx.AsyncClient(timeout=15.0) as client:
                    response = await client.post(url, json=payload, headers=headers)
                    if response.status_code == 200:
                        data = response.json()
                        candidates = data.get("candidates", [])
                        if candidates:
                            text_parts = candidates[0].get("content", {}).get("parts", [])
                            if text_parts:
                                return text_parts[0].get("text", "")
                    else:
                        logger.warning(f"Chat API returned status {response.status_code}: {response.text}")
            except Exception as e:
                logger.error(f"Error communicating with Chat API: {str(e)}")

        # Fallback offline knowledge responder
        lower_msg = user_message.lower()
        for keyword, reply in OFFLINE_FALLBACKS.items():
            if keyword in lower_msg:
                return reply

        return (
            "Hello! I am the TumorMultiNetAI Assistant. I can assist you with brain MRI scans, "
            "tumor screening (Glioma, Meningioma, Pituitary, Normal), DICOM preprocessing, and Grad-CAM explainability."
        )
