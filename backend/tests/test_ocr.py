"""
Tests for src/ocr.py. These run against the REAL Tesseract engine (not
mocked) since it's a system binary, not a network call -- fully testable
in any environment that has it installed. If Tesseract isn't installed,
these tests will fail with a clear OcrUnavailableError rather than an
unrelated crash, which is itself useful signal.
"""
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image, ImageDraw, ImageFont
from src.ocr import extract_text_from_image, OcrUnavailableError


def _make_test_image(lines):
    img = Image.new("RGB", (900, 300), color="white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 26)
    except Exception:
        font = ImageFont.load_default()
    y = 30
    for line in lines:
        draw.text((30, y), line, font=font, fill="black")
        y += 40
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_extracts_drug_lines_from_a_clean_image():
    image_bytes = _make_test_image([
        "Prescribe Metformin 500mg oral twice daily",
        "for type 2 diabetes.",
    ])
    text = extract_text_from_image(image_bytes)
    assert "Metformin" in text, f"Expected 'Metformin' in OCR output, got: {text!r}"
    assert "500mg" in text or "500" in text, f"Expected dose in OCR output, got: {text!r}"
    print("PASS: extracts drug name and dose from a clean synthetic image")


def test_non_image_bytes_raise_value_error():
    try:
        extract_text_from_image(b"not an image at all")
        assert False, "Expected ValueError for non-image bytes"
    except ValueError:
        print("PASS: non-image bytes raise ValueError")


def test_blank_image_returns_empty_string_not_error():
    blank = Image.new("RGB", (200, 200), color="white")
    buf = io.BytesIO()
    blank.save(buf, format="PNG")
    text = extract_text_from_image(buf.getvalue())
    assert text == "", f"Expected empty string for a blank image, got: {text!r}"
    print("PASS: a blank image returns an empty string rather than raising")


def test_full_pipeline_from_ocr_text():
    """Confirms OCR output feeds cleanly into the existing parser/pipeline
    with no special-casing needed -- this is the actual point of the
    feature, not just that OCR works in isolation."""
    import src.config as config
    config.EMBEDDING_BACKEND = "tfidf"  # avoid needing a live model download here
    from src.graph import run_pipeline

    image_bytes = _make_test_image([
        "Patient on Warfarin 5mg oral once daily is",
        "additionally prescribed Ibuprofen 400mg",
        "oral three times daily.",
    ])
    ocr_text = extract_text_from_image(image_bytes)
    result = run_pipeline(ocr_text, "atrial fibrillation", ["INR"])

    drug_names = [d["name"] for d in result["parsed_drugs"]]
    assert "warfarin" in drug_names and "ibuprofen" in drug_names, f"Got: {drug_names}"
    violation_types = [v["type"] for v in result["violations"]]
    assert "drug-drug interaction" in violation_types, f"Got: {violation_types}"
    print("PASS: OCR output flows end-to-end through the full verification pipeline")


if __name__ == "__main__":
    try:
        test_extracts_drug_lines_from_a_clean_image()
        test_non_image_bytes_raise_value_error()
        test_blank_image_returns_empty_string_not_error()
        test_full_pipeline_from_ocr_text()
        print("\nAll OCR tests passed.")
    except OcrUnavailableError as e:
        print(f"SKIPPED: Tesseract engine not installed on this system: {e}")
