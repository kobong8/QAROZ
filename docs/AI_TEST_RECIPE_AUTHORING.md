# AI용 API · E2E 작업 지시서 작성 규약

이 문서는 AI가 사용자의 요구사항과 대상 애플리케이션 정보를 바탕으로 QAROZ에서 바로 불러올 수 있는 API 테스트 및 E2E 시나리오 레시피를 작성하기 위한 입력·출력 계약이다.

## 1. 출력 계약

- 최종 결과는 설명이나 Markdown 코드 펜스 없이 **JSON 객체 하나만** 출력한다.
- 최상위 `format`은 `qaroz-recipe`, `version`은 숫자 `1`로 고정한다.
- `name`, `api_tests`, `scenarios`를 항상 포함한다. 해당 테스트가 없으면 빈 배열을 사용한다.
- 한 파일의 `api_tests`와 `scenarios` 합계는 1,000개 이하여야 한다.
- JSON에는 주석, 후행 쉼표, 환경별로 바뀌는 데이터베이스 ID, 실행 이력 및 결과를 넣지 않는다.

```json
{
  "format": "qaroz-recipe",
  "version": 1,
  "name": "대상 프로젝트 이름",
  "api_tests": [],
  "scenarios": []
}
```

## 2. 작성 전에 필요한 입력

가능하면 다음 정보를 사용자 또는 저장소에서 확인한다. 확인할 수 없는 값은 임의로 단정하지 말고, 실행 가능한 항목만 작성한다.

1. 프런트엔드 기준 URL과 허용된 백엔드 URL
2. API 명세: method, URL, query, request body, 예상 상태, 응답 JSON 예시
3. 핵심 사용자 흐름과 시작 상태
4. 실제 DOM selector 또는 안정적인 `data-testid`
5. 테스트 계정·인증 방식과 필요한 환경 변수의 **이름**(비밀 값 자체는 제외)
6. 업로드 파일을 사용하는 경우 등록된 프로젝트 경로 내부의 파일 경로

존재가 확인되지 않은 endpoint, selector, 응답 필드 또는 기대 문구를 만들어 내지 않는다. 정보가 부족하면 안전한 연결 확인 항목만 만들거나, JSON을 만들기 전에 필요한 정보를 요청한다.

## 3. API 테스트 스키마

각 `api_tests` 항목은 다음 필드를 사용한다.

| 필드 | 형식 | 규칙 |
|---|---|---|
| `name` | string | 테스트 의도가 드러나는 고유한 이름 |
| `method` | string | HTTP method. 대문자 권장 |
| `url` | string | 완전한 `http://` 또는 `https://` URL |
| `headers` | object | 없으면 `{}`. 비밀 헤더 값은 `env:VARIABLE_NAME` |
| `query` | object | URL query parameter. 없으면 `{}` |
| `body` | JSON/null | 전송할 JSON 값. body가 없으면 `null` |
| `expected_status` | integer | `100`부터 `599`까지 |
| `assertions` | object | 응답 JSON의 dotted path와 정확한 기대값. 없으면 `{}` |
| `max_response_ms` | integer/null | 선택적 응답 시간 상한(ms) |
| `enabled` | boolean | 보통 `true` |

`assertions`의 경로는 객체 키를 점으로 연결하고 배열 인덱스는 숫자로 쓴다. 예를 들어 응답이 `{"data":{"items":[{"id":7}]}}`이면 `data.items.0.id`의 기대값을 `7`로 지정한다. 비교는 타입을 포함한 정확한 값 비교이며 부분 문자열, 정규식, 스키마 검증은 지원하지 않는다.

```json
{
  "name": "Health 응답 확인",
  "method": "GET",
  "url": "http://localhost:8000/api/health",
  "headers": {"Authorization": "env:TEST_API_TOKEN"},
  "query": {},
  "body": null,
  "expected_status": 200,
  "assertions": {"status": "ok"},
  "max_response_ms": 2000,
  "enabled": true
}
```

## 4. E2E 시나리오 스키마

회귀 검사 선택 필드도 지원한다: `regression_enabled`(boolean, 기본 true),
`group`(최대 200자 string/null, 기본 null), `order`(32비트 integer, 기본 0).
각 시나리오는 독립된 브라우저에서 실행되므로 이전 시나리오의 로그인/쿠키를 전제로 작성하지 않는다.

