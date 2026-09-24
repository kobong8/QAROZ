# QAROZ

**Quality Assurance Review & Orchestration with Zero-Trust**<br>
_Don't trust. Verify._

## 처음 시작하기 (Windows / 한국어)

QAROZ는 검사 대상 앱과 **별도의 Python 환경**에서 실행합니다.
프런트엔드 `5173`, 백엔드 `8000`은 대상 앱이고, QAROZ 대시보드는 `8787`입니다.
대상 앱의 프런트엔드/백엔드를 먼저 실행해 두세요.

### 1. QAROZ 설치와 실행

QAROZ 폴더의 PowerShell에서:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install.ps1
# 이미 실행 중인 QAROZ는 해당 터미널에서 Ctrl+C로 종료합니다.
powershell -ExecutionPolicy Bypass -File scripts/start.ps1
```

설치 스크립트는 `.venv` 생성, Python 패키지 설치, Chromium 다운로드를 수행합니다.
Python 3.12+가 필요하며, `python`이 다른 버전이면
`scripts/install.ps1 -Python 'C:\경로\python.exe'`로 지정하세요.
가상환경 활성화 없이도 실행되므로 PowerShell Activate 정책을 바꿀 필요가 없습니다.

설치 목록의 원본은 `pyproject.toml`입니다. `requirements.txt`도 같은 목록을 참조합니다.
수동 설치를 선호하면:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m playwright install chromium
.\.venv\Scripts\python.exe app.py
```

`pip install playwright`와 Chromium 설치는 별도입니다.
설치 후에도 예전 Python으로 실행 중인 서버에는 적용되지 않으므로 반드시 재시작하세요.
http://127.0.0.1:8787 → **설치 / 설정 → 준비 상태 확인**에서 서버가 사용하는 Python,
psutil, Playwright, Chromium, ZAP 연결 상태를 확인할 수 있습니다.

### 2. 대상 프로젝트 등록

| 필드 | 설정 예시 |
|---|---|
| Name | MetaverseSandbox |
| Frontend URL | `http://localhost:5173` |
| Backend URLs | 한 줄에 하나씩 입력. 예: `http://localhost:8000`, `http://localhost:8001` |
| Health URLs | 각 백엔드와 같은 순서로 한 줄에 하나씩 입력. 없으면 **빈칸**. 존재하지 않는 `/health`를 넣지 않습니다. |
| Expected ports | `5173, 8000, 8001` |
| Process rules | 선택. 실제 프로세스가 맞을 때만 `node.exe, python.exe` |
| Project path | 선택. 파일 업로드 시나리오를 쓸 때 실제 대상 소스 경로 입력 |

먼저 **SYSTEM CHECK**를 실행하세요. 프런트엔드는 HTTP 정상 응답을 확인하고,
각 Health URL을 확인하며, 해당 순서의 Health URL이 없으면 각 백엔드 기본 URL을 확인합니다. 백엔드 `/`만 404인 경우에는
`WARNING`과 설정 안내를 표시합니다. 서버의 모든 API가 실패했다는 뜻은 아닙니다.
명시적으로 지정한 Health URL이 404면 `FAIL`입니다.

프로젝트를 삭제하려면 **해당 프로젝트 탭 → 프로젝트 수정 / 삭제 → Delete**를 누르고
확인 창에서 삭제를 확인하세요. QAROZ에 등록한 프로젝트, API 테스트, 시나리오,
실행 이력과 증거 파일의 DB 연결이 삭제됩니다. 대상 앱의 소스 파일은 삭제하지 않으며,
이미 저장된 `artifacts` 폴더의 증거 파일도 디스크에는 남습니다.

현재 Metaverse Sandbox 예시 API는 `/api/health`를 제공합니다.
`http://localhost:8000/api/health`의 `{"status":"ok", ...}` 응답을 확인했다면
이 주소를 Health URL로 사용할 수 있습니다. `/health`와는 다른 경로입니다.

### 3. API와 E2E 시나리오 등록

**기본 연결 테스트 추가**를 누르면 중복 이름 없이 다음 두 테스트가 등록됩니다.

- API: 프런트엔드 `/`가 HTTP 200인지 확인 (HTTP 연결 테스트이며 업무 API 검증은 아님).
- E2E: 프런트엔드 `/` 이동 → `body` 표시 대기 → `body` 표시 검증.

