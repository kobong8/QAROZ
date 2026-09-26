## 0. 제품 명칭

> 2026-09 확장: Regression Suite와 선택 Trivy 검사는
> [Regression & Trivy 구현 명세](REGRESSION_AND_TRIVY.md)를 따른다.
> 기존 Playwright/Recorder 구조와 Run All 구성을 유지하며 프로젝트별 보안 설정을 추가한다.

- **Product name:** QAROZ
- **Tagline:** Don't trust. Verify.
- **Description:** Windows에서 여러 웹 애플리케이션의 시스템 상태, API, 브라우저 E2E, 보안 검사를 오케스트레이션하고 증거와 결과 이력을 통합 관리하는 local-first QA 플랫폼.
- **Naming rule:** 사용자 UI, 문서, 코드 주석, 패키징에서 기존 가칭 `Web QA Manager`를 사용하지 않고 `QAROZ`로 통일한다.

**QAROZ**

**PRD + TRD 통합 개발 명세서**

Windows Local Web Service QA Automation Platform  
V1.0 · Codex 구현용

| **항목**   | **결정**                                                      |
|------------|---------------------------------------------------------------|
| 실행 환경  | Windows 10/11 우선                                            |
| 플랫폼     | 로컬 Web Dashboard                                            |
| 주 언어    | Python 3.12+                                                  |
| Backend    | FastAPI                                                       |
| UI         | FastAPI가 정적 UI 제공 (V1은 별도 Node 런타임 불필요)         |
| Browser QA | Playwright for Python                                         |
| Security   | OWASP ZAP 로컬 연동                                           |
| DB         | SQLite                                                        |
| 핵심 원칙  | 사람의 확인이 아니라 반복 가능한 검사와 증거로 QA 상태를 판단 |

# 1. 제품 개요

> **QAROZ**
>
> Local-first automated QA orchestration platform for web applications.
>
> **Project principle:** Don't trust. Verify.


QAROZ는 Windows 개발 PC에서 실행 중인 하나 이상의 웹 서비스를
등록하고, 서비스 기동 상태·API·브라우저 E2E·웹 보안 검사를 한 화면에서
실행하고 결과를 이력화하는 로컬 QA 플랫폼이다.

V1은 AI Agent 없이 결정적(deterministic)이고 재현 가능한 검사를
우선한다. 향후 AI가 테스트 시나리오 생성, 탐색적 QA, 실패 원인 분석에
참여할 수 있도록 실행 엔진과 결과 모델을 분리한다.

# 2. V1 목표와 비목표

| **구분** | **내용**                                                     |
|----------|--------------------------------------------------------------|
| 목표     | 여러 웹서비스/프로젝트를 동시에 등록하고 탭으로 관리         |
| 목표     | localhost 및 사내 URL의 Process/Port/Health 상태 확인        |
| 목표     | Frontend/Backend를 Playwright와 API 테스트로 검증            |
| 목표     | 실패 시 screenshot, trace, console/network 정보 등 증거 보존 |
| 목표     | OWASP ZAP 결과를 동일 Dashboard에 통합                       |
| 목표     | QA 실행 결과와 과거 실행 이력 보존                           |
| 비목표   | AI Agent, GitHub Actions/CI 자동 실행                        |
| 목표     | Regression Suite 및 선택 Trivy filesystem 검사             |
| 비목표   | 클라우드 SaaS 형태의 다중 사용자 서비스                      |
| 비목표   | 외부 서버로 테스트 데이터/로그/스크린샷 업로드               |

# 3. 핵심 사용자 흐름

1\. python app.py  
2. 브라우저에서 QA Manager 접속  
3. Project 추가  
- Name  
- Frontend URL  
- Backend URL  
- Project Path (선택)  
- Health Endpoint  
- 예상 Port / Process  
4. System Check 실행  
5. API Test 실행  
6. Playwright Scenario 실행  
7. ZAP Scan 실행  
8. Run All로 전체 검사  
9. Dashboard에서 PASS / FAIL / WARNING 확인  
10. 실패 항목의 Screenshot / Trace / Log / ZAP Alert 확인

# 4. 기술 아키텍처

V1은 운영과 설치 복잡도를 줄이기 위해 Python 중심 단일 애플리케이션으로
구성한다. React/Vite를 필수로 사용하지 않는다. FastAPI가 REST API와
Dashboard 정적 파일을 함께 서비스한다.

