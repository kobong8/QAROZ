# JSON 작업 지시서(Recipe)와 실패 항목 재실행

## Regression 확장

Scenario의 선택 필드 `regression_enabled`(기본 true), `group`(기본 null), `order`(기본 0)를
레시피 version 1에서 함께 내보내고 불러온다. 이전 레시피에는 기본값을 적용한다.
Regression 실행의 재시도는 현재 활성화·포함된 실패 Scenario만 실행하며 suite도 regression으로 유지한다.
`POST /api/runs/{run_id}/retry-failed`에 `{"scenario_id":"…"}`를 보내면 실패한 Scenario 하나만 재시도한다.
실행 중인 이력의 재시도 및 재실행할 항목이 없는 경우는 HTTP 409다.

## 결정

API 테스트와 E2E 시나리오를 함께 옮기고 백업하는 형식으로 **버전이 명시된 JSON**을 사용한다. JSON은 QAROZ가 바로 검증·실행할 수 있고 사람이 diff를 확인할 수 있다. 임의 실행 코드가 들어가는 YAML/스크립트 대신 선언형 데이터만 허용한다.

## 작업 지시서 사용법

1. 프로젝트의 **검사 준비** 하단의 JSON 레시피 버튼을 확인한다.
2. **JSON 작업 지시서 저장**을 누르면 `<프로젝트>.qaroz.json`이 내려받아진다.
3. 다른 프로젝트에서 **JSON 작업 지시서 불러오기**를 눌러 파일을 선택한다.
4. 불러온 항목은 기존 항목을 삭제하지 않고 뒤에 추가된다. 같은 파일을 여러 번 불러오면 중복될 수 있으므로 목록을 확인한다.

파일의 최상위 구조는 다음과 같다.

```json
{
  "format": "qaroz-recipe",
  "version": 1,
  "name": "샘플 프로젝트",
  "api_tests": [],
  "scenarios": []
}
```

프로젝트 ID, 실행 이력, 결과, 증거 파일은 포함하지 않는다. API 항목에는 이름, method, URL, headers/query/body, 기대 상태와 assertion 등이 포함되고 E2E 항목에는 steps, expected, tags 등이 포함된다. 저장 시 기존 보안 저장 정책이 적용된 데이터만 내보내지만, 파일을 공유하기 전 URL·본문·헤더에 민감 정보가 없는지 다시 확인한다. 인증 값은 평문 대신 `env:VARIABLE_NAME`을 사용한다.

서버는 `format`과 `version`, URL, 예상 상태, 배열 구조와 지원 액션을 검증한다. 현재 한 파일은 최대 1,000개 항목으로 제한한다. 향후 스키마가 바뀌면 `version`을 올리고 명시적인 변환 절차를 제공한다.

## 실패 항목만 다시 실행

실행 상세에 API/E2E 결과 중 `FAIL` 또는 `ERROR`가 있으면 **실패한 API/E2E 항목만 다시 실행** 버튼이 표시된다. 누르면 원래 결과가 가리키는 등록 항목 ID만 새 실행에 포함한다.

- `FAIL`: 응답/화면은 실행됐지만 기대값이 맞지 않은 항목
- `ERROR`: 연결, 브라우저 또는 도구 문제로 실행하지 못한 항목
- `WARNING`, `PASS`, `SKIPPED`는 재실행하지 않는다.
- 재실행도 별도의 실행 이력으로 저장하며 `trigger`에 원본 실행 ID를 기록한다.
- 원본 뒤에 테스트가 삭제되거나 비활성화되면 해당 항목은 실행 대상에서 제외된다.
- 예전 버전에서 만들어져 원본 항목 ID가 없는 결과는 안전하게 자동 재실행하지 않는다.

API는 `POST /api/runs/{run_id}/retry-failed`이며 재시도할 항목이 없으면 HTTP 409를 반환한다. Recipe 내보내기/불러오기는 각각 `GET/POST /api/projects/{project_id}/recipe`다.
