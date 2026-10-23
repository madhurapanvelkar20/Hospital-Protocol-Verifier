"""
FastAPI backend for the Hospital Treatment Protocol Verifier.

Wraps the existing LangGraph pipeline (src/graph.py) behind a REST API for
the React frontend, plus authentication (signup/login with JWTs) and a
per-user verification history, backed by SQLite (src/db.py).

Run with:
    uvicorn main:app --reload --port 8000
"""

import json
from typing import List, Optional

from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from src.config import SAMPLE_PRESCRIPTIONS_FILE, KNOWN_DRUGS, KNOWN_DIAGNOSES, LIVE_FDA_RETRIEVAL_ENABLED, EMBEDDING_BACKEND, PARSER_BACKEND
from src.graph import run_pipeline
from src.auth import hash_password, verify_password, create_access_token, decode_access_token
from src.db import init_db, get_db, User, VerificationHistory, save_verification
from src.ocr import extract_text_from_image, OcrUnavailableError, OcrProcessingError
from src.prescription_extract import extract_structured_fields

app = FastAPI(title="Hospital Treatment Protocol Verifier API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

init_db()

security = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """Dependency used to protect an endpoint. Raises 401 if the request
    has no valid bearer token -- there is no "guest" fallback for
    protected routes, by design (see verify_authenticated below)."""
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    email = decode_access_token(credentials.credentials)
    if email is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User no longer exists")
    return user


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    display_name: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    access_token: str
    display_name: str
    email: str


@app.post("/api/auth/signup", response_model=AuthResponse)
def signup(req: SignupRequest, db: Session = Depends(get_db)):
    if len(req.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")
    existing = db.query(User).filter(User.email == req.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="An account with this email already exists.")

    user = User(
        email=req.email,
        display_name=req.display_name.strip() or req.email.split("@")[0],
        hashed_password=hash_password(req.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(subject=user.email)
    return AuthResponse(access_token=token, display_name=user.display_name, email=user.email)


@app.post("/api/auth/login", response_model=AuthResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == req.email).first()
    if user is None or not verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password.")

    token = create_access_token(subject=user.email)
    return AuthResponse(access_token=token, display_name=user.display_name, email=user.email)


@app.get("/api/auth/me")
def me(user: User = Depends(get_current_user)):
    return {"email": user.email, "display_name": user.display_name}


# ---------------------------------------------------------------------------
# Public metadata endpoints (unchanged, no auth needed)
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "live_fda_retrieval_enabled": LIVE_FDA_RETRIEVAL_ENABLED,
        "embedding_backend": EMBEDDING_BACKEND,
        "parser_backend": PARSER_BACKEND,
    }


@app.get("/api/meta")
def meta():
    return {"known_drugs": KNOWN_DRUGS, "known_diagnoses": KNOWN_DIAGNOSES}


@app.get("/api/samples")
def samples():
    with open(SAMPLE_PRESCRIPTIONS_FILE, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Verification (protected) + history
# ---------------------------------------------------------------------------

class VerifyRequest(BaseModel):
    raw_text: str
    diagnosis_hint: Optional[str] = None
    # None  -> field not supplied: fall back to the "tests ordered" section of
    #          raw_text (API clients that send only text).
    # list  -> the user-confirmed list is authoritative, even if empty. It is
    #          NOT merged with a re-scan of raw_text, otherwise lines the user
    #          removed from the field (or OCR header/footer text) would come back.
    ordered_tests: Optional[List[str]] = None


@app.post("/api/verify")
def verify(
    req: VerifyRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Runs the full 5-agent pipeline, saves the run to the logged-in
    user's history, and returns the complete result state."""
    if not req.raw_text.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Prescription text cannot be empty.",
        )

    if req.ordered_tests is None:
        ordered_tests = extract_structured_fields(req.raw_text)["ordered_tests"]
    else:
        ordered_tests = list(dict.fromkeys(t.strip() for t in req.ordered_tests if t and t.strip()))
    result = run_pipeline(req.raw_text, req.diagnosis_hint or "", ordered_tests)
    save_verification(db, user.id, req.raw_text, req.diagnosis_hint, result)
    return result


MAX_OCR_IMAGE_BYTES = 8 * 1024 * 1024  # 8MB
ALLOWED_IMAGE_MIME_TYPES = {"image/png", "image/jpeg", "image/jpg"}


@app.post("/api/ocr")
@app.post("/api/ocr/extract")
async def ocr(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
):
    """Extracts raw text from a photographed/scanned prescription image,
    plus a best-effort structured extraction of any diagnoses and ordered
    tests it can find (see src/prescription_extract.py). Everything is
    returned for the user to REVIEW AND EDIT before verification runs --
    OCR/extraction errors on a drug name, diagnosis, or test are exactly
    the kind of mistake this project exists to catch, not introduce."""
    if not file.content_type or file.content_type.lower() not in ALLOWED_IMAGE_MIME_TYPES:
        raise HTTPException(status_code=400, detail="Please upload an image file (PNG or JPEG).")

    image_bytes = await file.read(MAX_OCR_IMAGE_BYTES + 1)
    if len(image_bytes) > MAX_OCR_IMAGE_BYTES:
        raise HTTPException(status_code=400, detail="Image is too large (max 8MB).")

    try:
        text = extract_text_from_image(image_bytes)
    except OcrUnavailableError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except OcrProcessingError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not text:
        raise HTTPException(
            status_code=422,
            detail="No text could be read from this image. Try a clearer, well-lit photo.",
        )

    fields = extract_structured_fields(text)
    return {
        "extracted_text": text,
        "diagnoses": fields["diagnoses"],
        "ordered_tests": fields["ordered_tests"],
    }


@app.get("/api/history")
def history(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Returns the logged-in user's past verifications, newest first."""
    entries = (
        db.query(VerificationHistory)
        .filter(VerificationHistory.user_id == user.id)
        .order_by(VerificationHistory.created_at.desc())
        .limit(50)
        .all()
    )
    return [
        {
            "id": e.id,
            "raw_text": e.raw_text,
            "diagnosis_hint": e.diagnosis_hint,
            "violation_count": e.violation_count,
            "highest_severity": e.highest_severity,
            "created_at": e.created_at.isoformat(),
            "result": json.loads(e.result_json),
        }
        for e in entries
    ]
