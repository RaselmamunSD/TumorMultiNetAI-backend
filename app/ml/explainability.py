import io
from typing import Optional, Tuple
import cv2
import numpy as np
import torch
import torch.nn as nn
from PIL import Image


class GradCAM:
    """
    Gradient-weighted Class Activation Mapping (Grad-CAM) for PyTorch models.
    Provides visual interpretability by highlighting discriminative brain regions.
    """
    def __init__(self, model: nn.Module, target_layer: nn.Module):
        self.model = model
        self.target_layer = target_layer
        self.gradients: Optional[torch.Tensor] = None
        self.activations: Optional[torch.Tensor] = None
        self._register_hooks()

    def _register_hooks(self):
        def forward_hook(module, input, output):
            self.activations = output

        def backward_hook(module, grad_input, grad_output):
            self.gradients = grad_output[0]

        self.target_layer.register_forward_hook(forward_hook)
        self.target_layer.register_full_backward_hook(backward_hook)

    def generate_cam(
        self,
        input_tensor: torch.Tensor,
        target_class: Optional[int] = None,
    ) -> np.ndarray:
        """
        Computes the normalized 2D Grad-CAM heatmap array in range [0, 1].
        """
        self.model.eval()
        self.model.zero_grad()

        # Forward pass
        output = self.model(input_tensor)

        if target_class is None:
            target_class = torch.argmax(output, dim=1).item()

        # Backward pass for target class score
        target_score = output[0, target_class]
        target_score.backward(retain_graph=True)

        if self.gradients is None or self.activations is None:
            # Fallback if hooks didn't trigger
            return np.zeros((input_tensor.shape[2], input_tensor.shape[3]), dtype=np.float32)

        gradients = self.gradients.detach().cpu().numpy()[0]  # Shape: (C, H, W)
        activations = self.activations.detach().cpu().numpy()[0]  # Shape: (C, H, W)

        # Global average pooling on gradients across spatial dimensions
        weights = np.mean(gradients, axis=(1, 2))  # Shape: (C,)

        # Weighted combination of forward activation maps
        cam = np.zeros(activations.shape[1:], dtype=np.float32)
        for i, w in enumerate(weights):
            cam += w * activations[i, :, :]

        # Apply ReLU to retain only positive influence
        cam = np.maximum(cam, 0)

        # Resize CAM to match original image dimensions
        target_h, target_w = input_tensor.shape[2], input_tensor.shape[3]
        cam = cv2.resize(cam, (target_w, target_h))

        # Normalize CAM between 0 and 1
        cam_min, cam_max = np.min(cam), np.max(cam)
        if cam_max > cam_min:
            cam = (cam - cam_min) / (cam_max - cam_min)
        else:
            cam = np.zeros_like(cam)

        return cam


def create_heatmap_and_overlay(
    cam: np.ndarray,
    original_rgb_resized: np.ndarray,
    alpha: float = 0.5,
) -> Tuple[bytes, bytes]:
    """
    Creates PNG byte streams for:
    1. Heatmap (Jet Colormap)
    2. Overlay (Blended original RGB + Heatmap)
    """
    # Convert CAM [0, 1] to uint8 [0, 255]
    heatmap_uint8 = np.uint8(255 * cam)

    # Apply JET colormap (standard in clinical AI explainability)
    heatmap_colored = cv2.applyColorMap(heatmap_uint8, cv2.COLORMAP_JET)
    heatmap_rgb = cv2.cvtColor(heatmap_colored, cv2.COLOR_BGR2RGB)

    # Blend original image with heatmap
    overlay = cv2.addWeighted(original_rgb_resized, 1 - alpha, heatmap_rgb, alpha, 0)

    # Encode Heatmap as PNG bytes
    pil_heatmap = Image.fromarray(heatmap_rgb)
    heatmap_buffer = io.BytesIO()
    pil_heatmap.save(heatmap_buffer, format="PNG")
    heatmap_bytes = heatmap_buffer.getvalue()

    # Encode Overlay as PNG bytes
    pil_overlay = Image.fromarray(overlay)
    overlay_buffer = io.BytesIO()
    pil_overlay.save(overlay_buffer, format="PNG")
    overlay_bytes = overlay_buffer.getvalue()

    return heatmap_bytes, overlay_bytes
