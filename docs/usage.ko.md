# 사용자 가이드

이 문서는 사용자 입장에서 필요한 두 가지 독립 기능을 나누어 설명합니다.

| 기능 | 사용하는 상황 | 사용자 쪽 설정 |
|------|---------------|----------------|
| **1. Notify (`miraeping`)** | SGE 잡 스크립트나 Python 코드에서 Slack DM 알림 전송 | Slack 앱 추가, `SLACK_BOT_TOKEN` 받기, 본인 `SLACK_USER_ID` 설정, bash 헬퍼 또는 Python 패키지 설치 |
| **2. Slack slash commands** | Slack에서 `/qq`, `/qstat`, `/qwd`, `/gpu`, `/nvidia-smi`로 서버 상태 조회 | Slack 앱 추가, 본인 Slack 멤버 ID 복사, 관리자에게 Slack ID와 클러스터 계정명 등록 요청 |

두 기능은 서로 독립적입니다. Notify 알림은 Slack command server가 실행 중일 필요가 없습니다. Slack slash command를 쓰기 위해 사용자가 bash 헬퍼나 Python 패키지를 로컬에 설치할 필요도 없습니다.

---

## 공통 Slack 단계

아래 단계는 두 기능 모두에서 사용할 수 있습니다.

**1) 본인 Slack 멤버 ID 확인**

Slack 열기 -> 프로필 사진 클릭 -> "프로필" -> 세 점 메뉴 -> **"멤버 ID 복사"** (`UXXXXXXXXXX` 형식).
이 값은 알림 기능의 `SLACK_USER_ID`로도 사용되고, Slack command 등록에도 사용됩니다.
아래 이미지를 참고하세요. 필요한 값은 Slack 멤버 ID이며, 표시 이름·이메일·클러스터 계정명이 아닙니다.

<img src="../../assets/member_id.png" alt="Slack에서 멤버 ID 복사" width="720" />

**2) Slack에서 miraebot 앱 추가**

Slack -> Apps -> `miraebot` 검색 -> Slack 워크스페이스에 앱을 추가합니다.
아래 이미지를 참고하세요. `miraebot`이 보이지 않거나 Slack에서 승인을 요구하면 워크스페이스 관리자에게 앱 승인 또는 설치를 요청하세요.

<img src="../../assets/add_bot.png" alt="Slack에서 miraebot 앱 추가" width="720" />

---

## 기능 1 - Notify (`miraeping`)

SGE 잡 스크립트나 Python 코드에서 Slack DM 알림을 보내고 싶을 때 사용하는 기능입니다.

알림 기능은 사용자의 잡 스크립트나 Python 프로세스에서 Slack으로 직접 메시지를 보냅니다. Slack command server가 필요하지 않습니다.

### Notify 셋업

워크플로우에 따라 설치 경로를 선택하세요:

| 워크플로우 | 설치 | 자격 증명 |
|------------|------|-----------|
| SGE 스크립트용 Bash 헬퍼 | `git clone` + `bash setup.sh` | 관리자에게 받은 `SLACK_BOT_TOKEN` + 본인 Slack 멤버 ID (`SLACK_USER_ID`) |
| Python API | conda에서는 `pip install miraeping`, uv에서는 `uv venv -p 3.7` + `uv pip install miraeping` | 동일한 `SLACK_BOT_TOKEN` + `SLACK_USER_ID`; `~/.miraeping/credentials` 또는 환경변수에서 읽음 |

**1) 관리자에게 `SLACK_BOT_TOKEN` 받기**

관리자가 봇 토큰(`xoxb-...`)을 공유해줍니다.

**2A) Bash 헬퍼 경로: setup.sh 실행**

```bash
git clone https://github.com/kangmg/miraeping
cd miraeping
bash setup.sh
source ~/.bashrc
```

`setup.sh`를 실행하면 `SLACK_BOT_TOKEN`과 `SLACK_USER_ID`를 대화형으로 입력받은 뒤(입력 마스킹), bash 헬퍼를 설치하고 자격 증명을 `~/.miraeping/credentials` (chmod 600)에 저장합니다.

**2B) Python API 경로: PyPI에서 설치**

```bash
# conda
conda create -n miraeping python=3.7 -y
conda activate miraeping
pip install miraeping

# uv
uv venv -p 3.7 .venv
uv pip install miraeping
```

**확인 (Bash 헬퍼 경로):**

```bash
miraeping_send "hello from setup test"
```

