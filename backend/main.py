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

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from src.config import SAMPLE_PRESCRIPTIONS_FILE, KNOWN_DRUGS, KNOWN_DIAGNOSES, LIVE_FDA_RETRIEVAL_ENABLED, EMBEDDING_BACKEND, PARSER_BACKEND
from src.graph import run_pipeline
from src.auth import hash_password, verify_password, create_access_token, decode_access_token
from src.db import init_db, get_db, User, VerificationHistory, save_verification

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
    ordered_tests: List[str] = []


@app.post("/api/verify")
def verify(
    req: VerifyRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Runs the full 5-agent pipeline, saves the run to the logged-in
    user's history, and returns the complete result state."""
    result = run_pipeline(req.raw_text, req.diagnosis_hint or "", req.ordered_tests)
    save_verification(db, user.id, req.raw_text, req.diagnosis_hint, result)
    return result


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
