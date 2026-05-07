# 개발자 가이드

이 문서는 **기능 2: Slack command server** 운영자를 위한 가이드입니다.

command server는 Slack에서 `/qq`, `/qstat`, `/qwd`, `/gpu`, `/nvidia-smi` 같은 slash command를 처리합니다. 이것은 **기능 1: Notify (`miraeping`)**와 별도입니다. 사용자는 이 서버가 없어도 잡 알림을 보낼 수 있고, 이 서버를 실행한다고 사용자 계정에 bash 헬퍼가 자동 설치되지는 않습니다.

서버 운영자에게 필요한 것:

| 요구사항 | 이유 |
|----------|------|
| Socket Mode가 활성화된 Slack 앱 | 클러스터 서버가 outbound WebSocket으로 slash command를 받을 수 있게 함 |
| `SLACK_BOT_TOKEN` (`xoxb-...`) | 명령어 응답과 사용자 DM 전송 |
| `SLACK_APP_TOKEN` (`xapp-...`) | Socket Mode 연결 생성 |
| Slash commands | Slack에 `/qq`, `/qstat`, `/qwd`, `/gpu`, `/nvidia-smi` 등록 |
| 선택적 사용자 매핑과 allowlist | Slack 사용자와 클러스터 계정을 연결하고 명령어 사용자를 제한 |

---

## 1단계 — Slack 앱 생성

