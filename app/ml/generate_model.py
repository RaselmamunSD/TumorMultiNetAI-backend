import os
from pathlib import Path
import torch
from app.ml.architecture import BrainMRIClassifier


def generate_default_weights(output_path: str = "./models/brain_mri_resnet50_v1.pt"):
    """
    Initializes BrainMRIClassifier and saves structured PyTorch checkpoint.
    """
    path = Path(output_path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Creating PyTorch Brain MRI model architecture...")
    model = BrainMRIClassifier(num_classes=4)
    model.eval()

    # Create dummy checkpoint metadata
    checkpoint = {
        "model_name": "BrainMRIClassifier",
        "version": "1.0.0",
        "architecture": "Custom-CNN-4Class",
        "supported_classes": ["no_tumor", "glioma", "meningioma", "pituitary"],
        "state_dict": model.state_dict(),
    }

    torch.save(checkpoint, path)
    print(f"Model saved successfully at: {path}")


if __name__ == "__main__":
    generate_default_weights()
