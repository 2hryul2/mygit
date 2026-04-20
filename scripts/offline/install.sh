#!/usr/bin/env bash
# mygit offline installer (Ubuntu 22.04 / x86_64)
# 에어갭 환경에서 번들된 .deb + wheel 로 mygit 서비스 설치

set -euo pipefail

PREFIX="/opt/mygit"
DATA_DIR="/var/lib/mygit"
CONF_DIR="/etc/mygit"
LOG_DIR="/var/log/mygit"
SERVICE_NAME="mygit"
DO_START=0
SKIP_GIT=0

BUNDLE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

log()  { printf '\033[1;34m[install]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[install:warn]\033[0m %s\n' "$*" >&2; }
err()  { printf '\033[1;31m[install:err]\033[0m %s\n' "$*" >&2; }

usage() {
  cat <<EOF
Usage: sudo ./install.sh [options]

Options:
  --prefix <path>   설치 prefix (기본: /opt/mygit)
  --start           설치 후 서비스 즉시 시작
  --skip-git        번들된 git .deb 설치 건너뛰기 (이미 설치됨)
  -h, --help        도움말
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --prefix)    PREFIX="$2"; shift 2 ;;
    --start)     DO_START=1; shift ;;
    --skip-git)  SKIP_GIT=1; shift ;;
    -h|--help)   usage; exit 0 ;;
    *) err "알 수 없는 옵션: $1"; usage; exit 2 ;;
  esac
done

# ────────────────────────────────────────────────────────────────
# 1. Preflight
# ────────────────────────────────────────────────────────────────
log "Preflight 검사"

if [[ $EUID -ne 0 ]]; then
  err "root 권한 필요 (sudo 로 실행)"
  exit 1
fi

if [[ ! -r /etc/os-release ]]; then
  err "/etc/os-release 읽기 실패 — Ubuntu 환경이 아님"
  exit 1
fi
# shellcheck disable=SC1091
. /etc/os-release
if [[ "${ID:-}" != "ubuntu" ]]; then
  err "Ubuntu 가 아님 (현재: ${ID:-unknown})"
  exit 1
fi
if [[ "${VERSION_ID:-}" != "22.04" ]]; then
  warn "Ubuntu 22.04 이외 버전 (${VERSION_ID:-unknown}) — 동작 미보장. 계속 진행합니다."
fi

ARCH="$(uname -m)"
if [[ "$ARCH" != "x86_64" ]]; then
  err "x86_64 전용 번들입니다 (현재 arch: $ARCH)"
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  err "python3 가 설치되어 있지 않음 — Ubuntu 22.04 기본 패키지 확인 필요"
  exit 1
fi
PY_VER="$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
PY_MAJOR="${PY_VER%.*}"
PY_MINOR="${PY_VER#*.}"
if (( PY_MAJOR < 3 )) || { (( PY_MAJOR == 3 )) && (( PY_MINOR < 10 )); }; then
  err "Python >= 3.10 필요 (현재: $PY_VER)"
  exit 1
fi
log "Python $PY_VER 확인"

if ! python3 -c "import venv" >/dev/null 2>&1; then
  err "python3-venv 모듈 없음 — 번들에 .deb 이 포함되지 않은 경우 수동 설치 필요"
  exit 1
fi

# ────────────────────────────────────────────────────────────────
# 2. git 설치 (번들 .deb)
# ────────────────────────────────────────────────────────────────
if (( SKIP_GIT == 1 )); then
  log "--skip-git: git .deb 설치 건너뜀"
