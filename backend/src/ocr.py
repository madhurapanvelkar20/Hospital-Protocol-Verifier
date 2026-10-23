"""
OCR: extracts raw text from a photographed/scanned prescription image,
using Tesseract (via pytesseract).

Precedent: Rx Strategist and the MEDIC prescription-checking system both
start from an OCR'd image rather than typed text, feeding the extracted
text into the same downstream parsing/verification pipeline used for
typed input. This module follows that same pattern -- it does NOT try to
parse structured fields itself; it just returns raw text, which is then
handed to the existing Prescription Parser Agent unchanged.

IMPORTANT: OCR output is shown to the user for review/editing before
verification runs, never submitted automatically -- prescription
handwriting and even printed text can be misread, and a silently
mis-OCR'd drug name or dose is exactly the kind of error this whole
project exists to catch, not introduce.

REQUIRES the Tesseract OCR *engine* to be installed on the system
separately from the `pytesseract` Python package (pytesseract is just a
wrapper that shells out to the `tesseract` binary). See README.md for
platform-specific install instructions -- this is the one feature in the
project that needs a non-Python system dependency.
"""

import io

from PIL import Image, ImageOps, ImageFilter


class OcrUnavailableError(Exception):
    """Raised when the Tesseract binary itself isn't installed/found on
    this system -- distinct from a normal 'couldn't read this image'
    failure, so the API can return a clear, actionable error message."""


class OcrProcessingError(Exception):
    """Raised when Tesseract is present but cannot process a readable image."""


def _preprocess(image: Image.Image) -> Image.Image:
    """Light preprocessing to help OCR accuracy on prescription-style
    text: convert to grayscale, boost contrast, and upscale small images.
    This is intentionally simple (no deskew/denoise) -- good enough for a
    reasonably clear photo, not a scanner-grade pipeline."""
    image = image.convert("L")  # grayscale
    image = ImageOps.autocontrast(image)
    if image.width < 1200:
        scale = 1200 / image.width
        image = image.resize((int(image.width * scale), int(image.height * scale)), Image.LANCZOS)
    image = image.filter(ImageFilter.SHARPEN)
    return image


def extract_text_from_image(image_bytes: bytes) -> str:
    """Runs OCR on raw image bytes and returns the extracted text.

    Raises OcrUnavailableError if the Tesseract binary isn't installed.
    Raises ValueError if the bytes aren't a readable image.
    Returns "" (not an error) if Tesseract runs but finds no text --
    that's a valid outcome for a blank/unreadable photo, not a bug.
    """
    import pytesseract
    from pytesseract import TesseractError, TesseractNotFoundError

    try:
        image = Image.open(io.BytesIO(image_bytes))
        image.load()
    except (OSError, ValueError, SyntaxError, Image.DecompressionBombError) as e:
        raise ValueError(f"Could not read this file as an image: {e}")

    processed = _preprocess(image)

    try:
        text = pytesseract.image_to_string(processed)
    except TesseractNotFoundError:
        raise OcrUnavailableError(
            "The Tesseract OCR engine isn't installed on this machine. "
            "See README.md for install instructions."
        )
    except TesseractError as e:
        raise OcrProcessingError(
            "Tesseract could not process this image. Try a clearer PNG or JPEG image."
        ) from e

    return text.strip()
