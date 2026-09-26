# Regression Suite와 Optional Trivy

## 범위와 사용자 흐름

프로젝트 화면은 검사 준비 탭(System/API/E2E/Regression/Security), 검사 실행 버튼,
결과 요약/상세, Run History 순서로 배치한다. 각 종류의 설정은 실행 전에 해당 준비 탭에서 편집한다.
API와 E2E 시나리오 목록 및 등록 폼은 각각의 준비 탭 안에서 표시한다.

새 기능은 개발자가 직접 확인하고, 정상 동작을 확인한 시나리오를 Recorder로 저장해 반복 검증한다.
Recorder → Scenario JSON → PlaywrightRunner 흐름은 그대로 사용한다.

1. 프로젝트의 **검사 준비 → Regression → RECORD SCENARIO**에서 동작과 기대 결과를 기록한다.
2. 저장된 시나리오는 기본적으로 Regression에 포함된다. 체크박스로 제외/포함한다.
3. Group과 Order를 편집하고 저장한다. 화면은 그룹별로 표시하며 실행은 Order 오름차순이다.
4. **RUN REGRESSION**은 `enabled=true`와 `regression_enabled=true`인 시나리오만 실행한다.
5. History에서 PASS/FAIL/WARNING/ERROR/SKIPPED 수, 시간, 결과를 확인한다.
6. **Retry Scenario**는 실패한 시나리오 하나, **Retry Failed**는 해당 실행의 FAIL/ERROR만 새 이력으로 실행한다.

Order가 같으면 등록 순서가 적용된다. 각 시나리오는 독립된 브라우저 context에서 실행하므로
Login 시나리오의 쿠키가 다음 시나리오로 전달되지 않는다. 필요한 로그인 등의 사전 조건은 각 시나리오에 포함한다.
별도 Suite CRUD는 없다. 그룹별 실행은 API의 `group` 옵션으로 제공한다.

## Scenario와 레시피 호환성

기존 steps/expected/runner_ref/tags는 변경하지 않는다. 선택 필드만 추가한다.

| 필드 | 기본값 | 의미 |
|---|---|---|
| `regression_enabled` | `true` | 회귀 검사 포함 여부 |
| `group` | `null` | 최대 200자 그룹 이름 |
| `order` | `0` | 32비트 정수 실행 순서 |

기존 DB는 시작 시 열을 추가한다. 기존 Scenario도 기본적으로 포함된다.
레시피 `format=qaroz-recipe`, `version=1`을 유지하며 이전 파일에 새 필드가 없어도 불러온다.
내보내기에는 새 필드가 포함된다. Run All의 E2E는 기존처럼 활성 시나리오 전체를 실행한다.
Regression 제외는 Run All/E2E 비활성화와 다르다.

## 실행과 결과 구조

- `RunService`: 스레드 작업 예약, 상태 집계, TestRun/TestResult/Artifact 저장.
- `RegressionService`: 프로젝트별 선택 및 정렬, 기존 PlaywrightRunner 호출. 저장·집계는 RunService에 위임한다.
- Regression의 TestRun.suite는 `regression`, TestResult.category는 기존 `e2e`이다.
- 원본 Scenario ID를 source_id로 보존하며 재시도 이력 trigger에 `retry:<run_id>`를 기록한다.
- 삭제/비활성화/Regression 제외된 시나리오는 Regression 재시도에서도 제외한다. 대상이 없으면 HTTP 409.
- 실행 중인 이력은 재시도할 수 없다. 다른 프로젝트의 ID를 지정해 실행할 수 없다.
- 집계 우선순위는 ERROR → FAIL → WARNING → PASS이며, 전부 미실행이면 SKIPPED이다.
- 실패 step의 순서·action·selector와 실패 expectation을 details에 보관한다.
  Console/network 오류와 screenshot/trace는 기존 Runner를 공유한다.
  브라우저 기동 실패처럼 캡처할 화면 자체가 없는 ERROR에는 screenshot/trace가 없을 수 있다.

## 프로젝트별 Security

프로젝트 화면의 **Enable ZAP**, **Enable Trivy**, scanner 체크박스를 설정하고 **Security 설정 저장**을 누른다.

| 설정 | 새 프로젝트 기본값 |
|---|---|
| `zap_enabled` | `false` |
| `trivy_enabled` | `false` |
| `trivy_scanners` | `["vuln", "misconfig", "secret"]` |

- Run Security와 Run All 모두 활성 scanner만 실행한다. 비활성 scanner는 각각 SKIPPED로 남긴다.
- Run ZAP과 Run Trivy는 각 도구만 실행하며 프로젝트 활성화 설정을 따른다.
- ZAP 대상은 기존 등록 frontend_url이다. API URL은 로컬 ZAP 서버 연결 주소다.
- Trivy 대상은 등록 project_path다. 프로젝트 수정에서 실제 소스 폴더를 지정한다.
- 기존 프로젝트의 `zap_enabled=null`은 전역 `security_enabled`를 상속한다.
  프로젝트에서 설정을 저장하면 명시적 true/false가 우선한다. 새 프로젝트는 상속하지 않는다.
- ZAP Active Scan은 **Active Scan…** 확인창 또는 명시적인 `/run/zap`의 `active:true`로만 실행한다.
  Run All/Run Security에서 active 옵션은 거부한다. 기존 localhost/allowed_active_hosts 제한을 유지한다.

