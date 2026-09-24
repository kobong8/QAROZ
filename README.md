# QAROZ

**Quality Assurance Review & Orchestration with Zero-Trust**<br>
_Don't trust. Verify._

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
2. Add API cases and declarative Playwright scenarios with the REST endpoints documented at `/docs`.
3. Run an individual suite or **Run All**. Runs execute in background workers, independently per project.
4. Configure the local ZAP API URL under `PUT /api/settings`. Passive scans are the default.
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
pytest
python scripts/smoke_test.py
```

The smoke test uses a temporary database and does not require a browser or ZAP.

## Data removal

Stop QAROZ and delete `data\qaroz.db` and `artifacts\` to remove all local history.
No cloud upload, analytics, or update service is part of V1.
