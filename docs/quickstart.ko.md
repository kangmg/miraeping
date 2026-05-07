# :fire: 빠른 시작

몇 분 안에 miraeping을 시작하세요! 이 가이드는 Bash와 Python 사용을 위한 필수 설정을 다룹니다.

## 사전 요구사항

- Python 3.7 이상
- 봇 권한이 있는 Slack 워크스페이스
- Slack 사용자 ID 및 봇 토큰 ([설정 가이드](develop.md))

## 환경 설정

선호하는 Python 환경 관리자를 선택하세요:

=== "uv"
    ```bash
    uv venv -p 3.7
    ```

=== "conda"
    ```bash
    conda create -n miraeping python=3.7
    conda activate miraeping
    ```


## 설치

저장소를 클론하고 설정 스크립트를 실행하세요:

```bash
git clone https://github.com/kangmg/miraeping
cd miraeping && bash setup.sh && cd ..
```

설정 중에 다음을 입력하라는 메시지가 표시됩니다:

- **Slack 사용자 ID**: `U0XXXXXXXXX` (본인의 멤버 ID)
- **봇 토큰**: `xoxb-YOUR-BOT-TOKEN-HERE` (`xoxb-`로 시작)

설정이 완료되면 셸 설정을 다시 로드하세요:

```bash
source ~/.bashrc
```

!!! tip "setup.sh가 하는 일"
    - bash 헬퍼를 `~/.miraeping/miraeping`에 설치
    - Slack 자격 증명으로 `~/.miraeping/credentials` 생성 (권한 `600`)
    - `~/.bashrc`에 `source ~/.miraeping/miraeping` 추가 (없는 경우)

## Bash 사용법

간단한 메시지로 bash 설정을 테스트하세요:

```bash
miraeping_send 'miraeping에서 보낸 메시지!'
```

봇으로부터 Slack DM을 받아야 합니다. 더 많은 사용법은:

```bash
miraeping_send '더 많은 사용법: https://kangmg.github.io/miraeping/ko/usage/#bash-helper'
```

### 빠른 예제: SGE 작업 알림

```bash
#!/bin/bash
#$ -V
#$ -S /bin/bash
#$ -N my_job
#$ -cwd

source ~/.miraeping/miraeping

# 계산 작업
./run_simulation.sh

# 완료 시 알림
miraeping_send "작업 $JOB_NAME이 $PWD에서 완료되었습니다"
```

## Python 사용법

Python 패키지를 설치하세요:

```bash
pip install miraeping
```

Python 설정을 테스트하세요:

```bash
python3 - <<'PY'
import miraeping

miraeping.send("miraeping Python API에서 보낸 메시지!")
miraeping.send("자세한 정보: https://kangmg.github.io/miraeping/ko/usage/#python-api")
PY
```

### 빠른 예제: 계산 모니터링

```python
import miraeping
import time

with miraeping.Job("모델 학습") as job:
    for epoch in range(10):
        # 학습 코드
        time.sleep(1)
        job.send(f"에포크 {epoch+1}/10 완료")
    
job.send("학습 완료!")
```

## 다음 단계

- **[사용자 가이드](usage.md)**: Bash 및 Python에 대한 자세한 사용 예제
- **[개발자 가이드](develop.md)**: Slack 봇 및 명령 서버 설정
- **[GitHub 저장소](https://github.com/kangmg/miraeping)**: 소스 코드 및 이슈

## Slack 명령어 사용하기

!!! info "`/qq`, `/qstat`, `/gpu` 같은 Slack 슬래시 명령어를 사용하고 싶으신가요?"
    클러스터 상태 확인을 위한 Slack 명령어를 사용하려면:
    
    1. 봇을 Slack 워크스페이스에 추가
    2. 관리자에게 **Slack ID** (`U0XXXXXXXXX`)와 **Mirae 서버 아이디**를 알려주세요
    
    **[→ Slack 명령어에 대해 더 알아보기](usage.md#2-slack-slash-commands)**

## 문제 해결

!!! warning "자격 증명을 찾을 수 없나요?"
    설정 후 `source ~/.bashrc`를 실행했는지 확인하세요. bash 헬퍼와 Python API 모두 `~/.miraeping/credentials`에서 읽습니다.

!!! warning "메시지를 받지 못하나요?"
    - Slack 사용자 ID가 올바른지 확인하세요 ([개발자 가이드](develop.md#slack-사용자-id-찾기) 참조)
    - 봇이 워크스페이스에 추가되었는지 확인하세요
