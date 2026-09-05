import numpy as np
import pytest
import torch
from app.ml.architecture import BrainMRIClassifier
from app.ml.preprocessing import MRIPreprocessor, load_image_bytes, apply_clahe_enhancement
from app.ml.postprocessing import MRIPostprocessor
from app.ml.predictor import ModelService
from app.ml.explainability import GradCAM, create_heatmap_and_overlay


def test_brain_mri_classifier_forward():
    model = BrainMRIClassifier(num_classes=4)
    model.eval()
    dummy_input = torch.randn(2, 3, 224, 224)
    output = model(dummy_input)
    assert output.shape == (2, 4)


def test_mri_preprocessing_pipeline(sample_mri_png_bytes):
    preprocessor = MRIPreprocessor(target_size=(224, 224), use_clahe=True)
    tensor, rgb_resized = preprocessor.preprocess(sample_mri_png_bytes, "scan.png")
    
    assert tensor.shape == (1, 3, 224, 224)
    assert rgb_resized.shape == (224, 224, 3)
    assert isinstance(tensor, torch.Tensor)


def test_postprocessor_normal_output():
    postprocessor = MRIPostprocessor()
    # Logits strongly favoring no_tumor (index 0)
    logits = torch.tensor([[10.0, 1.0, 0.5, 0.2]])
    result = postprocessor.process(logits)

    assert result["predicted_class"] == "no_tumor"
    assert result["is_abnormal"] is False
    assert result["confidence"] > 0.90
    assert "No abnormality pattern detected" in result["screening_label"]
    assert "disclaimer" in result


def test_postprocessor_tumor_suspected_output():
    postprocessor = MRIPostprocessor()
    # Logits strongly favoring glioma (index 1)
    logits = torch.tensor([[1.0, 9.5, 2.0, 0.5]])
    result = postprocessor.process(logits)

    assert result["predicted_class"] == "glioma"
    assert result["is_abnormal"] is True
    assert result["confidence"] > 0.90
    assert "Abnormality pattern suspected" in result["screening_label"]


def test_gradcam_and_overlay_generation(sample_mri_png_bytes):
    service = ModelService()
    heatmap_bytes, overlay_bytes, pred = service.explain(sample_mri_png_bytes, "scan.png")

    assert isinstance(heatmap_bytes, bytes)
    assert len(heatmap_bytes) > 0
    assert isinstance(overlay_bytes, bytes)
    assert len(overlay_bytes) > 0
    assert "predicted_class" in pred
