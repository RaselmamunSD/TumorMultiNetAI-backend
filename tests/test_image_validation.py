import pytest
from app.core.exceptions import (
    FileTooLargeException,
    InvalidImageException,
    UnsupportedFormatException,
)
from app.services.validation_service import ImageValidationService


def test_valid_png_validation(sample_mri_png_bytes):
    mime, w, h, modality = ImageValidationService.validate_and_inspect_image(
        sample_mri_png_bytes, "test_scan.png"
    )
    assert mime == "image/png"
    assert w == 256
    assert h == 256
    assert modality == "MRI"


def test_valid_jpeg_validation(sample_mri_jpeg_bytes):
    mime, w, h, modality = ImageValidationService.validate_and_inspect_image(
        sample_mri_jpeg_bytes, "brain_scan.jpeg"
    )
    assert mime == "image/jpeg"
    assert w == 256
    assert h == 256


def test_unsupported_file_extension():
    fake_data = b"Some random executable code or text file"
    with pytest.raises(UnsupportedFormatException):
        ImageValidationService.validate_and_inspect_image(fake_data, "malicious.exe")


def test_corrupted_image_header():
    corrupted_data = b"\x89PNG\r\n\x1a\nCorruptedGarbageData"
    with pytest.raises(InvalidImageException):
        ImageValidationService.validate_and_inspect_image(corrupted_data, "broken.png")


def test_oversized_image():
    # 51MB dummy bytes
    oversized_data = b"0" * (51 * 1024 * 1024)
    with pytest.raises(FileTooLargeException):
        ImageValidationService.validate_file_size(oversized_data)