각 `scenarios` 항목은 다음 구조를 사용한다. `steps`와 `expected`는 각각 하나 이상의 항목이 필요하다.

```json
{
  "name": "검색 결과 표시",
  "runner_ref": null,
  "steps": [],
  "expected": [],
  "enabled": true,
  "tags": ["smoke", "search"]
}
```

### Steps

| `action` | 필수 필드 | 의미 |
|---|---|---|
| `goto` | `url` | 절대 URL 또는 프런트엔드 기준 상대 경로로 이동 |
| `click` | `selector` | 요소 클릭 |
| `fill` | `selector`, `value` | 입력 값을 문자열로 채움 |
| `select` | `selector`, `value` | select option의 value 선택 |
| `upload` | `selector`, `path` | 프로젝트 경로 내부 파일 업로드 |
| `wait` | `selector` | 요소 상태를 기다림. `state`는 `visible`, `hidden`, `attached`, `detached`; `timeout`은 1~300000ms이며 기본값은 10000 |

`goto`의 절대 URL은 등록된 프런트엔드와 같은 host여야 한다. 가능한 경우 상대 경로를 사용한다. 각 사용자 동작 뒤에는 필요한 대상만 명시적으로 기다리고, 단순한 고정 시간 sleep은 만들지 않는다.

### Expected

| `type` | 필수 필드 | 의미 |
|---|---|---|
| `visible` | `selector` | 요소가 보이는지 확인 |
| `text` | `selector`, `value` | 요소가 문자열을 포함하는지 확인 |
| `count` | `selector`, `value` | 일치하는 요소 개수가 정수 값과 같은지 확인 |

selector는 가능하면 `data-testid`, 고유 id, 접근성 목적에 맞춘 안정적인 속성 순으로 선택한다. 스타일 class, DOM 순서에 의존하는 `nth-child`, 동적으로 생성된 값은 피한다. 녹화기가 민감한 입력에 만드는 `${SECRET:필드명}`은 비밀 값이 아니며 실행 시 자동 해석되지 않으므로, 레시피에 실제 비밀을 넣지 말고 실행 전에 안전한 주입 방식이 마련됐는지 사용자에게 확인한다.

## 5. 완성 예시

아래 값은 형식을 설명하는 예시이므로 실제 endpoint와 selector가 확인된 경우에만 그대로 사용한다.

```json
{
  "format": "qaroz-recipe",
  "version": 1,
  "name": "Sample Web App",
  "api_tests": [
    {
      "name": "Health 응답 확인",
      "method": "GET",
      "url": "http://localhost:8000/api/health",
      "headers": {},
      "query": {},
      "body": null,
      "expected_status": 200,
      "assertions": {"status": "ok"},
      "max_response_ms": 2000,
      "enabled": true
    }
  ],
  "scenarios": [
    {
      "name": "검색 결과 표시",
      "runner_ref": null,
      "steps": [
        {"action": "goto", "url": "/"},
        {"action": "fill", "selector": "[data-testid=search-input]", "value": "sample"},
        {"action": "click", "selector": "[data-testid=search-button]"},
        {"action": "wait", "selector": "[data-testid=search-results]", "state": "visible", "timeout": 10000}
      ],
      "expected": [
        {"type": "text", "selector": "[data-testid=search-results]", "value": "sample"},
        {"type": "count", "selector": "[data-testid=search-results] [data-testid=result-item]", "value": 1}
      ],
      "enabled": true,
      "tags": ["smoke", "search"]
    }
  ]
}
```

## 6. 생성 전 자체 점검

1. 결과가 파싱 가능한 단일 JSON 객체인가?
2. `format`과 `version`이 정확한가?
3. 모든 URL, endpoint, selector, 기대값이 제공된 근거에 기반하는가?
4. API status와 JSON assertion이 실제 계약을 검증하는가?
5. 각 E2E에 의미 있는 최종 `expected`가 있으며 단순 `body` 표시로 끝나지 않는가?
6. secret, token, password, cookie 또는 개인정보가 평문으로 포함되지 않았는가?
7. 테스트끼리 실행 순서나 이전 테스트의 데이터에 불필요하게 의존하지 않는가?
8. destructive API나 운영 환경을 대상으로 하지 않는가?

완성된 파일은 `POST /api/projects/{project_id}/recipe`로 불러온다. 불러오기는 기존 항목을 교체하지 않고 추가하므로 중복 여부를 먼저 확인한다.
