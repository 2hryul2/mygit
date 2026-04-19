from flask import Blueprint, Response, current_app, request, stream_with_context

from ..auth import check_basic_auth
from ..git_backend import advertise_refs, run_service
from ..pktline import FLUSH_PKT, pkt_line
from ..repos import is_valid_repo_name, resolve_repo

smart_http = Blueprint("smart_http", __name__)

_NO_CACHE_HEADERS = {
    "Cache-Control": "no-cache, max-age=0, must-revalidate",
    "Pragma": "no-cache",
}
_STREAM_CHUNK = 65536


def _auth_required_response() -> Response:
    return Response(
        "authentication required",
        status=401,
        headers={"WWW-Authenticate": 'Basic realm="mygit"'},
    )


def _check_auth(allow_anonymous: bool) -> Response | None:
    """Return None if request is allowed; otherwise a 401 Response."""
    if allow_anonymous:
        return None
    users = current_app.config.get("MYGIT_USERS", {})
    header = request.headers.get("Authorization")
    username = check_basic_auth(header, users)
    if username is None:
        return _auth_required_response()
    return None


def _resolve_or_error(repo: str):
    cfg = current_app.config["MYGIT"]
    repo_path = resolve_repo(repo, cfg.repos_root)
    if repo_path is not None:
        return repo_path, None
    if not is_valid_repo_name(repo):
        return None, Response("invalid repo name", status=400)
    return None, Response("repo not found", status=404)


def _service_endpoint(service: str, repo: str):
    expected_ct = f"application/x-{service}-request"
    if request.content_type != expected_ct:
        return Response(f"expected Content-Type {expected_ct}", status=415)

    repo_path, err = _resolve_or_error(repo)
    if err is not None:
        return err

    git_protocol = request.headers.get("Git-Protocol")
    stream = request.stream

    def body_iter():
        while True:
            chunk = stream.read(_STREAM_CHUNK)
            if not chunk:
                break
            yield chunk

    generator = run_service(service, repo_path, body_iter(), git_protocol)

    headers = {
        "Content-Type": f"application/x-{service}-result",
        **_NO_CACHE_HEADERS,
    }
    return Response(stream_with_context(generator), status=200, headers=headers)


@smart_http.get("/<path:repo>.git/info/refs")
def info_refs(repo: str):
    service = request.args.get("service", "")
    if service not in ("git-upload-pack", "git-receive-pack"):
        return Response("invalid service", status=400)

    cfg = current_app.config["MYGIT"]
    if service == "git-upload-pack":
        allow_anon = cfg.allow_anonymous_read
    else:
        allow_anon = cfg.allow_anonymous_write
    auth_err = _check_auth(allow_anon)
    if auth_err is not None:
        return auth_err

    repo_path, err = _resolve_or_error(repo)
    if err is not None:
        return err

    git_protocol = request.headers.get("Git-Protocol")
    refs_body = advertise_refs(service, repo_path, git_protocol)

    body = pkt_line(f"# service={service}\n".encode("ascii")) + FLUSH_PKT + refs_body

    headers = {
        "Content-Type": f"application/x-{service}-advertisement",
        **_NO_CACHE_HEADERS,
    }
    return Response(body, status=200, headers=headers)


@smart_http.post("/<path:repo>.git/git-upload-pack")
def upload_pack(repo: str):
    cfg = current_app.config["MYGIT"]
    auth_err = _check_auth(allow_anonymous=cfg.allow_anonymous_read)
    if auth_err is not None:
        return auth_err
    return _service_endpoint("git-upload-pack", repo)


@smart_http.post("/<path:repo>.git/git-receive-pack")
def receive_pack(repo: str):
    cfg = current_app.config["MYGIT"]
    auth_err = _check_auth(allow_anonymous=cfg.allow_anonymous_write)
    if auth_err is not None:
        return auth_err
    return _service_endpoint("git-receive-pack", repo)