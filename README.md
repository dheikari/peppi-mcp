<p align="center">
  <img src="docs/assets/peppi-mcp-logo.png" alt="Peppi MCP" width="360">
</p>

<p align="center">
  <strong>An unofficial, read-only MCP server for Peppi study records. 🇫🇮</strong>
</p>

<p align="center">
  Read completed studies, explore saved study plans, and understand credit discrepancies.<br>
  From your assistant, through an isolated browser, with your own university sign-in.
</p>

<p align="center">
  <a href="#try-it-without-a-peppi-account">Installation</a> &bull;
  <a href="#connect-to-your-own-peppi-records">Connect</a> &bull;
  <a href="#tools-and-data-modes">MCP Tools</a> &bull;
  <a href="#further-documentation">Documentation</a>
</p>

<p align="center">
  <a href="docs/compatibility.md"><img src="https://img.shields.io/badge/Python-3.12-3776AB" alt="Python 3.12"></a>
  <a href="docs/architecture.md"><img src="https://img.shields.io/badge/MCP-read--only-0D9488" alt="MCP: read-only"></a>
  <a href="docs/compatibility.md"><img src="https://img.shields.io/badge/platform-Windows-0078D4" alt="Platform: Windows"></a>
  <a href="#verification-and-release-status"><img src="https://img.shields.io/badge/status-experimental-F59E0B" alt="Status: experimental"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-lightgrey" alt="License: MIT"></a>
</p>

---

**Unofficial, read-only and experimental.** The current experimental candidate is
`0.1.0a1`, prepared for its first experimental GitHub prerelease on Windows 11
with Python 3.12.14. The verified live connector
supports University of Lapland accounts. Other institutions and operating systems
are not supported by the verified connector.

## What it does

- Lists study rights and completed achievements, with pagination and source timestamps.
- Reconciles completed credits with the transcript's displayed count and total.
- Reads a saved HOPS version you explicitly select, keeping draft and approved versions separate.
- Compares that version with completed studies and preserves conflicting figures and unresolved matches.
- Offers a credential-free fictional demo, a supported local transcript import, and optional public course search.

Example requests after connecting:

> List my study rights, then ask which one to use.
>
> Show the saved HOPS versions for that right. Compare the approved version with my completed studies and explain any discrepancies.

The connector does **not** enrol you, edit HOPS or change academic records. It
does not acquire GPA or verified degree-credit requirements, and cannot establish
graduation eligibility. A displayed HOPS target is not a verified graduation requirement.

## Why discrepancies stay visible

Source conflicts, unresolved matching and unverified curriculum rules are
different problems. A selected plan or progress response puts a typed
`assessment` before the detailed records, with separate statuses, limitations,
compared quantities and exact decimal differences.

For example, in a **fictional illustration**:

> Partial: the HOPS sidebar reports 42 credits inside the plan, while its root
> groups sum to 40. The transcript reports 42 credits, including 2 credits with
> no verified plan allocation. That arithmetic could explain the gap, but does
> not establish its cause or resolve the conflicting source figures.

An unmatched course is not automatically classified as outside the plan.
Matching totals do not prove that electives, agreements or other degree rules
are satisfied. See [HOPS and progress](docs/study-plan-progress.md). The default
fictional demo below exercises transcript and credit tools; it does not expose HOPS tools.

## Try it without a Peppi account

From a source copy of this repository, open PowerShell in the project directory.
Use **Python 3.12.x**; the package currently excludes other Python versions.

```powershell
python --version
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install .
.\.venv\Scripts\python.exe -m peppi_mcp.demo
```

Installation downloads dependencies from PyPI. The demo itself needs no network,
credentials or AI-provider account: it launches the server through the official
MCP stdio client, discovers four tools, checks a fictional **15.5-credit** summary,
verifies error responses and shuts down. Look for `"client_shutdown": "completed"`.

No environment activation or PowerShell execution-policy change is needed.
If `python` is missing or opens the Microsoft Store, use the absolute path to an
installed Python 3.12 executable for the first two commands.