Windows  
└─ QAROZ (python app.py)  
├─ FastAPI  
│ ├─ REST API  
│ └─ Web Dashboard (HTML/CSS/JS)  
├─ SQLite  
├─ System Checker  
│ ├─ Process  
│ ├─ Port  
│ └─ HTTP Health  
├─ API Test Runner  
├─ Playwright for Python  
│ ├─ Chromium  
│ ├─ Screenshot  
│ └─ Trace  
└─ ZAP Adapter  
└─ Local OWASP ZAP process

따라서 최종 V1 사용자는 기본적으로 python app.py 하나만 실행한다. npm
run dev는 필요하지 않다. 향후 UI가 복잡해져 React/Vite로 전환하면 개발
시 Python backend와 Vite dev server를 동시에 실행할 수 있지만, 배포
시에는 빌드된 frontend를 FastAPI에서 제공하도록 유지한다.

# 5. 프로젝트 관리

| **필드**       | **필수** | **설명**                          |
|----------------|----------|-----------------------------------|
| name           | Y        | 프로젝트 표시 이름                |
| frontend_url   | Y        | 예: http://localhost:5173         |
| backend_url    | N        | 예: http://localhost:8000         |
| project_path   | N        | 로컬 소스 경로                    |
| health_url     | N        | 예: http://localhost:8000/health  |
| expected_ports | N        | 3000, 5173, 8000 등               |
| process_rules  | N        | node.exe, python.exe 등 확인 규칙 |
| enabled        | Y        | 프로젝트 검사 활성화 여부         |

상단 탭은 등록된 프로젝트를 표시한다. 각 프로젝트의 테스트는 독립적으로
실행할 수 있어야 하며 여러 프로젝트의 실행 상태가 서로 덮어쓰이지 않아야
한다.

# 6. System Check

PowerShell 창이 열려 있다는 사실 자체를 정상 여부로 간주하지 않는다.
Process → Port → Health의 계층적 검사로 실제 서비스 준비 상태를
판단한다.

| **검사**       | **예시**                   | **판정**               |
|----------------|----------------------------|------------------------|
| Process        | python.exe / node.exe 존재 | 프로세스 존재 여부     |
| Port           | localhost:8000 LISTENING   | 소켓 리슨 여부         |
| HTTP           | GET /health                | HTTP 상태와 응답시간   |
| Functional API | GET /api/projects          | 실제 애플리케이션 기능 |

가능한 프로젝트에는 /health endpoint를 표준으로 권장한다. Health
endpoint가 없는 프로젝트도 Port 및 기본 URL HTTP 검사만으로 등록할 수
있어야 한다.

# 7. API Test

사용자가 API Test Case를 등록하고 개별/그룹/전체 실행할 수 있게 한다.

| **검증 항목**                | **V1**                            |
|------------------------------|-----------------------------------|
| HTTP Method / URL            | 지원                              |
| Headers                      | 지원                              |
| Query / Path parameter       | 지원                              |
| JSON Body                    | 지원                              |
| Expected status              | 지원                              |
| JSON field/value assertion   | 지원                              |
| Response time threshold      | 지원                              |
| Authentication header/secret | 지원하되 UI 마스킹 및 로그 비노출 |
| JSON Schema validation       | 선택 구현                         |

API 요청/응답 원문에는 인증정보가 포함될 수 있으므로 저장 전
Authorization, Cookie, API Key 등 지정 헤더를 redaction한다.

# 8. Playwright E2E

브라우저 기반 검증은 Playwright for Python을 사용한다. V1의 기본
브라우저는 Chromium이며 향후 Firefox/WebKit을 확장 가능하게 한다.

| **기능**                         | **V1** |
|----------------------------------|--------|
| URL navigation                   | 지원   |
| click / fill / select            | 지원   |
| text/element assertion           | 지원   |
| file upload                      | 지원   |
| wait for element/navigation      | 지원   |
| Screenshot on failure            | 필수   |
| Trace on failure                 | 필수   |
| Console error collection         | 필수   |
| HTTP 4xx/5xx network observation | 필수   |
| Visual regression                | V2     |

## 8.1 테스트 시나리오

Playwright는 서비스의 업무 목적을 스스로 알 수 없으므로 V1에는 명시적인
시나리오가 필요하다. Scenario는 이름, 선행조건, Steps, Expected Result로
구성한다.

Scenario: 프로젝트 생성  
Precondition: 로그인 완료  
  
1. /projects 이동  
2. Create 버튼 클릭  
3. 이름에 "QA-Test" 입력  
4. Save 클릭  
5. 프로젝트 목록 확인  
  
Expected:  
- 성공 메시지가 표시된다.  
- "QA-Test" 프로젝트가 목록에 존재한다.

