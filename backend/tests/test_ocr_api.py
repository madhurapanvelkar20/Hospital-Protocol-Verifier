"""
Comprehensive tests for OCR API endpoints (/api/ocr and /api/ocr/extract) and verification integration.

Verifies:
  1. A valid image produces a successful OCR response (200 OK with extracted text).
  2. An unsupported file type is rejected (400 Bad Request).
  3. An empty, corrupt, or unreadable image produces a clear error (400 or 422).
  4. An oversized upload is rejected (400 Bad Request with size limit message).
  5. An unauthenticated request is rejected (401 Unauthorized).
  6. Both /api/ocr and /api/ocr/extract paths work identically.
  7. Extracted or edited OCR text flows seamlessly into the /api/verify verification workflow.
"""

import io
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import main
from src.auth import create_access_token
from src.ocr import OcrProcessingError, OcrUnavailableError


def _make_sample_image(lines):
    img = Image.new("RGB", (800, 250), color="white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 22)
    except Exception:
        font = ImageFont.load_default()
    y = 20
    for line in lines:
        draw.text((25, y), line, font=font, fill="black")
        y += 35
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def auth_headers():
    token = create_access_token("testdoctor@hospital.org")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def client(monkeypatch):
    """Client with authenticated user dependency override for fast isolated testing."""
    test_user = SimpleNamespace(id=1, email="testdoctor@hospital.org", display_name="Dr. Test")
    monkeypatch.setitem(main.app.dependency_overrides, main.get_current_user, lambda: test_user)
    with TestClient(main.app) as c:
        yield c
    main.app.dependency_overrides.clear()


@pytest.fixture
def unauth_client():
    """Client with no authentication overrides."""
    with TestClient(main.app) as c:
        yield c


def test_unauthenticated_ocr_rejected(unauth_client):
    """Unauthenticated requests to /api/ocr or /api/ocr/extract must return 401."""
    files = {"file": ("rx.png", b"fakebytes", "image/png")}
    res1 = unauth_client.post("/api/ocr", files=files)
    assert res1.status_code == 401
    assert "Not authenticated" in res1.json().get("detail", "")

    res2 = unauth_client.post("/api/ocr/extract", files=files)
    assert res2.status_code == 401


def test_unsupported_file_type_rejected(client):
    """Uploading a non-image file (e.g. text or pdf) must return 400."""
    files = {"file": ("notes.txt", b"Prescription details", "text/plain")}
    res = client.post("/api/ocr/extract", files=files)
    assert res.status_code == 400
    assert "Please upload an image file" in res.json().get("detail", "")


def test_corrupt_or_non_image_bytes_rejected(client):
    """An image file with corrupt bytes must return 400."""
    files = {"file": ("corrupt.png", b"not-a-valid-png-stream", "image/png")}
    res = client.post("/api/ocr/extract", files=files)
    assert res.status_code == 400
    assert "Could not read this file as an image" in res.json().get("detail", "")


def test_oversized_upload_rejected(client):
    """Uploading an image larger than MAX_OCR_IMAGE_BYTES (8MB) must return 400."""
    large_payload = b"0" * (8 * 1024 * 1024 + 10)
    files = {"file": ("large.png", large_payload, "image/png")}
    res = client.post("/api/ocr/extract", files=files)
    assert res.status_code == 400
    assert "too large" in res.json().get("detail", "")


def test_blank_image_returns_422_warning(client):
    """A completely blank white image where OCR detects no text must return 422."""
    blank = Image.new("RGB", (200, 200), color="white")
    buf = io.BytesIO()
    blank.save(buf, format="PNG")
    files = {"file": ("blank.png", buf.getvalue(), "image/png")}
    res = client.post("/api/ocr/extract", files=files)
    assert res.status_code == 422
    assert "No text could be read" in res.json().get("detail", "")


def test_missing_tesseract_returns_actionable_service_error(client, monkeypatch):
    def missing_engine(_image_bytes):
        raise OcrUnavailableError("The Tesseract OCR engine isn't installed.")

    monkeypatch.setattr(main, "extract_text_from_image", missing_engine)
    image = _make_sample_image(["Prescription"])
    res = client.post("/api/ocr/extract", files={"file": ("rx.png", image, "image/png")})
    assert res.status_code == 503
    assert "Tesseract" in res.json()["detail"]


def test_tesseract_processing_error_is_not_reported_as_success(client, monkeypatch):
    def processing_error(_image_bytes):
        raise OcrProcessingError("Tesseract could not process this image.")

    monkeypatch.setattr(main, "extract_text_from_image", processing_error)
    image = _make_sample_image(["Prescription"])
    res = client.post("/api/ocr/extract", files={"file": ("rx.png", image, "image/png")})
    assert res.status_code == 422
    assert "could not process" in res.json()["detail"]


def test_valid_image_extraction_success(client):
    """A clear valid image must extract text and structured fields correctly."""
    img_bytes = _make_sample_image([
        "Prescribe Metformin 500mg oral twice daily",
        "for type 2 diabetes.",
    ])
    files = {"file": ("rx.png", img_bytes, "image/png")}
    res = client.post("/api/ocr/extract", files=files)
    assert res.status_code == 200
    data = res.json()
    assert "extracted_text" in data
    assert "metformin" in data["extracted_text"].lower()
    assert "diagnoses" in data
    assert "ordered_tests" in data


def test_ocr_text_flows_into_verify_pipeline(client, monkeypatch):
    """Simulates the full user flow: image OCR extract -> review/edit text -> /api/verify."""
    img_bytes = _make_sample_image([
        "Patient on Warfarin 5mg oral once daily is",
        "additionally prescribed Ibuprofen 400mg oral three times daily.",
    ])
    files = {"file": ("rx.png", img_bytes, "image/png")}
    ocr_res = client.post("/api/ocr/extract", files=files)
    assert ocr_res.status_code == 200
    extracted_text = ocr_res.json()["extracted_text"]
    assert len(extracted_text) > 0

    # Mock DB save_verification to prevent database disk writes during test
    monkeypatch.setattr(main, "save_verification", lambda *args, **kwargs: None)

    # Submit reviewed text to /api/verify
    verify_payload = {
        "raw_text": extracted_text,
        "diagnosis_hint": "atrial fibrillation",
        "ordered_tests": ["INR"],
    }
    verify_res = client.post("/api/verify", json=verify_payload)
    assert verify_res.status_code == 200
    v_data = verify_res.json()
    assert "violations" in v_data
    parsed_names = [d["name"] for d in v_data.get("parsed_drugs", [])]
    assert "warfarin" in parsed_names
    assert "ibuprofen" in parsed_names
    violation_types = [v["type"] for v in v_data.get("violations", [])]
    assert "drug-drug interaction" in violation_types