**테스트 / 시나리오 관리**에서 실제 백엔드 테스트를 추가하세요.
예시: 이름 `Backend health`, Method `GET`, URL `http://localhost:8000/api/health`,
예상 상태 `200`, JSON 필드 기대값 `{"status":"ok"}`, Body `null`.
백엔드가 여러 개라면 각 백엔드의 실제 API URL에 대한 테스트 케이스를 각각 추가하세요.
이 예시 앱의 `/api/models`, `/api/maps`, `/api/characters`에도 GET 테스트를 추가할 수 있습니다.
다른 앱에는 그 앱에서 실제 제공하는 URL과 기대값을 사용하세요.

E2E의 Steps와 Expected는 JSON 배열입니다. 첫 검사는 기본 페이지 표시로 시작하고,
업무별로 실제 selector와 기대 문구를 정하세요. 아래 검색 예시는 그대로 실행할 수 있는
범용 시나리오가 아니라 **대상 화면에 맞춰 수정할 템플릿**입니다.

```json
[
  {"action":"goto","url":"/"},
  {"action":"fill","selector":"[data-testid=search-input]","value":"sample"},
  {"action":"click","selector":"[data-testid=search-button]"},
  {"action":"wait","selector":"[data-testid=search-results]"}
]
```

Expected:

```json
[{"type":"text","selector":"[data-testid=search-results]","value":"sample"}]
```

지원 액션: `goto`, `click`, `fill`, `select`, `upload`, `wait`.
지원 검증: `visible`, `text`, `count`. 인증 헤더 등 고급 API 옵션은 `/docs`에서 등록할 수 있습니다.
기본 body 검사는 빈 앱 shell도 통과할 수 있으므로 업무 기능 검증 완료로 해석하지 마세요.
등록된 테스트가 없으면 `SKIPPED`, 검증 불일치는 `FAIL`, 도구 실행 문제는 `ERROR`입니다.
브라우저 console 오류나 HTTP 4xx/5xx 관측은 `WARNING`과 로그로 남깁니다.

### 4. ZAP은 선택 설치

처음에는 **Run All에 ZAP 보안 검사 포함**을 끄고 System/API/E2E부터 확인하세요.
기본값은 꺼짐이며 Security는 `SKIPPED`입니다. 이 상태는 보안 검사 통과를 뜻하지 않습니다.
`SECURITY SCAN` 버튼으로 직접 실행하거나 설정에서 포함을 켜면 실제 ZAP 연결이 필요하며,
연결 실패는 `ERROR`로 보고합니다.

