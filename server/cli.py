"""CLI entry: `python -m server.cli <subcommand>`.

Subcommands:
    add-user <username>              # reads password from stdin
    create-repo <name>               # creates a bare repo (supports nested paths)
    list-repos                       # lists all repos under MYGIT_REPOS_ROOT
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from .auth import hash_password, load_users, save_users
from .config import load_config
from .repos import is_valid_repo_name


def cmd_add_user(username: str) -> int:
    cfg = load_config()
    if cfg.auth_file is None:
        print(
            "error: MYGIT_AUTH_FILE env var is not set.",
            file=sys.stderr,
        )
        return 2

    password = sys.stdin.readline().rstrip("\n")
    if not password:
        print("error: empty password", file=sys.stderr)
        return 2

    auth_file: Path = cfg.auth_file
    users = load_users(auth_file if auth_file.exists() else None)
    users[username] = hash_password(password)
    save_users(auth_file, users)
    print(f"user '{username}' written to {auth_file}")
    return 0


def cmd_create_repo(name: str) -> int:
    if not is_valid_repo_name(name):
        print(f"error: invalid repo name '{name}'", file=sys.stderr)
        return 2

    cfg = load_config()
    bare = name if name.endswith(".git") else f"{name}.git"
    target = cfg.repos_root / bare

    target.parent.mkdir(parents=True, exist_ok=True)

    r = subprocess.run(
        ["git", "init", "--bare", "-b", "main", str(target)],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        print(f"error: git init failed: {r.stderr}", file=sys.stderr)
        return 1

    r = subprocess.run(
        ["git", "-C", str(target), "config", "http.receivepack", "true"],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        print(f"error: git config failed: {r.stderr}", file=sys.stderr)
        return 1

    print(f"created bare repo at {target}")
    return 0


def cmd_list_repos() -> int:
    cfg = load_config()
    repos = sorted(cfg.repos_root.glob("**/*.git"))
    if not repos:
        print("no repositories")
        return 0

    for repo_path in repos:
        rel = repo_path.relative_to(cfg.repos_root)
        name = str(rel)[:-4]
        print(name)
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if not argv:
        print(__doc__, file=sys.stderr)
        return 2
    cmd, *rest = argv
    if cmd == "add-user":
        if len(rest) != 1:
            print("usage: add-user <username>", file=sys.stderr)
            return 2
        return cmd_add_user(rest[0])
    elif cmd == "create-repo":
        if len(rest) != 1:
            print("usage: create-repo <name>", file=sys.stderr)
            return 2
        return cmd_create_repo(rest[0])
    elif cmd == "list-repos":
        if rest:
            print("usage: list-repos", file=sys.stderr)
            return 2
        return cmd_list_repos()
    print(f"unknown command: {cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())