## Trivy 설치와 실행

사용자가 [공식 설치 안내](https://trivy.dev/latest/getting-started/installation/)에 따라 설치한다.
QAROZ는 Trivy를 자동 설치하지 않는다. Windows에서는 `trivy.exe`가 PATH에 있어야 하며,
**설치 / 설정 → Trivy executable path**에 전체 경로를 지정할 수도 있다.
Security의 설치 상태 확인은 10초 제한으로 `--version`을 실행한다.

실행은 `shell=False`인 subprocess 인자 배열이다. `.cmd/.bat`와 임의 명령 문자열은 허용하지 않는다.
Trivy fs, JSON 출력, scanner allowlist, 300초 제한을 사용한다. timeout은 subprocess.run이 프로세스를 종료하고 회수한다.
취약점 DB·검사 규칙 다운로드도 제한 시간에 포함된다. 초기 다운로드가 실패하면 ERROR이며 재실행할 수 있다.

Trivy의 설정 파일이나 TRIVY_SERVER/OUTPUT 환경변수가 외부 서버 전송이나 원문 파일 저장을 켜지 않도록
전용 임시 작업 디렉터리의 빈 설정 파일과 TRIVY_*를 제외한 환경을 사용한다.
`--disable-telemetry`, `--skip-version-check`, `--cache-backend memory`를 명시한다.
등록 경로 밖 target을 받지 않으며, 외부를 가리키는 symlink/junction이 있으면 스캔을 거부한다.
CLI를 지원하지 않는 구버전 또는 잘못된 실행 파일은 ERROR로 표시한다.

Trivy는 기본적으로 취약점 DB와 검사 규칙을 다운로드할 수 있으므로 완전한 네트워크 미사용 모드가 아니다.
Runner의 `offline` 옵션은 향후 UI 확장을 위한 내부 옵션이며 필요한 DB/규칙이 사전에 있어야 한다.
QAROZ에는 검사 결과 업로드 기능이 없다.

## Trivy 결과와 민감정보

요약은 CRITICAL/HIGH/MEDIUM/LOW/UNKNOWN별 개수를 표시한다. 상세는 다음 네 종류로 구분한다.

- Vulnerabilities: CVE/ID, 패키지, 설치/수정 버전, 심각도, 제목, 대상 파일.
- Misconfigurations: ID, 유형, 파일, 심각도, 메시지, 리소스·행 번호 등 원인 메타데이터.
- Secrets: 탐지 규칙/유형, 파일, 행, 심각도. 값은 `********`.
- Licenses: 패키지/파일, 이름, Trivy 분류, 심각도. UNKNOWN도 표시하며 법적 결론을 내리지 않는다.

정상적으로 검사가 끝나고 항목이 없으면 PASS, 발견 항목이 있으면 WARNING이다.
실행 실패·설치 누락·잘못된 JSON·timeout은 ERROR다. ZAP 오류가 Trivy 실행을 대신하지 않는다.

**원문 JSON 저장 요구보다 Secret 비저장 요구를 우선한다.** stdout은 메모리에서 파싱하며,
필드 allowlist를 거친 `trivy.sanitized.json`만 artifact로 저장한다. 원문 Match/Code/소스 문맥,
임의 metadata, stdout/stderr 원문은 DB·UI·artifact에 기록하지 않는다. 알려진 secret match가
다른 허용 필드에 반복되면 마스킹한다. 이 파일은 원문 전체가 아닌 정제된 검사 결과다.

## API

| Method | Path | 용도 |
|---|---|---|
| PATCH | `/api/scenarios/{id}` | regression_enabled/group/order/enabled 수정 |
| POST | `/api/projects/{id}/run/regression` | 기본 Regression. 선택 옵션 group/scenario_ids |
| POST | `/api/runs/{id}/retry-failed` | 실패 항목 재실행. `{ "scenario_id": "…" }`로 하나만 선택 |
| PUT | `/api/projects/{id}` | zap_enabled/trivy_enabled/trivy_scanners 저장 |
| POST | `/api/projects/{id}/run/security` | 활성 보안 scanner 실행 |
| POST | `/api/projects/{id}/run/zap` | ZAP만 실행, 선택 옵션 active |
| POST | `/api/projects/{id}/run/trivy` | Trivy만 실행 |
| GET | `/api/system/trivy/status` | 설치 상태/버전 |
| PUT | `/api/settings` | 선택 trivy_executable 경로 |

## 검증

`python -m pytest`는 실제 Trivy/ZAP 없이 fixture JSON과 subprocess 대역으로 검사한다.
선택 필터·순서·상태 집계·개별/전체 재시도·History·증거 연결·마이그레이션·레시피 호환,
보안 scanner 조합·경로/명령 제한·Secret 비저장·timeout·비정상 출력 등을 검증한다.
`node --test tests/unit/dashboard.test.cjs`는 프로젝트 전환, Regression 그룹 표시 및 결과 요약을 검증한다.
실제 Chromium 테스트는 `QAROZ_BROWSER_TESTS=1`로 별도 실행한다.

## 공식 참고

- [Trivy filesystem CLI](https://www.trivy.dev/docs/latest/guide/references/configuration/cli/trivy_filesystem/)
- [Trivy Secret scanner](https://www.trivy.dev/docs/latest/guide/scanner/secret/)
- [Trivy License scanner](https://www.trivy.dev/docs/latest/scanner/license/)
