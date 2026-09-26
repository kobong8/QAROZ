# Scenario Recorder 및 조건 기반 Wait 구현 기록

## Regression 연동

Recorder가 저장하는 steps/expected는 동일하다. 저장된 Scenario의 `regression_enabled` 기본값은
`true`이며, 프로젝트 검사 준비의 Regression 탭에서 포함 여부·group·order를 편집할 수 있다.
실행/재시도/증거 저장은 [Regression & Trivy 명세](REGRESSION_AND_TRIVY.md)를 참조한다.

## 목적

기존 Playwright Runner의 Scenario JSON(`steps`, `expected`) 계약은 변경하지 않고, headed Chromium에서 사용자의 작업을 수집해 같은 JSON을 만드는 Recorder 계층을 추가했다.

## 구현 범위

- 프로젝트 Frontend URL을 headed Playwright Chromium으로 열고 `goto`, `click`, `fill`, `select`, `upload`를 기록한다.
- locator는 `data-testid` → role/name → label → id → CSS 경로 순으로 생성한다.
- password 또는 이름/id/autocomplete에 password, secret, token, api-key 계열 문자열이 있는 입력은 `${SECRET:필드명}` placeholder로 기록한다. 실제 값은 API나 DB에 전달하지 않는다.
- Verify Element/Text/Count 버튼을 누르고 대상 브라우저의 요소를 선택하면 기존 `expected` 항목으로 기록한다.
- 완료된 Steps/Expected는 JSON 단위로 수정하고 삭제하거나 위/아래로 재정렬한 뒤 기존 Scenario API로 저장한다.
- Wait Step은 selector, `visible|hidden|attached|detached`, timeout(ms)을 지원한다. 기본 timeout은 10,000ms이며 UI에서 Step별 변경 가능하다.
- Runner의 Playwright `locator.wait_for`는 조건 충족 즉시 반환한다. timeout은 기존 실패 처리 경로를 통해 해당 Scenario를 FAIL로 만들고 screenshot과 trace를 보존한다.

## 계층과 API

Recorder는 `ScenarioRecorderService`의 전용 daemon thread에서 Playwright 객체를 소유한다. 브라우저 DOM 이벤트는 init script의 메모리 큐에 쌓이고 서비스가 이를 Scenario 항목으로 변환한다.

- `POST /api/projects/{project_id}/recordings`: 녹화 시작
- `GET /api/recordings/{recording_id}`: 상태와 draft 조회
- `POST /api/recordings/{recording_id}/commands`: verify 모드, wait 추가, stop
- `POST /api/projects/{project_id}/scenarios`: 검토가 끝난 draft를 기존 Scenario로 저장

## 로컬 확인 사항

headed 브라우저이므로 GUI 세션과 Playwright Chromium 설치가 필요하다. 설치 후 `python -m playwright install chromium`을 실행한다. upload는 브라우저 보안상 선택한 로컬 파일의 전체 경로를 DOM에서 읽을 수 없으므로 `${UPLOAD_FILE}` placeholder를 생성한다. 저장 전 프로젝트 내부 실제 경로로 수정해야 하며 Runner가 프로젝트 경계 검사를 수행한다.
