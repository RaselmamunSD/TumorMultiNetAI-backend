import io
from typing import Tuple, Union
import numpy as np
import cv2
from PIL import Image
import torch
import torchvision.transforms as transforms
from app.core.exceptions import InvalidImageException


def load_image_bytes(image_bytes: bytes, filename: str) -> np.ndarray:
    """
    Load image from raw bytes supporting DICOM (.dcm) and standard image formats (PNG, JPG, JPEG).
    Returns a normalized RGB numpy array with shape (H, W, 3), dtype uint8 [0, 255].
    """
    ext = filename.lower().split(".")[-1] if "." in filename else ""

    if ext == "dcm":
        try:
            import pydicom
            dataset = pydicom.dcmread(io.BytesIO(image_bytes), force=True)
            pixel_array = dataset.pixel_array.astype(np.float32)

            # Apply Rescale Slope and Intercept if present in DICOM header
            slope = getattr(dataset, "RescaleSlope", 1)
            intercept = getattr(dataset, "RescaleIntercept", 0)
            pixel_array = pixel_array * slope + intercept

            # Min-Max Windowing to [0, 255]
            min_val = np.min(pixel_array)
            max_val = np.max(pixel_array)
            if max_val > min_val:
                pixel_array = ((pixel_array - min_val) / (max_val - min_val)) * 255.0
            else:
                pixel_array = np.zeros_like(pixel_array)
            
            img_uint8 = pixel_array.astype(np.uint8)

            # Convert Grayscale to 3-channel RGB
            if len(img_uint8.shape) == 2:
                img_rgb = cv2.cvtColor(img_uint8, cv2.COLOR_GRAY2RGB)
            elif len(img_uint8.shape) == 3 and img_uint8.shape[2] == 1:
                img_rgb = cv2.cvtColor(img_uint8, cv2.COLOR_GRAY2RGB)
            else:
                img_rgb = img_uint8[:, :, :3]
            return img_rgb
        except Exception as e:
            raise InvalidImageException(f"Failed to decode DICOM image: {str(e)}")

    # Standard formats: PNG, JPG, JPEG
    try:
        pil_image = Image.open(io.BytesIO(image_bytes))
        # Ensure image is fully loaded and converted to RGB
        pil_image.load()
        if pil_image.mode != "RGB":
            pil_image = pil_image.convert("RGB")
        return np.array(pil_image)
    except Exception as e:
        raise InvalidImageException(f"Corrupted or invalid image file: {str(e)}")


def apply_clahe_enhancement(image_rgb: np.ndarray) -> np.ndarray:
    """
    Apply Contrast Limited Adaptive Histogram Equalization (CLAHE) on the Luminance (L) channel.
    Significantly improves visibility of brain MRI anatomical features and soft-tissue boundaries.
    """
    lab = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2LAB)
    l_channel, a_channel, b_channel = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced_l = clahe.apply(l_channel)
    enhanced_lab = cv2.merge((enhanced_l, a_channel, b_channel))
    return cv2.cvtColor(enhanced_lab, cv2.COLOR_LAB2RGB)


class MRIPreprocessor:
    """
    Prepares raw MRI images into PyTorch Tensors for deep learning inference.
    Exactly matches the training normalization and input dimensions (224x224).
    """
    def __init__(self, target_size: Tuple[int, int] = (224, 224), use_clahe: bool = True):
        self.target_size = target_size
        self.use_clahe = use_clahe
        self.transform = transforms.Compose([
            transforms.ToPILImage(),
            transforms.Resize(self.target_size),
            transforms.ToTensor(),
            # ImageNet standard normalization (mean & std)
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225],
            ),
        ])

    def preprocess(self, image_bytes: bytes, filename: str) -> Tuple[torch.Tensor, np.ndarray]:
        """
        Loads raw image bytes, applies enhancement, and returns:
        1. tensor: Shape (1, 3, 224, 224)
        2. original_rgb_resized: Shape (224, 224, 3) for visualization and explainability
        """
        raw_rgb = load_image_bytes(image_bytes, filename)
        
        if self.use_clahe:
            enhanced_rgb = apply_clahe_enhancement(raw_rgb)
        else:
            enhanced_rgb = raw_rgb

        # Resize RGB for heatmap overlay alignment
        rgb_resized = cv2.resize(enhanced_rgb, self.target_size, interpolation=cv2.INTER_AREA)

        # Transform to normalized Tensor
        tensor = self.transform(rgb_resized)
        tensor = tensor.unsqueeze(0)  # Add batch dimension (1, 3, H, W)
        return tensor, rgb_resized
