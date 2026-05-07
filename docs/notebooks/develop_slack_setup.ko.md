# 개발자 셋업

이 페이지는 Slack slash command 서버를 운영하는 유지보수자를 위한 단계별 가이드입니다.

## 범위

이 문서는 아래를 다룹니다.
- Slack 앱/명령어 엔드포인트 설정
- 서버 환경 변수 및 실행 모드
- `/qwd` 포함 명령어 검증 절차
- 배포 전 점검 및 보안 체크

## 1) Slack 앱 준비

Slack 앱을 생성(또는 기존 앱 사용)하고 아래를 설정하세요.

- OAuth scope:
  - `chat:write`
  - `im:write`
  - `commands`
- 워크스페이스에 Install/Reinstall

반드시 확보할 값:
- Bot token (`xoxb-...`)
- Signing secret

## 2) Slash command 엔드포인트 등록

각 명령어의 Request URL:

- `/qq` -> `https://<YOUR_SERVER>/slack/qq`
- `/qstat` -> `https://<YOUR_SERVER>/slack/qstat`
- `/qwd` -> `https://<YOUR_SERVER>/slack/qwd`
- `/gpu` -> `https://<YOUR_SERVER>/slack/gpu`
- `/nvidia-smi` -> `https://<YOUR_SERVER>/slack/nvidia-smi`

`/qwd` 응답 필드:
- `JOB_ID`
- `JOB_NAME`
- `STATE`
- `SUBMISSION_DIR`

`SUBMISSION_DIR`는 `qstat -j <job_id>`의 `sge_o_workdir` 값을 파싱해 채웁니다.
응답은 ANSI 색상 없는 plain text 표입니다.

## 3) 서버 환경 변수

필수:
- `SLACK_SIGNING_SECRET`

운영 시 유용:
- `SLACK_QSTAT_USER_MAP` (예: `U01:alice,U02:bob`)
- `SLACK_GPU_SSH_HOST`
- `SLACK_ALLOWED_USER_IDS`
- `SLACK_ALLOWED_CHANNEL_IDS`
- `SLACK_ENFORCE_USER_ALLOWLIST`
- `SLACK_ENFORCE_CHANNEL_ALLOWLIST`

## 4) 서버 실행 모드

Foreground:

```bash
export SLACK_SIGNING_SECRET="..."
uv run miraeping-slack-serve --host 0.0.0.0 --port 8080
```

Background:

```bash
uv run miraeping-slack-start --host 0.0.0.0 --port 8080
uv run miraeping-slack-status
uv run miraeping-slack-stop
```

로컬 테스트 전용(루프백에서만 서명 검증 비활성):

```bash
uv run miraeping-slack-serve --host 127.0.0.1 --port 8080 --allow-insecure-local
```

## 5) 기능 검증 체크리스트

배포 후 Slack에서 명령어를 직접 확인하세요.

- `/qq`: 큐/노드 요약 표 반환
- `/qstat`: 매핑된 사용자 잡 목록 요약
- `/qwd`: 매핑된 사용자 잡 목록 + `sge_o_workdir`
- `/gpu`, `/nvidia-smi`: GPU 사용률 요약

`/qstat` 또는 `/qwd`에서 사용자 미등록 메시지가 나오면:
- `SLACK_QSTAT_USER_MAP`에 사용자 추가
- 서버 재시작 후 재검증

## 6) `/qwd` 동작 기준

다음 셸 동작과 동일한 의미를 가져야 합니다.

```bash
qstat | awk 'NR>2 && $1 ~ /^[0-9]+$/ {print $1 "\t" $3 "\t" $5}'
qstat -j <job_id> | awk -F': *' '/sge_o_workdir/ {print $2; exit}'
```

활성 잡이 없을 때는 빈 표 대신 명확한 안내 문구를 반환해야 합니다.

## 7) 배포 전 점검

```bash
uv run --extra dev pytest -q tests/test_slack_parsing.py tests/test_slack_commands.py
uv build
uv run --with twine twine check --strict dist/*
```

검증이 통과하면 Twine + PyPI 토큰으로 수동 업로드합니다.

## 8) 보안 체크리스트

- 모든 시크릿은 환경 변수로만 관리
- 사용자 알림용 자격 증명은 `~/.miraeping/credentials` 사용
- 운영 환경에서 Slack signature 검증 강제
- 필요하면 user/channel allowlist 활성화

## 9) 유지보수 메모

- 사용자 헬퍼 명령은 `miraeping_send`, `miraeping_monitor`, `miraeping_stop` 중심으로 유지
- 제거된 레거시 명령은 신규 문서에 다시 넣지 않기
