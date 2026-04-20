# mygit 오프라인 설치 가이드 (Ubuntu 22.04 LTS)

폐쇠망(에어갭) 환경의 Ubuntu 22.04 LTS 서버에 mygit Smart HTTP Git 서버를 설치한다.
본 번들은 **인터넷 연결 없이** 단독으로 설치가 완료되도록 구성되어 있다.

---

## 1. 시스템 요구사항

| 항목 | 조건 |
|---|---|
| OS | Ubuntu 22.04 LTS (Jammy) |
| 아키텍처 | x86_64 |
| Python | 3.10 이상 (Ubuntu 22.04 기본 `python3`, `python3-venv` 필요) |
| 권한 | root (`sudo`) |
| 포트 | 기본 8000/tcp (설정 변경 가능) |
| 디스크 | 약 100MB + 리포 용량 |

> `python3-venv` 패키지가 누락된 최소 설치본일 경우, 본 번들은 **설치를 중단한다**.
> 사내 APT 미러 또는 별도 .deb 로 `python3-venv` 를 먼저 확보할 것.

---

## 2. 번들 구조

```
mygit-offline-v{VERSION}-ubuntu2204-x86_64/
├── install.sh           # 메인 설치 스크립트 (root)
├── uninstall.sh         # 제거 스크립트
├── VERSION              # 버전 문자열
├── README-OFFLINE.md    # 이 문서
├── src/                 # mygit 소스 (/opt/mygit 로 복사됨)
├── vendor/
│   ├── wheels/          # Flask, gunicorn 등 Python 의존 wheel
│   └── debs/            # git + 의존 .deb (22.04 jammy)
├── systemd/mygit.service
└── config/mygit.env.example
```

---

## 3. 설치

```bash
# 1) 번들 압축 해제
tar xzf mygit-offline-v*-ubuntu2204-x86_64.tar.gz
cd mygit-offline-v*-ubuntu2204-x86_64

# 2) 설치 (서비스까지 즉시 기동)
sudo ./install.sh --start
```

### 설치 옵션

| 옵션 | 설명 |
|---|---|
| `--start` | 설치 후 `systemctl start mygit` 자동 실행 |
| `--skip-git` | 이미 git 이 설치된 환경에서 번들 .deb 설치 건너뜀 |
| `--prefix <path>` | 설치 경로 변경 (기본: `/opt/mygit`) |

### 설치 후 생성되는 경로

| 경로 | 용도 |
|---|---|
| `/opt/mygit/` | 소스 및 venv |
| `/var/lib/mygit/repos/` | Git bare 리포 저장 |
| `/etc/mygit/mygit.env` | 환경 변수 설정 |
| `/etc/mygit/users.json` | 사용자 인증 (설치 직후 없음 — `add-user` 로 생성) |
| `/var/log/mygit/` | gunicorn access/error 로그 |
| `/etc/systemd/system/mygit.service` | systemd 유닛 |

---

## 4. 최초 설정

### 4-1. 사용자 추가

```bash
sudo -u mygit /opt/mygit/bin/mygit-cli add-user alice
# Password: (입력)
# Confirm : (입력)
```

→ `/etc/mygit/users.json` 에 pbkdf2_sha256 해시로 저장.

### 4-2. 리포 생성

```bash
# 단일 리포
sudo -u mygit /opt/mygit/bin/mygit-cli create-repo demo.git

# nested 경로 (팀/프로젝트 형식)
sudo -u mygit /opt/mygit/bin/mygit-cli create-repo teamA/backend/service.git
```

### 4-3. 리포 목록

```bash
sudo -u mygit /opt/mygit/bin/mygit-cli list-repos
```

---

## 5. 서비스 관리

```bash
sudo systemctl start   mygit      # 시작
sudo systemctl stop    mygit      # 중지
sudo systemctl restart mygit      # 재시작
sudo systemctl status  mygit      # 상태 확인
sudo systemctl disable mygit      # 부팅 시 자동 시작 해제
sudo systemctl enable  mygit      # 부팅 시 자동 시작 (설치 시 기본 활성)
```

---

## 6. 로그 확인

```bash
# systemd 저널 (gunicorn stderr 포함)
sudo journalctl -u mygit -f
sudo journalctl -u mygit -n 100

# gunicorn 액세스 로그
sudo tail -f /var/log/mygit/access.log

# gunicorn 에러 로그
sudo tail -f /var/log/mygit/error.log
```

---

## 7. 클라이언트 사용 예

서버 IP 를 `192.168.10.50` 으로 가정:

```bash
# clone
git clone http://alice@192.168.10.50:8000/demo.git
# → Password 입력

# push (자격 증명 저장)
git config --global credential.helper store
git clone http://alice@192.168.10.50:8000/demo.git
echo "hello" > README.md
git add README.md && git commit -m "init"
git push origin master
```

---

## 8. 설정 변경

`/etc/mygit/mygit.env` 편집 후 서비스 재시작:

```bash
sudo nano /etc/mygit/mygit.env
sudo systemctl restart mygit
```

주요 설정:
- `MYGIT_PORT` — 바인드 포트
- `MYGIT_REPOS_ROOT` — 리포 저장 경로 (이동 시 실제 디렉토리도 이동 필요)
- `MYGIT_ALLOW_ANONYMOUS_READ` — `true` 설정 시 읽기는 비밀번호 불필요
- `MYGIT_ALLOW_ANONYMOUS_WRITE` — 공개 쓰기 허용(권장하지 않음)

---

## 9. 문제 해결

| 증상 | 원인 / 해결 |
|---|---|
| `python3-venv` 미설치 오류 | 사내 APT 또는 별도 .deb 로 `python3-venv` 설치 |
| `git 설치 실패` | `dpkg -i vendor/debs/*.deb` 수동 실행, 의존 메시지 확인 |
| `서비스 시작 실패` | `journalctl -u mygit -n 50` 확인. 주로 포트 충돌, 권한 문제 |
| `Permission denied (repos)` | `chown -R mygit:mygit /var/lib/mygit/repos` |
| `Port 8000 already in use` | `mygit.env` 에서 `MYGIT_PORT` 변경 후 restart |
| `push 시 401 Unauthorized` | 사용자 미등록 또는 비밀번호 불일치 — `add-user` 재실행 |
| `push 시 500/타임아웃 (대용량)` | `mygit.service` 의 `--timeout 120` 값을 늘려 restart |

---

## 10. 제거

```bash
# 기본 제거 (데이터/설정 보존)
sudo ./uninstall.sh

# 데이터/설정/계정까지 완전 제거
sudo ./uninstall.sh --purge
```

---

## 11. 버전 및 해시 검증

```bash
cat VERSION
sha256sum -c mygit-offline-v*-ubuntu2204-x86_64.tar.gz.sha256
```
