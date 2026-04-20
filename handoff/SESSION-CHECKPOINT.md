# Session Checkpoint — 2026-04-20

## Where We Stopped

**Step 7 전체 완료.** 에어갭 Ubuntu 22.04 오프라인 인스톨러 배포 가능.

아티팩트:
- `dist/setup/mygit-offline-v0.7.0-ubuntu2204-x86_64.tar.gz` (16MB)
- `dist/setup/mygit-offline-v0.7.0-ubuntu2204-x86_64.tar.gz.sha256`

USB 복사 → 폐쇠망 Ubuntu 22.04 서버 → `tar xzf ... && sudo ./install.sh --start` 로 기동 완료 가능.

## What Was Decided This Session

- Ubuntu 22.04 LTS / x86_64 / Python 3.10 단일 타깃
- gunicorn 23.0.0 WSGI (sync worker, 2 process, 120s timeout)
- systemd 서비스 + 전용 `mygit` 계정 + 보안 하드닝(NoNewPrivileges, ProtectSystem=strict 등)
- git 바이너리는 번들 .deb 37 개 (git + perl 의존 포함)
- 런타임 경로: `/opt/mygit`, `/var/lib/mygit/repos`, `/etc/mygit`, `/var/log/mygit`
- CLI 래퍼 `/opt/mygit/bin/mygit-cli` 로 cwd + env 로딩 문제 해결
- `/etc/mygit` 권한 0770 (mygit 그룹 쓰기 필요)

## Verified

- `--network none` 컨테이너에서 오프라인 설치 성공
- add-user, create-repo, list-repos CLI 작동
- gunicorn 기동 → Basic Auth → `git push`/`git clone` 왕복 내용 일치
- pytest 40/41 통과 (1 실패는 기존 Windows-only PATH 하드코딩 문제)

## New/Changed Files

```
# 루트 편집
requirements.txt        (+gunicorn==23.0.0, BOM 제거)
pyproject.toml          (version 0.7.0, +gunicorn, BOM 제거)
VERSION                 (신규: 0.7.0)
.gitignore              (+dist/, vendor/)
README.md               (BOM 제거)
CLAUDE.md               (BOM 제거)
requirements-dev.txt    (BOM 제거)

# 오프라인 신규
scripts/offline/install.sh
scripts/offline/uninstall.sh
scripts/offline/mygit.service
scripts/offline/mygit.env.example
scripts/offline/build_offline_bundle.sh
scripts/offline/README-OFFLINE.md

# 빌드 산출 (.gitignore 적용됨)
dist/setup/mygit-offline-v0.7.0-ubuntu2204-x86_64.tar.gz
dist/setup/mygit-offline-v0.7.0-ubuntu2204-x86_64.tar.gz.sha256
dist/setup/mygit-offline-v0.7.0-ubuntu2204-x86_64/   (풀린 번들 디렉토리)

# handoff
handoff/ARCHITECT-BRIEF.md      (Step 7 브리프)
handoff/BUILD-LOG.md             (Step 7 기록)
handoff/SESSION-CHECKPOINT.md    (이 파일)
```

## Still Open

- **Git 커밋 + 태그 v0.7.0** — Project Owner 승인 후 Arch 가 수행 (배포 게이트)
- **실제 에어갭 서버에 USB 반입 & 설치** — 최종 사용자 검증
- **Known Gaps** 해소 항목들은 Step 8+ 로 분리

## Resume Prompt

You are Arch on mygit. Read SESSION-CHECKPOINT.md.
Step 7 완료. 다음: git 커밋/태그 혹은 Step 8 착수.