See the [fictional terminal walkthrough](docs/demo.md) for pinned setup commands
and output captured from the installed alpha package.

## Connect to your own Peppi records

Live access currently supports the **Finnish University of Lapland student views**.
It uses Selenium and a disposable local browser session to read verified rendered
pages. No supported third-party API contract or independent bearer token has
been established. See [the access evidence](docs/live-personal-access.md).

Install the optional live dependencies:

```powershell
.\.venv\Scripts\python.exe -m pip install ".[live]"
```

Firefox is the default and must be installed at
`C:\Program Files\Mozilla Firefox\firefox.exe`. Google Chrome is also supported
when installed in a standard Windows location. Selenium Manager obtains the
matching driver on first use, which requires network access. There is no automatic
fallback between browsers.

### Configure your MCP client

Use the absolute path to the virtual environment's Python executable as the
stdio server command. For example, in a **Claude-style `mcpServers` configuration**:

```json
{
  "mcpServers": {
    "peppi": {
      "command": "C:/path/to/peppi-mcp/.venv/Scripts/python.exe",
      "args": ["-m", "peppi_mcp", "--mode", "live", "--browser", "chrome"],
      "env": {"PYTHONUTF8": "1"}
    }
  }
}
```

Replace the example path. For Firefox, use `"--browser", "firefox"` or omit that
pair. Clients use different configuration formats; this JSON is not a Codex
configuration file. See [Claude Code and Desktop setup](docs/claude-setup.md) and
[client compatibility](docs/compatibility.md). Restart the client/server session
after changing arguments or installing an updated build.

The client starts the server; **no browser opens until `connect_personal` is
called**. Make personal tool calls one at a time:

1. Call `connect_personal` with `{}`. It opens one isolated window and returns `awaiting_login`.
2. Complete normal HAKA/MFA sign-in yourself **in that window**. Do not send credentials in chat.
3. Call `connect_personal` again to verify the session with a fresh response.
4. Call `list_study_rights` and use a returned `study_right_id` for subsequent reads.
5. For HOPS, discover versions with `get_study_plan`, then explicitly pass a returned `plan_id` to a plan or progress read.
6. Call `disconnect_personal` when finished. Reconnection or a server restart requires fresh sign-in and new identifiers.

Leave the isolated browser untouched during reads. Your everyday browser profile
is not used. To try the official interactive stdio client instead of an assistant:

```powershell
.\.venv\Scripts\python.exe -m peppi_mcp.live_demo --browser chrome
```

After signing in, enter `{"action":"verify"}`. Enter `{"action":"close"}` to disconnect and exit.

## Tools and data modes

| Personal tool | Purpose | Modes |
|---|---|---|
| `get_connection_status` | Source mode, capabilities and historical connection state | All |
| `list_study_rights` | Available study-right contexts | All |
| `list_achievements` | Paginated source records for an explicit right | All |
| `get_credit_summary` | Exact decimal credits and per-record counting decisions | All |
| `connect_personal` | Open sign-in or verify the owned session | Live |
| `disconnect_personal` | Invalidate the session and clean up its browser | Live |
| `get_study_plan` | Discover saved versions or read an explicitly selected version | Live |
| `get_study_progress` | Compare a selected version with a fresh completed transcript | Live |

`--mode synthetic` is the default: four tools read bundled fictional data.
`--mode imported` reads one explicitly selected local snapshot; see
[transcript imports](docs/imports.md) for commands, storage and the supported
Finnish selectable-text Lapland PDF layout. Redacted PDFs can work when their
table text and layout survive redaction. Imported snapshots are never silently combined.

`--mode live` adds the connection and HOPS tools. Live achievements support
completed records only; other status filters return `CAPABILITY_UNAVAILABLE`.
Unsupported tools or modes do not silently fall back to another data source.

