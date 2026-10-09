# Read-only hardening and local candidate checks

Version 0.1.0.dev2 targets Windows, Python 3.12 and the observed Finnish Lapland
views. Codex and the official stdio client are the required consumers. No new
academic capabilities or persistent authentication were added.

## Assessment contract

Selected HOPS and progress responses start with a typed `assessment`. Discovery
still requires explicit version selection and has no tree assessment. Existing
fields remain available, and JSON text agrees with structured content.

`source_consistency` is `consistent` or `conflicting`; it covers the checked
source figures only. `comparison_status` is `not_requested`, `reconciled` or
`unresolved`. Neither axis establishes degree requirements. Fixed limitations
cover incomplete curriculum rules, unverified equivalences, missing source GPA
and missing verified degree-credit requirements.

Quantities separate the sidebar, HOPS headline, root groups, transcript total and
matched credits. Discrepancies have stable codes, category, scope, opaque row IDs
where applicable, an explanation and compared quantities. Differences are exact
decimal strings: first quantity minus second. Unknown differences remain null.
An absent course's credits may explain arithmetic without resolving contradictory
source statements. Unmapped entries now include credits, but do not acquire an
outside-plan classification merely because they are absent.

Authentication/context errors, unsupported layouts and incomplete transcripts
remain errors. A readable HOPS with conflicting totals remains explicitly partial.
Group targets do not establish credits remaining to graduate.

## Session scheduling and failure boundaries

One personal operation runs at a time. Up to four wait for at most five seconds;
overflow or expired waiting returns `PERSONAL_BUSY`. Clients should wait for the
current operation instead of looping retries. The active deadline is 30 seconds,
separate from waiting and a ten-second cleanup wait budget shared across termination, removal and bounded retries. A filesystem operation can outlast that wait; its daemon worker stays tracked and blocks reconnect until it finishes. It does not prolong interpreter shutdown through the default executor.

Status does no browser I/O and remains responsive. `operation_state`,
`active_stage`, `queued_requests` and `cleanup_pending` describe local state;
`is_current_health_check` remains false. Disconnect interrupts active work,
invalidates the connection generation and clears waiting requests. Cancellation
of a waiting request never cancels someone else's active read. Late results are
discarded before they can establish identity or return data.

Source/schema errors retain a usable session without returning a stale result.
Authentication or context loss, fatal worker failures and interrupted browser
operations discard it. Live 429/503 responses use `RATE_LIMITED` and
`retry_after_seconds`; a monotonic cooldown persists across disconnect/reconnect
within the server process. The existing 1–86400 second policy defaults to 60
seconds when Retry-After is invalid. No automatic retry or login loop is added.

The private worker uses sequential request IDs, action matching, strict bounded
JSON envelopes and typed data validation. Invalid framing, duplicate keys,
oversized messages and stale replies invalidate the exchange. Worker error text
is replaced by fixed client-facing descriptions rather than trusted as log text.

## Owned profile cleanup

