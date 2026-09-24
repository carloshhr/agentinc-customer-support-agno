"""Password, session, origin, and CSRF primitives."""

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

LOCKOUT_ATTEMPTS = 5
LOCKOUT_MINUTES = 15
password_hasher = PasswordHasher()


@dataclass(frozen=True)
class SessionPolicy:
    idle_seconds: int = 30 * 60
    absolute_seconds: int = 8 * 60 * 60


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(encoded: str, password: str) -> bool:
    try:
        return password_hasher.verify(encoded, password)
    except (InvalidHashError, VerificationError, VerifyMismatchError):  # fmt: skip
        return False


def digest_token(token: str) -> bytes:
    return hashlib.sha256(token.encode("utf-8")).digest()


def new_token() -> str:
    return secrets.token_urlsafe(32)


def is_session_expired(
    created_at: datetime, idle_expires_at: datetime, absolute_expires_at: datetime, policy: SessionPolicy, now: datetime
) -> bool:
    del created_at, policy
    return now >= idle_expires_at or now >= absolute_expires_at


def check_origin(origin: str | None, allowed: set[str]) -> bool:
    return origin is not None and origin in allowed


def csrf_matches(expected_digest: bytes, supplied: str) -> bool:
    return hmac.compare_digest(expected_digest, digest_token(supplied))


def lockout_deadline(now: datetime) -> datetime:
    return now + timedelta(minutes=LOCKOUT_MINUTES)


def record_failed_attempt(count: int, now: datetime) -> tuple[int, datetime | None]:
    next_count = count + 1
    return next_count, lockout_deadline(now) if next_count >= LOCKOUT_ATTEMPTS else None
