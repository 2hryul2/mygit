"""Step 3 tests ? real `git clone` against a live server thread."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

import requests


def test_git_clone_succeeds(live_server, tmp_path_factory):
    dest = tmp_path_factory.mktemp("clone")
    result = subprocess.run(
        ["git", "clone", "-q", f"{live_server['url']}/demo.git", str(dest / "work")],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr

    cloned_head = subprocess.run(
        ["git", "-C", str(dest / "work"), "rev-parse", "HEAD"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    assert cloned_head == live_server["head"]
    assert (dest / "work" / "README.md").read_text() == "hello from mygit\n"


def test_git_fetch_noop(live_server, tmp_path_factory):
    dest = tmp_path_factory.mktemp("fetch")
    subprocess.run(
        ["git", "clone", "-q", f"{live_server['url']}/demo.git", str(dest / "work")],
        check=True,
    )
    r = subprocess.run(
        ["git", "-C", str(dest / "work"), "fetch"],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr


def test_git_fetch_picks_up_new_commit(live_server, tmp_path_factory):
    bare = live_server["repos_root"] / "demo.git"
    dest = tmp_path_factory.mktemp("fetch2")
    subprocess.run(
        ["git", "clone", "-q", f"{live_server['url']}/demo.git", str(dest / "work")],
        check=True,
    )

    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(["git", "clone", "-q", str(bare), tmp + "/w"], check=True)
        (Path(tmp) / "w" / "NEWFILE").write_text("added later\n")
        subprocess.run(["git", "-C", tmp + "/w", "add", "NEWFILE"], check=True)
        subprocess.run(
            [
                "git", "-C", tmp + "/w",
                "-c", "user.email=test@mygit",
                "-c", "user.name=test",
                "-c", "commit.gpgsign=false",
                "commit", "-m", "added", "-q",
            ],
            check=True,
        )
        subprocess.run(
            ["git", "-C", tmp + "/w", "push", "-q", "origin", "main"], check=True
        )

    new_head = subprocess.run(
        ["git", "-C", str(bare), "rev-parse", "HEAD"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()

    subprocess.run(
        ["git", "-C", str(dest / "work"), "fetch", "-q"], check=True
    )
    fetched_head = subprocess.run(
        ["git", "-C", str(dest / "work"), "rev-parse", "origin/main"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    assert fetched_head == new_head


def test_upload_pack_wrong_content_type(live_server):
    r = requests.post(
        f"{live_server['url']}/demo.git/git-upload-pack",
        data=b"",
        headers={"Content-Type": "text/plain"},
    )
    assert r.status_code == 415


def test_upload_pack_missing_repo(live_server):
    r = requests.post(
        f"{live_server['url']}/does-not-exist.git/git-upload-pack",
        data=b"",
        headers={"Content-Type": "application/x-git-upload-pack-request"},
    )
    assert r.status_code == 404