1. [ZAP 공식 다운로드](https://www.zaproxy.org/download/)에서 Windows 설치 파일을 설치합니다.
   Windows에서는 Java 17+도 필요합니다 ([공식 설치 안내](https://www.zaproxy.org/getting-started/)).
2. ZAP을 실행하고 **Tools → Options**의 Network / Local Servers / Proxies에서
   로컬 주소 `127.0.0.1`, 포트 `8090`을 설정합니다 (버전에 따라 메뉴 이름은 다를 수 있음).
3. Options의 API에서 API Key를 확인하고 키 보호를 유지합니다. API 접속 허용 주소는 로컬만 사용하세요.
   자동 업데이트 확인은 끄고, 임의 add-on을 자동 설치하지 않습니다.
4. QAROZ를 시작하는 PowerShell에 키를 설정합니다. 아래 예시는 키 입력을 화면에 숨깁니다.

```powershell
$zapKey = Read-Host 'ZAP API Key' -AsSecureString
$env:QAROZ_ZAP_API_KEY = [System.Net.NetworkCredential]::new('', $zapKey).Password
powershell -ExecutionPolicy Bypass -File scripts/start.ps1
```

5. QAROZ **설치 / 설정**에서 ZAP API URL을 `http://127.0.0.1:8090`으로 저장하고
   준비 상태에서 연결을 확인한 뒤 Run All 포함을 켭니다. ZAP 기본 포트 `8080`을 유지했다면
   QAROZ URL도 `http://127.0.0.1:8080`으로 맞추세요.

키는 DB나 화면에 저장하지 않고 `X-ZAP-API-Key` 요청 헤더로 전달합니다.
QAROZ는 ZAP을 자동 설치/기동하지 않으며, 현재 UI의 검사는 Spider + Passive Scan입니다.
Active Scan은 기본 실행하지 않습니다. 보안 검사는 등록된 프런트엔드 URL을 대상으로 하며,
현재 ZAP 연동은 JavaScript 화면의 모든 경로나 별도 백엔드 전체를 자동으로 검사하지 않습니다.

### 5. 결과 확인

**RUN ALL → Run history의 상세 버튼**에서 각 검사별 결과, 실패 이유, 로그, ZAP 경고를 확인합니다.
E2E 실패/경고의 스크린샷과 trace는 해당 결과에서 다운로드할 수 있습니다.
Trace ZIP은 로컬에서 `.venv\Scripts\python.exe -m playwright show-trace '다운로드한파일.zip'`으로 확인하세요.
전체 ERROR가 모든 검사 실패를 의미하지는 않습니다. 카드에는 각 분류의 실제 결과가 표시됩니다.
수정 전 이력은 그대로 남으므로 환경 설정을 고친 뒤 **새 실행** 결과를 확인하세요.

공식 참고: [Playwright Python 설치](https://playwright.dev/python/docs/library),
[ZAP API와 키 설정](https://www.zaproxy.org/docs/api/).

QAROZ V1 is a local-first dashboard that runs repeatable system, API, Chromium E2E,
and OWASP ZAP checks against web applications. Results, evidence, and history stay on
the machine in SQLite and the `artifacts` directory.

## Requirements

- Windows 10/11 and Python 3.12 or newer
- Chromium installed through Playwright (for E2E checks)
- Optional: a local OWASP ZAP installation (for security checks)

## Windows installation

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[test]"
playwright install chromium
```

Alternatively, run `powershell -ExecutionPolicy Bypass -File scripts/install.ps1`.
QAROZ never installs ZAP add-ons or enables external telemetry.

## Run

```powershell
.\.venv\Scripts\Activate.ps1
python app.py
```

Open <http://127.0.0.1:8787>. The bind address defaults to loopback and should not
be changed to a LAN-facing address. Runtime paths and limits can be changed with:

| Variable | Default |
|---|---|
| `QAROZ_HOST` | `127.0.0.1` |
| `QAROZ_PORT` | `8787` |
| `QAROZ_DATA_DIR` | `./data` |
| `QAROZ_ARTIFACT_DIR` | `./artifacts` |
| `QAROZ_MAX_CONCURRENT_RUNS` | `3` |

## Usage

1. Add a project, including its frontend URL and optional process, port, and health checks.
2. Use the dashboard's test manager to add API cases and declarative Playwright scenarios; advanced options are available at `/docs`.
3. Run an individual suite or **Run All**. Runs execute in background workers, independently per project.
4. Configure the local ZAP API URL in Settings and enable `security_enabled` to include it in Run All.
   Until enabled, security is SKIPPED. The dedicated Security button explicitly requests a scan.
   Spider/passive scans are the default.
   Active scanning must be explicitly requested and is limited to localhost or hosts in
   `allowed_active_hosts`.
5. Review history in the dashboard and retrieve evidence with `/api/artifacts/{artifact_id}`.

API headers with names such as Authorization, Cookie, API-Key, token, password, or secret
are replaced with `[REDACTED]` before persistence. To use authentication without storing a
secret, set the header value to `env:VARIABLE_NAME` and define that environment variable
before starting QAROZ. Use a dedicated non-production QA account and never place credentials
inside a URL.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe scripts/smoke_test.py
# Optional: verify real Chromium failure screenshots and trace ZIPs
$env:QAROZ_BROWSER_TESTS = '1'
.\.venv\Scripts\python.exe -m pytest tests/integration/test_browser_evidence.py
# Optional developer-only JS regression tests (Node is not an app runtime dependency)
node --test tests/unit/dashboard.test.cjs
```

The smoke test uses a temporary database and does not require a browser or ZAP.

## Data removal

Stop QAROZ and delete `data\qaroz.db` and `artifacts\` to remove all local history.
No cloud upload, analytics, or update service is part of V1.
