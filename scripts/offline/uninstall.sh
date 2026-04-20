#!/usr/bin/env bash
# mygit uninstaller
# 기본: 서비스/소스/로그 제거, 데이터(리포·사용자)는 유지
# --purge: 데이터와 계정까지 전부 제거

set -euo pipefail

PREFIX="/opt/mygit"
DATA_DIR="/var/lib/mygit"
CONF_DIR="/etc/mygit"
LOG_DIR="/var/log/mygit"
SERVICE_NAME="mygit"
PURGE=0

log()  { printf '\033[1;34m[uninstall]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[uninstall:warn]\033[0m %s\n' "$*" >&2; }
err()  { printf '\033[1;31m[uninstall:err]\033[0m %s\n' "$*" >&2; }

usage() {
  cat <<EOF
Usage: sudo ./uninstall.sh [--purge]

  (기본)   서비스 중지, $PREFIX 와 $LOG_DIR 제거. $DATA_DIR / $CONF_DIR 는 보존.
  --purge  데이터/설정/계정까지 모두 삭제.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --purge)   PURGE=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) err "알 수 없는 옵션: $1"; usage; exit 2 ;;
  esac
done

if [[ $EUID -ne 0 ]]; then
  err "root 권한 필요 (sudo 로 실행)"
  exit 1
fi

log "서비스 중지 및 비활성화"
systemctl stop "${SERVICE_NAME}.service" 2>/dev/null || true
systemctl disable "${SERVICE_NAME}.service" 2>/dev/null || true
rm -f "/etc/systemd/system/${SERVICE_NAME}.service"
systemctl daemon-reload

log "$PREFIX 제거"
rm -rf "$PREFIX"
log "$LOG_DIR 제거"
rm -rf "$LOG_DIR"

if (( PURGE == 1 )); then
  warn "--purge 지정됨 — 데이터/설정/계정 전부 삭제"
  rm -rf "$DATA_DIR"
  rm -rf "$CONF_DIR"
  if id -u mygit >/dev/null 2>&1; then
    userdel mygit || true
  fi
  if getent group mygit >/dev/null; then
    groupdel mygit || true
  fi
else
  log "데이터 보존: $DATA_DIR  /  설정 보존: $CONF_DIR"
  log "완전 삭제는 --purge 플래그 사용"
fi

log "제거 완료"
