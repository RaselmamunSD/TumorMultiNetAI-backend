from typing import Any, Dict, List, Tuple
import torch
import torch.nn.functional as F
from app.core.config import settings

CLASS_MAPPING = {
    0: "no_tumor",
    1: "glioma",
    2: "meningioma",
    3: "pituitary",
}

SCREENING_LABELS = {
    "no_tumor": "No abnormality pattern detected by the model",
    "glioma": "Abnormality pattern suspected: Glioma",
    "meningioma": "Abnormality pattern suspected: Meningioma",
    "pituitary": "Abnormality pattern suspected: Pituitary Tumor",
}


class MRIPostprocessor:
    """
    Transforms raw model logits into clinically safe predictions, confidence scores,
    and appropriate decision-support terminology.
    """
    def __init__(self, supported_classes: List[str] = None, confidence_threshold: float = None):
        self.supported_classes = supported_classes or settings.SUPPORTED_CLASSES
        self.confidence_threshold = confidence_threshold or settings.CONFIDENCE_THRESHOLD

    def process(self, logits: torch.Tensor) -> Dict[str, Any]:
        """
        Converts model logits into calibrated probabilities and screening descriptions.
        """
        probabilities_tensor = F.softmax(logits, dim=1).squeeze(0)
        probabilities_list = probabilities_tensor.detach().cpu().numpy().tolist()

        # Build class-to-probability dictionary
        prob_dict: Dict[str, float] = {}
        for idx, prob in enumerate(probabilities_list):
            class_name = CLASS_MAPPING.get(idx, f"class_{idx}")
            prob_dict[class_name] = round(float(prob), 4)

        # Find top predicted class index and confidence
        top_idx = int(torch.argmax(probabilities_tensor).item())
        predicted_class = CLASS_MAPPING.get(top_idx, "unknown")
        confidence = prob_dict.get(predicted_class, 0.0)

        # Medical safety rule: Check if abnormality is suspected
        is_abnormal = predicted_class != "no_tumor" and confidence >= self.confidence_threshold
        
        screening_label = SCREENING_LABELS.get(
            predicted_class, "Abnormality pattern detected - Clinical review recommended"
        )
        if not is_abnormal and predicted_class != "no_tumor":
            screening_label = "Inconclusive screening pattern - Low model confidence. Radiologist review strongly recommended."

        return {
            "predicted_class": predicted_class,
            "screening_label": screening_label,
            "confidence": confidence,
            "is_abnormal": is_abnormal,
            "probabilities": prob_dict,
            "disclaimer": settings.MEDICAL_DISCLAIMER,
        }