Add `--public-catalogue` to any mode to expose `search_courses`, `get_course` and
`list_course_offerings`. These make anonymous, bounded requests to the Lapland
study guide independently of personal sign-in. The optional real-data smoke
check is `.\.venv\Scripts\python.exe -m peppi_mcp.demo --public-catalogue`;
it requires network access and depends on sampled public records remaining available.

Credits are decimal strings. Use the summary's counting decisions: blindly adding
displayed rows can double-count modules, components or corrected achievements.
Achievements accept `limit` from 1 to 100 (default 25). Reuse `next_cursor` as
`cursor` with the same right, status and page size. In live mode, an initial query
reads afresh; continuations retain that acquisition's timestamp and cached provenance.
Their memory-only snapshots expire after five minutes, with at most eight retained.

Status is historical local state, **not a fresh authentication check**. Responses
include source provenance and acquisition times. JSON text and structured content
agree; errors use MCP `isError=true` with a stable code and retryability flag.
See [the tool contract](docs/architecture.md).

## Privacy, cleanup and failures

Live record snapshots stay in process memory. Authentication belongs to the
isolated browser; its disposable profile uses temporary disk storage and is
removed after owned processes stop. Cleanup failures are reported, surviving
authentication is never reused, and reconnect waits for verified cleanup.
Deliberately imported records persist separately under `%LOCALAPPDATA%\peppi-mcp`.

**Your MCP client and its assistant provider receive the returned records.**
They may retain conversations or tool-result files. Local browser isolation does
not prevent that retention. Keep transcripts, credentials, authenticated source
responses and personal screenshots out of the repository.

The MCP server exposes no arbitrary shell, file-reading or URL-fetching tool.
Live operations are restricted to observed reads and existing presentation-state
selection controls; read-only does not mean every HTTP request is a GET. No
academic-record mutation is implemented. Source text is treated as untrusted data.

One personal browser operation runs at a time, with up to four waiting requests.
Waiting has a five-second deadline; active work has a 30-second deadline, followed
by a separate ten-second cleanup wait budget. A slow deletion remains tracked
and blocks reconnect. There is no automatic login loop, read retry or stale-data fallback.

| Error or state | What to do |
|---|---|
| `SIGN_IN_NEEDED` / `SESSION_EXPIRED` | Connect and complete a fresh sign-in; rediscover rights and versions. |
| `PERSONAL_BUSY` | Wait for the current operation or cleanup to finish before another call. |
| `PERSONAL_CLEANUP_PENDING` | Retry `disconnect_personal`; a replacement browser is blocked until cleanup succeeds. |
| `RATE_LIMITED` | Respect `retry_after_seconds`; do not loop requests. |
| `CURSOR_EXPIRED` | Start a new query without the cursor. |
| Source, schema or completeness error | No records from that failed read are returned; check the documented supported view. |

A readable HOPS credit conflict is a partial success with prominent warnings.
Uncertain identity, unsupported markup, changed plan context or incomplete
transcript acquisition fails outright. See [troubleshooting](docs/troubleshooting.md).

## Security reporting

