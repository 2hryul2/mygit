"""Step 4 tests ? real `git push` against a live server thread."""

from __future__ import annotations

import subprocess
from pathlib import Path

import requests


def _clone(url: str, dest: Path, env: dict | None = None) -> None:
    subprocess.run(
        ["git", "clone", "-q", url, str(dest)],
        check=True, env=env,
    )


def _commit(workdir: Path, filename: str, contents: str, message: str) -> str:
    (workdir / filename).write_text(contents)
    subprocess.run(["git", "-C", str(workdir), "add", filename], check=True)
    subprocess.run(
        [
            "git", "-C", str(workdir),
            "-c", "user.email=test@mygit",
            "-c", "user.name=test",
            "-c", "commit.gpgsign=false",
            "commit", "-m", message, "-q",
        ],
        check=True,
    )
    return subprocess.run(
        ["git", "-C", str(workdir), "rev-parse", "HEAD"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()


def test_git_push_succeeds(live_server, tmp_path_factory):
    work = tmp_path_factory.mktemp("push") / "w"
    _clone(f"{live_server['url']}/demo.git", work)

    new_sha = _commit(work, "hi.txt", "hi\n", "add hi")
    r = subprocess.run(
        ["git", "-C", str(work), "push", "-q", "origin", "main"],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr

    bare = live_server["repos_root"] / "demo.git"
    server_sha = subprocess.run(
        ["git", "-C", str(bare), "rev-parse", "HEAD"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    assert server_sha == new_sha


def test_second_clone_sees_pushed_commit(live_server, tmp_path_factory):
    work_a = tmp_path_factory.mktemp("push_a") / "w"
    _clone(f"{live_server['url']}/demo.git", work_a)
    pushed_sha = _commit(work_a, "a.txt", "a\n", "add a")
    subprocess.run(
        ["git", "-C", str(work_a), "push", "-q", "origin", "main"], check=True
    )

    work_b = tmp_path_factory.mktemp("push_b") / "w"
    _clone(f"{live_server['url']}/demo.git", work_b)
    b_head = subprocess.run(
        ["git", "-C", str(work_b), "rev-parse", "HEAD"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    assert b_head == pushed_sha
    assert (work_b / "a.txt").read_text() == "a\n"


def test_non_fast_forward_push_rejected(live_server, tmp_path_factory):
    work_a = tmp_path_factory.mktemp("nff_a") / "w"
    _clone(f"{live_server['url']}/demo.git", work_a)
    _commit(work_a, "a.txt", "a\n", "add a")
    subprocess.run(
        ["git", "-C", str(work_a), "push", "-q", "origin", "main"], check=True
    )

    work_b = tmp_path_factory.mktemp("nff_b") / "w"
    _clone(f"{live_server['url']}/demo.git", work_b)
    subprocess.run(
        ["git", "-C", str(work_b), "reset", "--hard", "HEAD~1", "-q"], check=True
    )
    _commit(work_b, "divergent.txt", "x\n", "divergent")

    r = subprocess.run(
        ["git", "-C", str(work_b), "push", "origin", "main"],
        capture_output=True, text=True,
    )
    assert r.returncode != 0
    assert "rejected" in (r.stderr + r.stdout).lower()


def test_force_push_succeeds(live_server, tmp_path_factory):
    work_a = tmp_path_factory.mktemp("force_a") / "w"
    _clone(f"{live_server['url']}/demo.git", work_a)
    _commit(work_a, "a.txt", "a\n", "add a")
    subprocess.run(
        ["git", "-C", str(work_a), "push", "-q", "origin", "main"], check=True
    )

    work_b = tmp_path_factory.mktemp("force_b") / "w"
    _clone(f"{live_server['url']}/demo.git", work_b)
    subprocess.run(
        ["git", "-C", str(work_b), "reset", "--hard", "HEAD~1", "-q"], check=True
    )
    divergent_sha = _commit(work_b, "divergent.txt", "x\n", "divergent")

    r = subprocess.run(
        ["git", "-C", str(work_b), "push", "--force", "-q", "origin", "main"],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr

    bare = live_server["repos_root"] / "demo.git"
    server_sha = subprocess.run(
        ["git", "-C", str(bare), "rev-parse", "HEAD"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    assert server_sha == divergent_sha


def test_receive_pack_wrong_content_type(live_server):
    r = requests.post(
        f"{live_server['url']}/demo.git/git-receive-pack",
        data=b"",
        headers={"Content-Type": "text/plain"},
    )
    assert r.status_code == 415


def test_receive_pack_info_refs_content_type(live_server):
    r = requests.get(
        f"{live_server['url']}/demo.git/info/refs",
        params={"service": "git-receive-pack"},
    )
    assert r.status_code == 200
    assert r.headers["Content-Type"] == "application/x-git-receive-pack-advertisement"