초기 구현에서는 시나리오를 Python 테스트 파일로 관리해도 되지만,
Dashboard에서 목록·실행·활성화 여부를 관리할 수 있도록 메타데이터를 DB에
둔다. V2 이후 자연어/GUI 시나리오 편집기로 확장할 수 있게 Runner
interface를 분리한다.

# 9. OWASP ZAP

ZAP은 실행 중인 웹서비스를 대상으로 한 DAST 엔진으로 사용한다. QA
Manager가 로컬 ZAP 프로세스를 실행/연결하고 결과 Alert를 표준 결과
모델로 변환한다.

보안 원칙: 테스트 데이터, URL, API 응답, 인증정보, 스크린샷, 취약점
결과를 외부 서비스로 전송하지 않는다. ZAP은 silent/offline 지향 설정으로
실행하고 자동 업데이트·call-home에 의존하지 않는다. 임의의 third-party
add-on 자동 설치는 금지한다.

| **기능**                 | **V1**             |
|--------------------------|--------------------|
| ZAP 설치 경로 설정       | 지원               |
| ZAP 실행 상태 확인       | 지원               |
| Spider/Passive Scan      | 지원               |
| Active Scan              | 명시적 실행만 지원 |
| Alert severity 수집      | 지원               |
| Alert 상세/URL/설명 표시 | 지원               |
| 외부 자동 업데이트       | 기본 비활성        |

Active Scan은 대상에 실제 공격 요청을 보낼 수 있으므로 기본 자동
실행하지 않는다. localhost 또는 사용자가 명시적으로 허용한 대상에
대해서만 실행하며 실행 전 UI에 대상 URL을 명확히 표시한다.

# 10. Dashboard UX

2026-09 UI 흐름: **검사 준비 → 검사 실행 → 검사 결과 → Run History**.
검사 준비는 System, API, E2E Scenarios, Regression, Security 탭으로 구성하며
각 종류의 설정을 실행 전에 관리한다. 결과 요약/상세를 실행 영역 뒤에 보여주고,
과거 실행 이력은 화면 아래에 둔다. API와 E2E 편집기도 각각의 설정 탭을 제공한다.

┌─────────────────────────────────────────────────────────┐  
│ QAROZ \[ Run All \] │  
├─────────────────────────────────────────────────────────┤  
│ Project A │ Project B │ Project C │ + Add │  
├─────────────────────────────────────────────────────────┤  
│ Project A · http://localhost:3000 │  
│ │  
│ OVERALL FAIL │  
│ │  
│ System 3/3 PASS │  
│ API 18/20 PASS │  
│ Playwright 7/8 PASS │  
│ Security 0 High · 2 Medium · 4 Low │  
│ │  
│ Recent Run 2026-09-23 21:30 · 01:42 │  
│ │  
│ \[System\] \[API\] \[E2E\] \[Security\] \[History\] │  
└─────────────────────────────────────────────────────────┘

색상만으로 상태를 표현하지 않고 PASS/FAIL/WARNING/RUNNING 텍스트와
아이콘을 함께 사용한다. 실행 중에는 현재 단계와 경과시간을 표시한다.

# 11. 결과 및 증거 모델

| **상태** | **의미**                              |
|----------|---------------------------------------|
| PASS     | 기대 조건 충족                        |
| FAIL     | 명확한 기능/검증 실패                 |
| WARNING  | 보안 경고, 비필수 조건, 불완전한 검사 |
| SKIPPED  | 조건 또는 설정에 의해 실행하지 않음   |
| ERROR    | 테스트 도구/환경 자체의 실행 오류     |

FAIL과 ERROR를 반드시 구분한다. 예: 로그인 assertion 실패는 FAIL,
Playwright browser binary 미설치는 ERROR이다.

각 Run은 시작/종료 시간, 프로젝트, 검사 종류, 결과, 메시지, duration,
artifact path를 저장한다. Artifact는 프로젝트별 run-id 디렉터리에
screenshot, trace, raw report를 저장한다.

# 12. 데이터 모델

| **Entity**   | **주요 필드**                                                 |
|--------------|---------------------------------------------------------------|
| Project      | id, name, URLs, path, enabled, created_at                     |
| ServiceCheck | project_id, type, target, expected, enabled                   |
| ApiTestCase  | project_id, name, method, path/url, headers, body, assertions |
| Scenario     | project_id, name, runner_ref, enabled, tags                   |
| TestRun      | id, project_id, started_at, ended_at, status, trigger         |
| TestResult   | run_id, category, test_name, status, duration, message        |
| Artifact     | result_id, type, local_path, metadata                         |
| ZapAlert     | run_id, risk, confidence, url, name, description              |

# 13. REST API 초안

