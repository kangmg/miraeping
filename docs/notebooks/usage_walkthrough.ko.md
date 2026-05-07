# 사용자 워크스루

이 페이지는 SGE 장시간 잡 실행 중 Slack DM 알림을 받으려는 사용자를 위한 단계별 가이드입니다.

## 목표

이 문서를 따라가면 아래를 할 수 있습니다.
- 헬퍼 스크립트를 `~/.miraeping/miraeping`에 설치
- 자격 증명을 `~/.miraeping/credentials`에 안전하게 저장
- 잡 스크립트에 시작/진행/종료 알림 추가
- 같은 셸 환경에서 Python API 사용

## 1) 사전 준비

- 클러스터 로그인 노드에서 셸 실행 가능
- `bash`, `curl` 사용 가능
- Slack Bot Token (`xoxb-...`)
- Slack User ID (`U...` 또는 `W...`)

## 2) 빠른 설치 (권장)

레포 루트에서 실행:

```bash
bash setup.sh
source ~/.bashrc
```

`setup.sh`가 수행하는 작업:
- 안전한 권한으로 `~/.miraeping/` 생성
- 헬퍼를 `~/.miraeping/miraeping`으로 설치
- `~/.miraeping/credentials` 생성, 권한 `600` 설정
- `~/.bashrc`에 `source ~/.miraeping/miraeping`이 없으면 자동 추가

런타임 자격 증명 조회 순서:
1. `~/.miraeping/credentials`
2. 환경 변수(`SLACK_BOT_TOKEN`, `SLACK_USER_ID`)

## 3) 수동 설치 (setup.sh 미사용)

```bash
mkdir -p ~/.miraeping && chmod 700 ~/.miraeping
cp miraeping.sh ~/.miraeping/miraeping && chmod 700 ~/.miraeping/miraeping

cat > ~/.miraeping/credentials << 'EOF'
SLACK_USER_ID=U012AB3CD
SLACK_BOT_TOKEN=xoxb-your-token
EOF
chmod 600 ~/.miraeping/credentials

grep -q 'source ~/.miraeping/miraeping' ~/.bashrc || echo 'source ~/.miraeping/miraeping' >> ~/.bashrc
source ~/.bashrc
```

## 4) 30초 검증

```bash
ls -l ~/.miraeping
type miraeping_send
```

기대 결과:
- `~/.miraeping/miraeping` 파일 존재 + 실행 가능
- `~/.miraeping/credentials` 권한이 `-rw-------`
- `miraeping_send`가 셸에서 인식됨

## 5) 잡 스크립트 템플릿 (바로 사용 가능)

아래를 그대로 붙여 넣고 워크로드 부분만 바꾸세요.

```bash
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
cat $TMPDIR/machines
export OMP_NUM_THREADS=1

source ~/local/.env
source ~/.miraeping/miraeping
cd $SGE_O_WORKDIR

module load vasp/6.3.2-vtst-vaspsol-beef-intel

miraeping_send "Started: $JOB_NAME ($JOB_ID) at $PWD"
miraeping_monitor "tail -n 20 OUTCAR" 300

mpirun -machinefile $TMPDIR/machines -n $NSLOTS vasp_std

miraeping_stop
miraeping_send "Finished: $PWD
$(grep 'reached required accuracy' OUTCAR)"
```

## 6) 자주 쓰는 bash 패턴

원샷 알림:

```bash
miraeping_send "SCF converged"
```

10분 간격 상태 알림:

```bash
miraeping_monitor "grep 'TOTEN' OUTCAR | tail -1" 600
```

종료 전 모니터 중지:

```bash
miraeping_stop
```

## 7) Python API 사용

```python
import miraeping

miraeping.send("Calculation done!", name="Trainer")

with miraeping.Job("MD simulation") as job:
    job.send("step: ", 42)

with miraeping.Monitor(lambda: "SCF running", interval=300, name="MiraePing") as mon:
    mon.send("checkpoint saved")
```

Python 주의사항:
- Python API는 `SLACK_BOT_TOKEN`, `SLACK_USER_ID` 환경 변수를 읽습니다.
- `setup.sh`로 설치했다면 `source ~/.miraeping/miraeping`가 적용된 셸에서 Python을 실행하세요.

## 8) 증상별 트러블슈팅

DM이 오지 않음:
- `~/.miraeping/credentials` 값 확인
- Slack scope(`chat:write`, `im:write`) 확인
- `https://slack.com` 아웃바운드 네트워크 확인

`miraeping_send: command not found`:
- `source ~/.bashrc` 실행
- `.bashrc`에 `source ~/.miraeping/miraeping` 존재 확인

주기 알림이 멈추지 않음:
- 잡 종료 경로에서 `miraeping_stop` 호출 확인

## 9) 관리자 설정 문서

Slack 앱 생성, slash command, 서버 운영은 [Develop](../develop.md) 문서에서 다룹니다.
