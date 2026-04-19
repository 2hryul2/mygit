"""Step 5 tests ? HTTP Basic authentication."""

from __future__ import annotations

import base64
import subprocess
from pathlib import Path

import pytest
import requests

from server.auth import (
    check_basic_auth,
    hash_password,
    load_users,
    save_users,
    verify_password,
)


def test_hash_roundtrip():
    encoded = hash_password("hunter2")
    assert encoded.startswith("pbkdf2_sha256$200000$")
    assert verify_password("hunter2", encoded)
    assert not verify_password("hunter3", encoded)


def test_verify_password_on_garbage():
    assert not verify_password("any", "not-an-encoded-string")
    assert not verify_password("any", "wrong$scheme$a$b")
    assert not verify_password("any", "")


def test_check_basic_auth_success():
    users = {"alice": hash_password("pw")}
    token = base64.b64encode(b"alice:pw").decode("ascii")
    assert check_basic_auth(f"Basic {token}", users) == "alice"


def test_check_basic_auth_wrong_password():
    users = {"alice": hash_password("pw")}
    token = base64.b64encode(b"alice:nope").decode("ascii")
    assert check_basic_auth(f"Basic {token}", users) is None


def test_check_basic_auth_unknown_user():
    users = {"alice": hash_password("pw")}
    token = base64.b64encode(b"bob:pw").decode("ascii")
    assert check_basic_auth(f"Basic {token}", users) is None


def test_check_basic_auth_bad_header():
    users = {"alice": hash_password("pw")}
    assert check_basic_auth(None, users) is None
    assert check_basic_auth("", users) is None
    assert check_basic_auth("Bearer token", users) is None
    assert check_basic_auth("Basic !!!notb64", users) is None


def test_load_save_users_roundtrip(tmp_path):
    path = tmp_path / "users.json"
    users = {"alice": hash_password("p1"), "bob": hash_password("p2")}
    save_users(path, users)
    loaded = load_users(path)
    assert set(loaded.keys()) == {"alice", "bob"}
    assert verify_password("p1", loaded["alice"])
    assert verify_password("p2", loaded["bob"])


def test_load_users_missing_file(tmp_path):
    assert load_users(tmp_path / "does-not-exist.json") == {}
    assert load_users(None) == {}


def test_healthz_no_auth_required(auth_server):
    r = requests.get(f"{auth_server['url']}/healthz")
    assert r.status_code == 200


def test_info_refs_requires_auth_when_no_anon(auth_server):
    r = requests.get(
        f"{auth_server['url']}/demo.git/info/refs",
        params={"service": "git-upload-pack"},
    )
    assert r.status_code == 401
    assert r.headers.get("WWW-Authenticate") == 'Basic realm="mygit"'


def test_info_refs_wrong_password(auth_server):
    r = requests.get(
        f"{auth_server['url']}/demo.git/info/refs",
        params={"service": "git-upload-pack"},
        auth=("alice", "wrong"),
    )
    assert r.status_code == 401


def test_info_refs_correct_creds(auth_server):
    r = requests.get(
        f"{auth_server['url']}/demo.git/info/refs",
        params={"service": "git-upload-pack"},
        auth=("alice", "s3cret"),
    )
    assert r.status_code == 200


def test_receive_pack_info_refs_always_needs_auth_even_with_anon_read(anon_read_server):
    r = requests.get(
        f"{anon_read_server['url']}/demo.git/info/refs",
        params={"service": "git-receive-pack"},
    )
    assert r.status_code == 401


def test_receive_pack_post_requires_auth(anon_read_server):
    r = requests.post(
        f"{anon_read_server['url']}/demo.git/git-receive-pack",
        data=b"",
        headers={"Content-Type": "application/x-git-receive-pack-request"},
    )
    assert r.status_code == 401


def test_upload_pack_allowed_anonymously_when_anon_read(anon_read_server):
    r = requests.get(
        f"{anon_read_server['url']}/demo.git/info/refs",
        params={"service": "git-upload-pack"},
    )
    assert r.status_code == 200


def test_git_clone_with_credentials_in_url(auth_server, tmp_path_factory):
    port = auth_server["port"]
    dest = tmp_path_factory.mktemp("authclone") / "w"
    url = f"http://alice:s3cret@127.0.0.1:{port}/demo.git"
    r = subprocess.run(
        ["git", "clone", "-q", url, str(dest)],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr


def test_git_clone_wrong_password_fails(auth_server, tmp_path_factory):
    port = auth_server["port"]
    dest = tmp_path_factory.mktemp("authfail") / "w"
    url = f"http://alice:nope@127.0.0.1:{port}/demo.git"
    r = subprocess.run(
        ["git", "clone", "-q", url, str(dest)],
        capture_output=True, text=True,
        env={
            "HOME": str(tmp_path_factory.mktemp("h")),
            "GIT_TERMINAL_PROMPT": "0",
            "PATH": "C:\\Program Files\\Git\\cmd;C:\\Windows\\System32",
        },
    )
    assert r.returncode != 0


def test_git_push_with_credentials(auth_server, tmp_path_factory):
    port = auth_server["port"]
    work = tmp_path_factory.mktemp("authpush") / "w"
    url = f"http://alice:s3cret@127.0.0.1:{port}/demo.git"

    subprocess.run(["git", "clone", "-q", url, str(work)], check=True)
    (work / "f.txt").write_text("hi\n")
    subprocess.run(["git", "-C", str(work), "add", "f.txt"], check=True)
    subprocess.run(
        [
            "git", "-C", str(work),
            "-c", "user.email=t@mygit",
            "-c", "user.name=t",
            "-c", "commit.gpgsign=false",
            "commit", "-m", "auth push", "-q",
        ],
        check=True,
    )
    r = subprocess.run(
        ["git", "-C", str(work), "push", "-q", "origin", "main"],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr

    bare = auth_server["repos_root"] / "demo.git"
    local_head = subprocess.run(
        ["git", "-C", str(work), "rev-parse", "HEAD"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    server_head = subprocess.run(
        ["git", "-C", str(bare), "rev-parse", "HEAD"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    assert local_head == server_head