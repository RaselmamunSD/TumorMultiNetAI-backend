import io
import hashlib
from typing import Dict, Optional, Tuple
from PIL import Image
from app.core.config import settings
from app.core.exceptions import (
    FileTooLargeException,
    InvalidImageException,
    UnsupportedFormatException,
)

# Magic numbers signatures for fast and safe file verification
MAGIC_NUMBERS = {
    b"\xff\xd8\xff": "image/jpeg",
    b"\x89PNG\r\n\x1a\n": "image/png",
    b"DICM": "application/dicom",
}


class ImageValidationService:
    """
    Validates uploaded medical images for integrity, security, dimensions, and format.
    Ensures safe handling of DICOM and standard images.
    """
    @staticmethod
    def calculate_sha256(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    @staticmethod
    def validate_file_size(file_bytes: bytes) -> None:
        max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
        if len(file_bytes) > max_bytes:
            raise FileTooLargeException(
                f"File size ({len(file_bytes) / (1024*1024):.2f}MB) exceeds maximum permitted limit of {settings.MAX_UPLOAD_SIZE_MB}MB."
            )
        if len(file_bytes) < 100:  # Suspiciously small file
            raise InvalidImageException("File is empty or too small to be a valid MRI image.")

    @staticmethod
    def validate_and_inspect_image(
        file_bytes: bytes, filename: str, content_type: Optional[str] = None
    ) -> Tuple[str, Optional[int], Optional[int], str]:
        """
        Validates magic numbers, format, and dimensions.
        Returns: (detected_mime_type, width, height, modality)
        """
        ImageValidationService.validate_file_size(file_bytes)

        ext = f".{filename.lower().split('.')[-1]}" if "." in filename else ""
        if ext not in settings.ALLOWED_EXTENSIONS:
            raise UnsupportedFormatException(
                f"Unsupported file extension '{ext}'. Allowed: {', '.join(settings.ALLOWED_EXTENSIONS)}"
            )

        # Check DICOM
        if ext == ".dcm" or (len(file_bytes) > 132 and file_bytes[128:132] == b"DICM"):
            try:
                import pydicom
                dataset = pydicom.dcmread(io.BytesIO(file_bytes), force=True)
                # Verify required pixel data
                if not hasattr(dataset, "pixel_array"):
                    raise InvalidImageException("DICOM file contains no readable pixel data.")
                
                rows = getattr(dataset, "Rows", None)
                cols = getattr(dataset, "Columns", None)
                modality = getattr(dataset, "Modality", "MR")
                
                # Check for reasonable MRI dimensions
                if rows and cols and (rows < 32 or cols < 32 or rows > 4096 or cols > 4096):
                    raise InvalidImageException(f"Invalid MRI dimensions: {cols}x{rows}.")

                return "application/dicom", cols, rows, modality
            except Exception as e:
                raise InvalidImageException(f"Failed to parse DICOM header: {str(e)}")

        # Check standard formats (PNG / JPEG)
        is_jpeg = file_bytes.startswith(b"\xff\xd8\xff")
        is_png = file_bytes.startswith(b"\x89PNG\r\n\x1a\n")

        if not (is_jpeg or is_png):
            raise UnsupportedFormatException("Image content does not match allowed magic byte headers.")

        try:
            pil_image = Image.open(io.BytesIO(file_bytes))
            pil_image.verify()  # Verify integrity without decoding entire image

            # Re-open to read dimensions safely (verify destroys image instance in PIL)
            pil_image = Image.open(io.BytesIO(file_bytes))
            width, height = pil_image.size

            # Decompression bomb and minimum dimension check
            if width < 32 or height < 32:
                raise InvalidImageException(f"Image dimensions ({width}x{height}) too small for clinical evaluation.")
            if width > 4096 or height > 4096:
                raise InvalidImageException(f"Image dimensions ({width}x{height}) exceed maximum allowed dimension (4096px).")

            detected_mime = "image/png" if is_png else "image/jpeg"
            return detected_mime, width, height, "MRI"

        except Exception as e:
            raise InvalidImageException(f"Image validation failed: {str(e)}")
