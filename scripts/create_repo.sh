#!/usr/bin/env bash
set -euo pipefail
NAME="${1:?usage: create_repo.sh <name>}"
ROOT="${MYGIT_REPOS_ROOT:-$(dirname "$0")/../repos}"
TARGET="$ROOT/$NAME.git"
mkdir -p "$(dirname "$TARGET")"
git init --bare -b main "$TARGET"
git -C "$TARGET" config http.receivepack true
echo "Created bare repo at $TARGET"