Slack에 DM이 도착하면 완료.

**확인 (Python API 경로):**

```python
import miraeping

miraeping.send("hello from setup test")
```

---

### Bash 헬퍼

`source ~/.miraeping/miraeping` 이후 아래 세 함수를 사용할 수 있습니다:

> **런타임 파일** — PID, 채널 캐시, 제출 시각은 `~/.miraeping/run/`에 저장됩니다 (자동 생성, chmod 700). 잡이 비정상 종료된 경우 잔여 파일을 안전하게 삭제할 수 있습니다: `rm -f ~/.miraeping/run/miraeping_<JOB_ID>.*`

| 함수 | 설명 |
|------|------|
| `miraeping_send [comment]` | 잡 헤더 + 선택적 코멘트를 DM으로 전송 |
| `miraeping_monitor [cmd] [interval]` | 백그라운드 주기적 상태 DM 시작 |
| `miraeping_stop` | 모니터 중지 및 백그라운드 상태 정리 |

모든 메시지에는 잡 헤더가 자동으로 포함됩니다:
```
> JOB_NAME (JOB_ID)  |  submitted: MM:DD:HH:MM  |  runtime: HH:MM:SS
```

---

### SGE 잡 스크립트

아래 예시는 기존 SGE 스크립트의 문맥을 유지하고, 추가해야 하는 줄만 `+`로 표시합니다.

#### 기본: 종료 알림

```diff
 #!/bin/bash
 #$ -V
 #$ -S /bin/bash
 #$ -N HER_VASP
 #$ -q all.q
 #$ -pe mpi_48 48
 #$ -j Y
 #$ -o $JOB_NAME.o$JOB_ID
 #$ -cwd

 echo "Got $NSLOTS slots."
 cat "$TMPDIR/machines"
 export OMP_NUM_THREADS=1

+ source ~/.miraeping/miraeping
 cd "$SGE_O_WORKDIR"

 module load vasp/6.3.2-vtst-vaspsol-beef-intel

 mpirun -machinefile "$TMPDIR/machines" -n "$NSLOTS" vasp_std
 rc=$?
+ miraeping_send "VASP 종료 (exit $rc): $PWD"
 exit "$rc"
```

#### VASP: OUTCAR 수렴 확인

```diff
 #!/bin/bash
 #$ -V
 #$ -S /bin/bash
 #$ -N HER_VASP
 #$ -q all.q
 #$ -pe mpi_48 48
 #$ -j Y
 #$ -o $JOB_NAME.o$JOB_ID
 #$ -cwd

 echo "Got $NSLOTS slots."
 cat "$TMPDIR/machines"
 export OMP_NUM_THREADS=1

+ source ~/.miraeping/miraeping
 cd "$SGE_O_WORKDIR"

 module load vasp/6.3.2-vtst-vaspsol-beef-intel
 mpirun -machinefile "$TMPDIR/machines" -n "$NSLOTS" vasp_std
 rc=$?
+ miraeping_send "VASP 종료 (exit $rc): $PWD"
+ grep -q "reached required accuracy" OUTCAR 2>/dev/null && miraeping_send "reached required accuracy"
 exit "$rc"
```

#### `miraeping_monitor`로 주기적 상태 알림

5분마다 OSZICAR 마지막 줄을 전송합니다. `miraeping_stop`이 백그라운드 모니터를 종료하고 최종 메시지를 전송합니다.

```diff
 #!/bin/bash
 #$ -V
 #$ -S /bin/bash
 #$ -N HER_VASP
 #$ -q all.q
 #$ -pe mpi_48 48
 #$ -j Y
 #$ -o $JOB_NAME.o$JOB_ID
 #$ -cwd

 echo "Got $NSLOTS slots."
 cat "$TMPDIR/machines"
 export OMP_NUM_THREADS=1

+ source ~/.miraeping/miraeping
 cd "$SGE_O_WORKDIR"

 module load vasp/6.3.2-vtst-vaspsol-beef-intel
+ miraeping_monitor "tail -n 1 OSZICAR" 300
 mpirun -machinefile "$TMPDIR/machines" -n "$NSLOTS" vasp_std
 rc=$?
+ miraeping_stop "VASP 종료 (exit $rc): $PWD"
 exit "$rc"
```

---

### Python API

```python
import miraeping

miraeping.send("hello from Python API")
```

#### 단발성 메시지

```python
import miraeping

miraeping.send("계산 제출 완료")

e0 = atoms.get_potential_energy()
miraeping.send(f"E0 = {e0:.4f} eV", name="VASP")  # [VASP] 접두사 추가
```

