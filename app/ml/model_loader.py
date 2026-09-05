import os
import threading
from typing import Optional
import torch
import torch.nn as nn
from app.core.config import settings
from app.core.logging import logger
from app.core.exceptions import ModelUnavailableException
from app.ml.architecture import BrainMRIClassifier


class ModelLoader:
    """
    Thread-safe Singleton for loading and caching the PyTorch Brain MRI model.
    Loads the model once during application startup rather than per request.
    """
    _instance: Optional["ModelLoader"] = None
    _lock = threading.Lock()

    def __init__(self):
        self.model: Optional[nn.Module] = None
        self.device: torch.device = self._get_device()
        self.is_loaded: bool = False
        self.model_version: str = settings.MODEL_VERSION
        self.model_path: str = settings.MODEL_PATH

    @classmethod
    def get_instance(cls) -> "ModelLoader":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def _get_device(self) -> torch.device:
        configured_device = settings.MODEL_DEVICE.lower()
        if configured_device == "cuda" and torch.cuda.is_available():
            return torch.device("cuda")
        elif configured_device == "mps" and hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return torch.device("mps")
        return torch.device("cpu")

    def load_model(self) -> nn.Module:
        with self._lock:
            if self.is_loaded and self.model is not None:
                return self.model

            logger.info(
                f"Loading PyTorch Brain MRI Model from {self.model_path} onto device {self.device}..."
            )

            try:
                model = BrainMRIClassifier(num_classes=len(settings.SUPPORTED_CLASSES))
                
                # If weights file exists, load state dict
                if os.path.exists(self.model_path):
                    state_dict = torch.load(self.model_path, map_location=self.device)
                    # Check if saved as state_dict or full model
                    if isinstance(state_dict, dict) and "state_dict" in state_dict:
                        model.load_state_dict(state_dict["state_dict"])
                    elif isinstance(state_dict, dict):
                        model.load_state_dict(state_dict)
                    logger.info(f"Loaded weights from {self.model_path}")
                else:
                    logger.warning(
                        f"Weights file not found at {self.model_path}. Initialized model with default architecture weights."
                    )

                model.to(self.device)
                model.eval()

                # Warm-up inference pass
                dummy_input = torch.randn(1, 3, 224, 224, device=self.device)
                with torch.no_grad():
                    _ = model(dummy_input)

                self.model = model
                self.is_loaded = True
                logger.info("PyTorch Brain MRI model successfully loaded and warmed up.")
                return self.model

            except Exception as e:
                self.is_loaded = False
                logger.error(f"Failed to load PyTorch model: {str(e)}")
                raise ModelUnavailableException(f"Error initializing AI inference engine: {str(e)}")

    def get_model(self) -> nn.Module:
        if not self.is_loaded or self.model is None:
            return self.load_model()
        return self.model

    def health_check(self) -> bool:
        """Verify model is loaded and can execute forward pass."""
        try:
            if not self.is_loaded or self.model is None:
                return False
            dummy_input = torch.randn(1, 3, 224, 224, device=self.device)
            with torch.no_grad():
                output = self.model(dummy_input)
            return output.shape == (1, len(settings.SUPPORTED_CLASSES))
        except Exception:
            return False