GET /api/projects  
POST /api/projects  
GET /api/projects/{id}  
PUT /api/projects/{id}  
DELETE /api/projects/{id}  
  
POST /api/projects/{id}/run/system  
POST /api/projects/{id}/run/api  
POST /api/projects/{id}/run/e2e  
POST /api/projects/{id}/run/security  
POST /api/projects/{id}/run/all  
  
GET /api/projects/{id}/runs  
GET /api/runs/{run_id}  
GET /api/runs/{run_id}/results  
  
GET /api/settings  
PUT /api/settings  
GET /api/system/zap/status

# 14. 디렉터리 구조

qaroz/  
├─ app.py  
├─ pyproject.toml  
├─ README.md  
├─ qa_manager/  
│ ├─ api/  
│ ├─ core/  
│ │ ├─ config.py  
│ │ ├─ models.py  
│ │ └─ database.py  
│ ├─ runners/  
│ │ ├─ system_runner.py  
│ │ ├─ api_runner.py  
│ │ ├─ playwright_runner.py  
│ │ └─ zap_runner.py  
│ ├─ services/  
│ │ ├─ project_service.py  
│ │ ├─ run_service.py  
│ │ └─ artifact_service.py  
│ └─ web/  
│ ├─ index.html  
│ ├─ css/  
│ └─ js/  
├─ tests/  
│ ├─ unit/  
│ └─ integration/  
├─ scenarios/  
│ └─ \<project-id\>/  
├─ data/  
│ └─ qa_manager.db  
└─ artifacts/  
└─ \<project-id\>/\<run-id\>/

# 15. 실행 및 설치

\# 최초 설치 예시  
py -m venv .venv  
.venv\Scripts\activate  
pip install -e .  
playwright install chromium  
  
\# 실행  
python app.py  
  
\# Dashboard  
http://127.0.0.1:\<configured-port\>

V1은 npm을 런타임 의존성으로 요구하지 않는다. 설치/실행 스크립트는
PowerShell(.ps1)로 추가 제공할 수 있다. ZAP은 사용자가 설치한 로컬
경로를 설정하거나 향후 별도 installer에서 의존성 검사를 수행한다.

# 16. 동시 실행 및 Job 관리

여러 프로젝트를 동시에 평가할 수 있어야 하므로 HTTP 요청 handler에서
테스트를 직접 blocking 실행하지 않는다. 내부 Job Manager가 run_id를
생성하고 background worker/thread/process로 실행한다.

프로젝트별로 동시에 하나의 Run All만 허용하는 것을 기본값으로 한다. 서로
다른 프로젝트는 병렬 실행 가능하다. Playwright/ZAP의 자원 사용량 때문에
전체 동시 실행 개수는 설정값(max_concurrent_runs)으로 제한한다.

Dashboard는 polling 또는 Server-Sent Events(SSE)로 상태를 갱신한다. V1은
구현이 단순한 polling으로 시작하고 SSE로 교체 가능하게 API를 분리한다.

# 17. 보안 및 개인정보 요구사항

| **ID** | **요구사항**                                                     |
|--------|------------------------------------------------------------------|
| SEC-01 | 기본 bind address는 127.0.0.1이며 외부 LAN 공개 금지             |
| SEC-02 | Authorization/Cookie/API Key 등 secret은 화면 및 로그에서 마스킹 |
| SEC-03 | Artifact와 DB는 로컬에만 저장                                    |
| SEC-04 | 외부 telemetry/cloud upload 기능을 V1에 구현하지 않음            |
| SEC-05 | ZAP Active Scan은 명시적 허용 대상만 가능                        |
| SEC-06 | 임의 shell command 입력 기능을 V1에 제공하지 않음                |
| SEC-07 | Project Path 접근은 등록된 로컬 경로 범위로 제한                 |

Process/PowerShell 상태 확인 기능은 임의 명령 실행기가 되어서는 안 된다.
QA Manager는 조회 중심의 안전한 시스템 API를 사용하고, 사용자가
Dashboard에서 arbitrary PowerShell을 실행하는 기능은 V1에서 제외한다.

# 18. GitHub Actions / CI 결정

V1에서는 GitHub Actions를 구현하지 않는다. 주요 사용 사례가 Windows 개발
PC의 localhost 서비스 QA이기 때문이다. 단, Runner와 결과 판정 로직은
UI에 종속시키지 않아 향후 CLI(exit code 0/1) 및 Windows self-hosted
runner에서 호출할 수 있게 한다.

Future:  
qa-manager run --project project-a --suite all  
exit 0 \# PASS  
exit 1 \# FAIL/ERROR

# 19. 향후 확장(V2/V3)