#### Job 컨텍스트 매니저

```python
import miraeping
from pathlib import Path

with miraeping.Job("VASP relax") as job:
    # ... your calculation ...
    if "reached required accuracy" in Path("OUTCAR").read_text(errors="ignore"):
        job.send("required accuracy 확인")
    else:
        job.send("종료, 수렴 미달")
```

#### `with` 없이 Job 객체 사용

```python
import miraeping

job = miraeping.Job("preprocessing")
job.send("started")
# ... your script ...
job.send("done")
```

#### 주기적 모니터

```python
import miraeping
from pathlib import Path

def status():
    lines = Path("OSZICAR").read_text(errors="ignore").splitlines()
    return lines[-1] if lines else "OSZICAR not ready"

with miraeping.Monitor(status, interval=300, name="VASP relax"):
    # ... your calculation ...
```

#### 수동 시작 / 중지

```python
mon = miraeping.Monitor(status, interval=600, name="AIMD 300K")
mon.start()
try:
    # ... your calculation ...
finally:
    mon.stop()
```

> Python API는 `~/.miraeping/credentials` 파일을 자동으로 읽습니다 (`setup.sh`가 생성하는 파일과 동일). 환경변수가 설정되어 있으면 환경변수가 우선합니다.

---

## 기능 2 - Slack slash commands

Slack에서 바로 서버 상태를 확인하고 싶을 때 사용하는 기능입니다.

이 기능은 별도의 Slack command server가 처리합니다. slash command만 사용하려면 사용자가 `setup.sh`를 실행하거나 `miraeping`을 로컬에 설치할 필요는 없습니다.

필요한 것:

| 필요 항목 | 이유 |
|-----------|------|
| Slack에 `miraebot` 앱 추가 | 워크스페이스에서 봇과 slash command를 사용할 수 있게 함 |
| 본인 Slack 멤버 ID | 관리자가 Slack 계정을 식별하는 데 사용 |
| 클러스터 계정명 (`echo $USER`) | `/qstat`, `/qwd`에서 본인 잡을 조회하기 위해 필요 |
| 관리자가 실행 중인 Slack command server | `/qq`, `/qstat`, `/qwd`, `/gpu`, `/nvidia-smi`가 응답하려면 필요 |

관리자가 Slack 멤버 ID와 클러스터 계정명을 등록하면 아래 명령어를 사용할 수 있습니다:

| 명령어 | 설명 |
|--------|------|
| `/qq` | 노드 가용 현황 (48코어 / 64코어, 대기 중 잡) |
| `/qstat` | 실행 중·대기 중 잡 목록 (JOB_ID, NAME, STATE, SLOTS, QUEUE) |
| `/qwd` | 현재 잡의 작업 디렉터리 |
| `/gpu` | GPU 노드의 메모리 및 사용률 |
| `/nvidia-smi` | `/gpu`와 동일 |

### 출력 예시

**`/qq`**
```
+----------+-----------+------------+
| Node     | Available | Queued (qw)|
+----------+-----------+------------+
| 48-core  | 3/10      | 2          |
| 64-core  | 1/4       | 0          |
| Total    | 4/14      | 2          |
+----------+-----------+------------+

Available nodes:
n03 n07 n11 n12
```

**`/qstat`**
```
target user: alice
+--------+----------+-------+-------+-----------+
| JOB_ID | NAME     | STATE | SLOTS | QUEUE     |
+--------+----------+-------+-------+-----------+
| 100234 | HER_VASP | r     | 48    | all.q@n03 |
| 100235 | NEB_run  | qw    | 48    | -         |
+--------+----------+-------+-------+-----------+
```

**`/qwd`**
```
target user: alice
+--------+----------+-------+----------------------------+
| JOB_ID | NAME     | STATE | SUBMISSION_DIR             |
+--------+----------+-------+----------------------------+
| 100234 | HER_VASP | r     | /home/alice/project/run001 |
+--------+----------+-------+----------------------------+
```

**`/gpu`**
```
node: g01
+-----+--------------+-------------------+------+
| GPU | Name         | Mem (GiB)         | Util |
+-----+--------------+-------------------+------+
| 0   | RTX 6000 Ada | 12.3 / 47.5       | 45%  |
| 1   | RTX 6000 Ada |  0.4 / 47.5       |  2%  |
+-----+--------------+-------------------+------+
```
