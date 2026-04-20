# Build Log

## Current Status

**Step 7 완료 (2026-04-20)**. 오프라인 Ubuntu 22.04 인스톨러 배포 가능.
산출: `dist/setup/mygit-offline-v0.7.0-ubuntu2204-x86_64.tar.gz` (16MB)
E2E 에어갭 검증 통과 (설치 → CLI → push/clone 왕복).

## Architecture Decisions

- Flask 3.0 + subprocess git 래핑 (Step 1–6)
- pbkdf2_sha256 stdlib-only 인증
- nested repo 경로 지원
- **Step 7**: gunicorn WSGI + systemd + 전용 계정, Ubuntu 22.04/x86_64 타깃

## Step History

- Steps 1–6: 완료 (2026-04-18), 42 tests passing (Windows dev 환경)
- Step 7: 완료 (2026-04-20)
  - 7.1 gunicorn==23.0.0 추가, VERSION 0.7.0, .gitignore 갱신
  - 7.2 `scripts/offline/install.sh` (preflight, dpkg, useradd, venv, systemd)
  - 7.3 `uninstall.sh`, `mygit.service` (gunicorn 2 worker + hardening), `mygit.env.example`
  - 7.4 `build_offline_bundle.sh` (docker ubuntu:22.04 경유)
  - 7.5 `README-OFFLINE.md` 한글 가이드
  - 7.6 실제 번들 생성 & `--network none` 컨테이너 E2E 검증
    - 9 wheels, 37 .deb, 16MB tarball
    - 설치/CLI/gunicorn/HTTP 200/git push/clone 전부 성공
  - 부수: UTF-8 BOM 제거(pyproject/README/CLAUDE/requirements), CLI 래퍼 `/opt/mygit/bin/mygit-cli` 추가, `/etc/mygit` 디렉토리 권한 0770 로 수정

## Verification Results (Step 7)

- E2E 오프라인 설치: ✅ `[install] exit=0` on ubuntu:22.04 with `--network none`
- CLI 작동: ✅ add-user / create-repo / list-repos
- gunicorn 기동: ✅ `Listening at: http://127.0.0.1:8000`
- Basic Auth + git info/refs: ✅ HTTP 200
- git push → clone 왕복: ✅ 내용 일치 ("hello mygit")
- pytest 회귀: 40/41 통과. 1 실패는 **기존 Windows-only 테스트** (`test_git_clone_wrong_password_fails` 가 `PATH` 를 하드코딩하여 Linux 에서 불가능). Step 7 변경과 무관.

## Known Gaps (범위 밖 — 향후)

- Ubuntu 24.04 지원 (Python 3.12 wheel + noble .deb 별도 번들)
- arm64 지원
- HTTPS / 리버스 프록시 (nginx/caddy)
- logrotate 설정
- `test_git_clone_wrong_password_fails` Linux 호환 개선 (PATH 하드코딩 제거)
