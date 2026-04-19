#!/usr/bin/env bash
set -euo pipefail
USERNAME="${1:?usage: add_user.sh <username>}"
export MYGIT_AUTH_FILE="${MYGIT_AUTH_FILE:-$(dirname "$0")/../config/users.json}"
read -r -s -p "Password for $USERNAME: " PW1
echo
read -r -s -p "Confirm: " PW2
echo
if [ "$PW1" != "$PW2" ]; then
    echo "passwords do not match" >&2
    exit 1
fi
if [ -z "$PW1" ]; then
    echo "password cannot be empty" >&2
    exit 1
fi
printf '%s\n' "$PW1" | python -m server.cli add-user "$USERNAME"