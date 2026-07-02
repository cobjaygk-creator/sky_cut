import base64
import hashlib
import hmac
import json
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import HTTPException, status

from app.core.config import settings


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 210_000)
    return "pbkdf2_sha256$210000$" + base64.urlsafe_b64encode(salt).decode("ascii") + "$" + base64.urlsafe_b64encode(digest).decode("ascii")


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, iterations, salt_b64, digest_b64 = stored_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        salt = base64.urlsafe_b64decode(salt_b64.encode("ascii"))
        expected = base64.urlsafe_b64decode(digest_b64.encode("ascii"))
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(iterations))
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode((data + padding).encode("ascii"))


def create_access_token(subject: str) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.jwt_expire_minutes)).timestamp()),
    }
    header = {"alg": settings.jwt_algorithm, "typ": "JWT"}
    signing_input = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8")) + "." + _b64url_encode(
        json.dumps(payload, separators=(",", ":")).encode("utf-8")
    )
    signature = hmac.new(settings.jwt_secret_key.encode("utf-8"), signing_input.encode("ascii"), hashlib.sha256).digest()
    return signing_input + "." + _b64url_encode(signature)


def decode_access_token(token: str) -> dict[str, Any]:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        header_b64, payload_b64, signature_b64 = token.split(".")
        signing_input = header_b64 + "." + payload_b64
        expected_signature = hmac.new(
            settings.jwt_secret_key.encode("utf-8"), signing_input.encode("ascii"), hashlib.sha256
        ).digest()
        actual_signature = _b64url_decode(signature_b64)
        if not hmac.compare_digest(actual_signature, expected_signature):
            raise credentials_error
        header = json.loads(_b64url_decode(header_b64))
        payload = json.loads(_b64url_decode(payload_b64))
        if header.get("alg") != settings.jwt_algorithm:
            raise credentials_error
        if int(payload.get("exp", 0)) < int(datetime.now(UTC).timestamp()):
            raise credentials_error
        return payload
    except (ValueError, json.JSONDecodeError, TypeError):
        raise credentials_error from None
