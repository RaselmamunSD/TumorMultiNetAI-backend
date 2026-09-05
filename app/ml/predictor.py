import time
from typing import Any, Dict, Optional, Tuple
import numpy as np
import torch
from app.core.config import settings
from app.core.exceptions import PredictionFailedException
from app.core.logging import logger
from app.ml.model_loader import ModelLoader
from app.ml.preprocessing import MRIPreprocessor
from app.ml.postprocessing import MRIPostprocessor
from app.ml.explainability import GradCAM, create_heatmap_and_overlay


class ModelService:
    """
    Unified AI Inference Service.
    Separates ML inference from FastAPI web layer.
    """
    def __init__(self):
        self.loader = ModelLoader.get_instance()
        self.preprocessor = MRIPreprocessor()
        self.postprocessor = MRIPostprocessor()

    def load_model(self):
        return self.loader.load_model()

    def preprocess(self, image_bytes: bytes, filename: str) -> Tuple[torch.Tensor, np.ndarray]:
        return self.preprocessor.preprocess(image_bytes, filename)

    def postprocess(self, logits: torch.Tensor) -> Dict[str, Any]:
        return self.postprocessor.process(logits)

    def health_check(self) -> bool:
        return self.loader.health_check()

    def predict(self, image_bytes: bytes, filename: str) -> Dict[str, Any]:
        """
        Execute full AI inference pipeline on raw image bytes.
        """
        start_time = time.time()
        try:
            model = self.loader.get_model()
            device = self.loader.device

            # Preprocessing
            input_tensor, _ = self.preprocess(image_bytes, filename)
            input_tensor = input_tensor.to(device)

            # Inference
            with torch.no_grad():
                logits = model(input_tensor)

            # Postprocessing
            result = self.postprocess(logits)
            
            inference_time_ms = round((time.time() - start_time) * 1000, 2)
            result["inference_time_ms"] = inference_time_ms
            result["model_name"] = "BrainMRIClassifier"
            result["model_version"] = self.loader.model_version

            return result

        except Exception as e:
            logger.error(f"Inference error on image {filename}: {str(e)}")
            raise PredictionFailedException(f"Failed to process MRI image: {str(e)}")

    def explain(
        self,
        image_bytes: bytes,
        filename: str,
        target_class: Optional[int] = None,
    ) -> Tuple[bytes, bytes, Dict[str, Any]]:
        """
        Generate Grad-CAM heatmap and overlay visualization for the input MRI image.
        Returns: (heatmap_bytes, overlay_bytes, prediction_result)
        """
        try:
            model = self.loader.get_model()
            device = self.loader.device

            input_tensor, rgb_resized = self.preprocess(image_bytes, filename)
            input_tensor = input_tensor.to(device)
            input_tensor.requires_grad = True

            # Get target convolution layer for Grad-CAM
            target_layer = model.target_conv_layer

            grad_cam = GradCAM(model=model, target_layer=target_layer)
            cam = grad_cam.generate_cam(input_tensor, target_class=target_class)

            # Create heatmap and overlay PNG byte streams
            heatmap_bytes, overlay_bytes = create_heatmap_and_overlay(cam, rgb_resized)

            # Also compute prediction details
            with torch.no_grad():
                logits = model(input_tensor)
            prediction_result = self.postprocess(logits)

            return heatmap_bytes, overlay_bytes, prediction_result

        except Exception as e:
            logger.error(f"Explainability generation error: {str(e)}")
            raise PredictionFailedException(f"Grad-CAM generation failed: {str(e)}")


# Singleton instance for dependency injection
model_service = ModelService()