else
  if command -v git >/dev/null 2>&1; then
    log "git 이미 설치됨: $(git --version)"
  else
    if [[ ! -d "$BUNDLE_DIR/vendor/debs" ]] || ! compgen -G "$BUNDLE_DIR/vendor/debs/*.deb" >/dev/null; then
      err "vendor/debs/*.deb 없음. git 미설치 상태이면 설치 불가."
      exit 1
    fi
    log "번들된 .deb 로 git 설치"
    dpkg -i "$BUNDLE_DIR"/vendor/debs/*.deb || {
      warn "dpkg 의존 문제 — apt 로컬 해결 시도"
      apt-get install -f -y --no-download || {
        err "git 설치 실패 — vendor/debs 에 누락된 의존 있는지 확인"
        exit 1
      }
    }
  fi
fi

if ! command -v git >/dev/null 2>&1; then
  err "git 설치 확인 실패"
  exit 1
fi
log "git 확인: $(git --version)"

# ────────────────────────────────────────────────────────────────
# 3. 계정/디렉토리
# ────────────────────────────────────────────────────────────────
log "계정 및 디렉토리 준비"

if ! getent group mygit >/dev/null; then
  groupadd -r mygit
fi
if ! id -u mygit >/dev/null 2>&1; then
  useradd -r -g mygit -s /usr/sbin/nologin -d "$DATA_DIR" mygit
fi

install -d -m 0755 -o mygit -g mygit "$PREFIX"
install -d -m 0750 -o mygit -g mygit "$DATA_DIR"
install -d -m 0750 -o mygit -g mygit "$DATA_DIR/repos"
install -d -m 0770 -o root  -g mygit "$CONF_DIR"
install -d -m 0750 -o mygit -g mygit "$LOG_DIR"

# ────────────────────────────────────────────────────────────────
# 4. 소스 배치
# ────────────────────────────────────────────────────────────────
log "소스 배치 → $PREFIX"

if [[ ! -d "$BUNDLE_DIR/src" ]]; then
  err "$BUNDLE_DIR/src 없음 — 번들 구조 오류"
  exit 1
fi

# 기존 코드 정리 후 복사 (.venv 는 유지)
find "$PREFIX" -mindepth 1 -maxdepth 1 ! -name '.venv' -exec rm -rf {} +
cp -a "$BUNDLE_DIR/src/." "$PREFIX/"
chown -R mygit:mygit "$PREFIX"

# ────────────────────────────────────────────────────────────────
# 5. venv + 오프라인 pip install
# ────────────────────────────────────────────────────────────────
log "Python venv 생성 및 오프라인 의존성 설치"

if [[ ! -d "$PREFIX/.venv" ]]; then
  sudo -u mygit python3 -m venv "$PREFIX/.venv"
fi

if [[ ! -d "$BUNDLE_DIR/vendor/wheels" ]]; then
  err "vendor/wheels 없음 — 번들 구조 오류"
  exit 1
fi

sudo -u mygit "$PREFIX/.venv/bin/pip" install --no-index \
  --find-links "$BUNDLE_DIR/vendor/wheels" \
  --upgrade pip setuptools wheel 2>/dev/null || \
  log "pip/setuptools/wheel 업그레이드 스킵 (번들에 없음 — 정상)"

sudo -u mygit "$PREFIX/.venv/bin/pip" install --no-index \
  --find-links "$BUNDLE_DIR/vendor/wheels" \
  -r "$PREFIX/requirements.txt"

# CLI 래퍼 — server 모듈이 $PREFIX 루트에 있으므로 cwd 고정 필수
install -d -m 0755 -o mygit -g mygit "$PREFIX/bin"
cat > "$PREFIX/bin/mygit-cli" <<EOF
#!/bin/bash
# /etc/mygit/mygit.env 을 로드해 서버와 동일 환경으로 CLI 실행
if [[ -f "$CONF_DIR/mygit.env" ]]; then
  set -a
  . "$CONF_DIR/mygit.env"
  set +a
fi
cd "$PREFIX" && exec "$PREFIX/.venv/bin/python" -m server.cli "\$@"
EOF
chmod 0755 "$PREFIX/bin/mygit-cli"
chown mygit:mygit "$PREFIX/bin/mygit-cli"

# ────────────────────────────────────────────────────────────────
# 6. 환경 파일 배치
# ────────────────────────────────────────────────────────────────
if [[ ! -f "$CONF_DIR/mygit.env" ]]; then
  log "$CONF_DIR/mygit.env 생성 (샘플 복사)"
  install -m 0640 -o root -g mygit "$BUNDLE_DIR/config/mygit.env.example" "$CONF_DIR/mygit.env"
else
  log "$CONF_DIR/mygit.env 존재 — 덮어쓰지 않음"
fi

# ────────────────────────────────────────────────────────────────
# 7. systemd unit
# ────────────────────────────────────────────────────────────────
log "systemd unit 등록"

install -m 0644 -o root -g root "$BUNDLE_DIR/systemd/mygit.service" "/etc/systemd/system/${SERVICE_NAME}.service"
systemctl daemon-reload
systemctl enable "${SERVICE_NAME}.service" >/dev/null

# ────────────────────────────────────────────────────────────────
# 8. 선택적 기동
# ────────────────────────────────────────────────────────────────
if (( DO_START == 1 )); then
  log "서비스 시작"
  systemctl start "${SERVICE_NAME}.service"
  sleep 2
  if ! systemctl is-active --quiet "${SERVICE_NAME}.service"; then
    err "서비스 시작 실패 — journalctl -u ${SERVICE_NAME} -n 50 확인"
    systemctl status "${SERVICE_NAME}.service" --no-pager || true
    exit 1
  fi
  log "서비스 active"
fi

# ────────────────────────────────────────────────────────────────
# 9. 후속 안내
# ────────────────────────────────────────────────────────────────
PORT="$(grep -E '^MYGIT_PORT=' "$CONF_DIR/mygit.env" 2>/dev/null | cut -d= -f2 || echo 8000)"

cat <<EOF

───────────────────────────────────────────────
  mygit 설치 완료
───────────────────────────────────────────────
  설치 경로 : $PREFIX
  데이터    : $DATA_DIR/repos
  설정      : $CONF_DIR/mygit.env
  로그      : $LOG_DIR
  서비스    : ${SERVICE_NAME}.service (포트 $PORT)

  ▶ 사용자 추가:
     sudo -u mygit $PREFIX/bin/mygit-cli add-user <username>

  ▶ 리포 생성:
     sudo -u mygit $PREFIX/bin/mygit-cli create-repo <name>

  ▶ 리포 목록:
     sudo -u mygit $PREFIX/bin/mygit-cli list-repos

  ▶ 서비스 시작/중지/상태:
     sudo systemctl start   ${SERVICE_NAME}
     sudo systemctl stop    ${SERVICE_NAME}
     sudo systemctl status  ${SERVICE_NAME}

  ▶ 로그 확인:
     sudo journalctl -u ${SERVICE_NAME} -f
     sudo tail -f $LOG_DIR/access.log
───────────────────────────────────────────────
EOF
