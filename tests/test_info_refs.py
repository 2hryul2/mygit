import subprocess
from pathlib import Path

import pytest

from server.app import create_app


def _ensure_demo_repo(repos_root: Path) -> Path:
    bare = repos_root / "demo.git"
    if not bare.exists():
        subprocess.run(
            ["git", "init", "--bare", str(bare)], check=True, capture_output=True
        )
    result = subprocess.run(
        ["git", "-C", str(bare), "rev-parse", "--verify", "--quiet", "HEAD"],
        capture_output=True,
    )
    if result.returncode != 0:
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
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
    return bare


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("MYGIT_REPOS_ROOT", str(tmp_path))
    monkeypatch.setenv("MYGIT_ALLOW_ANONYMOUS_READ", "true")
    monkeypatch.setenv("MYGIT_ALLOW_ANONYMOUS_WRITE", "true")
    monkeypatch.delenv("MYGIT_AUTH_FILE", raising=False)
    _ensure_demo_repo(tmp_path)
    app = create_app()
    return app.test_client()


def test_info_refs_upload_pack_ok(client):
    r = client.get("/demo.git/info/refs?service=git-upload-pack")
    assert r.status_code == 200
    assert r.headers["Content-Type"] == "application/x-git-upload-pack-advertisement"
    assert "no-cache" in r.headers["Cache-Control"]
    body = r.data
    assert body.startswith(b"001e# service=git-upload-pack\n")
    assert b"0000" in body[30:34]


def test_info_refs_missing_service(client):
    r = client.get("/demo.git/info/refs")
    assert r.status_code == 400


def test_info_refs_receive_pack_ok(client):
    r = client.get("/demo.git/info/refs?service=git-receive-pack")
    assert r.status_code == 200
    assert r.headers["Content-Type"] == "application/x-git-receive-pack-advertisement"
    body = r.data
    assert body.startswith(b"001f# service=git-receive-pack\n")


def test_info_refs_repo_not_found(client):
    r = client.get("/missing.git/info/refs?service=git-upload-pack")
    assert r.status_code == 404


def test_info_refs_invalid_name(client):
    r = client.get("/..%2Fetc.git/info/refs?service=git-upload-pack")
    assert r.status_code in (400, 404)