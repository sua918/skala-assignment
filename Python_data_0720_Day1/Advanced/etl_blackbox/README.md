# ETL 블랙박스

데이터 파이프라인에 정상·지연·장애 폭주 상황을 재현하고, 요청별 이벤트와 동시성 변화를 기록하는 추가과제입니다.

## 주요 기능

- 고정 동시성 3·10·30과 적응형 동시성 비교
- 지연, 일시 오류, 영구 장애와 검증 오류 재현
- 지수 백오프 재시도와 dead-letter 격리
- 요청·재시도·검증·적재 이벤트 JSONL 기록
- 유효 데이터 CSV 및 시나리오별 요약 JSON 저장
- 외부 서버 없이 열 수 있는 인터랙티브 HTML 리포트
- 동일 시드 기반 장애 조건 재현

## 실행

```powershell
python Advanced/etl_blackbox/main.py
pytest Advanced/etl_blackbox -v
```

실행 결과는 `Advanced/etl_blackbox/output`에 생성됩니다.
