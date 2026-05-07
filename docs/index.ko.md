# miraeping

클러스터 서버에서 SGE 잡과 Python 계산에 Slack DM 알림을 보내고, Slack 명령으로 서버 상태도 조회하는 도구입니다.

---

## 이 프로젝트가 제공하는 것

`miraeping`에는 두 가지 사용 흐름이 있습니다.

| 흐름 | 내용 | 시작 위치 |
|------|------|-----------|
| **잡 알림** | SGE 잡 스크립트나 Python 코드에서 Slack DM 알림 전송 | [사용자 가이드 -> Notify](usage.md#1-notify-miraeping) |
| **Slack 서버 상태 명령어** | `/qq`, `/qstat`, `/qwd`, `/gpu`, `/nvidia-smi`로 큐, 잡, GPU 상태 조회. 먼저 관리자 또는 서버 운영자가 command server를 실행해야 함 | [사용자 가이드 -> Slash commands](usage.md#2-slack-slash-commands) |
| **Command server 셋업** | Slack 앱, Socket Mode, slash command, 토큰, 사용자 매핑, allowlist 설정 | [개발자 가이드 ->](develop.md) |

대부분의 사용자는 사용자 가이드만 보면 됩니다. command server를 운영하는 사람은 개발자 가이드를 보면 됩니다.

---

역할별로 선택하세요:

| 역할 | 설명 | 문서 |
|------|------|------|
| **사용자** | 잡 알림을 보내거나 이미 준비된 Slack 명령어 사용 | [사용자 가이드 ->](usage.md) |
| **관리자** | Slack 앱 생성 및 command server 운영 | [개발자 가이드 ->](develop.md) |
