# Contributing

Peppi MCP is an experimental, unofficial project. Small fixes, fictional
regressions and clearer documentation are welcome. Read the [README](README.md),
[architecture](docs/architecture.md) and [compatibility limits](docs/compatibility.md)
before proposing a change. Discuss a new institution or academic capability first;
it needs its own observed access contract and verification.

## Set up on Windows

Use Windows and CPython **3.12.x**, Git, Firefox and Google Chrome in their
documented standard locations. Run PowerShell in a fresh source checkout:

```powershell
git clone https://github.com/dheikari/peppi-mcp.git
cd peppi-mcp
python --version
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.lock -r requirements-live.lock
.\.venv\Scripts\python.exe -m pip install --no-build-isolation --no-deps -e .
.\.venv\Scripts\python.exe -m peppi_mcp.demo
```

Use a Python 3.12 executable's full path if `python` opens the Microsoft Store.
Activation and execution-policy changes are unnecessary. The locks pin the
resolved Windows dependencies; they do not contain hashes. Dependency downloads
and advisory scans are separate network steps, not part of fictional tests.
The default demo uses the official MCP stdio client and fictional records only.
See the [terminal walkthrough](docs/demo.md).

## Verify a change

Start with tests covering the behavior you changed. For example:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/unit/test_release_assets.py tests/unit/test_release_metadata.py
.\.venv\Scripts\python.exe -m pytest -q --require-browser --require-chrome
```

The required matrix runs both Firefox and Chrome. Missing browser support must
fail, not be recorded as a passing release check through skips. Routine tests
use local fictional pages and data, with no Peppi credentials or university
requests. First provision drivers in the separate network step described in
[release verification](docs/hardening.md); required tests then run offline.

For the complete candidate check, download the pinned wheels first:

```powershell
.\.venv\Scripts\python.exe -m pip download --only-binary=:all: -r requirements-dev.lock -r requirements-live.lock -d .verification/wheelhouse
.\.venv\Scripts\python.exe tools/release_check.py
```

This runs the required browser matrix, builds and inspects the wheel/source
archive, then checks wheel-core, wheel-live and source-core installations and
actual MCP stdio calls outside the checkout. Hosted Windows CI uses the same
command with read-only repository permissions. Its result is separate evidence
from a local run. Do not use the private-reference option in hosted CI.

## Keep changes reviewable

Explain the problem, resulting behavior and verification in the pull request.
Keep unrelated refactoring out. Add meaningful fictional regression tests for
behavioral changes, including failure at the actual service, worker or transport
boundary where applicable. A changed runtime contract needs affected browser and
live acceptance to be reassessed; a documentation-only edit does not need a new
HAKA session.

Preserve these existing rules:

- Read only verified operations and presentation-state selections. Do not add
  academic mutations, arbitrary fetching, authentication bypasses or transport fallback.
- Require explicit connect, owner-completed sign-in and selected study-right/plan
  context. Never infer identity from a display name or accept stale generation IDs.
- Keep snapshots in memory, bound requests and deadlines, and block reconnect
  until owned process/profile cleanup is verified. Cancelled waiters must not
  cancel shared cleanup or expose delayed records.
- Use exact decimal credits and source completeness checks. Keep source conflicts,
  unresolved matching and unverified curriculum rules distinct. Arithmetic does
  not establish graduation eligibility or a GPA the connector did not acquire.

## Safe issues and fixtures

Use invented accounts, course titles, identifiers and secrets in fixtures.
Report ordinary bugs with package version, Windows/browser/client versions,
sanitized error codes, expected behavior and fictional reproduction steps.
Do not submit credentials, MFA codes, cookies, tokens, browser profiles, HAR files,
transcripts, authenticated page captures or personal tool-result files. Do not
paste a real response merely because some fields have been redacted.

Report vulnerabilities through [SECURITY.md](SECURITY.md), not public issues.
If its private channel is unavailable, wait for activation rather than posting
sensitive details publicly. Do not test against somebody else's account.

## License and attribution

Contributions are distributed under the project's [MIT license](LICENSE).
Retain applicable copyright and permission notices. Identify third-party code or
artwork and its license; do not assume the project license replaces upstream
terms. There is no separate contribution agreement.

AI-assisted contributions are welcome when you understand the changes, can
explain them and provide verification. Mention material assistance in the pull
request. A generated review or plausible explanation is not evidence that tests
or live acceptance passed.
