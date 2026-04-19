#!/usr/bin/env bash
set -euo pipefail
ROOT="${MYGIT_REPOS_ROOT:-$(dirname "$0")/../repos}"
BARE="$ROOT/demo.git"
if [ ! -d "$BARE" ]; then
    echo "error: $BARE does not exist. Run scripts/create_repo.sh demo first." >&2
    exit 1
fi
if git -C "$BARE" rev-parse --verify --quiet HEAD > /dev/null; then
    echo "demo repo already seeded: $(git -C "$BARE" rev-parse HEAD)"
    exit 0
fi
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
git -c init.defaultBranch=main init -q "$TMP/work"
cd "$TMP/work"
git -c user.email=seed@mygit -c user.name=seed -c commit.gpgsign=false \
    commit --allow-empty -m "seed: initial empty commit" -q
git remote add origin "$BARE"
git push -q origin main
echo "seeded $BARE with commit $(git -C "$BARE" rev-parse HEAD)"