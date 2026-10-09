# Compatibility

| Component | Status |
|---|---|
| Windows 11, build 26200 | Local runtime and subprocess tests verified |
| CPython 3.12.14 | Verified interpreter; project currently requires 3.12.x |
| Official Python MCP SDK 2.3.0 | Installed from PyPI, pinned, tested |
| MCP 2026-07-28 | Negotiated by official SDK client over stdio |
| MCP 2025-11-25 | Legacy initialize/tools exchange tested over raw stdio |
| Codex desktop | CLI registration and SDK discovery verified; owner confirmed sign-in, study rights, completed achievements and credit summaries in a fresh desktop chat on 3 October 2026 |
| macOS, Linux, other Python versions | Not tested or advertised as supported |
| University of Lapland public catalogue | Experimental packaged adapter; real stdio search/details/past offerings compared with browser |
| Europe/Helsinki timezone | Pinned tzdata 2026.4; date overlap and DST boundaries tested |
| Lapland Finnish indented transcript PDF | One deliberately selected redacted document verified through imported MCP; see imports.md for exact limits |
| pypdf 6.19.0 | Pinned local extraction in a bounded subprocess; fictional PDF failures tested |
| University of Lapland personal account | Real stdio MCP read of two study rights, completed achievements, pagination and credit reconciliation verified; one authorized account |
| Lapland recorded HOPS and progress | Clean-installed stdio MCP verified all three recorded versions across two study rights; one approved version remains partial due conflicting source totals; no degree audit |
| HOPS in Codex desktop | Earlier dev1 success and a focused fresh dev2 chat verified the approved plan/progress, source-conflict and matching limitations, sign-out refusal, cleanup and fresh sign-in requirement; remaining degree credits and source GPA were not inferred |
| 0.1.0.dev1 candidate | Original local acceptance passed; the Claude compatibility update passed 329 tests and three clean installations. Three cleanup defects were reproduced afterward; see the dev2 correction status in claude-review.md |
| 0.1.0.dev2 candidate | 356 required-Firefox tests, three clean installations and source/privacy inspection passed; Sonnet 5.5 implementation and coverage follow-ups found no concrete remaining defect in inspected changes. Live SDK, fresh Codex/Code and owner-assisted fresh Desktop lifecycle verified. Safely refused source/completeness failures remain recorded; local candidate only |
| Claude Code 2.1.288, Sonnet 5.5 | Dev1 full read matrix passed; focused fresh dev2 run verified both rights, separate version discovery, approved plan/progress conflict and uncertainty wording, fresh cursor, sign-out refusal, cleanup and anonymous reconnection requiring sign-in. Earlier source/harness failures remain in verification.md |
| Claude Desktop chat (installed Windows package 2.19675.0.0) | Owner confirmed dev1 full read matrix; fresh dev2 chat verified both rights, version discovery, approved plan/progress conflicts and uncertainty wording, fresh cursor, sign-out refusal, clean disconnect and anonymous reconnection requiring sign-in. Native UI and model-usage metadata were not directly inspected |
| Selenium 4.43.0, Firefox 157.0, geckodriver 0.37.1 | Optional live runtime; isolated private profile and fictional browser tests verified |
| Google Chrome 154.0.8037.98, ChromeDriver 154.0.8037.92 on Windows | Dev3 explicit `--browser chrome`; required local browser/stdio fixtures passed, including timeout cleanup, cancellation, forced termination and fresh cookie/storage isolation. Installed official stdio MCP verified both real study rights, transcript pagination/freshness/reconciliation, all three HOPS versions, sign-out refusal, clean shutdown and fresh sign-in. One refused source failure preceded the successful HOPS pass; see verification.md |
| 0.1.0.dev3 candidate | 398 tests with both Firefox and Chrome required, three offline clean installations, source/artifact inspection and installed Chrome live SDK acceptance passed. Earlier dev2 client-chat evidence remains scoped to dev2/Firefox |
| Playwright 1.63.0 managed browsers | Failed locally with Windows error 14001; not used by the connector |
| Live session and pagination service | Fictional lifecycle tests and real-account MCP pagination/freshness passed; cross-account switching remains simulated |
| Other institutions | Not verified |

The package is pure Python, but its Windows lock includes Windows dependencies.
Do not infer cross-platform support from a `py3-none-any` wheel tag. Portable
application code can be tested on other platforms in a later milestone.

Bundled data is fictional and its institution identifier is explicitly synthetic.
The fixture is an internal test format, not a supported university export format.

## Alpha scope

`0.1.0a1` retains the accepted dev3 application behavior; only its reported
version, release documentation and verification tooling change. The required
fictional Firefox 157.0.1 / Chrome 155.0.8059.39 matrix passed all 445 tests
without skips, and three clean installations passed installed stdio checks.
The initial run's two Firefox startup failures and unchanged successful rerun
are recorded separately in
[verification.md](verification.md). The live observations in the table remain
evidence for their listed internal candidates, not a new alpha live session.
Natural expiry, real second-account switching, Chrome in fresh assistant chats
and independent human review remain unverified. The initial hosted run was
rejected for workflow YAML syntax before any tests ran. The first executing
hosted matrix had 435 passing and five failing tests. After the ownership-observer
and browser-readiness corrections, the [hosted Windows run for `800ca83`](https://github.com/dheikari/peppi-mcp/actions/runs/37963403553)
passed all 443 required Firefox/Chrome tests without skips, builds, package
inspection, three clean installations, actual stdio checks and the advisory
scan. The subsequent [run for `01d48e9`](https://github.com/dheikari/peppi-mcp/actions/runs/37966963385)
had 442 passes and one timeout-cleanup assertion failure. Its underlying cleanup
cause was not captured. The revised test checks the permitted pending-cleanup
contract and physical disposal before EOF; the final corrected commit still
requires hosted verification. These fictional checks add no live-account or
cross-platform claim. See [the alpha record](release-alpha.md).
