import os
import subprocess
import threading
from collections.abc import Iterable, Iterator
from pathlib import Path

ALLOWED_SERVICES = ("git-upload-pack", "git-receive-pack")
_CHUNK = 65536


def _subprocess_env(git_protocol: str | None) -> dict[str, str]:
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": os.environ.get("HOME", "/tmp"),
        "LANG": os.environ.get("LANG", "C"),
    }
    if git_protocol:
        env["GIT_PROTOCOL"] = git_protocol
    return env


def advertise_refs(
    service: str, repo_path: Path, git_protocol: str | None = None
) -> bytes:
    if service not in ALLOWED_SERVICES:
        raise ValueError(f"unsupported service: {service}")

    subcommand = service.removeprefix("git-")
    result = subprocess.run(
        ["git", subcommand, "--stateless-rpc", "--advertise-refs", str(repo_path)],
        check=True,
        capture_output=True,
        env=_subprocess_env(git_protocol),
        shell=False,
    )
    return result.stdout


def run_service(
    service: str,
    repo_path: Path,
    stdin_iter: Iterable[bytes],
    git_protocol: str | None = None,
) -> Iterator[bytes]:
    if service not in ALLOWED_SERVICES:
        raise ValueError(f"unsupported service: {service}")

    subcommand = service.removeprefix("git-")
    proc = subprocess.Popen(
        ["git", subcommand, "--stateless-rpc", str(repo_path)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        env=_subprocess_env(git_protocol),
        shell=False,
        bufsize=0,
    )

    def _pump_stdin():
        try:
            for chunk in stdin_iter:
                if not chunk:
                    continue
                proc.stdin.write(chunk)
            proc.stdin.flush()
        except (BrokenPipeError, OSError):
            pass
        finally:
            try:
                proc.stdin.close()
            except Exception:
                pass

    pump = threading.Thread(target=_pump_stdin, daemon=True)
    pump.start()

    try:
        while True:
            chunk = proc.stdout.read(_CHUNK)
            if not chunk:
                break
            yield chunk
    except GeneratorExit:
        proc.kill()
        raise
    finally:
        try:
            proc.stdout.close()
        except Exception:
            pass
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        pump.join(timeout=1)