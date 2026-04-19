import re
from pathlib import Path

_NAME_RE = re.compile(r"^[A-Za-z0-9._-]+(/[A-Za-z0-9._-]+)*$")


def is_valid_repo_name(name: str) -> bool:
    if not name or name.startswith("/"):
        return False
    if ".." in name.split("/"):
        return False
    return bool(_NAME_RE.match(name))


def resolve_repo(name: str, repos_root: Path) -> Path | None:
    bare = name if name.endswith(".git") else f"{name}.git"
    stripped = bare[:-4]
    if not is_valid_repo_name(stripped):
        return None

    candidate = (repos_root / bare).resolve()
    try:
        if not candidate.is_relative_to(repos_root):
            return None
    except ValueError:
        return None

    if not candidate.is_dir():
        return None
    if not (candidate / "HEAD").is_file():
        return None
    return candidate
