#!/usr/bin/env bash
set -euo pipefail
export MYGIT_PORT="${MYGIT_PORT:-8000}"
export MYGIT_REPOS_ROOT="${MYGIT_REPOS_ROOT:-$(dirname "$0")/../repos}"
export FLASK_APP="server.app:create_app"
exec python -m flask run --host 0.0.0.0 --port "$MYGIT_PORT"