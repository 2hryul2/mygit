#!/usr/bin/env bash
# mygit 오프라인 번들 생성 스크립트
# 실행 환경: Ubuntu 22.04 (WSL2 또는 docker run ubuntu:22.04)
# 출력: dist/setup/mygit-offline-v{VERSION}-ubuntu2204-x86_64.tar.gz

set -euo pipefail

log()  { printf '\033[1;34m[build]\033[0m %s\n' "$*"; }
err()  { printf '\033[1;31m[build:err]\033[0m %s\n' "$*" >&2; }

# ────────────────────────────────────────────────────────────────
# 환경 조건 검사
# ────────────────────────────────────────────────────────────────
if [[ ! -r /etc/os-release ]]; then
  err "/etc/os-release 없음 — Ubuntu 22.04 환경 필요"
  exit 1
fi
# shellcheck disable=SC1091
. /etc/os-release
if [[ "${ID:-}" != "ubuntu" || "${VERSION_ID:-}" != "22.04" ]]; then
  err "Ubuntu 22.04 전용 (현재: ${ID:-?} ${VERSION_ID:-?})"
  err "Docker 로 실행: docker run --rm -v \$(pwd):/work -w /work ubuntu:22.04 bash scripts/offline/build_offline_bundle.sh"
  exit 1
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

if [[ ! -f VERSION ]]; then
  err "VERSION 파일 없음"
  exit 1
fi
VERSION="$(tr -d '[:space:]' < VERSION)"
BUNDLE_NAME="mygit-offline-v${VERSION}-ubuntu2204-x86_64"
OUT_DIR="dist/setup/${BUNDLE_NAME}"
TAR_PATH="dist/setup/${BUNDLE_NAME}.tar.gz"

log "Version: ${VERSION}"
log "Output:  ${TAR_PATH}"

# ────────────────────────────────────────────────────────────────
# 빌드툴 준비 (apt-get, pip, rsync, tar)
# ────────────────────────────────────────────────────────────────
log "빌드 도구 설치 (apt-get update + deps)"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y --no-install-recommends \
  python3 python3-pip python3-venv rsync tar ca-certificates >/dev/null

# ────────────────────────────────────────────────────────────────
# 1. 출력 디렉토리 초기화
# ────────────────────────────────────────────────────────────────
log "출력 디렉토리 초기화"
rm -rf "${OUT_DIR}" "${TAR_PATH}" "${TAR_PATH}.sha256"
mkdir -p "${OUT_DIR}/src" "${OUT_DIR}/vendor/wheels" "${OUT_DIR}/vendor/debs" \
         "${OUT_DIR}/systemd" "${OUT_DIR}/config"

# ────────────────────────────────────────────────────────────────
# 2. src 복사 (개발 폴더/캐시 제외)
# ────────────────────────────────────────────────────────────────
log "소스 복사 → ${OUT_DIR}/src"
rsync -a \
  --exclude '.git' \
  --exclude '.venv' \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  --exclude '.pytest_cache' \
  --exclude 'dist' \
  --exclude 'handoff' \
  --exclude 'doc' \
  --exclude 'ideation' \
  --exclude '.vscode' \
  --exclude '.idea' \
  --exclude 'repos/*' \
  --include 'repos/' \
  --include 'repos/.gitkeep' \
  server/ "${OUT_DIR}/src/server/"