1. [https://api.slack.com/apps](https://api.slack.com/apps)로 이동 → **"Create New App"** 클릭 → **"From scratch"** 선택
2. 앱 이름 입력 (예: `miraeping`) 후 워크스페이스 선택
3. **Create App** 클릭

---

## 2단계 — Socket Mode 활성화

App Settings → **Socket Mode** → **Enable Socket Mode** 토글 켜기

---

## 3단계 — App-Level Token 발급

App Settings → **Basic Information** → 하단의 **App-Level Tokens** → **Generate Token and Scopes** 클릭

- Token name: 임의 이름 (예: `miraeping-socket`)
- Scope: `connections:write`
- **Generate** 클릭 → 토큰 복사 (`xapp-...`로 시작)

---

## 4단계 — OAuth 스코프 추가

App Settings → **OAuth & Permissions** → **Bot Token Scopes** → **Add an OAuth Scope**

아래 세 가지를 모두 추가:

- `chat:write`
- `im:write`
- `commands`

---

## 5단계 — 슬래시 명령어 생성

App Settings → **Slash Commands** → **Create New Command** — 아래 명령어마다 반복:

| 명령어 | Short Description (Slack에 입력하는 설명) |
|--------|------------------------------------------|
| `/qq` | Current node usage status |
| `/qstat` | Your submitted job status |
| `/qwd` | Show working directories of your current jobs |
| `/gpu` | Show GPU memory and utilization on the GPU node |
| `/nvidia-smi` | Alias for /gpu |

각 명령어 생성 시 **Request URL 필드는 비워두세요**. Socket Mode는 WebSocket으로 명령어를 라우팅하므로 URL이 필요 없습니다.

---

## 6단계 — 워크스페이스에 앱 설치

App Settings → **Install App** → **Install to Workspace** → **Allow** 클릭

**Bot User OAuth Token** (`xoxb-...`로 시작) 복사

---

## 7단계 — 자격 증명 정리

이제 다음 두 가지를 보유하게 됩니다:

- `SLACK_BOT_TOKEN` = `xoxb-...` (Bot User OAuth Token)
- `SLACK_APP_TOKEN` = `xapp-...` (App-Level Token)

각 사용자에게는 `SLACK_BOT_TOKEN`만 공유하세요.  
`SLACK_USER_ID`는 각 사용자가 Slack에서 본인 값을 직접 확인해 `setup.sh` 입력 시 사용하면 됩니다.  
`SLACK_APP_TOKEN`은 서버에만 보관합니다.

---

## 8단계 — 서버에 miraeping 설치

Slack 명령어 서버를 실행할 conda 또는 uv 환경 안에서 아래 명령어를 실행하세요.

```bash
# PyPI에서 uv 환경에 설치:
uv venv -p 3.11 .venv
uv pip install "miraeping[server]"

# 소스 체크아웃에서 설치:
git clone https://github.com/kangmg/miraeping
cd miraeping
uv sync --extra server

# 또는 체크아웃에서 uv로 바로 실행:
uv run --extra server miraeping-slack-serve --help
```

---

## 9단계 — 환경 변수 설정

필수:

```bash
export SLACK_BOT_TOKEN="xoxb-..."
export SLACK_APP_TOKEN="xapp-..."
```

선택:

```bash
# Slack 사용자 ID → Unix 사용자명 매핑 (/qstat, /qwd에 필요)
# 멀티라인 형식 지원, trailing 쉼표 허용
SLACK_QSTAT_USER_MAP="
UXXXXXXXXXX:alice,
UYYYYYYYYYY:bob
"
export SLACK_QSTAT_USER_MAP

# /gpu, /nvidia-smi용 SSH 호스트 (기본값: g01)
# 유효한 호스트명 형식: 영문자·숫자·하이픈·점 (첫 글자는 영문자 또는 숫자)
export SLACK_GPU_SSH_HOST="g01"

# 슬래시 명령어를 사용할 수 있는 Slack 사용자 ID (쉼표 구분)
export SLACK_ALLOWED_USER_IDS="UXXXXXXXXXX,UYYYYYYYYYY"

# 슬래시 명령어를 사용할 수 있는 Slack 채널 ID (쉼표 구분)
export SLACK_ALLOWED_CHANNEL_IDS="C0XXXXXXXXX"

# 허용 목록 강제 여부. 1=강제, 0=비활성
# 기본값: ALLOWED_* 목록이 설정되어 있으면 자동으로 강제 적용
export SLACK_ENFORCE_USER_ALLOWLIST=1
export SLACK_ENFORCE_CHANNEL_ALLOWLIST=0
```

---

## 10단계 — 서버 실행

포그라운드 (테스트용):

```bash
miraeping-slack-serve
```

백그라운드 (운영):

```bash
miraeping-slack-start
miraeping-slack-status
miraeping-slack-restart
miraeping-slack-stop
```

로그는 `~/.miraeping_slack_server.log`에 기록됩니다.

---

## 11단계 — 사용자 등록 및 자격 증명 공유

각 사용자에게 아래를 요청하세요:

1. Slack 사용자 ID 확인: Slack → 프로필 → 세 점 메뉴 → **"멤버 ID 복사"**
2. 클러스터에서 `echo $USER` 실행 후 두 값을 알려달라고 요청

`SLACK_QSTAT_USER_MAP`에 추가 (멀티라인 형식 지원):

```bash
SLACK_QSTAT_USER_MAP="
UXXXXXXXXXX:alice,
UYYYYYYYYYY:bob
"
export SLACK_QSTAT_USER_MAP
```

각 사용자에게 `SLACK_BOT_TOKEN`을 공유하여 본인 계정에서 `setup.sh`를 실행할 수 있도록 합니다.
`SLACK_APP_TOKEN`은 서버에만 보관하고 사용자에게 공유하지 마세요.

---

## Socket Mode를 사용하는 이유 (아키텍처)

```
Lab server (172.20.x.x, private)
  └─ miraeping-slack-serve
       └─ outbound WebSocket ──────► Slack API (api.slack.com)
                                          ▲
                               User types /qq in Slack
```

공개 URL, 포트 포워딩, 리버스 프록시가 필요 없습니다. 서버가 아웃바운드로 연결을 시작합니다.

---

## 보안 유의사항

**봇 토큰 공유 구조**

모든 사용자가 동일한 `SLACK_BOT_TOKEN`을 사용합니다. Slack 봇 아키텍처상 단일 토큰 구조는 불가피합니다. 피해를 최소화하려면:

- 토큰에 최소 스코프만 부여되어 있습니다: `chat:write`, `im:write`, `commands`. 유출되더라도 DM 발송만 가능하며, 메시지 읽기·파일 접근·워크스페이스 관리는 불가합니다.
- 토큰 유출이 의심될 경우 즉시 **App Settings → OAuth & Permissions → Revoke Token**에서 토큰을 폐기하고, 앱을 재설치해 새 토큰을 생성한 뒤 사용자들에게 재배포하세요.
- 사용자에게는 `.bashrc`에 직접 토큰을 노출하는 대신 `~/.miraeping/credentials` (chmod 600)에 저장하도록 안내하세요.
- 서버에 `SLACK_ALLOWED_USER_IDS`를 설정해 등록된 랩 구성원만 슬래시 명령어를 사용할 수 있도록 제한하세요.

**기타 유의사항**

- `SLACK_BOT_TOKEN`과 `SLACK_APP_TOKEN`은 버전 관리에 절대 커밋하지 마세요 — `chmod 600` env 파일에 보관
- `SLACK_APP_TOKEN`은 서버에만 보관하고, 사용자에게는 `SLACK_BOT_TOKEN`만 공유
- `SLACK_ALLOWED_USER_IDS` + `SLACK_ENFORCE_USER_ALLOWLIST=1` 항상 설정하세요 — 미설정 시 서버 시작 시 WARNING이 출력됩니다
- uv 관리 Python을 사용하는 서버에서 SSL 인증서 오류 발생 시: `export SSL_CERT_FILE=/etc/pki/tls/certs/ca-bundle.crt`
- credentials 파일 (`~/.miraeping/credentials`)은 따옴표 없이 `KEY=VALUE` 형식으로 작성

---

## 릴리즈 체크리스트

1. `miraeping/_version.py` 버전 업데이트
2. `uv run --extra dev pytest -q`
3. `uv build`
4. `uv run --with twine twine check --strict dist/*`
5. Twine + PyPI 토큰으로 업로드
