import base64
import hashlib
import hmac
import json
import os
from pathlib import Path

_SCHEME = "pbkdf2_sha256"
_ITERATIONS = 200000


def hash_password(password: str) -> str:
    """Return `pbkdf2_sha256$<iters>$<salt_b64>$<hash_b64>`."""
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _ITERATIONS)
    return (
        f"{_SCHEME}${_ITERATIONS}$"
        f"{base64.b64encode(salt).decode('ascii')}$"
        f"{base64.b64encode(digest).decode('ascii')}"
    )


def verify_password(password: str, encoded: str) -> bool:
    """Constant-time verify. False on any parse failure."""
    try:
        scheme, iters_str, salt_b64, hash_b64 = encoded.split("$")
        if scheme != _SCHEME:
            return False
        iters = int(iters_str)
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(hash_b64)
    except (ValueError, TypeError):
        return False

    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iters)
    return hmac.compare_digest(actual, expected)


def load_users(path: Path | None) -> dict[str, str]:
    """Return {username: encoded_hash}. Empty dict if file missing."""
    if path is None or not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    users = raw.get("users") if isinstance(raw, dict) else None
    if not isinstance(users, dict):
        return {}
    return {k: v for k, v in users.items() if isinstance(k, str) and isinstance(v, str)}


def save_users(path: Path, users: dict[str, str]) -> None:
    """Atomically write users dict to `path`, mode 0600."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps({"users": users}, indent=2, sort_keys=True))
    try:
        os.chmod(tmp, 0o600)
    except Exception:
        pass
    tmp.replace(path)


def check_basic_auth(
    authorization_header: str | None, users: dict[str, str]
) -> str | None:
    """Verify a `Basic <b64>` header against `users`. Returns username on success."""
    if not authorization_header or not authorization_header.startswith("Basic "):
        return None
    try:
        raw = base64.b64decode(authorization_header[6:].strip(), validate=True)
        username, _, password = raw.decode("utf-8").partition(":")
    except (ValueError, UnicodeDecodeError):
        return None
    if not username:
        return None
    encoded = users.get(username)
    if encoded is None:
        return None
    if not verify_password(password, encoded):
        return None
    return username