Report security defects through [GitHub private vulnerability reporting](https://github.com/dheikari/peppi-mcp/security/advisories/new).
See [the security policy](SECURITY.md)
for report contents and maintained versions. Keep credentials and personal study
records out of reports and public issues.

Private reporting and maintainer notifications are enabled. See
[the verification record](docs/security-reporting.md).

## Verification and release status

| Evidence | Verified scope |
|---|---|
| Alpha local checks | 443 tests passed with Firefox and Chrome required, no skips; three clean installations, actual stdio smoke tests, fictional demo and source/package privacy inspection passed. |
| Alpha hosted checks | [GitHub Windows run](https://github.com/dheikari/peppi-mcp/actions/runs/37963403553): 443 tests passed with both browsers required, no skips; builds, package inspection, three clean installations, stdio checks and dependency advisory scan passed. |
| Automated dev3 checks | Historical: 398 tests passed with Firefox and Chrome required, no skips; fictional browser/stdio failures, cleanup and privacy checks. |
| Dev3 packaging | Historical: wheel/source inspection and three offline clean installations passed. |
| Live Chrome, dev3 | Official stdio MCP client: both rights, all three available HOPS versions, transcript pagination/freshness, sign-out refusal, cleanup and fresh sign-in. |
| Live Firefox, dev2 | Official stdio client and fresh Codex, Claude Code and owner-assisted Claude Desktop checks, including discrepancy wording and lifecycle behavior. |

These are scoped observations from **one authorized account**, not a guarantee
for every Peppi installation. Earlier safely refused reads and their limits remain
in [verification evidence](docs/verification.md). Chrome in fresh assistant chats,
real second-account switching and natural session expiry remain unverified.
The earlier workflow syntax failure and first executing test failures remain in
[the alpha preparation record](docs/release-alpha.md), alongside the corrected hosted pass.

Development and reviews used AI assistants, with owner-directed design and
real-account acceptance testing. The [Sonnet review and reproduced cleanup fixes](docs/claude-review.md)
are documented; no independent human security review has been completed.

The **experimental source repository is public**, licensed under MIT. For
downloadable alpha builds and their checksums, see [GitHub Releases](https://github.com/dheikari/peppi-mcp/releases).
The [alpha preparation record](docs/release-alpha.md) describes the required
local and hosted checks. `dev0`–`dev3` were internal candidates, not public releases.

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md) for pinned setup, focused regressions,
required browser checks, safe bug reports and contribution rules.

For the pinned Windows development environment, after creating `.venv`:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.lock -r requirements-live.lock
.\.venv\Scripts\python.exe -m pip install --no-build-isolation --no-deps -e .
.\.venv\Scripts\python.exe -m pytest -q
```

Routine tests use fictional local data and no Peppi credentials. Browser cases can
skip when their runtime is missing; use `-m pytest -q --require-browser --require-chrome`
for the required Firefox/Chrome matrix. Provision browsers, drivers and dependency
wheels separately before `.\.venv\Scripts\python.exe tools/release_check.py`.
That command tests, builds, inspects and performs clean offline installation checks.
See [reproducible release checks](docs/hardening.md) for prerequisites and
[dependency findings](docs/dependencies.md) for versions, licenses and advisories.
The locks pin versions; they do not include package hashes.

## Further documentation

| Guide | Contents |
|---|---|
| [Architecture](docs/architecture.md) | Data model, MCP contracts and service boundaries |
| [Reference designs](docs/reference-mcps.md) | Inspiration from the Moodle and Sisu MCP projects |
| [Live personal access](docs/live-personal-access.md) | Observed session/read mechanism and setup limits |
| [HOPS and progress](docs/study-plan-progress.md) | Version selection, matching and uncertainty |
| [Compatibility](docs/compatibility.md) | Exact platform, browser and client evidence |
| [Verification](docs/verification.md) | Candidate history, successful checks and refused attempts |
| [Roadmap](docs/roadmap.md) | Remaining work and separate release decisions |
| [Security reporting](SECURITY.md) | Private reporting policy and maintained versions |
| [Contributing](CONTRIBUTING.md) | Setup, verification and safe contributions |
| [Changelog](CHANGELOG.md) | Alpha changes and internal candidate history |
| [Terminal demo](docs/demo.md) | Fictional installed-package walkthrough |
| [Alpha preparation](docs/release-alpha.md) | Release notes, verification and publication sequence |

---

## Disclaimer

Peppi MCP is an independent project for reading Peppi study records. It is not
affiliated with, endorsed by or sponsored by the
[Peppi consortium](https://www.peppi-konsortio.fi/) or the
[University of Lapland](https://ulapland.fi/en/frontpage/).

Use your own university account and follow the terms that apply to it.
The software is provided "as is", without warranty, as described in the license.

## License

[MIT](LICENSE). You may use, modify and redistribute the software, including
commercially, provided you retain the copyright and permission notice.
Dependencies retain their own licenses; see the [dependency inventory](docs/dependencies.md).

README layout inspired by [Torium](https://github.com/ahnl/torium).
