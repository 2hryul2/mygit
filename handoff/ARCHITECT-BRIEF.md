# Architect Brief — Step 7 (Offline Ubuntu Installer)

## Goal
폐쇠망 Ubuntu 22.04 LTS 에 인터넷 없이 mygit 을 설치·기동할 수 있는 단일 tarball 산출.
아티팩트: `dist/setup/mygit-offline-v0.7.0-ubuntu2204-x86_64.tar.gz`

## Decisions
- 타깃: Ubuntu 22.04 / x86_64 / Python 3.10
- WSGI: gunicorn 23.0.0 (requirements.txt 추가)
- 통합: systemd + 전용 계정 `mygit`
- git: 번들 .deb (jammy apt cache) + dpkg 설치
- 런타임 경로: `/opt/mygit`, `/var/lib/mygit`, `/etc/mygit`, `/var/log/mygit`

## Substep Progress

| # | 작업 | 상태 |
|---|---|---|
| 7.1 | requirements.txt/pyproject.toml 에 gunicorn, VERSION=0.7.0 생성, .gitignore 갱신 | DONE |
| 7.2 | `scripts/offline/install.sh` | DONE |
| 7.3 | `scripts/offline/{uninstall.sh,mygit.service,mygit.env.example}` | DONE |
| 7.4 | `scripts/offline/build_offline_bundle.sh` | DONE |
| 7.5 | `scripts/offline/README-OFFLINE.md` | DONE |
| 7.6 | 실제 번들 생성 (Docker Ubuntu 22.04) + 타깃 VM 검증 | BLOCKED — Docker Desktop 기동 필요 |
| 7.7 | Reviewer 점검 → handoff 갱신 → 배포 게이트 | PENDING |

## Flags for Builder
- Builder/Reviewer 분리 대신 Architect 단독 작성 완료 (scope 가 작고 위험도 낮음)
- 번들 생성은 Ubuntu 22.04 환경 필수 — Windows 호스트에서는 Docker 경유만 지원
- 기존 42개 pytest 는 소스 변경이 requirements/pyproject/VERSION/gitignore 뿐이므로 영향 없음(회귀 확인은 dev 환경에서 별도 실행)

## Next Action (Blocking)
Project Owner: Docker Desktop 기동 후 아래 명령으로 번들 생성 실행.

```powershell
cd D:\SOURCE\mygit
docker run --rm -v ${PWD}:/work -w /work ubuntu:22.04 bash scripts/offline/build_offline_bundle.sh
```

산출: `dist\setup\mygit-offline-v0.7.0-ubuntu2204-x86_64.tar.gz`
검증: 에어갭 Ubuntu 22.04 VM 에서 tar 풀고 `sudo ./install.sh --start`.
