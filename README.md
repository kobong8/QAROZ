# QAROZ 사용 설명서

QAROZ는 로컬 웹 프로젝트의 **System, API, 브라우저 E2E, Regression, 선택 보안 검사**를 실행하고 결과와 증거를 보관하는 QA 대시보드입니다.

새 기능은 개발자가 직접 정상 동작을 확인한 다음 시나리오로 저장하고, 이후 같은 시나리오를 반복 실행해 기존 기능이 유지되는지 확인합니다. QAROZ가 대상 앱을 시작하거나 업무 기능의 정답을 자동으로 판단하지는 않습니다. 검사할 동작과 기대값을 등록해야 합니다.

이 문서는 현재 구현된 화면 기준입니다. 예시 프로젝트 **Task Board**는 가상의 업무 앱이며 URL, API 경로, 화면 선택자는 실제 프로젝트에 맞게 바꾸세요.

## 목차

- [1. 처음 실행해서 결과 보기](#quick-start)
- [2. 설치, 시작, 종료와 포트](#installation)
- [3. 화면 구성과 저장 방법](#screen)
- [4. 프로젝트 등록과 System 검사](#project)
- [5. API 테스트 만들기](#api-tests)
- [6. E2E 시나리오와 Recorder](#e2e)
- [7. Regression 검사와 재시도](#regression)
- [8. Security: ZAP과 Trivy](#security)
- [9. JSON 작업 지시서](#recipe)
- [10. 실행 버튼, 결과, History와 증거](#results)
- [11. 데이터 보관, 삭제와 백업](#data)
- [12. 자주 막히는 상황](#troubleshooting)
- [13. 고급 설정과 REST API](#advanced)
- [14. 개발 검증과 관련 문서](#development)

<a id="quick-start"></a>
## 1. 처음 실행해서 결과 보기

처음에는 보안 도구 설치 없이 **System → 기본 API/E2E → 업무 시나리오** 순서로 시작하면 됩니다.

1. 검사할 앱의 프런트엔드와 백엔드를 실행합니다. 브라우저에서 앱이 열리는지 확인합니다.
2. QAROZ 폴더의 PowerShell에서 설치하고 실행합니다.

   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts/install.ps1
   powershell -ExecutionPolicy Bypass -File scripts/start.ps1
   ```

3. 브라우저에서 <http://127.0.0.1:8787>을 엽니다.
4. **ADD PROJECT**에서 Name과 실제 Frontend URL을 입력하고 **Save project**를 누릅니다. 나머지 필드는 필요한 것부터 추가해도 됩니다.
5. **검사 준비 → System → 기본 연결 테스트 추가**를 누릅니다. 프런트엔드 HTTP 200 확인용 API 테스트와 `body` 표시 확인용 E2E 시나리오가 생깁니다.
6. 검사 준비 아래의 **SYSTEM CHECK**, **API TESTS**, **E2E SCENARIOS**를 차례로 실행합니다.
7. **Run History**의 해당 실행에서 **상세** 버튼을 누릅니다. 위쪽 검사 결과 영역에 세부 결과가 열립니다.
8. 연결 검사가 정상이라면 실제 API 기대값을 등록하거나 **E2E Scenarios → RECORD SCENARIO**로 업무 동작을 기록합니다.

기본 연결 테스트는 페이지가 열리는지만 확인합니다. 로그인·검색·저장 같은 기능이 정상이라는 뜻은 아닙니다. 같은 이름의 기본 연결 테스트는 중복 추가하지 않습니다.

<a id="installation"></a>
## 2. 설치, 시작, 종료와 포트

### 필요한 환경

| 항목 | 용도 |
|---|---|
| Windows, Python 3.12 이상 | QAROZ 서버 실행 |
| Playwright용 Chromium | E2E 실행 및 Recorder 사용 |
| ZAP, Trivy | 사용할 보안 도구만 별도 설치 |
| Node.js | 개발용 JavaScript 테스트에만 필요. 앱 실행에는 불필요 |

QAROZ는 검사 대상 프로젝트와 **별도의 Python 가상환경**을 사용합니다. 대상 앱의 가상환경에 QAROZ를 설치할 필요가 없습니다.

### 설치

QAROZ 폴더에서 실행하세요.

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install.ps1
```

스크립트는 `.venv` 생성, Python 패키지 및 테스트 의존성 설치, Playwright Chromium 설치를 수행합니다. `python`이 다른 버전이면 실행 파일을 지정합니다.

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install.ps1 -Python 'C:\Python312\python.exe'
```

System/API만 먼저 사용하려면 `-SkipBrowser`로 브라우저 설치를 생략할 수 있습니다. 나중에 설치할 때는 다음 명령을 사용합니다.

```powershell
.\.venv\Scripts\python.exe -m playwright install chromium
```

수동 설치도 가능합니다. 설치 목록의 원본은 `pyproject.toml`이며 `requirements.txt`도 같은 목록을 참조합니다.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m playwright install chromium
.\.venv\Scripts\python.exe app.py
```

가상환경을 활성화하지 않고 `.venv`의 실행 파일을 직접 사용하므로 `Activate.ps1` 실행 정책을 바꿀 필요가 없습니다.

### 시작, 종료, 업데이트

- 시작: `powershell -ExecutionPolicy Bypass -File scripts/start.ps1`
- 종료: QAROZ를 실행한 터미널에서 **Ctrl+C**.
- 설치 확인: 상단 **설치 / 설정 → 준비 상태 확인**. 서버가 사용하는 Python, psutil, Playwright, Chromium, ZAP 연결 정보를 확인합니다.
- 업데이트 후: 실행 중인 서버를 종료하고 다시 시작합니다. 의존성이 변경됐다면 설치 스크립트도 다시 실행합니다.
- 화면이 이전 상태로 보이면: 서버 재시작 후 브라우저에서 **Ctrl+F5**로 새로고침합니다.

Python 패키지 `playwright` 설치와 Chromium 다운로드는 별개입니다. 패키지만 설치되어 있으면 E2E나 Recorder가 실행되지 않을 수 있습니다.

### 여러 백엔드와 8787 포트

**8787은 QAROZ용 포트로 그대로 사용해도 됩니다.** 같은 주소에서 실행하는 서버끼리 듣는 포트만 겹치지 않으면 됩니다.

| 프로그램 | 예시 주소 | QAROZ에서 설정하는 곳 |
|---|---|---|
| QAROZ | `http://127.0.0.1:8787` | 실행 환경변수 QAROZ_PORT |
| 대상 프런트엔드 | `http://localhost:5173` | 프로젝트 Frontend URL |
| 대상 백엔드 A | `http://localhost:8000` | 프로젝트 Backend URLs |
| 대상 백엔드 B | `http://localhost:8001` | 프로젝트 Backend URLs |
| ZAP API | `http://127.0.0.1:8090` | 상단 설치 / 설정의 ZAP API URL |

프로젝트를 여러 개 등록한다고 QAROZ 서버를 여러 개 띄울 필요는 없습니다. 하나의 대시보드에서 프로젝트 탭을 바꿔 사용합니다. QAROZ가 대상 앱의 포트를 배정하거나 서버를 시작해 주지는 않습니다.

8787을 다른 프로그램이 사용 중이면 QAROZ를 종료하고 다른 포트로 시작합니다.

```powershell
$env:QAROZ_PORT = '8788'
powershell -ExecutionPolicy Bypass -File scripts/start.ps1
```

이 경우 대시보드는 `http://127.0.0.1:8788`입니다. 대상 앱의 API URL은 그대로입니다. 환경변수는 명령을 실행한 PowerShell과 그 자식 프로세스에 적용됩니다.

<a id="screen"></a>
## 3. 화면 구성과 저장 방법

프로젝트 탭을 선택하면 다음 순서로 표시됩니다.

```text
검사 준비
  System | API | E2E Scenarios | Regression | Security
  JSON 작업 지시서 저장 / 불러오기
↓
검사 실행 버튼
  RUN ALL / SYSTEM CHECK / API TESTS / E2E SCENARIOS / RUN REGRESSION / RUN SECURITY
  보안 도구별 실행: Run ZAP / Run Trivy / Active Scan…
↓
검사 결과
  상태 카드 / Regression·ZAP·Trivy 요약 / 선택한 실행의 상세
↓
Run History
```

검사 준비의 탭은 **설정할 항목**을 선택합니다. 탭을 눌렀다고 검사가 실행되지는 않습니다. 준비 아래의 실행 버튼으로 검사를 시작하세요.

| 변경한 항목 | 저장하는 방법 |
|---|---|
| 프로젝트 URL, 경로, 포트, 프로세스 | System → 프로젝트 / 시스템 설정 → **Save project** |
| 새 API 테스트 | API → API 테스트 추가 → **API 테스트 저장** |
| 직접 작성한 E2E | E2E Scenarios → 직접 등록 → **시나리오 저장** |
| Recorder 결과 | 녹화 완료 후 **기존 E2E Scenario로 저장** |
| Regression 포함 체크박스 | 변경 즉시 저장 |
| Regression Group / Order | 해당 행의 **저장** |
| ZAP/Trivy 활성화, Trivy scanner | Security → **Security 설정 저장** |
| ZAP API URL, Trivy 실행 파일 | 상단 설치 / 설정 → **설정 저장** |

등록된 API/E2E 항목은 이름을 펼치면 저장된 JSON을 확인할 수 있습니다. 현재 일반 API/E2E 내용에는 별도 수정 폼이 없습니다. 내용을 바꾸려면 기존 항목을 삭제하고 다시 등록하거나, 내보낸 레시피를 수정해 기존 항목 삭제 후 불러오세요. **불러오기는 덮어쓰기가 아니라 추가**입니다.

<a id="project"></a>
## 4. 프로젝트 등록과 System 검사

신규 등록은 **ADD PROJECT**, 수정은 **검사 준비 → System → 프로젝트 / 시스템 설정**입니다.

| 필드 | 입력 방법과 의미 |
|---|---|
| Name | 화면에서 구분할 이름. 예: Task Board |
| Frontend URL | 필수. 실제 앱 주소. 예: `http://localhost:5173` |
| Backend URLs | 백엔드 기본 URL을 한 줄에 하나씩 입력 |
| Health URLs | 실제 상태 확인 URL을 백엔드와 같은 순서로 입력 |
| Project path | QAROZ 실행 컴퓨터에 존재하는 폴더. Trivy와 E2E 업로드 파일 검증에 사용 |
| Expected ports | 접속 가능해야 하는 포트. 예: `5173, 8000, 8001` |
| Process rules | 실행 중이어야 하는 프로세스 이름의 일부. 예: `node.exe, python.exe` |
| Enable automated checks | 프로젝트 검사 활성화 여부. 예약 실행 주기 설정은 아님 |

백엔드가 두 개이고 각각 상태 확인 API가 있다면 다음처럼 입력합니다.

Backend URLs:

```text
http://localhost:8000
http://localhost:8001
```

Health URLs:

```text
http://localhost:8000/api/health
http://localhost:8001/health
```

존재하지 않는 `/health`를 임의로 넣지 마세요. Health URLs를 모두 비우면 각 백엔드 기본 URL을 확인합니다. 현재 폼은 빈 줄을 제거하므로 **중간 백엔드의 Health URL만 빈 줄로 건너뛸 수 없습니다**. 이 경우 실제 확인 가능한 URL을 순서대로 입력하거나 해당 엔드포인트를 API 테스트로 별도 등록하세요.

### SYSTEM CHECK가 확인하는 것

- **Process**: 로컬 프로세스 이름에 입력한 문자열이 포함되는지 확인합니다. 특정 프로젝트의 프로세스인지까지 판별하지는 않습니다. `python.exe`는 QAROZ 자체와도 일치할 수 있습니다.
- **Port**: TCP 연결 가능 여부를 확인합니다. 같은 포트가 등록 URL에 있으면 해당 호스트를 사용하고 없으면 localhost를 사용합니다.
- **HTTP**: 프런트엔드 및 백엔드 Health URL의 정상 응답을 확인합니다. JSON 본문 기대값은 API 테스트에서 검사합니다.

백엔드 기본 `/`가 404이고 Health URL을 지정하지 않았다면 `WARNING`입니다. API 서버가 루트 페이지를 제공하지 않는 경우이므로 실제 API를 확인하세요. **직접 지정한 Health URL이 404이면 FAIL**입니다.

<a id="api-tests"></a>
## 5. API 테스트 만들기

프로젝트에 Backend URL을 등록하는 것만으로 업무 API 테스트가 자동 생성되지는 않습니다. 검사할 요청을 각각 등록합니다.

### GET 요청 예제

대상 앱의 `GET /api/health` 응답이 실제로 `{"status":"ok"}`일 때:

1. **검사 준비 → API → API 테스트 추가**를 펼칩니다.
2. 다음 값을 입력합니다.

   | 필드 | 값 |
   |---|---|
   | 이름 | Backend health |
   | Method | GET |
   | 예상 HTTP 상태 | 200 |
   | 실제 API URL | `http://localhost:8000/api/health` |
   | JSON 필드 기대값 | `{"status":"ok"}` |
   | JSON Body | `null` |

3. **API 테스트 저장**을 누르고 목록에 추가됐는지 확인합니다.
4. **API TESTS**를 실행한 뒤 History에서 상세를 엽니다.

응답 본문이 HTML이거나 본문 검증이 필요 없다면 JSON 필드 기대값을 `{}`로 둡니다. 이 경우 HTTP 상태와 설정된 응답 시간 조건만 검사합니다.

### JSON 필드 기대값 작성

다음 응답을 받는다고 가정합니다.

```json
{"status":"ok","data":{"items":[{"id":7,"done":false}]}}
```

필드 경로는 점으로 구분하고 배열은 0부터 시작하는 인덱스를 씁니다.

```json
{"status":"ok","data.items.0.id":7,"data.items.0.done":false}
```

필드가 없거나 값·타입이 다르면 FAIL입니다. 문자열 `"7"`과 숫자 `7`, `true`와 `1`은 다르게 취급합니다. 객체나 배열 전체를 기대값으로 지정하면 그 전체 구조와 값을 비교합니다.

### POST 요청과 데이터 변경

실제 앱이 `POST /api/tasks`를 지원한다면 Method, URL, 예상 상태를 해당 명세에 맞게 설정하고 JSON Body를 입력합니다.

```json
{"title":"QAROZ sample task","done":false}
```

예상 상태가 201인지 200인지, 어떤 필드가 반환되는지는 대상 앱의 명세를 따릅니다. 테스트 요청은 실제로 전송되므로 생성·수정·삭제 API는 대상 앱의 데이터를 바꿉니다. 반복 실행할 데이터와 정리 방법도 함께 정하세요.

### 헤더, 인증, 쿼리, 응답 시간

간단한 등록 폼에는 모든 옵션이 노출되어 있지 않습니다. JSON 작업 지시서 또는 QAROZ의 <http://127.0.0.1:8787/docs>에서 다음 필드를 설정할 수 있습니다.

| 필드 | 예시 | 의미 |
|---|---|---|
| headers | `{"Authorization":"env:TASK_BOARD_AUTH"}` | 요청 헤더 |
| query | `{"page":1}` | URL 쿼리 매개변수 |
| max_response_ms | `1000` | 응답 시간 합격 기준. 요청 제한시간을 바꾸는 옵션은 아님 |
| enabled | `false` | 해당 API 테스트 실행 제외 |

인증이 필요하면 QAROZ를 시작하는 터미널에서 환경변수를 설정합니다. 다음은 입력값을 화면에 표시하지 않는 예입니다.

```powershell
$taskBoardAuth = Read-Host 'Authorization 값 전체 (Bearer 접두어 포함)' -AsSecureString
$env:TASK_BOARD_AUTH = [System.Net.NetworkCredential]::new('', $taskBoardAuth).Password
powershell -ExecutionPolicy Bypass -File scripts/start.ps1
```

`env:TASK_BOARD_AUTH`는 **API 요청 헤더에서만** 실행 시 해석합니다. 환경변수 값에는 `Bearer ` 등 필요한 접두어도 포함해야 합니다. Body, URL, E2E 입력값에 같은 문법을 넣어도 자동 치환되지 않습니다. 민감한 헤더의 평문 저장은 마스킹될 수 있으므로 환경변수 참조를 사용하세요.

<a id="e2e"></a>
## 6. E2E 시나리오와 Recorder

E2E는 실제 Chromium에서 화면 동작을 실행하고 기대한 요소·문구·개수를 확인합니다.

- **Steps**: 무엇을 할지. 이동, 입력, 클릭, 업로드, 대기 등.
- **Expected**: 정상이라고 판단할 조건. 요소 표시, 문구 포함, 요소 개수 등.

클릭만 기록하면 기능의 성공 여부를 알 수 없습니다. **Steps와 Expected가 모두 있어야 저장할 수 있습니다.**

### Recorder로 만드는 순서

1. 대상 앱에서 기록할 기능이 정상 동작하는지 직접 확인합니다.
2. **검사 준비 → E2E Scenarios → RECORD SCENARIO**를 누릅니다. Regression 탭의 같은 버튼으로도 시작할 수 있습니다.
3. 별도로 열린 Chromium에서 대상 기능을 조작합니다. 이동, 클릭, 입력, 선택 등이 Steps에 기록됩니다.
4. QAROZ의 Recorder 창에서 검증 버튼을 누르고 **대상 브라우저에서 검사할 요소를 클릭**합니다.

   | 버튼 | 저장되는 검증 |
   |---|---|
   | Verify Element | 요소가 표시되는지 |
   | Verify Text | 선택한 요소에 기대 문구가 포함되는지 |
   | Verify Count | 선택자와 일치하는 요소 수가 기대 개수인지 |

5. 비동기 로딩이 있다면 **＋ Wait Step**에서 Selector, State, Timeout을 입력하고 **Wait 추가**를 누릅니다.
6. **녹화 완료**를 누릅니다. Steps와 Expected를 검토하고 항목의 JSON 수정, 삭제, 순서 변경을 합니다.
7. Scenario name을 정하고 **기존 E2E Scenario로 저장**을 누릅니다.
8. **E2E SCENARIOS**로 재생해 봅니다. 저장된 시나리오는 기본적으로 Regression에도 포함됩니다.

검증 요소를 고르는 동안의 클릭은 앱의 일반 클릭 동작으로 실행되지 않습니다. Verify Count는 선택자가 어떤 요소들을 가리키는지 확인하세요. 목록 전체를 세려면 개별 항목 하나에만 일치하는 선택자를 목록 항목 공통 선택자로 수정해야 할 수 있습니다.

### 대기와 선택자

`[data-testid=search-input]`처럼 앱에서 안정적으로 유지하는 선택자를 사용하세요. 아래 예제 선택자는 실제 앱에 있어야 합니다.

| Wait의 State | 기다리는 조건 |
|---|---|
| visible | 요소가 표시됨 |
| hidden | 요소가 숨겨지거나 사라짐 |
| attached | DOM에 요소가 존재함 |
| detached | DOM에서 요소가 제거됨 |

Timeout은 밀리초이며 기본 10000은 10초입니다. 고정 시간 동안 무조건 쉬는 동작이 아니라 조건이 충족될 때까지 기다립니다. 개별 검증에도 자체 제한시간이 있으므로 모든 실패가 같은 10초 제한을 사용하는 것은 아닙니다.

### JSON으로 직접 등록하기

**E2E Scenarios → E2E 시나리오 직접 등록**을 펼칩니다. 아래는 검색 화면에 맞게 수정해서 사용하는 템플릿입니다.

Steps:

```json
[
  {"action":"goto","url":"/"},
  {"action":"fill","selector":"[data-testid=search-input]","value":"sample"},
  {"action":"click","selector":"[data-testid=search-button]"},
  {"action":"wait","selector":"[data-testid=search-results]","state":"visible","timeout":10000}
]
```

Expected:

```json
[
  {"type":"visible","selector":"[data-testid=search-results]"},
  {"type":"text","selector":"[data-testid=search-results]","value":"sample"}
]
```

| 지원 액션 | 필수 입력 예시 |
|---|---|
| goto | url: `/` 또는 등록된 프런트엔드와 같은 호스트·포트의 URL |
| click | selector |
| fill | selector, value |
| select | selector, value — select 요소의 옵션 값 |
| upload | selector, path — 허용된 로컬 파일 경로 |
| wait | selector, 선택적으로 state, timeout |

| 지원 검증 | 의미 |
|---|---|
| visible | selector 요소가 표시됨 |
| text | selector 요소의 텍스트에 value가 포함됨 |
| count | selector 요소 개수가 정수 value와 같음 |

### 파일 업로드

프로젝트의 Project path를 등록하고 그 폴더 안의 파일을 사용합니다. JSON에서는 Windows 역슬래시를 두 번 써야 합니다.

```json
{"action":"upload","selector":"input[type=file]","path":"C:\\projects\\task-board\\fixtures\\sample.pdf"}
```

Recorder가 `${UPLOAD_FILE}`을 남겼다면 실제 경로로 교체하세요. 상대 경로는 대상 프로젝트 폴더가 아니라 QAROZ 실행 위치를 기준으로 해석되므로 전체 경로를 권장합니다.

### 로그인과 민감한 입력의 현재 제한

각 시나리오는 새 브라우저 컨텍스트에서 실행됩니다. 일반 브라우저나 Recorder에서 로그인한 세션, 앞 시나리오의 쿠키가 다음 시나리오로 이어지지 않습니다. 필요한 초기 상태와 로그인 절차를 각각 준비해야 합니다.

Recorder는 비밀번호 등 민감한 입력을 `${SECRET:필드명}`으로 바꾸며 실제 값을 기록하지 않습니다. **현재 Runner에는 이 자리표시자를 실제 비밀번호로 바꾸는 기능이 없습니다.** 그대로 저장하면 로그인 재생에 사용할 수 없습니다. API 헤더용 `env:`도 E2E에는 적용되지 않습니다.

인증 시나리오를 자동화하려면 대상 앱의 QA 전용 인증 흐름을 준비하거나 별도의 안전한 자격증명 주입 기능이 필요합니다. Steps에 비밀번호를 직접 넣는 방식은 DB·레시피에 값이 남을 수 있으므로 해결책으로 권장하지 않습니다.

<a id="regression"></a>
## 7. Regression 검사와 재시도

Regression은 기존 E2E 시나리오 중 반복 확인할 항목을 선택해 실행하는 기능입니다. 별도의 테스트 작성 형식이나 Runner를 사용하지 않습니다.

### 대상 선택

1. **검사 준비 → Regression**을 엽니다.
2. 반복 확인할 시나리오를 체크합니다. 체크 변경은 즉시 저장됩니다.
3. 필요하면 Group에 Authentication, Tasks 같은 분류를 입력합니다.
4. Order에 실행 순서를 정수로 입력하고 해당 행의 **저장**을 누릅니다.
5. **RUN REGRESSION**을 실행합니다.

새 시나리오는 기본적으로 포함되며 `enabled=false`인 시나리오는 실행되지 않습니다. Order는 작은 숫자부터 적용되고 같은 값은 등록 순서를 따릅니다. Group은 화면 분류이며 로그인 상태를 공유하는 묶음이 아닙니다. 별도의 Suite 생성·삭제 화면은 없습니다.

| 실행 | E2E 선택 기준 |
|---|---|
| E2E SCENARIOS | 활성화된 모든 E2E |
| RUN REGRESSION | 활성화되어 있고 Regression에 체크한 E2E |
| RUN ALL | 활성화된 모든 E2E와 System/API/Security |

Regression에서 체크를 해제해도 **E2E SCENARIOS와 RUN ALL에서는 실행**됩니다. 두 실행에서도 제외하려면 시나리오 자체를 `enabled=false`로 설정해야 합니다. 이 옵션은 레시피 또는 API로 변경할 수 있습니다.

### 결과와 재시도

Run History에서 Regression 상세를 열면 PASS, FAIL, WARNING, ERROR, SKIPPED 개수와 시나리오별 결과를 확인할 수 있습니다.

- **Retry Scenario**: 실패한 E2E 시나리오 한 개만 다시 실행합니다.
- **Retry Failed**: 해당 Regression 실행에서 FAIL 또는 ERROR인 시나리오만 다시 실행합니다.
- 일반 API/E2E 실행 상세의 **실패한 API/E2E 항목만 다시 실행**도 같은 방식으로 실패 항목을 선택합니다.

재시도는 기존 결과를 덮어쓰지 않고 **새 History**를 만듭니다. WARNING은 재시도 대상에 포함되지 않습니다. 원래 테스트가 삭제·비활성화됐거나 Regression에서 제외됐다면 대상에서 빠집니다. 삭제 후 같은 이름으로 다시 등록한 항목도 ID가 달라 기존 결과의 재시도 대상이 되지 않습니다.

<a id="security"></a>
## 8. Security: ZAP과 Trivy

두 도구는 검사 대상이 다르며 독립적으로 사용할 수 있습니다.

| 도구 | 검사 대상 | 준비할 것 |
|---|---|---|
| ZAP | 실행 중인 프로젝트 Frontend URL | 별도 실행 중인 로컬 ZAP과 API 연결 |
| Trivy | 등록된 Project path의 파일·의존성·설정 | 설치된 Trivy 실행 파일과 실제 프로젝트 폴더 |

### 공통 설정 순서

1. 상단 **설치 / 설정**에서 도구 연결 정보를 저장합니다.
2. **프로젝트 → 검사 준비 → Security**에서 사용할 도구를 켭니다.
3. Trivy를 켰다면 scanner를 하나 이상 선택합니다.
4. **Security 설정 저장**을 누릅니다.
5. **RUN SECURITY** 또는 **보안 도구별 실행 → Run ZAP / Run Trivy**를 실행합니다.

Security 탭의 Target은 등록 정보를 보여 줍니다. ZAP 대상을 바꾸려면 프로젝트의 Frontend URL을, Trivy 대상을 바꾸려면 Project path를 수정합니다. ZAP API URL은 ZAP 프로그램과 통신할 주소이며 검사 대상 URL과 다릅니다.

새 프로젝트는 두 도구 모두 꺼져 있습니다. RUN SECURITY와 RUN ALL은 켜진 도구만 실행하며 꺼진 도구는 SKIPPED입니다. 개별 실행 버튼도 프로젝트의 활성화 설정을 따릅니다. 이전 프로젝트는 기존 전역 ZAP 설정을 상속할 수 있으며 프로젝트별 설정을 저장하면 그 값이 우선합니다.

### OWASP ZAP 준비

1. [공식 설치 안내](https://www.zaproxy.org/getting-started/)에 따라 ZAP과 해당 버전이 요구하는 실행 환경을 설치합니다.
2. ZAP을 직접 실행하고 로컬 API가 접근 가능한 주소와 포트를 확인합니다. 예: `http://127.0.0.1:8090`.
3. ZAP의 API Key를 확인한 후 QAROZ를 시작하는 PowerShell에서 설정합니다.

   ```powershell
   $zapKey = Read-Host 'ZAP API Key' -AsSecureString
   $env:QAROZ_ZAP_API_KEY = [System.Net.NetworkCredential]::new('', $zapKey).Password
   powershell -ExecutionPolicy Bypass -File scripts/start.ps1
   ```

4. QAROZ **설치 / 설정 → ZAP API URL**에 실제 주소를 입력하고 **설정 저장**을 누릅니다. ZAP이 8080을 사용한다면 8090 대신 8080을 입력합니다.
5. **준비 상태 확인**에서 연결을 확인하고 프로젝트 Security에서 **Enable ZAP**을 켜서 저장합니다.

API Key는 X-ZAP-API-Key 헤더로 전달합니다. QAROZ는 ZAP을 자동 설치하거나 실행하지 않습니다. ZAP API 연결 주소는 로컬 주소를 사용합니다. 도구 설정은 [ZAP API 문서](https://www.zaproxy.org/docs/api/)를 참고하세요.

기본 실행은 **Spider + Passive Scan**입니다. 별도 백엔드 전체나 JavaScript 화면의 모든 경로를 자동으로 탐색한다고 가정하면 안 됩니다.

**Active Scan…**은 보안 도구별 실행을 펼쳐 명시적으로 실행하고 대상 URL을 확인해야 합니다. RUN ALL에는 자동으로 포함되지 않습니다. localhost 또는 allowed_active_hosts로 허용한 대상만 사용할 수 있습니다. Active Scan은 대상 앱에 공격성 요청을 보내므로 검사 권한이 있는 테스트 환경에서 사용하세요.

### Trivy 준비

1. [공식 설치 안내](https://trivy.dev/latest/getting-started/installation/)에 따라 Trivy를 직접 설치합니다. QAROZ는 자동 다운로드하지 않습니다.
2. trivy.exe를 PATH에 추가하거나 상단 **설치 / 설정 → Trivy executable path**에 전체 경로를 입력하고 저장합니다. Windows에서는 .bat / .cmd 래퍼 대신 실행 파일을 지정합니다.
3. 프로젝트 설정의 Project path에 실제 폴더를 등록합니다. 예: `C:\projects\task-board`.
4. Security 탭에서 **설치 상태 확인**을 누릅니다. Installed와 버전 표시는 실행 파일 확인 결과이며 파일 검사를 완료했다는 뜻은 아닙니다.
5. **Enable Trivy**, scanner를 선택하고 **Security 설정 저장** 후 **Run Trivy**를 실행합니다.

| Scanner | 내용 | 기본 선택 |
|---|---|---|
| Vulnerability (vuln) | 패키지 취약점, 설치 버전, 수정 버전 | 켜짐 |
| Misconfiguration (misconfig) | 설정 파일의 보안 문제 | 켜짐 |
| Secret (secret) | 토큰·키 등 민감 정보 흔적 | 켜짐 |
| License (license) | 패키지 라이선스와 Trivy 분류 | 꺼짐 |

등록된 프로젝트 폴더만 filesystem 검사합니다. 프로젝트 밖으로 이어지는 심볼릭 링크·junction도 거부될 수 있습니다. 명령은 shell 문자열이 아닌 인수 목록으로 실행합니다.

검사 결과에는 CRITICAL/HIGH/MEDIUM/LOW/UNKNOWN 개수와 카테고리별 상세가 표시됩니다. 취약점은 ID, 패키지, 설치·수정 버전 등을, Secret은 유형·파일·줄·심각도만 표시합니다. **Secret 실제 값과 소스 문맥은 DB/UI/증거 JSON에 보관하지 않습니다.** 증거 파일 `trivy.sanitized.json`은 민감 내용을 제거한 JSON이며 Trivy 원본 출력을 그대로 저장한 파일이 아닙니다.

License는 원본 라이선스 정보와 Trivy 분류를 보여 줍니다. QAROZ가 상업적 이용 가능 여부 같은 법적 결론을 내리지는 않습니다.

Trivy는 취약점 DB·검사 규칙을 다운로드할 수 있습니다. 첫 검사에는 시간이 걸릴 수 있으며 실행 제한시간은 300초입니다. QAROZ는 검사 결과를 외부 서비스로 업로드하지 않지만 **완전한 네트워크 미사용 모드라는 뜻은 아닙니다**. 현재 UI에는 Offline Mode가 없습니다.

### 보안 결과 해석

- 발견 사항 없음: PASS.
- ZAP 경고 또는 Trivy 발견 사항 있음: WARNING. Trivy의 CRITICAL도 현재 실행 상태는 WARNING이며 심각도를 따로 확인해야 합니다.
- 설치 누락, 연결 실패, 잘못된 출력, 실행 제한시간 초과: ERROR.
- 비활성 도구: SKIPPED. 검사 통과를 의미하지 않습니다.

<a id="recipe"></a>
## 9. JSON 작업 지시서

작업 지시서(Recipe)는 **API 테스트와 E2E 시나리오 정의를 함께 옮기는 JSON 파일**입니다.

- 내보내기: 검사 준비 하단의 **JSON 작업 지시서 저장** → `<프로젝트>.qaroz.json` 다운로드.
- 불러오기: 대상 프로젝트 선택 → **JSON 작업 지시서 불러오기** → 파일 선택.
- 불러온 항목은 기존 목록에 추가됩니다. 이름이 같아도 자동 병합·교체하지 않으므로 중복에 주의하세요.
- 프로젝트 설정, 실행 이력, 증거 파일, 실제 업로드 파일은 포함되지 않습니다.
- 다른 프로젝트로 옮길 때 API의 절대 URL, 화면 선택자, 파일 경로, 기대값을 수정하세요. 자동으로 새 프로젝트에 맞춰 치환되지 않습니다.

다음은 Task Board의 health API와 기본 페이지 확인을 포함한 예입니다. health API가 실제로 있는 프로젝트에 맞춰 수정하세요.

```json
{
  "format": "qaroz-recipe",
  "version": 1,
  "name": "Task Board 기본 검사",
  "api_tests": [
    {
      "name": "Backend health",
      "method": "GET",
      "url": "http://localhost:8000/api/health",
      "headers": {},
      "query": {},
      "body": null,
      "expected_status": 200,
      "assertions": {"status": "ok"},
      "max_response_ms": 1000,
      "enabled": true
    }
  ],
  "scenarios": [
    {
      "name": "페이지 표시",
      "steps": [
        {"action": "goto", "url": "/"},
        {"action": "wait", "selector": "body", "state": "visible", "timeout": 10000}
      ],
      "expected": [{"type": "visible", "selector": "body"}],
      "enabled": true,
      "regression_enabled": true,
      "group": "Smoke",
      "order": 0
    }
  ]
}
```

기존 version 1 레시피에 Regression 필드가 없어도 기본값을 적용합니다. 파일 하나의 항목 수는 최대 1,000개입니다. JSON에는 주석이나 마지막 항목 뒤의 쉼표를 넣지 마세요.

공유하기 전 URL·본문·시나리오에 민감한 값이 없는지 확인하세요. 인증 헤더는 env:변수명 참조로 작성합니다. 상세 형식은 [작업 지시서와 재시도](docs/TEST_RECIPE_AND_RETRY.md), AI에 작성을 맡길 때의 입력 계약은 [AI 작성 안내](docs/AI_TEST_RECIPE_AUTHORING.md)를 참고하세요.

<a id="results"></a>
## 10. 실행 버튼, 결과, History와 증거

### 어떤 버튼을 눌러야 하나요?

| 버튼 | 실행 범위 |
|---|---|
| SYSTEM CHECK | 프로세스, 포트, HTTP 연결 |
| API TESTS | 활성 API 테스트 전체 |
| E2E SCENARIOS | 활성 E2E 시나리오 전체 |
| RUN REGRESSION | 활성·선택된 Regression 시나리오 |
| RUN SECURITY | 활성 ZAP/Trivy |
| RUN ALL | System → API → E2E → Security. 별도 Regression 실행은 추가하지 않음 |
| Run ZAP / Run Trivy | 해당 보안 도구만, 프로젝트 활성화 설정 적용 |
| Active Scan… | 대상 확인 후 명시적인 ZAP Active Scan |

실행은 백그라운드 작업으로 처리됩니다. 기본 동시 작업 수는 3이며 같은 프로젝트에서 RUN ALL을 중복 실행하는 것은 제한됩니다. 별도 실행을 겹치면 대상 앱의 데이터를 함께 바꿀 수 있으므로 생성·삭제 시나리오는 순서대로 실행하는 편이 좋습니다.

### 상태 읽기

| 상태 | 의미 |
|---|---|
| NOT RUN | 아직 표시할 해당 검사 이력이 없음 |
| QUEUED | 작업 대기 중 |
| RUNNING | 실행 중 |
| PASS | 등록한 검사 조건 충족 |
| FAIL | 기대 상태·값·화면 조건 등의 불일치 |
| WARNING | 검사 중 경고 관측 또는 보안 발견 사항 |
| ERROR | 도구·연결·실행 환경 등의 문제 |
| SKIPPED | 등록된 대상이 없거나 비활성화되어 검사 생략 |

전체 결과는 ERROR, FAIL, WARNING 순으로 우선합니다. 따라서 전체 ERROR라고 해서 모든 개별 항목이 실패한 것은 아닙니다. 모두 생략된 실행은 SKIPPED입니다.

### 상세 결과 여는 순서

1. Run History에서 확인할 날짜와 실행 종류를 찾습니다. 화면에는 최근 20개가 표시됩니다.
2. 해당 실행의 **상세** 버튼을 누릅니다.
3. 위쪽 **검사 결과**에 열린 상세에서 항목별 상태, 소요 시간, 실패 메시지, 로그를 확인합니다.
4. E2E는 실패 Step/Expected, console 오류, HTTP 4xx/5xx와 증거를 확인합니다. ZAP 경고와 Trivy 카테고리별 상세도 이 영역에 표시됩니다.
5. 문제를 고친 뒤 다시 실행하고 **새로 생성된 이력**을 확인합니다. 이전 실패 기록은 그대로 남습니다.

상단 카드는 각 분류의 최근 실행 결과를 보여 주므로 서로 다른 실행 시점의 값이 함께 보일 수 있습니다. Regression 결과는 별도 요약에 표시되며 전체 E2E 결과를 덮어쓰지 않습니다. 특정 실행 하나의 결과를 판단할 때는 해당 History 상세를 기준으로 보세요.

### Screenshot과 Trace

E2E의 FAIL/ERROR/WARNING에서는 브라우저를 사용할 수 있는 경우 스크린샷과 Playwright Trace를 보관합니다. Chromium을 시작하지 못한 오류처럼 증거를 만들 수 없는 경우도 있습니다.

상세 결과의 증거 링크로 파일을 내려받고 Trace ZIP은 로컬에서 엽니다.

```powershell
.\.venv\Scripts\python.exe -m playwright show-trace 'C:\Downloads\trace.zip'
```

Trace에서는 어떤 동작에서 멈췄는지 확인할 수 있습니다. 브라우저 console 오류나 HTTP 4xx/5xx 관측은 WARNING으로 남을 수 있으며 화면 기대값의 FAIL과 구분해서 읽으세요. E2E 화면·Trace에는 대상 앱에서 표시한 정보가 포함될 수 있으므로 공유 전 내용을 확인하세요.

<a id="data"></a>
## 11. 데이터 보관, 삭제와 백업

기본 저장 위치는 QAROZ 폴더 안입니다. 경로를 환경변수로 바꿨다면 해당 위치를 사용합니다.

| 위치 | 내용 |
|---|---|
| data/qaroz.db | 프로젝트, 설정, API/E2E 정의, 실행 결과와 증거 파일 참조 |
| artifacts/ | 실행별 스크린샷, Trace, 정제된 Trivy JSON 등의 실제 파일 |
| 다운로드한 *.qaroz.json | 내보낸 테스트 정의 |

### Clear history와 프로젝트 삭제의 차이

| 작업 | 삭제되는 것 | 유지되는 것 |
|---|---|---|
| Run History → Clear history | 선택 프로젝트의 완료된 실행, 결과, 경고, 증거 파일의 DB 참조 | 프로젝트 설정, 등록 테스트, 실행·대기 중 작업, 디스크 증거 파일 |
| 프로젝트 설정 → Delete | 프로젝트와 연결된 테스트·시나리오·이력의 DB 데이터 | 대상 프로젝트 소스, 디스크 증거 파일 |

**“증거 파일이 디스크에 남는다”**는 것은 화면의 이력을 지워도 artifacts 안의 PNG·ZIP 등이 실제로는 삭제되지 않는다는 뜻입니다. 삭제된 이력에서는 다운로드 링크를 더 이상 사용할 수 없지만 탐색기에서는 파일이 남아 있습니다. 따라서 Clear history는 디스크 용량 정리 기능이 아닙니다.

불필요한 증거 파일은 필요한 자료를 백업하고 실행 중인 작업이 없는지 확인한 뒤 해당 실행 폴더를 직접 정리하세요. DB만 지우는 것은 전체 프로젝트 설정과 테스트 정의까지 잃는 초기화이므로 일반적인 이력 정리에 사용하지 마세요.

### 백업과 복원

1. 실행 중인 검사가 끝난 뒤 QAROZ 서버를 종료합니다.
2. data/qaroz.db와 artifacts를 함께 백업합니다. 사용자 지정 저장 경로가 있으면 그 경로를 백업합니다.
3. 다른 환경에서는 같은 저장 경로 설정을 맞추고 DB와 증거 파일을 복원합니다. 기존 증거 참조를 유지하려면 경로도 유지하는 것이 안전합니다.
4. 환경변수의 인증 값, Trivy/ZAP 설치, 대상 프로젝트 폴더는 별도로 준비합니다.

테스트 정의만 다른 프로젝트로 옮길 목적이면 전체 DB 대신 JSON 작업 지시서를 사용하세요.

<a id="troubleshooting"></a>
## 12. 자주 막히는 상황

| 증상 | 확인할 것 / 해결 방법 |
|---|---|
| 대시보드가 열리지 않음 | QAROZ 터미널이 실행 중인지, 실제 QAROZ_PORT가 무엇인지 확인 |
| 8787 주소 사용 중 오류 | 기존 QAROZ 실행을 종료하거나 QAROZ_PORT 변경 |
| 화면이 예전 배치이거나 탭이 이상함 | 서버 재시작 후 Ctrl+F5. 실행 중인 폴더가 업데이트한 폴더인지 확인 |
| 설정했는데 실행에 반영 안 됨 | 프로젝트/Regression Group·Order/Security/전역 설정 각각의 저장 버튼 확인 |
| API 또는 E2E가 SKIPPED | URL만 등록한 것은 아닌지, 실제 테스트가 있고 enabled인지 확인 |
| Regression에 항목이 없음 | E2E 시나리오부터 저장. 녹화 완료만 하고 저장하지 않은 것은 아닌지 확인 |
| 백엔드 루트 404 WARNING | 실제 Health URL을 지정하거나 업무 API 테스트 등록 |
| API JSON 검증 실패 | 응답이 JSON인지, 필드 경로·배열 인덱스·값의 타입이 맞는지 확인 |
| API 401/403 | env: 헤더 변수와 Bearer 접두어 확인. 환경변수 설정 후 QAROZ 재시작 |
| Recorder/Chromium 실행 오류 | QAROZ의 .venv에서 playwright install chromium 실행 후 서버 재시작 |
| E2E 선택자 Timeout | 실제 선택자와 화면 상태 확인. 로그인, 로딩 Wait, 팝업 등 선행 조건 확인 |
| 녹화한 로그인 재생 실패 | ${SECRET:…}는 자동 치환되지 않음. 시나리오별 세션도 새로 시작함 |
| E2E 업로드 오류 | Project path, 파일 존재 여부, 폴더 내부 경로, JSON 역슬래시 확인 |
| ZAP 연결 ERROR | ZAP 직접 실행 여부, API URL의 포트, QAROZ_ZAP_API_KEY 확인 |
| Trivy Not Installed | 서버 프로세스의 PATH 또는 설정의 trivy.exe 전체 경로 확인 |
| Trivy ERROR | 상세 메시지에서 경로·출력 형식·제한시간 확인. CLI의 옵션 지원 여부도 확인 |
| 보안 도구 개별 실행이 SKIPPED | 프로젝트의 Enable ZAP/Trivy를 켠 뒤 Security 설정 저장 |
| 재시도할 항목이 없다는 오류 | FAIL/ERROR인지, 원래 테스트가 삭제·비활성화·Regression 제외되지 않았는지 확인 |
| Clear history 후 용량이 줄지 않음 | 실제 artifacts 파일은 유지됨. 데이터 보관 절 참고 |

### 터미널에 GET 200 OK가 계속 나오는 이유

```text
127.0.0.1:61663 - "GET /api/projects/.../runs HTTP/1.1" 200 OK
127.0.0.1:61663 - "GET /api/runs/... HTTP/1.1" 200 OK
```

대시보드가 약 2.5초 간격으로 실행 상태와 이력을 조회하는 정상적인 요청입니다. **테스트가 계속 새로 실행되는 로그가 아닙니다.** 200 OK는 조회 성공이고 61663 같은 번호는 브라우저 연결의 임시 포트입니다. QAROZ 서버 포트 8787과 별개입니다.

<a id="advanced"></a>
## 13. 고급 설정과 REST API

### 실행 환경변수

서버를 시작하기 전에 설정합니다. 기본값은 QAROZ 폴더에서 실행했을 때 기준입니다.

| 변수 | 기본값 | 의미 |
|---|---|---|
| QAROZ_HOME | 현재 작업 폴더 | 기본 데이터·증거 위치의 기준 |
| QAROZ_HOST | 127.0.0.1 | 대시보드 바인딩 주소. 로컬 사용 기본 |
| QAROZ_PORT | 8787 | 대시보드 포트 |
| QAROZ_DATA_DIR | QAROZ_HOME/data | 데이터 폴더 |
| QAROZ_DATABASE | QAROZ_DATA_DIR/qaroz.db | SQLite 파일 경로 |
| QAROZ_ARTIFACT_DIR | QAROZ_HOME/artifacts | 증거 폴더 |
| QAROZ_MAX_CONCURRENT_RUNS | 3 | 동시 실행 작업 수, 최소 1 |
| QAROZ_ZAP_API_KEY | 없음 | ZAP API 인증 키 |

서버 설정과 프로젝트 설정은 구분됩니다. Trivy 실행 파일과 ZAP API URL은 상단 설치 / 설정에서, 검사 대상과 도구 활성화는 각 프로젝트에서 정합니다. QAROZ에는 결과 업로드나 분석용 telemetry 기능이 없습니다.

### 주요 REST API

기본 주소의 `/docs`에서 요청을 확인하고 실행할 수 있습니다. 아래 project_id 등은 이름이 아니라 API에서 반환하는 실제 ID로 바꿔야 합니다.

| Method / 경로 | 용도 |
|---|---|
| GET /api/health | QAROZ 자체 상태 |
| GET /api/projects | 프로젝트와 ID 조회 |
| POST /api/projects | 프로젝트 등록 |
| PUT /api/projects/{project_id} | 프로젝트 수정 |
| GET/POST /api/projects/{project_id}/api-tests | API 테스트 조회/추가 |
| GET/POST /api/projects/{project_id}/scenarios | E2E 조회/추가 |
| PATCH /api/scenarios/{scenario_id} | enabled, regression_enabled, group, order 변경 |
| GET/POST /api/projects/{project_id}/recipe | 레시피 내보내기/추가 |
| POST /api/projects/{project_id}/run/{suite} | 검사 시작 |
| GET /api/projects/{project_id}/runs | 프로젝트 실행 이력 |
| GET /api/runs/{run_id} | 실행 상태 |
| GET /api/runs/{run_id}/results | 실행 결과 |
| POST /api/runs/{run_id}/retry-failed | 실패 항목 재시도 |
| GET /api/artifacts/{artifact_id} | 증거 다운로드 |
| GET /api/system/readiness | 실행 환경 준비 상태 |
| GET /api/system/trivy/status | Trivy 설치 상태 |

suite는 system, api, e2e, regression, security, all, zap, trivy 중 하나입니다. 실행 시작 응답은 완료 결과가 아니므로 반환된 실행 ID로 상태와 결과를 조회하세요.

Regression은 요청 본문으로 특정 Group만 선택할 수도 있습니다. 현재 UI에는 Group별 실행 버튼이 없습니다.

```http
POST /api/projects/{project_id}/run/regression
Content-Type: application/json

{"group":"Tasks"}
```

단일 실패 시나리오 재시도:

```http
POST /api/runs/{run_id}/retry-failed
Content-Type: application/json

{"scenario_id":"실제-시나리오-ID"}
```

재시도 가능한 항목이 없거나 실행이 아직 진행 중이면 HTTP 409를 반환합니다. 시나리오 PATCH는 실행 메타데이터 변경용이며 Steps/Expected 수정 API가 아닙니다.

<a id="development"></a>
## 14. 개발 검증과 관련 문서

개발용 의존성이 포함된 설치 스크립트를 실행한 환경에서:

```powershell
# Python 단위·통합 테스트
.\.venv\Scripts\python.exe -m pytest

# 임시 DB를 사용하는 기본 smoke test
.\.venv\Scripts\python.exe scripts/smoke_test.py

# 실제 Chromium 증거 생성 및 대시보드 UI까지 검증
$env:QAROZ_BROWSER_TESTS = '1'
.\.venv\Scripts\python.exe -m pytest tests/integration/test_browser_evidence.py tests/integration/test_browser_dashboard.py

# 개발용 JavaScript 테스트 (Node 필요)
node --test tests/unit/dashboard.test.cjs
```

보안 통합 테스트는 fixture와 mock을 사용하므로 외부 ZAP/Trivy를 실행하지 않고 검사할 수 있습니다. 실제 도구 설치와 대상 프로젝트의 정상 동작은 별도로 확인해야 합니다.

| 문서 | 내용 |
|---|---|
| [제품·기술 명세](docs/QAROZ_PRD_TRD.md) | 전체 구조와 설계 |
| [Scenario Recorder](docs/SCENARIO_RECORDER_IMPLEMENTATION.md) | 녹화, 검증, 저장 구현 |
| [JSON 작업 지시서와 재시도](docs/TEST_RECIPE_AND_RETRY.md) | 이동 가능한 테스트 정의, 실패 재실행 |
| [AI 작업 지시서 작성 안내](docs/AI_TEST_RECIPE_AUTHORING.md) | 레시피 작성 규칙과 스키마 |
| [Regression과 Trivy](docs/REGRESSION_AND_TRIVY.md) | 설정, API, 보안 처리와 검증 범위 |