The server creates a unique directory below `%LOCALAPPDATA%/peppi-mcp/runtime`
and passes it to geckodriver's [supported `--profile-root` option](https://firefox-source-docs.mozilla.org/testing/geckodriver/Flags.html#profile-root-profile-root).
Mozilla documents [profile leaks after interrupted sessions](https://firefox-source-docs.mozilla.org/testing/geckodriver/Profiles.html#temporary-profiles-not-being-removed),
so recovery is required as well as normal driver shutdown. The ownership marker contains
only a run identifier, PID and process creation time. Profiles remain temporary;
no credentials, browser state, HAR or private source fixtures are exported.

Normal disconnect and failure cleanup invalidate the connection immediately,
then share one service cleanup task and one backend shutdown task. Caller
cancellation cannot cancel those tasks or clear their ownership guards. Process,
job and lease references are captured once; failed resources remain registered.
The owned Windows job is terminated and its active-process count must reach zero
before profile removal. Uncertain termination preserves the profile and handles.

Removal preserves the ownership marker until other contents are gone and restores
it if final directory removal fails. A retained lease may non-recursively remove
its same verified empty filesystem directory if the marker could not be restored;
startup never extends this exception to unknown paths. Successful cleanup is verified by directory
absence. Retained leases can be retried explicitly even while their server PID
remains alive. Startup recovery only removes directories whose recorded PID and
creation time no longer identify a live owner. Verified live connector instances
are protected. Unknown ownership, junctions and reparse points are refused.

At most one filesystem cleanup job is active. It runs on a tracked daemon worker;
if the ten-second wait expires, status remains `closing`, the stage is fixed at
`owned browser cleanup`, and `cleanup_pending` is true until completion. There is
no overlapping deletion, replacement browser, automatic retry or authentication
reuse. Normal Firefox profiles, imported records and client tool-result files
remain outside this boundary. An interrupted process can leave a marker for the
next startup to recover.

During cleanup, connecting returns `PERSONAL_BUSY`. After a completed failed
attempt, an explicit connect performs one bounded recovery attempt; failure
returns retryable `PERSONAL_CLEANUP_PENDING` and directs the caller to retry
`disconnect_personal`. Failed cleanup reports an unavailable connection. A
successful explicit disconnect reports signed out with no pending cleanup.

The three original Sonnet review defects have corrected-behavior regressions in
`tests/unit/test_cleanup_regressions.py`; candidate verification and review status
are recorded in [claude-review.md](claude-review.md) and [verification.md](verification.md).

## Reproduce the checks

Install the development and live locks and the project without dependency changes.
Firefox must be installed in Program Files. Provision its driver in a separate
network step, then run the credential-free checks:

```powershell
.\.venv\Scripts\python.exe -c "from peppi_mcp.firefox_runtime import open_firefox; d=open_firefox(headless=True); d.quit()"
.\.venv\Scripts\python.exe -c "from selenium.webdriver.common.selenium_manager import SeleniumManager; from peppi_mcp.browser_runtime import chrome_binary; assert chrome_binary() is not None; SeleniumManager().binary_paths(['--browser','chrome','--browser-path',str(chrome_binary()),'--avoid-stats'])"
.\.venv\Scripts\python.exe -m pip download --only-binary=:all: -r requirements-dev.lock -r requirements-live.lock -d .verification/wheelhouse
.\.venv\Scripts\python.exe tools/release_check.py
```

The command requires Firefox and Chrome tests instead of silently skipping them, prevents
Selenium Manager downloads during tests, builds both artifacts, audits contents,
and installs wheel/core, wheel/live and source/core in separate temporary
environments without an index. Installed checks run outside the source checkout.
An optional `--reference-pdf` accepts a deliberately selected private reference
outside the repository, reads it only in memory, and prints no record values.
After documentation-only edits, `--artifacts-only` rebuilds and audits without
repeating passed tests. Reports stay in ignored `.verification` storage.

The Windows CI workflow uses the same command, with separate provisioning and
advisory-audit steps. It contains no Peppi credentials or live university tests.
Its local presence does not establish that hosted CI has run.

Dev3 adds an explicit Chrome browser choice. The release command now requires
both installed Firefox and Google Chrome, with their drivers separately
provisioned before tests. Run `python -m pytest -q --require-browser
--require-chrome` for the complete local matrix. `--browser-tests chrome` or
`--browser-tests firefox` restricts the parametrized browser cases for diagnosis;
the release check uses both. Missing required browser installations/drivers must
fail rather than silently remove their coverage. Fictional tests run headless;
real HAKA acceptance uses the headed installed browser.

For the separate advisory check, install pip-audit 2.10.1 in an isolated tool
environment and scan both lock files with `--no-deps --disable-pip`. See the
[metadata inventory and findings](dependencies.md). No advisory is silently
ignored and no automated dependency upgrade is part of verification.

Real acceptance uses the normal packaged worker after automated checks pass:
two sequential passes through both rights/all available versions, fresh transcript
pagination, sign-out refusal and restart isolation. A fresh Codex chat must
preserve discrepancies and avoid invented GPA or degree requirements. Exact
evidence belongs in [verification.md](verification.md). Natural expiry, a second
real account and other platforms remain separate unverified claims. Claude client
checks and the three reproduced cleanup defects are tracked in
[claude-review.md](claude-review.md). Corrected dev2 SDK and focused fresh
Codex/Code/Desktop lifecycle acceptance passed within the recorded scope;
MIT has been selected for project code. GitHub private vulnerability reporting
is the selected security channel; [activation checks](security-reporting.md)
remain pending. Independent human review and publication remain separate
release decisions.

## First alpha preparation

`0.1.0a1` changes package/server version and release documentation/tooling. It adds
no academic behavior. Contribution and changelog guidance are in the root
[CONTRIBUTING.md](../CONTRIBUTING.md) and [CHANGELOG.md](../CHANGELOG.md).
The inspector checks all four version references, MIT metadata/exact license,
release documents, full public-tree fingerprint and packaged-source correspondence.
The selected private transcript is inspected in memory locally only.

Official action pins were resolved from the upstream release tags on 9 October:
[checkout v4.3.1](https://github.com/actions/checkout/releases/tag/v4.3.1),
`34e114876b0b11c390a56381ad16ebd13914f8d5`, and
[setup-python v5.6.0](https://github.com/actions/setup-python/releases/tag/v5.6.0),
`a26af69be951a213d495a4c3e4e4022e16d87065`.
Read-only permissions and required browser checks remain in place, following
[GitHub's workflow security guidance](https://docs.github.com/en/actions/reference/security/secure-use).
Hosted execution is pending publication authorization; action pinning alone
does not verify the workflow on a hosted runner.
