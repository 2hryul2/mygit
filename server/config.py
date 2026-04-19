import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Config:
    port: int
    repos_root: Path
    auth_file: Path | None
    allow_anonymous_read: bool
    allow_anonymous_write: bool


def _read_bool(env: str, default: bool) -> bool:
    val = os.environ.get(env)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


def load_config() -> Config:
    repos_root = Path(
        os.environ.get("MYGIT_REPOS_ROOT", str(Path(__file__).parent.parent / "repos"))
    ).resolve()
    repos_root.mkdir(parents=True, exist_ok=True)

    auth_raw = os.environ.get("MYGIT_AUTH_FILE")
    auth_file = Path(auth_raw).resolve() if auth_raw else None

    return Config(
        port=int(os.environ.get("MYGIT_PORT", "8000")),
        repos_root=repos_root,
        auth_file=auth_file,
        allow_anonymous_read=_read_bool("MYGIT_ALLOW_ANONYMOUS_READ", False),
        allow_anonymous_write=_read_bool("MYGIT_ALLOW_ANONYMOUS_WRITE", False),
    )