| **버전** | **후보**                                                                  |
|----------|---------------------------------------------------------------------------|
| V2       | Visual Regression, CLI, GitHub Actions/self-hosted runner, Firefox/WebKit |
| V2       | OpenAPI import 기반 API testcase 생성, richer scenario editor             |
| V2       | SBOM 및 추가 보안 보고서 확장 (Trivy filesystem/License는 현재 지원)      |
| V3       | AI Agent 탐색적 QA                                                        |
| V3       | AI 시나리오 초안 생성                                                     |
| V3       | 실패 로그/trace 기반 AI 원인 분석                                         |
| V3       | AI가 발견한 버그를 deterministic regression test로 승격                   |

# 20. 구현 순서

| **Phase** | **구현 내용**                      | **완료 기준**                                       |
|-----------|------------------------------------|-----------------------------------------------------|
| 1         | FastAPI + SQLite + Dashboard shell | python app.py로 UI 접속                             |
| 2         | Project CRUD + Tab                 | 3개 이상 프로젝트 등록/전환                         |
| 3         | System Check                       | Process/Port/Health 결과 표시                       |
| 4         | API Runner                         | 등록 API의 assertion/결과 이력                      |
| 5         | Playwright Runner                  | 시나리오 실행 + screenshot/trace                    |
| 6         | Job/Parallel Run                   | 프로젝트 간 병렬 실행/상태 표시                     |
| 7         | ZAP Adapter                        | 로컬 ZAP 검사와 Alert 통합                          |
| 8         | Run All + History                  | 통합 판정 및 과거 실행 비교                         |
| 9         | Hardening                          | secret redaction, path/target validation, 오류 처리 |
| 10        | Packaging                          | Windows 설치/실행 문서 및 smoke test                |

# 21. Codex 구현 지침

Codex는 한 번에 전체 시스템을 생성하기보다 위 Phase 순서대로 구현하고 각
Phase마다 실행 가능한 상태를 유지한다.

- Windows를 1차 지원 대상으로 한다. Linux 전용 shell/path 가정을 넣지
  않는다.

- V1에서 Node/React를 새로 도입하지 않는다. Python 단일 런타임을
  유지한다.

- Runner(system/api/playwright/zap)는 공통 결과 DTO를 반환하고 UI를 직접
  알지 못하게 한다.

- 외부 네트워크 서비스나 cloud API를 임의로 추가하지 않는다.

- 테스트 실패와 도구 실행 오류를 구분한다.

- 모든 subprocess에는 timeout, 종료 처리, stdout/stderr capture를
  구현한다.

- ZAP Active Scan을 자동으로 무조건 실행하지 않는다.

- 인증정보를 로그/DB/artifact에 평문으로 남기지 않는다.

- 각 Phase마다 unit/integration test를 추가하고 기존 테스트를
  통과시킨다.

- 새 기능 추가 전에 README의 실행 방법이 실제 Windows 명령과 일치하는지
  유지한다.

# 22. V1 Acceptance Criteria

- Windows에서 python app.py 하나로 QA Manager Dashboard가 실행된다.

- 최소 3개 프로젝트를 등록하고 탭으로 독립 관리할 수 있다.

- 각 프로젝트의 Process/Port/Health 상태가 구분되어 표시된다.

- API 테스트를 저장·실행하고 assertion 실패 원인을 확인할 수 있다.

- Playwright 시나리오를 실행하고 실패 screenshot 및 trace를 열람할 수
  있다.

- 서로 다른 프로젝트 테스트를 동시에 실행할 수 있고 상태가 섞이지
  않는다.

- 로컬 ZAP을 통해 허용된 대상의 보안 검사를 실행하고 Alert를
  Dashboard에서 확인할 수 있다.

- Run All 결과가 PASS/FAIL/WARNING/ERROR로 체계적으로 집계된다.

- 과거 Run의 시간, 결과 및 artifact를 다시 조회할 수 있다.

- V1의 정상 QA 과정에서 테스트 데이터나 결과를 외부 cloud 서비스로
  전송하지 않는다.

# 23. 참고 자료

- Playwright for Python: https://playwright.dev/python/docs/intro

- Playwright Python API Testing:
  https://playwright.dev/python/docs/api-testing

- Playwright Trace Viewer:
  https://playwright.dev/python/docs/trace-viewer

- FastAPI: https://fastapi.tiangolo.com/

- OWASP ZAP Automation Framework:
  https://www.zaproxy.org/docs/automate/automation-framework/

- OWASP ZAP Call Home FAQ:
  https://www.zaproxy.org/faq/what-calls-home-does-zap-make/
