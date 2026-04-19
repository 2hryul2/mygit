"""Shared fixtures ? live HTTP server + seeded demo.git repo."""

from __future__ import annotations

import socket
import subprocess
import tempfile
import threading
import time
from pathlib import Path

import pytest
import requests
from werkzeug.serving import make_server

from server.app import create_app


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _seed_demo(repos_root: Path) -> str:
    bare = repos_root / "demo.git"
    subprocess.run(
        ["git", "init", "--bare", "-b", "main", str(bare)],
        check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(bare), "config", "http.receivepack", "true"],
        check=True,
    )
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(
            ["git", "-c", "init.defaultBranch=main", "init", "-q", tmp], check=True
        )
        (Path(tmp) / "README.md").write_text("hello from mygit\n")
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
    sha = subprocess.run(
        ["git", "-C", str(bare), "rev-parse", "HEAD"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    return sha


@pytest.fixture
def live_server(tmp_path, monkeypatch):
    monkeypatch.setenv("MYGIT_REPOS_ROOT", str(tmp_path))
    monkeypatch.setenv("MYGIT_ALLOW_ANONYMOUS_READ", "true")
    monkeypatch.setenv("MYGIT_ALLOW_ANONYMOUS_WRITE", "true")
    monkeypatch.delenv("MYGIT_AUTH_FILE", raising=False)
    head_sha = _seed_demo(tmp_path)

    app = create_app()
    port = _free_port()
    server = make_server("127.0.0.1", port, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    deadline = time.time() + 5
    while time.time() < deadline:
        try:
            r = requests.get(f"http://127.0.0.1:{port}/healthz", timeout=1)
            if r.status_code == 200:
                break
        except requests.RequestException:
            time.sleep(0.05)
    else:
        server.shutdown()
        raise RuntimeError("server failed to start")

    yield {
        "port": port,
        "url": f"http://127.0.0.1:{port}",
        "repos_root": tmp_path,
        "head": head_sha,
    }

    server.shutdown()
    thread.join(timeout=5)


def _start_server_with_env(tmp_path, monkeypatch, env: dict[str, str]):
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("MYGIT_REPOS_ROOT", str(tmp_path))
    head_sha = _seed_demo(tmp_path)

    app = create_app()
    port = _free_port()
    server = make_server("127.0.0.1", port, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    deadline = time.time() + 5
    while time.time() < deadline:
        try:
            r = requests.get(f"http://127.0.0.1:{port}/healthz", timeout=1)
            if r.status_code == 200:
                break
        except requests.RequestException:
            time.sleep(0.05)
    else:
        server.shutdown()
        raise RuntimeError("server failed to start")

    return {
        "server": server,
        "thread": thread,
        "info": {
            "port": port,
            "url": f"http://127.0.0.1:{port}",
            "repos_root": tmp_path,
            "head": head_sha,
        },
    }


@pytest.fixture
def auth_server(tmp_path, monkeypatch):
    from server.auth import hash_password, save_users

    auth_file = tmp_path / "users.json"
    save_users(auth_file, {"alice": hash_password("s3cret")})

    bundle = _start_server_with_env(
        tmp_path, monkeypatch,
        {
            "MYGIT_AUTH_FILE": str(auth_file),
            "MYGIT_ALLOW_ANONYMOUS_READ": "false",
            "MYGIT_ALLOW_ANONYMOUS_WRITE": "false",
        },
    )
    info = bundle["info"]
    info["username"] = "alice"
    info["password"] = "s3cret"
    info["auth_file"] = auth_file

    yield info

    bundle["server"].shutdown()
    bundle["thread"].join(timeout=5)


@pytest.fixture
def anon_read_server(tmp_path, monkeypatch):
    from server.auth import hash_password, save_users

    auth_file = tmp_path / "users.json"
    save_users(auth_file, {"alice": hash_password("s3cret")})

    bundle = _start_server_with_env(
        tmp_path, monkeypatch,
        {
            "MYGIT_AUTH_FILE": str(auth_file),
            "MYGIT_ALLOW_ANONYMOUS_READ": "true",
            "MYGIT_ALLOW_ANONYMOUS_WRITE": "false",
        },
    )
    info = bundle["info"]
    info["username"] = "alice"
    info["password"] = "s3cret"

    yield info

    bundle["server"].shutdown()
    bundle["thread"].join(timeout=5)


@pytest.fixture
def git_env(tmp_path_factory):
    home = tmp_path_factory.mktemp("githome")
    return {
        "HOME": str(home),
        "GIT_AUTHOR_NAME": "test",
        "GIT_AUTHOR_EMAIL": "test@mygit",
        "GIT_COMMITTER_NAME": "test",
        "GIT_COMMITTER_EMAIL": "test@mygit",
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_SYSTEM": "/dev/null",
    }