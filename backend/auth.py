"""
AEGIS Auth — JWT authentication for government layer.
Uses hashlib + hmac for password hashing (no cryptography dependency).
"""
import hashlib
import hmac
import json
import base64
import time
import os
from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from database import get_db
from models import GovernmentUser
from config import JWT_SECRET, JWT_ALGORITHM, JWT_EXPIRATION_HOURS

security = HTTPBearer()

# ── Password Hashing (hashlib-based, no external deps) ────

_SALT_LENGTH = 16


def hash_password(password: str) -> str:
    """Hash password with random salt using SHA-256."""
    salt = os.urandom(_SALT_LENGTH).hex()
    hashed = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000).hex()
    return f"{salt}${hashed}"


def verify_password(plain: str, stored: str) -> bool:
    """Verify password against stored hash."""
    try:
        salt, hashed = stored.split('$', 1)
        check = hashlib.pbkdf2_hmac('sha256', plain.encode(), salt.encode(), 100000).hex()
        return hmac.compare_digest(check, hashed)
    except Exception:
        return False


# ── JWT (manual implementation, no PyJWT dependency) ──────

def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode()


def _b64url_decode(s: str) -> bytes:
    s += '=' * (4 - len(s) % 4)
    return base64.urlsafe_b64decode(s)


def create_access_token(username: str) -> str:
    """Create a JWT token using HMAC-SHA256."""
    header = _b64url_encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    now = int(time.time())
    payload_data = {
        "sub": username,
        "iat": now,
        "exp": now + int(JWT_EXPIRATION_HOURS * 3600),
    }
    payload = _b64url_encode(json.dumps(payload_data).encode())
    signature_input = f"{header}.{payload}".encode()
    signature = _b64url_encode(
        hmac.new(JWT_SECRET.encode(), signature_input, hashlib.sha256).digest()
    )
    return f"{header}.{payload}.{signature}"


def decode_token(token: str) -> dict:
    """Decode and verify a JWT token."""
    try:
        parts = token.split('.')
        if len(parts) != 3:
            raise ValueError("Invalid token format")

        header_b64, payload_b64, signature_b64 = parts

        # Verify signature
        signature_input = f"{header_b64}.{payload_b64}".encode()
        expected_sig = _b64url_encode(
            hmac.new(JWT_SECRET.encode(), signature_input, hashlib.sha256).digest()
        )
        if not hmac.compare_digest(expected_sig, signature_b64):
            raise ValueError("Invalid signature")

        # Decode payload
        payload = json.loads(_b64url_decode(payload_b64))

        # Check expiration
        if payload.get("exp", 0) < int(time.time()):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token expired",
            )

        return payload

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> GovernmentUser:
    payload = decode_token(credentials.credentials)
    username = payload.get("sub")
    user = db.query(GovernmentUser).filter(GovernmentUser.username == username).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    return user


def seed_admin(db: Session):
    """Create default admin user if none exists."""
    from config import DEFAULT_ADMIN_USER, DEFAULT_ADMIN_PASS
    existing = db.query(GovernmentUser).filter(
        GovernmentUser.username == DEFAULT_ADMIN_USER
    ).first()
    if not existing:
        admin = GovernmentUser(
            username=DEFAULT_ADMIN_USER,
            hashed_password=hash_password(DEFAULT_ADMIN_PASS),
        )
        db.add(admin)
        db.commit()
