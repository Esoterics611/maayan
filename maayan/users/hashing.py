"""Password hashing using only the standard library (PBKDF2-HMAC-SHA256).

No external dependency — keeps the install light (CLAUDE.md). The stored value is
self-describing: ``pbkdf2_sha256$<iterations>$<salt_hex>$<hash_hex>``. Verification reads
the iteration count from the stored string, so raising the config default later does not
invalidate existing hashes. Comparison is constant-time (`hmac.compare_digest`).
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

_ALGO = "pbkdf2_sha256"
_SALT_BYTES = 16
_DK_LEN = 32


def hash_password(password: str, *, iterations: int) -> str:
    """Hash a password into the self-describing storage string. Random per-call salt."""
    if not password:
        raise ValueError("password must not be empty")
    salt = secrets.token_bytes(_SALT_BYTES)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations, dklen=_DK_LEN)
    return f"{_ALGO}${iterations}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Constant-time check against a stored hash string. False on any malformed input."""
    try:
        algo, iter_s, salt_hex, hash_hex = stored.split("$")
        if algo != _ALGO:
            return False
        iterations = int(iter_s)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(hash_hex)
    except (ValueError, AttributeError):
        return False
    dk = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, iterations, dklen=len(expected)
    )
    return hmac.compare_digest(dk, expected)
