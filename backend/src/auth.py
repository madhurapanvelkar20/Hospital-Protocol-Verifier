"""
Authentication: password hashing (bcrypt, used directly -- passlib has a
known compatibility bug with modern bcrypt versions where its self-test
fails outright, so this avoids that dependency entirely) and JWT issuing
verification (python-jose).

SECRET_KEY defaults to a fixed dev value so the app runs out of the box,
but that means every install shares the same signing key -- fine for a
student project demo, NOT fine for any real deployment. Set a real
JWT_SECRET_KEY environment variable before deploying this anywhere
outside your own machine.
"""

import os
import bcrypt
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError

SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "dev-only-insecure-secret-change-me")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days -- fine for a demo/exhibition app


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> str | None:
    """Returns the subject (user email) if the token is valid, else None."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None
