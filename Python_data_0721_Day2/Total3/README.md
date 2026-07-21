# 종합실습 3 실행 방법

한 번만 리포트를 생성합니다.

```powershell
python Total3\report.py
python Total3\run_scheduler.py --mode once
```

60초 간격으로 반복 실행합니다. 중지는 `Ctrl+C`입니다.

```powershell
python Total3\run_scheduler.py --mode interval --interval 60
```

매일 오전 9시에 실행합니다.

```powershell
python Total3\run_scheduler.py --mode daily --at 09:00
```

Windows 작업 스케줄러에서는 프로그램에 가상환경의 `python.exe`, 인수에
`Total3\report.py`, 시작 위치에 `Python_data_0721_Day2`의 절대 경로를 지정합니다.

Linux cron 예시는 다음과 같습니다.

```cron
0 9 * * * cd /absolute/path/Python_data_0721_Day2 && /absolute/path/.venv/bin/python Total3/report.py >> Total3/output/scheduler.log 2>&1
```