# 루트 파일
cp requirements.txt pyproject.toml VERSION README.md "${OUT_DIR}/src/"
# scripts 폴더는 오프라인 스크립트 제외하고 개발용만 복사(참고용)
mkdir -p "${OUT_DIR}/src/scripts"
for f in scripts/*.sh; do
  [[ "$f" == scripts/offline/* ]] && continue
  cp "$f" "${OUT_DIR}/src/scripts/" 2>/dev/null || true
done
# 빈 config, repos 디렉토리 (런타임에 /etc, /var/lib로 이동)
mkdir -p "${OUT_DIR}/src/config" "${OUT_DIR}/src/repos"

# requirements.txt 에 gunicorn 보장
if ! grep -q '^gunicorn==' "${OUT_DIR}/src/requirements.txt"; then
  echo "gunicorn==23.0.0" >> "${OUT_DIR}/src/requirements.txt"
fi

# ────────────────────────────────────────────────────────────────
# 3. Python wheels 다운로드 (Linux x86_64 / py3.10)
# ────────────────────────────────────────────────────────────────
log "Python wheels 다운로드 (manylinux2014_x86_64, py3.10)"
pip3 download \
  --platform manylinux2014_x86_64 \
  --python-version 3.10 \
  --only-binary=:all: \
  --dest "${OUT_DIR}/vendor/wheels" \
  -r "${OUT_DIR}/src/requirements.txt"

# wheel 개수 확인
WHEEL_COUNT=$(find "${OUT_DIR}/vendor/wheels" -name '*.whl' | wc -l)
log "wheel 파일 ${WHEEL_COUNT} 개 수집"
if (( WHEEL_COUNT < 5 )); then
  err "wheel 개수가 비정상적으로 적음 (${WHEEL_COUNT}) — 다운로드 오류 가능"
  exit 1
fi

# ────────────────────────────────────────────────────────────────
# 4. git .deb 다운로드 (Ubuntu 22.04 jammy 미러)
# ────────────────────────────────────────────────────────────────
log "git .deb + 의존성 다운로드"
APT_CACHE="$(mktemp -d)"
mkdir -p "${APT_CACHE}/archives/partial"
# apt-get 옵션으로 별도 캐시 경로 지정 → 시스템 캐시 오염 방지
apt-get -y \
  -o Dir::Cache="${APT_CACHE}" \
  -o Dir::Cache::archives="${APT_CACHE}/archives" \
  -o Debug::NoLocking=1 \
  --download-only --reinstall install git >/dev/null

find "${APT_CACHE}/archives" -maxdepth 1 -name '*.deb' -exec cp {} "${OUT_DIR}/vendor/debs/" \;
rm -rf "${APT_CACHE}"

DEB_COUNT=$(find "${OUT_DIR}/vendor/debs" -name '*.deb' | wc -l)
log ".deb 파일 ${DEB_COUNT} 개 수집"
if (( DEB_COUNT < 1 )); then
  err ".deb 다운로드 실패"
  exit 1
fi

# ────────────────────────────────────────────────────────────────
# 5. install/uninstall/systemd/env/README 복사
# ────────────────────────────────────────────────────────────────
log "설치 스크립트 및 템플릿 복사"
cp scripts/offline/install.sh     "${OUT_DIR}/install.sh"
cp scripts/offline/uninstall.sh   "${OUT_DIR}/uninstall.sh"
cp scripts/offline/mygit.service  "${OUT_DIR}/systemd/mygit.service"
cp scripts/offline/mygit.env.example "${OUT_DIR}/config/mygit.env.example"
cp scripts/offline/README-OFFLINE.md "${OUT_DIR}/README-OFFLINE.md"
cp VERSION "${OUT_DIR}/VERSION"
chmod +x "${OUT_DIR}/install.sh" "${OUT_DIR}/uninstall.sh"

# ────────────────────────────────────────────────────────────────
# 6. tarball + SHA256
# ────────────────────────────────────────────────────────────────
log "tar.gz 패키징"
tar czf "${TAR_PATH}" -C "dist/setup" "${BUNDLE_NAME}"
( cd "dist/setup" && sha256sum "${BUNDLE_NAME}.tar.gz" > "${BUNDLE_NAME}.tar.gz.sha256" )

SIZE="$(du -h "${TAR_PATH}" | cut -f1)"
log "완료: ${TAR_PATH} (${SIZE})"
log "해시: $(cat "${TAR_PATH}.sha256")"
