from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
import uuid
from typing import Any


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 600_000)
    salt_text = base64.urlsafe_b64encode(salt).decode()
    digest_text = base64.urlsafe_b64encode(derived).decode()
    return f"pbkdf2_sha256$600000${salt_text}${digest_text}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, rounds, salt_text, digest_text = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        salt = base64.urlsafe_b64decode(salt_text)
        expected = base64.urlsafe_b64decode(digest_text)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, int(rounds))
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def _encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def create_access_token(user_id: uuid.UUID, secret: str, lifetime_minutes: int) -> str:
    header = _encode(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = _encode(
        json.dumps(
            {"sub": str(user_id), "exp": int(time.time()) + lifetime_minutes * 60},
            separators=(",", ":"),
        ).encode()
    )
    signature = _encode(
        hmac.new(secret.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest()
    )
    return f"{header}.{payload}.{signature}"


def decode_access_token(token: str, secret: str) -> uuid.UUID | None:
    try:
        header, payload, signature = token.split(".")
        expected = _encode(
            hmac.new(secret.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest()
        )
        if not hmac.compare_digest(signature, expected):
            return None
        data: dict[str, Any] = json.loads(_decode(payload))
        if int(data["exp"]) < int(time.time()):
            return None
        return uuid.UUID(str(data["sub"]))
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        return None
