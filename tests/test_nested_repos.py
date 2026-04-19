"""Step 6 tests ? nested repository paths and management CLI."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import requests


def test_create_repo_nested(tmp_path):
    repos_root = tmp_path / "repos"
    repos_root.mkdir()

    r = subprocess.run(
        ["python", "-m", "server.cli", "create-repo", "team/backend"],
        cwd=Path(__file__).parent.parent,
        capture_output=True,
        text=True,
        env={"MYGIT_REPOS_ROOT": str(repos_root)},
    )
    assert r.returncode == 0, r.stderr
    assert "created bare repo at" in r.stdout
    assert (repos_root / "team" / "backend.git" / "HEAD").exists()


def test_list_repos_nested(tmp_path):
    repos_root = tmp_path / "repos"
    repos_root.mkdir()

    for name in ["team/backend", "team/frontend", "core/api"]:
        subprocess.run(
            ["python", "-m", "server.cli", "create-repo", name],
            cwd=Path(__file__).parent.parent,
            capture_output=True,
            env={"MYGIT_REPOS_ROOT": str(repos_root)},
            check=True,
        )

    r = subprocess.run(
        ["python", "-m", "server.cli", "list-repos"],
        cwd=Path(__file__).parent.parent,
        capture_output=True,
        text=True,
        env={"MYGIT_REPOS_ROOT": str(repos_root)},
    )
    assert r.returncode == 0
    lines = r.stdout.strip().split("\n")
    assert set(lines) == {"team/backend", "team/frontend", "core/api"}


def test_list_repos_empty(tmp_path):
    repos_root = tmp_path / "repos"
    repos_root.mkdir()

    r = subprocess.run(
        ["python", "-m", "server.cli", "list-repos"],
        cwd=Path(__file__).parent.parent,
        capture_output=True,
        text=True,
        env={"MYGIT_REPOS_ROOT": str(repos_root)},
    )
    assert r.returncode == 0
    assert "no repositories" in r.stdout


def test_nested_repo_clone_push(live_server, tmp_path_factory):
    port = live_server["port"]
    repos_root = live_server["repos_root"]

    subprocess.run(
        ["python", "-m", "server.cli", "create-repo", "team/backend"],
        cwd=Path(__file__).parent.parent,
        capture_output=True,
        env={"MYGIT_REPOS_ROOT": str(repos_root)},
        check=True,
    )

    bare = repos_root / "team" / "backend.git"
    with __import__("tempfile").TemporaryDirectory() as tmp:
        subprocess.run(
            ["git", "-c", "init.defaultBranch=main", "init", "-q", tmp], check=True
        )
        (Path(tmp) / "README.md").write_text("nested repo\n")
        subprocess.run(["git", "-C", tmp, "add", "README.md"], check=True)
        subprocess.run(
            [
                "git", "-C", tmp,
                "-c", "user.email=test@mygit",
                "-c", "user.name=test",
                "-c", "commit.gpgsign=false",
                "commit", "-m", "initial", "-q",
            ],
            check=True,
        )
        subprocess.run(
            ["git", "-C", tmp, "remote", "add", "origin", str(bare)], check=True
        )
        subprocess.run(
            ["git", "-C", tmp, "push", "-q", "origin", "main"], check=True
        )

    dest = tmp_path_factory.mktemp("nested_clone") / "w"
    url = f"http://127.0.0.1:{port}/team/backend.git"
    r = subprocess.run(
        ["git", "clone", "-q", url, str(dest)],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr
    assert (dest / "README.md").read_text() == "nested repo\n"

    (dest / "file.txt").write_text("hi\n")
    subprocess.run(["git", "-C", str(dest), "add", "file.txt"], check=True)
    subprocess.run(
        [
            "git", "-C", str(dest),
            "-c", "user.email=t@mygit",
            "-c", "user.name=t",
            "-c", "commit.gpgsign=false",
            "commit", "-m", "nested push", "-q",
        ],
        check=True,
    )
    r = subprocess.run(
        ["git", "-C", str(dest), "push", "-q", "origin", "main"],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr

    local_head = subprocess.run(
        ["git", "-C", str(dest), "rev-parse", "HEAD"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    server_head = subprocess.run(
        ["git", "-C", str(bare), "rev-parse", "HEAD"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    assert local_head == server_head


def test_nested_repo_http_refs(live_server):
    port = live_server["port"]
    repos_root = live_server["repos_root"]

    subprocess.run(
        ["python", "-m", "server.cli", "create-repo", "team/backend"],
        cwd=Path(__file__).parent.parent,
        capture_output=True,
        env={"MYGIT_REPOS_ROOT": str(repos_root)},
        check=True,
    )

    bare = repos_root / "team" / "backend.git"
    with __import__("tempfile").TemporaryDirectory() as tmp:
        subprocess.run(
            ["git", "-c", "init.defaultBranch=main", "init", "-q", tmp], check=True
        )
        subprocess.run(
            [
                "git", "-C", tmp,
                "-c", "user.email=test@mygit",
                "-c", "user.name=test",
                "-c", "commit.gpgsign=false",
                "commit", "--allow-empty", "-m", "seed", "-q",
            ],
            check=True,
        )
        subprocess.run(
            ["git", "-C", tmp, "remote", "add", "origin", str(bare)], check=True
        )
        subprocess.run(
            ["git", "-C", tmp, "push", "-q", "origin", "main"], check=True
        )

    r = requests.get(
        f"http://127.0.0.1:{port}/team/backend.git/info/refs",
        params={"service": "git-upload-pack"},
    )
    assert r.status_code == 200
    assert "application/x-git-upload-pack-advertisement" in r.headers["Content-Type"]


def test_deep_nested_repo(tmp_path):
    repos_root = tmp_path / "repos"
    repos_root.mkdir()

    r = subprocess.run(
        ["python", "-m", "server.cli", "create-repo", "a/b/c"],
        cwd=Path(__file__).parent.parent,
        capture_output=True,
        text=True,
        env={"MYGIT_REPOS_ROOT": str(repos_root)},
    )
    assert r.returncode == 0
    assert (repos_root / "a" / "b" / "c.git" / "HEAD").exists()