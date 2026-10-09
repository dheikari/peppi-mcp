# Verification evidence

Current live-connector results appear at the end. Earlier milestone sections record historical states and may describe limitations since resolved.
Milestone checked on 3 October 2026, Europe/Helsinki. This is the implementer's
verification, not independent review.

## Completed evidence

| Evidence category | Result | What it proves / limitation |
|---|---|---|
| Synthetic unit and boundary checks | Passing | Conservative credit policy and argument handling for tested fictional cases |
| Real MCP client over stdio | Passing | Official SDK client launches a separate server, discovers/calls tools, receives errors and closes |
| Raw stdio wire check | Passing | Legacy initialize/tools exchange; every stdout line parses as JSON-RPC; process exits 0 on orderly EOF |
| Adapter fixtures | Invented catalogue responses plus bundled synthetic personal data | Public normalization, failures, pagination, cache expiry and rate limits tested without live requests |
| Manual public checks | Real MCP search/details/offerings and browser comparison confirmed | Source facts match sampled UI; no full catalogue/offerings coverage claim |
| Manual private-account checks | Not performed | No evidence of live personal integration |
| Installation/package checks | See local verification record below | Not publication or independent review |

`python -m pytest -q` initially ran 49 cases: 48 passed and a raw-pipe test closed
stdin while a call was pending. The test was corrected to await each protocol
response before orderly EOF. A repeated-course regression was added for distinct
credit groups. The subsequent run passed **50 tests**, including both protocol
versions. `python -m pip check` reported no broken requirements.

The calculation cases cover fractional credits, module/component coverage,
explicit corrections, transfers, failed/planned rows, duplicate/conflicting IDs,
repeated courses, unresolved mappings, missing metadata, source-total differences,
separate study rights and partial/empty results. Boundary cases cover strict
arguments, pagination, changed/stale/malformed cursors, unsupported tools, inert
source text and absence of network calls in the synthetic application operations.

The SDK client demonstration returned:

```json
{
  "transport": "stdio subprocess",
  "server": "peppi-mcp",
  "protocol_version": "2026-07-28",
  "tools": ["get_connection_status", "list_study_rights", "list_achievements", "get_credit_summary"],
  "mode": "synthetic",
  "demo_main_credits": "15.5",
  "ambiguous_total": null,
  "invalid_input": "INVALID_ARGUMENT",
  "unsupported_capability": "CAPABILITY_UNAVAILABLE",
  "client_shutdown": "completed"
}
```

## Milestone 1 installation/package record

The local wheel and source archive were built with `python -m build --no-isolation`.
A fresh `.venv-verify` environment installed the pinned dependency lock and the
wheel. Import inspection confirmed that the code came from that environment's
`site-packages`, not the working source tree. Running tests from the extracted
source archive passed **50 tests** again; the installed-wheel MCP demonstration
and `pip check` also passed.

The clean extracted source then installed successfully using the documented
`pip install --no-build-isolation --no-deps -e .` command, and its client
demonstration passed. The ordinary working environment remains `.venv`.

Wheel and source-archive manifests were inspected, including package metadata and
the bundled fixture. Checks found no user home paths, private-key markers,
credential/import directories, PDFs, private keys or log files. All bundled
records identify themselves as synthetic. This is a bounded local contents
check, not a comprehensive security review. The ignored
`.verification/artifact-audit.json` records final artifact hashes and file lists.
Final archive refreshes include this verification record and the source
`.gitignore`; application and test code are unchanged from the clean-install run.

The local Git repository has no remotes or commits; the project files remain
uncommitted. There is no earlier history to audit and nothing was published.

## Remaining limits

No live account, login expiry, account switch, remote transport, calendar feed,
real curriculum audit or third-party desktop host has been tested. A deliberately
supplied private transcript was verified in milestone 3 below. No external
AI-provider review was requested. The public release is not ready.

## Milestone 2: public catalogue

The final suite passed **92 tests**. New checks cover strict public arguments,
fixed-host paths, invalid JSON/HTML/oversized responses, timeouts, HTTP error codes,
rate-limit cooldowns, expiring/evicted/tampered cursors, source-count discrepancies,
null credits/descriptions, multiple/empty offerings, Finnish date boundaries and
DST. A separate real subprocess exposes all seven tools with an invented fetcher
and socket connections disabled. Production fixtures contain no captured catalogue
payloads. This is still implementer verification, not independent review.

The manual `python -m peppi_mcp.demo --public-catalogue` run passed with:

| Check | Observed result |
|---|---|
| Search `XAKA0103`, one row per page | Two local pages: IDs 7300 and 27674; continuation labelled cached |
| Course 7300 | XAKA0103, 2.0 credits, populated multilingual source sections |
| Historical offerings | 13 received; cancellation and upstream completeness remain unknown |
| Current offerings for 7300 | Empty array; not proof of no future teaching elsewhere |
| Offering XAKA0103-3001 | 17 March–22 April 2020, matching the browser |
| Enrolment window | 2 December 2019 00:00–31 December 2019 23:59 in Helsinki, matching the expanded browser entry |
| Inclusive date filter | 22 April 2020 retains that offering |
| Independent broader MCP search `johdatus` | Source reports 259; 224 received; two returned on first local page; completeness partial |
| Personal records / shutdown | Still synthetic; subprocess client shutdown completed |

The broader initial-prototype criterion, real source data through MCP, is now met.
No supported API contract, upstream quota, upstream pagination mechanism, or
cancellation interpretation was established. Those limitations are returned to
clients and documented; the adapter is experimental and opt-in.

The earlier artifact audit and 50-test clean-install result above describe
milestone 1. The local artifact filenames are reused during development.

## Milestone 2 installation/package record

A new `.venv-public-verify` environment installed the dependency lock and built
wheel. Import inspection confirmed `site-packages` within that environment.
All **92 tests from the extracted source archive passed against the installed
wheel**, including the synthetic and public-fixture stdio clients. `pip check`
reported no broken requirements. No real university requests run in that suite.

The final wheel contains 20 files and the source archive 44. The local audit
checks paths and contents for excluded private files, home paths and private-key
markers, verifies the personal fixture is synthetic, and compares all packaged
application/test bytes with the tested source copy. This is a bounded audit,
not a comprehensive security review. `.verification/public-artifact-audit.json`
records current hashes and manifests. A completion audit added multilingual
content preservation coverage and removed a possible no-op in cursor tampering;
production application code stayed unchanged. Nothing was published or added to a desktop client's
configuration.

## Phase 2 completion audit

The previous implementation turn made progress: it added the adapter and verified
real catalogue data through MCP. The subsequent audit checked the original Phase 2
requirements against current source, automated coverage, artifact contents and a
fresh live demonstration, rather than relying on the milestone summary.

| Original requirement | Evidence and conclusion |
|---|---|
| Implement the verified public route | `PublicFetcher` allows only the observed anonymous search/course/realization paths; the fresh real stdio demo passed |
| Preserve codes, languages, credits, descriptions, prerequisites and dates | Source schemas and normalization retain codes, decimal strings and all fi/en/sv title/section values; explicit multilingual boundary regression passes; sampled course and offering agree with browser evidence above |
| Distinguish current, historical and cancelled where provided | Separate current/past collections, computed date phase and explicit unknown cancellation status; sampled source has no verified cancellation state to interpret |
| Bounded pagination, timeouts, caching and limits | Argument bounds, signed snapshot cursors, response/list limits, expiring bounded cache, socket timeout, request spacing and cooldown behavior are implemented and covered by tests |
| Respect actual access requirements | Only anonymous fixed-host reads; no authentication, cookies, credential discovery, redirects or access bypass. Access-denied responses fail explicitly. No institutional usage contract or quota is claimed |
| Source links and retrieval times | Course links and per-result provenance retained; explicit tool-boundary timestamp/link assertions pass; cache labels preserve original retrieval time |
| Required failure and data cases | Fictional tests cover Unicode/multilingual content, multiple/empty/paginated offerings and courses, missing fields, malformed/changed schemas, timeouts, throttling, unavailable service and Helsinki date boundaries |
| Public-source agreement and accurate failures | Fresh live MCP demo returned the expected course, 13 historical offerings and checked date interval; browser agreement is recorded above; failure tests assert distinct safe error codes |
| Synthetic automated verification | Public-fixture subprocess disables sockets; the test suite makes no live catalogue requests. Network verification is an explicit manual demo command |

The second milestone is complete as an experimental public catalogue adapter.
Personal imports, live personal access and public release remain separate roadmap
milestones and are not claimed complete by this audit.

## Milestone 3: supplied transcript import

The working-source suite passes **148 tests**. In addition to existing synthetic
and public checks, invented PDFs exercise real text extraction, wrapped Unicode
titles, fractions, hierarchy across page boundaries, printed subtotals, graded
module/components, failed and unknown rows, missing fields, repeated codes,
source-total discrepancies and extra study-right sections. Unsupported transfer
and status markers fail explicitly; no mapping is invented for unverified cases.

Failure checks cover malformed/non-PDF/encrypted/scanned/rotated/oversized input,
page limits, worker timeout, missing stores, unsafe repository paths and sanitized
errors. Storage checks cover checksums/timestamps, exact/concurrent reimport,
changed mappings, new versions/documents, profile/right isolation and corrupt
payloads. The CLI-to-store-to-MCP path and imported demo run in real subprocesses.
Imported application operations are also exercised with sockets disabled.

The deliberately selected real redacted PDF was visually inspected on all pages.
Each normalized course code, title, credit value, grade and date was compared with
the source. Every printed subtotal and the cover total reconciled. The private
snapshot then passed the official SDK stdio client: discovery, selected context,
all paginated achievements, provenance, credit summary and clean shutdown. Real
records, document details, hashes, screenshots and counts stay outside this
repository; the suite uses entirely invented fixtures. This is implementer
verification, not independent review or evidence of live account access.

Supported scope and limits are in [imports.md](imports.md). Source issue time and
import time are distinct; signatures/identity are not verified. The real sample
does not establish transfer/correction semantics or coverage of other PDF layouts.

### Clean installation and artifact audit

A fresh `.venv-import-verify` installed the version lock and built wheel.
Import inspection confirmed code loaded from its `site-packages`. All **148 tests
from the extracted source archive passed against that installed wheel**.
`pip check` found no broken requirements. The installed `peppi-mcp-import`
console command reimported the selected real PDF without creating another
snapshot or changing its first import time. The installed imported MCP demo
then passed from outside the source checkout, including all achievement pages.

The wheel contains 25 files and the source archive 55. The bounded local audit
checks 47 source files and both package manifests/contents for excluded private
files, home paths, private-key markers and selected transcript identifiers/text.
Packaged application/test bytes match both the working source and the source
copy used for installed-wheel tests. Final archive refreshes update documentation
only; application and test bytes are unchanged. The ignored
`.verification/import-artifact-audit.json` records artifact hashes and manifests,
without private transcript values. Nothing was published or configured in a
desktop MCP client. Git still has no commits or remotes.

Milestone 3 is complete for the documented single-layout import scope. Live
personal access, further PDF variants, external review and release remain open.

## Milestone 4 work in progress

Working-source checks now pass **151 tests**. New unit and actual stdio assertions
verify that connection status distinguishes an unverified personal route from
an expired/signed-out session, remains honest in imported mode, and that `--mode
live` fails on stderr without fallback or a traceback. Readiness reporting makes
no network or sign-in attempt and labels its public observation as historical.
These checks do not verify authentication or live personal records.

The public portal was initially observed redirecting to HAKA's organisation selector
through Shibboleth/SAML. That initial check stopped before organisation selection.
The two owner-supplied Moodle/Sisu references were read at pinned revisions; no
third-party package was installed or code executed. Their source-level comparison
is in [reference-mcps.md](reference-mcps.md). No university inquiry was sent.

The distribution artifacts and their clean-install audit above remain milestone 3
artifacts. These milestone 4 source changes are not a completed live-access release.
See [the requirement-by-requirement audit](live-personal-access.md) for the missing
route, authentication and real-account verification evidence.

### Authenticated UI inspection, 3 October 2026

The owner subsequently completed sign-in/MFA in the legitimate portal and
explicitly authorised read-only study-page inspection. The study-right menu,
separate linked-right summaries, completed filter and transcript rows were
observed. The selected right's completed row count and credit sum agreed with
its source summary. Normalized course codes, titles, credits, grades and assessment
dates matched the previously imported snapshot by per-field and whole-row
FNV-1a fingerprints. A page reload returned the same completed records.
This consistency check is not a digital-signature or source-attestation check.

No private identifiers, record fields, fingerprints, cookies or session-bearing
URLs were saved into project files. A focused scan of application code, tests,
documentation and README found none of the inspected account identifiers,
personal name, comparison fingerprint or authentication query marker. This is
a scoped check, not a replacement for the later release artifact audit.

After updating the historical evidence in connection status, all **9 focused
unit and real stdio protocol tests passed**. They retain the distinction between
a manual browser observation and an authenticated MCP connection; live mode still
fails explicitly. The remaining authentication, account-isolation and expiry
cases are unverified. See [inspection constraints](live-personal-access.md).

### Completed-view normalization, 3 October 2026

The internal `normalize_transcript_view` function now validates the observed
Finnish completed-course projection before creating typed records. It performs
no authentication, network, browser or storage operations and is not exposed as
an MCP tool. Its bounded schema requires one explicit visible study-right context
and reconciles record count and exact decimal credits with the source summary.

A minimal projection read from the owner's live transcript through the approved
browser tool was passed to this actual Python normalizer through process stdin,
without writing a private fixture. Every normalized course code, title, credit
value, grade and assessment date equalled the existing imported snapshot; the
existing credit service also matched the live source total. The projection's
retrieval time was supplied at normalization during this manual verification;
a production collector must stamp the actual acquisition time. This is a manual
live-projection/parser check, not an authenticated MCP test or source attestation.

All **185 working-source tests passed**, including **34 new normalizer cases**.
They cover hidden/missing rows, context mismatch, count and credit mismatches,
explicit zero results, duplicate completions, unsupported types/statuses/annotations,
malformed dates/numbers, missing fields, strict booleans, oversized/malformed Unicode
input, deterministic content identity and retained retrieval timestamps. A failed
case caught Pydantic accepting numeric `1` for a `Literal[True]`; explicit strict
boolean fields and visibility checks fixed that before the full suite passed.

A focused project scan found none of the inspected account IDs, name, live
comparison fingerprint, source course-code markers or captured session token.
Negative tests use explicitly fictional identifiers and authentication-query
examples. No dependency, package artifact, browser credential or MCP launch
configuration changed. Authenticated collection, lifecycle tests and access-route
conditions remain unresolved as detailed in the milestone acceptance audit.

### Session foundation and investigation harness, 3 October 2026

The full working-source suite now passes **205 tests** (18.59 seconds), including
19 new session-service cases and a real MCP stdio subprocess case with a fictional
browser backend. Coverage includes quiet startup, explicit connection, retained
pagination timestamps, fresh acquisitions, cursor scope/expiry/eviction,
authentication loss before cached reads, account changes before/during reads,
unsupported status filters, concurrent calls, timeout/cancellation cleanup, and
sanitized unexpected exceptions. The test acquisition clock is deterministic;
successive Windows wall-clock reads can legitimately have equal timestamps.

`pip check` reports no broken requirements; modified Python modules compile.
Playwright 1.63.0 and its managed Chromium/Firefox binaries were installed. Both
browser executables fail before navigation with Windows error 14001 and matching
SideBySide events. The installed Firefox binary passes a version-only check;
that does not establish that it supports Playwright automation. No browser
authentication, network-route capture, DOM collector, real-account MCP read,
browser fixture suite, or clean live-install verification completed this step.

Production `--mode live` remains disabled; the new internal MCP live boundary
requires an injected backend and is exercised only by the fictional test module.
The owner selected isolated Firefox after Chromium failed and was asked to run
the investigation harness in ordinary PowerShell. The route selection and real
browser integration remain blocked on establishing a working isolated browser.
No inquiry was sent, no package was published, and Vire/My Dashboard was untouched.

## Isolated Firefox connector and current acceptance, 3 October 2026

The managed Playwright browser failure was resolved at the runtime-design level:
Selenium 4.43.0 drives installed Firefox 157.0 with geckodriver 0.37.1 in a disposable
private profile. This is an intentional change from the proposed managed Chromium
runtime, not evidence that the original browser binaries were repaired.

The connector-owned investigation session established the cookie-backed rights
selector POST, UI context-selection POST, fresh transcript account markers and
rendered completed-record view. Both linked rights were selected in that session,
including an explicitly empty right. No achievements JSON API or independent token
exchange was established. The production selection is recorded in
[live-personal-access.md](live-personal-access.md).

A new `.venv-live-clean` installed the wheel with `[live]` from PyPI dependencies.
`pip check` succeeded and the installed synthetic stdio demo passed outside the
source directory. This is a clean Python environment on the existing Windows host,
not a fresh Windows OS or second machine. Firefox and the Selenium Manager driver
cache already existed. A resolved live dependency version lock is included.

Actual MCP startup remained quiet until explicit connect, exposed six expected
tools, and started signed out. Fresh account verification succeeded after human
HAKA/MFA. The first transcript attempt exposed a native-input interaction error;
the next returned a transcript validation error. A possible filter-transition race
was reproduced with fictional delayed rows. The reader
now dispatches the normal DOM click and waits for a stable reconciled projection.
These failures returned errors, never stale or fictional personal records. Full
real-record and logout acceptance is still in progress.

Fictional verification additionally includes an actual Firefox HTTP fixture with
two fresh account identities, HTTP-200 signed-out content, redirect rejection and
access denial; hidden controls/rows and decimal parsing; delayed filter replacement;
MCP-style cancellation cleanup; and a real Windows job-object test terminating an
unresponsive owned worker and its child. These are simulated failure cases, not
observations of natural Peppi expiry or a second authorized Peppi account.

### Successful personal records through the installed MCP package

The corrected installed wheel ran through the official MCP stdio client outside
the source directory. Human sign-in established a fresh account, both linked study
rights were selected, and every returned completed row was acquired from the
visible Peppi transcript. The nonempty right required five MCP pages at a limit
of seven; the other right had an explicit zero-count/zero-credit source summary.
Both credit summaries reconciled exactly with current Peppi values. Initial
queries repeated acquisition with a newer timestamp and equal source fields;
continuations retained the original timestamp and carried cached provenance.

All course codes, titles, exact decimal credits, grades and completion dates for
the populated right matched the deliberately selected redacted PDF. The check
parsed the private reference in memory and printed aggregate pass/fail results
only. No private rows, identities, exact totals or comparison fingerprints were
stored in repository fixtures or documentation. A focused scan of 69 source files
found none of the reference's course-code/title/checksum markers or local user paths.

The full working suite passed **233 tests** in 46.12 seconds before the historical
readiness flag was updated to reflect this successful real MCP verification.
The hidden-input interaction and delayed-filter tests now reproduce both browser
conditions that had prevented the initial real reads.

### Observed sign-out failure and artifact audit

After successful reads, the client retained a newly acquired pagination cursor.
The owner used Peppi's sign-out action in the connector window. Attempting that
continuation returned **SESSION_EXPIRED**, not a cached result or an empty success.
The service discarded its identity/snapshots/cursors and closed the owned browser.
This is an observed explicit sign-out test. Natural timeout expiry, real denial,
and switching between two authorized Peppi accounts remain unverified; fictional
tests cover their failure behavior.

After updating historical readiness reporting, nine focused immutable-mode and
actual stdio tests passed. The source and built wheel/source archive audit checked
all 69 nonignored project files and all artifact members, comparing packaged code
with current source. No selected-reference course/title/checksum markers, private
file types, credential directories or local user paths were found. Only aggregate
results were printed. This scoped audit is not independent security review.

The final installed server was restarted outside the source directory. Startup
reported `signed_out`; explicit connect opened a new private window and repeated
connect still returned `awaiting_login`, despite the owner's separate everyday
browser remaining signed in. No earlier connector session was reused. The client
then disconnected and exited successfully without another human sign-in. All
connector-owned verification windows were closed. This completes the requested
experimental personal-read scope; publishing and university correspondence remain
outside this implementation.

## Codex registration follow-up, 3 October 2026

The owner asked for the next step after implementation. The local Codex CLI
registered the `peppi` stdio server in its user configuration, using the project's
Python environment, `--mode live`, and `PYTHONUTF8=1`. No credentials or persistent
browser profile were configured. `codex mcp get peppi --json` read the saved entry;
the official SDK client launched that exact configured command, discovered all
six expected tools, and confirmed signed-out startup without opening Firefox.
The owner then invoked the connector from a fresh normal Codex desktop chat.
Their screenshot shows successful sign-in and the two linked study rights;
they subsequently confirmed the completed-achievement and credit-summary query
worked. This is owner-observed desktop integration evidence, in addition to the
agent-run SDK checks. Claude clients remain untested. The preceding distribution
audit covers artifacts built before this documentation-only client follow-up.

## Recorded HOPS milestone, 3 October 2026

The live service now discovers recorded versions, reads a selected HOPS tree,
and compares it with a fresh transcript through `get_study_plan` and
`get_study_progress`. Synthetic, imported, public-catalogue and completed-record
behavior remains covered by regression tests. The full suite passed **279 tests**
in 56.88 seconds, including the real Firefox fixture and stdio checks.

Live discovery established stable row/version references, separate study rights,
draft and approved versions, group credit ranges and outside-plan credits. The
current draft's root groups reconcile with its sidebar; the inspected approved
view has a discrepancy in inside-plan group totals. The latter is preserved as
partial source evidence, with unresolved progress. Its cause is not inferred.
The sidebar completion total includes outside-plan credits. No titles are used
to infer equivalence or graduation eligibility.

Real source inspection also revealed an agreement information icon preceding
the course-name control. Selecting the named control, while separately binding
the agreement's row/right references, fixes the missing-title failure. Agreement
equivalence remains unverified. A local diagnostic worker reloaded parser code
without repeatedly discarding the owned browser. This harness is excluded from
all artifacts; final installed verification uses the normal shipped worker.
Private source bodies stayed inside the browser/worker/client processes; only
aggregate results and credential-safe field diagnostics were printed.

The initial clean-installed run passed the draft's tree/progress checks, then
hit the 30-second deadline during the next version's operations. The session was
discarded. Selected-version reads now use the previously observed version URL
directly, avoiding a redundant default-plan load before each refresh. Fresh
account/right/version verification remains required. Fictional tests verify
direct refresh and rejection of changed or removed contexts; fixed-stage timeout
messages and aggregate operation durations support diagnosis without source data.

The wheel installed in the separate Windows validation environment; `pip check`
reported no broken requirements. Launched outside the source directory, its
default stdio server discovered eight tools, started quietly signed out, and
rejected disconnected HOPS reads with `SIGN_IN_NEEDED`. The artifact audit
checked 76 nonignored source files, 37 wheel members and 84 source-archive members,
including matching packaged code to source and checking private reference markers.
No selected-reference content, local user paths, private files or diagnostic
harness was included. This remains a scoped local audit, not independent review.

The subsequent clean-installed run used the normal shipped browser worker and
official stdio MCP client, outside the repository working directory. All three
recorded versions across both rights passed tree linkage, explicit selection,
fresh-repeat fingerprint and acquisition-time checks:

| Right index / source version | Nodes / courses | Comparison evidence |
|---|---|---|
| 0 / draft 2 | 197 / 165 | Fresh reads agree; two unresolved items and one unmapped achievement; source totals reconcile |
| 0 / approved 1 | 196 / 164 | Fresh reads agree; three unresolved items and two unmapped achievements; `inside_plan_groups` discrepancy preserved |
| 1 / draft 1 | 130 / 112 | Fresh reads agree; source credits reconcile; no unmatched achievements |

Progress calls took 23.91, 24.33 and 21.98 seconds respectively, within the unchanged
30-second deadline. These timings describe this run, not a latency guarantee.
All three returned null graduation eligibility; reconciled accounting does not
resolve group-choice rules. Personal row bodies and exact credit totals remained
inside the local client. Natural expiry, a real second account, Claude clients,
and the two new HOPS tools in a fresh desktop chat remain unverified.

The same installed run also rechecked completed records after switching among
all HOPS versions: the populated right returned 30 records over five pages; the
other explicitly reported zero records. Cached continuations preserved their
acquisition timestamp, fresh reads matched all returned course fields, and exact
credit summaries reconciled for both rights.

After the owner explicitly signed out in the connector window, a real stdio
`get_study_progress` call using the previously selected plan returned
`SESSION_EXPIRED`. Status then reported `expired`, sign-in required and no active
read mechanism. No plan or cached records were returned. The service discarded
the session and its mappings; the client disconnected and exited successfully.
This verifies explicit sign-out, not natural timeout expiry or a second account.

The final documentation and artifacts were rebuilt and audited against current
source. The separate installed environment was refreshed and its default stdio
entry point rechecked outside the repository: eight tools, quiet signed-out
startup and refusal of disconnected HOPS reads. No publication was performed.

## Read-only hardening candidate, 3 October 2026

The owner subsequently supplied a successful fresh Codex HOPS conversation.
That demonstrates the earlier recorded-version tools in the desktop client;
it does not by itself validate the new dev1 assessment instructions.

The local `0.1.0.dev1` implementation adds typed assessments before selected
plan/progress records. Source consistency, transcript comparison and unverified
curriculum rules are distinct. Exact decimal differences retain their operands;
credit ranges are not collapsed to one difference. Unmatched transcript records
include credits without assuming outside-plan allocation. A fictional case where
an absent course numerically explains a discrepancy remains explicitly partial.

The scheduler allows one active call and four waiting calls, with five seconds
to acquire the browser, 30 seconds active time and separate bounded cleanup.
Status has no browser I/O. Disconnect/cancellation checks cover waiting callers,
late worker replies, a granted queue slot and a completed result awaiting delivery.
Each can be invalidated before returning records. Source failures do not return
cached success; cooldown prevents another request during the requested pause.

The credential-free test infrastructure runs the shipped worker implementation
against a fictional localhost Peppi page through the actual MCP stdio client.
Only test bootstraps change the origin or headless setting; there are no production
fault tools. It records routes/methods/parameters and checks response/error
consistency, two rights, recorded versions, partial conflicts, fresh acquisition,
cached pagination, explicit zero, denial, redirects, HTTP-200 signed-out pages,
unsupported/oversized source bodies, hidden/incomplete rows, changed plans and
account changes before/during/after acquisition despite identical display labels.
Real stdio tests also exercise queue overflow/expiry, cancellation, responsive
status, disconnect, the unchanged 30-second deadline and client EOF.

Focused service/normalizer/worker tests cover cursor retention and expiry,
ambiguous allocations/agreements, strict JSON framing and safe error text.
Windows process tests cover partial startup, a hung worker tree, abrupt parent
termination and profile recovery. Ownership checks preserve concurrent live
owners and unrelated directories; a real junction fixture is refused.

The EOF test exposed a cleanup ordering issue: the SDK terminates its subprocess
after a two-second grace period, while the worker previously waited three seconds.
Interrupted workers now terminate immediately; idle shutdown reserves time for
owned-job termination and profile removal. The actual EOF regression verifies
that the dedicated runtime root is empty afterward. Cleanup failure remains
explicit rather than reporting a clean session.

Package checks compare source bytes with the wheel/source archive, inspect
metadata and reject private files, selected-reference markers and local user
paths. The old interactive discovery command evaluator is excluded; only its
redaction helpers remain. Development reload/diagnostic harnesses remain ignored
and excluded. The supported official-client acceptance utility is retained.

The pinned live and development locks were scanned separately with pip-audit
2.10.1 on this date: no known vulnerabilities were reported, none ignored and no
project dependencies upgraded. Declared dependency licenses are inventoried in
[dependencies.md](dependencies.md). This is time-bound advisory evidence, not
independent review or a project-license compatibility decision.

The frozen candidate verification command passed **329 tests in 357.11 seconds**
with required browser mode enabled. It then built both distributions and checked
93 nonignored project files, 40 wheel members and 101 source-archive members.
The selected private PDF was used only for in-memory marker checking. Source
fingerprinting confirmed that code did not change while the tests ran.
Offline wheel/core, wheel/live-extra and source/core installations in three fresh
Windows virtual environments passed `pip check` and the official stdio smoke
client outside the repository. Core environments returned the actionable
`BROWSER_DEPENDENCY_MISSING` error; a separate simulated missing-binary check
verified the documented Firefox installation message. The Windows CI workflow
contains the equivalent checks but has not been run on a hosted runner.

After the owner completed fresh sign-in, the installed dev1 candidate ran through
the normal shipped worker and official stdio client outside the repository. Its
34 installed Python modules matched the audited wheel. Two sequential HOPS passes
covered both rights and all three recorded versions. Each selected tree and
progress comparison passed linkage, freshness, assessment ordering, discrepancy
arithmetic and scope checks. Progress operations took 21.81–28.06 seconds, within
the unchanged 30-second deadline for this run.

The approved version retained `inside_plan_groups` as a source conflict in both
passes, with partial provenance and unresolved comparison. No arithmetic
explanation cleared that warning. The other right's reconciled accounting still
returned no graduation decision. All unmatched achievement entries supplied
credits without an inferred outside-plan classification.

Subsequent live transcript checks returned 30 records over five pages for the
populated right and an explicit zero for the other. Continuations retained their
acquisition time; fresh reads matched every checked field and carried newer times.
Credit summaries reconciled with current Peppi figures for both rights. The
selected redacted reference matched the populated right's course codes, titles,
credits, grades and completion dates. Records and exact credit totals stayed in
local process memory; only aggregate evidence was printed.

After the owner explicitly signed out in the connector window, a selected HOPS
comparison returned `SESSION_EXPIRED`; the retained pagination cursor was then
refused with `SIGN_IN_NEEDED`. Status showed an expired, idle session, no read
mechanism, no queued requests and `cleanup_pending=false`. The official client
disconnected and exited successfully.

A subsequent installed-server run started quietly `signed_out`, refused a
disconnected study-right query, and returned `awaiting_login` from both initial
and repeated connect. It did not reuse the prior authenticated session. Disconnect
and process exit completed, and no owned runtime directories remained. This is
observed explicit sign-out and restart isolation, not natural expiry.

The final fresh Codex desktop chat used the registered live server and another
owner-completed sign-in. It discovered both rights and all recorded versions,
explicitly selected the approved bachelor's version and called the plan,
progress, credit-summary and status tools. Its progress call completed in 23.77
seconds. The final answer led with conflicting totals and unresolved matching,
included the selected version and acquisition times, and kept the arithmetic
explanation separate from the unresolved source conflict. It explicitly declined
to establish a graduation shortfall or claim a source GPA/authoritative degree
target. An absent course remained an unverified allocation, not a presumed
outside-plan course. Personal amounts, titles and identifiers are not copied
into this verification record.

That chat then called disconnect and checked status without further record reads:
`signed_out`, idle, no active stage or waiting requests and `cleanup_pending=false`.
A subsequent local ownership check found zero remaining runtime directories.
The source-code fingerprint still matched the fully tested candidate. Both
required consumers have therefore passed the scoped dev1 acceptance checks.

Milestone 6 is complete as a tested local candidate. A real second-account switch,
natural expiry, hosted CI run and publication remain unverified. License
selection, security contact, independent review and authorization to publish are
separate release gates.

## Claude review and compatibility checks — 4 October 2026

At the owner's request, Claude Code 2.1.288 ran Sonnet 5.5
(`claude-sonnet-5-5`) against the installed dev1 candidate. Initialization and
model-usage metadata confirmed that exact model. A fictional stdio smoke test
called all four core tools, paginated six completed rows over three pages,
retained the unresolved null total and handled `STUDY_RIGHT_NOT_FOUND` correctly.

A separate source-only Claude session reviewed an audited source-distribution
copy using 40 Read calls, two Glob calls and 12 Grep calls in 437.7 seconds.
It had no execution, editing, live MCP or access outside the review directory.
The [triaged report](claude-review.md) distinguishes static observations from
three locally reproduced cleanup defects. Those defects remain unresolved;
the prior normal-path acceptance does not establish that the edge cases are safe.

After explicit owner approval to send live study-record tool results to Anthropic,
the first live Claude Code session verified sign-in, both rights, complete
transcript pagination, newer initial acquisitions and scoped credit summaries.
Overlapping calls produced the correct `PERSONAL_BUSY` response. A controlled
continuation used sequential calls but the selected HOPS response hit Claude's
`TOOL_RESULT_TOO_LARGE` limit. This was a client compatibility failure, not a
passing HOPS acceptance result. No transport fallback was used.

Explicit owner sign-out then caused the selected HOPS comparison to return
`SESSION_EXPIRED` and the retained cursor to return `SIGN_IN_NEEDED`. Disconnect
and historical status confirmed signed-out, idle, zero waiting calls and
`cleanup_pending=false`. The client exited and zero runtime directories remained.

The compatibility patch adds Anthropic's per-tool 500,000-character annotation
for the two live HOPS tools and explicit sequential-call server instructions.
Tool names, arguments, result fields, read mechanism and operation deadlines are
unchanged. Actual stdio tests verified the `_meta` serialization and absence of
the annotation in synthetic tools. All 329 regression tests then passed in
353.05 seconds with required browser mode, followed by build/privacy audit and
offline wheel/core, wheel/live and source/core clean installations. The tested
code fingerprint is:

```
3f483759b55af2d2c64ed505c0658331b2ea95bcd9274cb56facb327abde15ed
```

The audited artifacts contained 40 wheel members and 103 source-archive members,
with 95 nonignored project files checked. The private reference was used only
for in-memory marker checking. The dedicated installed environment passed
`pip check`, exposed the HOPS annotation through the official stdio client and
started signed-out.

The first live run of this update passed transcript pagination, newer initial
acquisitions and exact credit reconciliation, then a selected HOPS read returned
`SOURCE_UNAVAILABLE`. One manually initiated diagnostic continuation returned
`BROWSER_UNAVAILABLE`; the connector discarded the session. The owner reported
closing the isolated window or changing pages during that run. This is an
interrupted attempt, not a passing HOPS test or proof of the precise failure cause.
Disconnect then reported signed-out, idle, no queued calls and no pending cleanup.

A fresh connection required another owner sign-in and newly discovered right,
version and cursor identifiers. With the window left untouched, Sonnet received
all three selected plans and their progress results across both rights. The large
plan response no longer hit the client's output-size rejection. The source
conflict remained partial with unresolved matching, while the reconciled version
still retained curriculum limitations. The aggregate final response preserved
uncertainty about graduation requirements, source GPA and absent-course allocation,
and retained a fresh pagination cursor. All six selected plan/progress calls
succeeded without unexpected errors. After explicit owner sign-out, the selected
HOPS comparison returned `SESSION_EXPIRED` and the fresh retained cursor returned
`SIGN_IN_NEEDED`. Historical status was expired, idle, with zero waiting calls and
`cleanup_pending=false`. Disconnect then reported signed-out and clean; the Claude
driver exited successfully. An ownership-directory check before Desktop's browser
session found zero runtime directories. This is observed sign-out refusal and
normal cleanup, not natural expiry or coverage of the three reproduced defects.

The owner confirmed that Desktop loaded the configured Peppi server after restart.
This establishes configuration discovery only; actual chat reads are a separate
acceptance step. Desktop's native UI is not accessible to the current automation
tools, so its chat verification will be identified explicitly as owner-observed.
The owner then completed Desktop's separate sign-in and confirmed successful live
study-right discovery in a Sonnet 5.5 chat. Supplied screenshots corroborated the
two linked rights and a live acquisition time; no private labels or identifiers
are copied here. The read-only scope remains existence in the authenticated
selector, not enrolment status, active validity or degree eligibility.

The owner subsequently supplied Desktop's full answer: both rights, transcript
pagination/freshness and exact reconciliation, all three selected HOPS versions,
partial source conflict and unverified graduation requirements were retained.
However, its claim that no GPA exists in the source overstated the connector's
observation. These tools do not acquire GPA; absence from their response does not
establish absence in Peppi. The client had also retained its cursor before the
long HOPS sequence, so the five-minute snapshot could already have expired.

The owner's separate normal Claude Code answer corroborated these live reads and
used the correct narrower GPA wording: no source GPA was provided. It recovered
large tool results from client-created local files. This is actual client storage,
outside the connector's memory-only snapshot policy; no such files were copied
into the repository or release artifacts. Its early retained cursor was also old.

Server and progress-tool guidance was strengthened to distinguish observations
not provided by the connector from figures absent in Peppi, and unmatched records
from courses absent or outside a selected plan. Five actual stdio protocol tests
passed after this instruction-only change. Both owner-directed chat follow-ups
then corrected the observation boundary, distinguished unresolved agreement
matching from plan absence, and retained newly acquired cursors privately.
These were directed follow-ups in already running chats, not fresh unprompted
model evaluations of the new server instructions. After the owner explicitly
signed out in both isolated windows, each normal chat reported `SIGN_IN_NEEDED`
for the retained approved plan and newly acquired cursor, with no records.
Both reported successful disconnect, signed-out/idle status, no active stage or
queued requests, and `cleanup_pending=false`. Historical verification timestamps
remained unchanged. These results are owner-observed chat evidence; the controlled
Claude Code driver separately verified `SESSION_EXPIRED` followed by
`SIGN_IN_NEEDED` through the actual transport.

The service verifies authentication before decoding a continuation cursor.
Therefore these sign-in refusals do not depend on diagnosing its age; natural
expiry remains unverified. Client-created tool-result files still exist outside
the repository and were not deleted or claimed as part of connector cleanup.

The final guidance update passed all 329 tests in 361.55 seconds with required
browser mode, followed by build/privacy inspection and all three offline clean
installations. Its tested code fingerprint is:

```
359c632662fd526c4344934e2fb8ac9ef9c435e03a749f8a92cdef500bc35ae7
```

Only documentation changed afterward to record the completed evidence; the final
archives were rebuilt and inspected against this tested source. The earlier
fingerprint describes the output-size patch before the guidance refinement.
The controlled model run, owner-run clients and final installed stdio checks are
distinct evidence. No unprompted model guarantee or correction of the three
cleanup defects is implied by the successful normal-path tests.

The unchanged development/live locks were rescanned on 4 October with pip-audit
2.10.1: 40 and 42 packages respectively, no known advisories and no skipped
packages. No advisories were ignored and no dependencies upgraded.

The final code was installed into the dedicated live environment and passed
`pip check`. An official stdio SDK client launched outside the checkout verified
the installed source, new observation-scope instructions and both HOPS annotations.
The fresh server started signed-out, refused study-right reads with
`SIGN_IN_NEEDED`, and disconnected cleanly without opening a browser. A final
ownership-directory check found zero runtime directories. Restarting the owner
clients will load the new instructions; their already running chats received the
explicit correction above. Client storage and the three reproduced cleanup
defects remain outside this normal-path success claim.


## Dev2 cleanup correction checks (4 October 2026)

Three corrected-behavior regressions were added before implementation and all
three failed against the unchanged dev1 source (2.01 seconds). After correction,
they pass. Failed leases remain owned, overlapping closes share cleanup, and
native waiter cancellation no longer releases the task guard prematurely.

The full dev2 suite passed **343 tests in 424.62 seconds**, with Firefox required
and no skipped browser checks. Fourteen added regressions cover the three defects,
multiple/AnyIO cancellation, bounded startup recovery, daemon deletion after its
wait budget, old cursor rejection, real Windows file locks and marker restoration,
interrupted startup, uncertain process termination, and recovery/cancellation
through the shipped browser worker and actual MCP stdio.

A fictional permanently stuck daemon-removal subprocess exited normally and its
abandoned directory was recovered by the next process. No live Peppi session was
used for these fault injections. The 30-second active deadline, five-second queue
wait, queue capacity and academic acquisition rules were preserved.

Package/clean-install completion, the Sonnet 5.5 source re-review and corrected
candidate live/client acceptance will be recorded separately. Historical dev1
live results do not establish acceptance of the cleanup changes.

Dev2 also passed wheel/core, wheel/live and source/core offline installation
checks, including `pip check` and actual installed stdio discovery. The privacy
audit checked 98 source files, 40 wheel members and 106 source-archive members,
including private-reference markers in memory only. Tested code fingerprint:

```
d047073ccd7259b51c70164e26a9e9e3f446a8955ee24c6e37f98c66cbcaa314
```

The development/live dependency locks remain unchanged; their same-day advisory
audit is recorded above. Documentation-only rebuilds preserve this tested code.

The first dev2 Sonnet 5.5 re-review agreed that the original three defects were
corrected. Two additional cleanup-related cases were reproduced before their
corrections: shutdown cancellation starting a hung recovery worker, and marker
creation failing after directory creation. Their new regressions passed after
cancellation propagation and initialization rollback/retained-lease fixes. Those
implementation and test changes triggered the verification runs recorded below.


### Final cleanup candidate verification

An intermediate frozen candidate passed **352 tests in 421.76 seconds**, with required
Firefox support, then all three offline clean installations (wheel/core,
wheel/live and source/core), `pip check` and installed MCP stdio discovery.
The audit checked 99 source files, 40 wheel members and 107 source-archive members;
private-reference markers were compared in memory. Final tested fingerprint:

```
0c59bced94bdfe6aa18ff7415e220205c6eca36a62c2f11d475f86f1dcbadc37
```

The focused final Sonnet 5.5 review completed in 44.5 seconds using 2 Read and
3 Grep calls. Initialization and final usage metadata confirmed the exact model.
It found no concrete remaining correctness defect in the reproduced fixes. This
last pass read the two changed storage/backend files and skimmed test names; it
did not execute tests or provide a human audit. The independent test run above
supplies runtime evidence. Windows inode and birth-time metadata are available
on this tested runtime; replacement-directory refusal passed.

Live transcript/HOPS, sign-out, shutdown, fresh-server isolation and focused
fresh Codex/Claude lifecycle acceptance are recorded below and passed.
Real second-account switching, natural expiry and hosted CI remain unverified.
License, security contact, independent human review and publication are separate
gates. No repository publication or dependency upgrade was performed.

### Dev2 live stdio read evidence

On 4 October the official SDK launched the clean-installed dev2 server outside
the checkout. The owner signed in through its isolated Firefox window. Two
completed transcript passes covered both study rights, pinned pagination,
newer repeated acquisition times, every stable returned achievement field and
exact credit reconciliation. The populated right matched the deliberately
selected private PDF on course code, title, credits, grade and completion date.
The other right explicitly reported zero completed records.

Two HOPS passes explicitly selected all three currently available versions.
Selected plan/progress observations agreed on tree structure and snapshot
identity while reporting fresh acquisition times. Decimal discrepancy arithmetic,
assessment ordering, per-version source consistency, unresolved matching and
unverified graduation eligibility were checked. The approved version retained
its source-conflict/partial warning; an arithmetic explanation did not remove it.

One intervening fresh transcript read returned `PERSONAL_VIEW_INCOMPLETE` after
14.5 seconds, with no records. Its session remained usable and the separately
requested HOPS pass succeeded. A subsequent explicit transcript verification
passed; no automatic read retry or transport fallback was added. The code proves
that the bounded completeness check did not accept the view, but the private
driver did not retain DOM/network response bodies, so the underlying cause is
unverified. This failed attempt remains evidence, not an error-free acceptance
claim. A fresh cursor was then retained privately for the sign-out check.

After the owner confirmed explicit sign-out, the selected HOPS query returned
`SESSION_EXPIRED`, with no records. The retained cursor then returned
`SIGN_IN_NEEDED`, also without records. The cursor had aged beyond its five-minute
TTL while awaiting confirmation, so this is not evidence of an unexpired-cursor
refusal; the independent selected-plan query establishes observed authentication
loss. Disconnect reported signed out, idle, no queued calls or active stage and
`cleanup_pending=false`. The SDK client/server exited normally, and inspection
found no owned runtime directories remaining.

A newly launched installed server started signed out and opened an anonymous
HAKA window. Repeated `connect_personal` calls still returned `awaiting_login`
with sign-in needed; they did not restore the previous session or open additional
windows. Closing this fresh anonymous session also succeeded and the client/server
exited normally. This verifies explicit sign-out, normal cleanup and restart
isolation, not natural expiry or artificial cleanup failures against Peppi.

### Final audit additions and preserved baseline

The final requirement audit added real stdio startup interruption cases for
disconnect, client cancellation, EOF and forced server termination. The first
expanded release run passed **356 tests in 439.21 seconds**, source/privacy
inspection and all three offline clean installations. Its tested fingerprint:

```
73854efff913ec4f18c07708a2de981553e6ee00064b8907f9e3dbc99d8ab545
```

Sonnet 5.5 reviewed the three relevant test/fixture files (40.2 seconds; 3 Read,
4 Grep; exact model confirmed). It found no concrete test correctness defect,
but identified indirect process-exit evidence in three paths. The tests were
strengthened to capture query-only handles for the test server's OS descendants,
including Firefox subprocesses. They check exit before releasing the blocked
HTTP fixture, graceful EOF exit code, handler completion and no source requests
during fresh-server recovery. All six cleanup transport tests passed in 76.30
seconds. Those stronger assertions led to the final full release run below;
production cleanup code and dependencies did not change.

The final strengthened source then passed **356 tests in 437.53 seconds**, with
Firefox required, followed by source/privacy inspection and all three offline
clean installations. Final tested fingerprint:

```
d1935228841da27c7ea3ef3a0eb81a13b61a5f01e9e344c32de2ac956ffea424
```

The audited artifacts had SHA-256 hashes
`170a4ab6d9e2fb7912750212b56a738ff0a8d784cb62316ce80d713ac2eac2a0`
(wheel) and `13dd3c6c0d87ec923af90342e4ebdd042b8f814af1e4c379e386b9ae3c4828ef`
(source). Documentation-only rebuild hashes are retained separately. The audit
checked 99 source files, 40 wheel members and 107 source members.

The focused Sonnet 5.5 follow-up read all three changed test/fixture files and
one source Grep (34.5 seconds; exact model confirmed). It found the explicit
coverage gaps closed and no concrete defect in the changed assertions. It did
not run tests or re-audit production implementation. Optional process-race and
test-diagnostics hypotheses remain unreproduced follow-ups. No exhaustive
security guarantee is inferred. Windows process ancestry is inspected using the
[documented process snapshot API](https://learn.microsoft.com/en-us/windows/win32/toolhelp/taking-a-snapshot-and-viewing-processes);
the observer opens query-only handles and never stops enumerated PIDs.

The preserved dev1 source archive was independently rechecked against its
historical SHA-256 (`dbba3cee81175ebdce1a34900032a19b94b2ef0830242dfafbc5e32b4b520798`).
All three shipped corrected-behavior regressions failed against that original
source, confirming the pre-fix evidence without relying on a documentation claim.

A fresh Codex chat passed initial discovery and disconnected-state acceptance:
eight live tools, signed out, sign-in needed, idle queue, no cleanup pending,
and `SIGN_IN_NEEDED` with `isError=true` and no records. It did not connect or
open another browser. The authenticated follow-up results are recorded below.

A separate fresh Claude Code session also passed historical signed-out/idle
status and `SIGN_IN_NEEDED` refusal without opening a browser. Initialization
and usage metadata confirmed Sonnet 5.5; the actual CLI still reported 2.1.288,
and the installed Firefox executable reported 157.0. The three active cold/live
client contexts left exactly one runtime directory, belonging to the pending
official SDK browser. Historical status is not fresh authentication evidence.

### Dev2 focused client acceptance attempts

The first authenticated Claude Code attempt selected the right with only a draft
version and explicitly zero achievements, so it did not satisfy the approved-plan
test. A directed selection correction stopped on `SOURCE_UNAVAILABLE`, without
records. The owner reported that the window remained open and untouched; the
historical status remained connected/idle, but that status alone did not verify
authentication. The fetch failure's exact network/HTTP cause was not retained.
A separately requested fresh attempt then read the approved plan, its progress
and a fresh initial achievements page successfully, preserving source conflict
and unresolved matching.

The private acceptance driver rejected that attempt's final answer format and
closed its client before the planned sign-out check. This was a harness failure,
not an observed connector source/schema failure. The owner process was no longer
running and no process referenced the remaining owned profile. Normal installed
server startup recovery removed that abandoned directory; the cold server still
refused disconnected reads and opened no browser. The private driver was corrected
to accept bounded English punctuation and retain the session if a final summary
fails validation. Production code and the tested fingerprint did not change.
These attempted reads did not substitute for the sign-out and reconnect gates;
the completed final lifecycle run is recorded below.

The fresh Codex chat then completed its authenticated lifecycle check. It
verified fresh authentication, listed both rights and discovered versions
separately before explicitly selecting the reported approved version. Selected
plan/progress reads preserved conflicting/partial source figures and unresolved
matching. Its answers stated that verified remaining graduation credits could
not be established and that a missing connector GPA observation did not establish
whether Peppi contains GPA information. One client diagnostic included aggregate
credit values despite the requested output filter; subsequent output was filtered.
Those values were not copied into this check's aggregate evidence.

After owner sign-out, the approved progress query returned `SESSION_EXPIRED` and
the retained cursor returned `SIGN_IN_NEEDED`, with no records. The client did not
establish the cursor's remaining TTL, so no unexpired-cursor claim is made. Both
subsequent anonymous connect calls remained `awaiting_login` with sign-in needed.
Final disconnect/status reported signed out, idle, no active stage or waiting
calls and `cleanup_pending=false`. Independent runtime inspection found zero
owned directories before opening the next client's browser. This was a focused
fresh-chat lifecycle check, not a repeat of the SDK's complete two-pass read matrix.

The corrected Claude Code driver then completed its focused lifecycle run using
CLI 2.1.288 and exact `claude-sonnet-5-5`, verified in initialization and final
usage metadata. Fresh authentication, both rights, separate version discovery,
explicit approved selection, plan/progress assessments and a fresh initial
achievements page succeeded. Its actual answers preserved the partial/conflicting
source figures, unresolved matching and unverified degree requirements; missing
connector GPA observation did not become a claim that Peppi lacks GPA.

Owner sign-out caused the approved progress query to return `SESSION_EXPIRED`
and the retained cursor to return `SIGN_IN_NEEDED`, with no records. Disconnect
reported signed out, idle, an empty queue and `cleanup_pending=false`. Both
subsequent anonymous connect calls required sign-in again, followed by another
successful disconnect and clean final status. The CLI/driver exited normally;
independent runtime inspection found zero owned directories. No unexpected tool
errors occurred in this final run. The earlier source error and private harness
failure remain recorded above. The Desktop package was independently rechecked
as 2.19675.0.0; its completed owner-assisted lifecycle run is recorded below.

In this final Code run, sanitized monotonic driver events place the fresh initial
page tool use at 525.4 seconds and the retained cursor tool use at 622.7 seconds
from driver start. The 97.3-second interval is below the advertised 300-second
snapshot TTL; acquisition occurred after the first event. This supplies a timely
cursor sign-out check, separately from the SDK's aged cursor and the Codex chat's
unverified TTL report. No cursor value was retained in the aggregate evidence.

The owner then restarted Desktop, selected Sonnet 5.5 in a fresh chat and
completed the connector's isolated sign-in. Their pasted client summary reports
fresh connection verification, both study rights, separate version discovery,
explicit approved selection, successful plan/progress reads and a fresh initial
achievements page with its cursor retained privately. The actual answer did not
establish remaining graduation credits: displayed targets and an arithmetic
example were explicitly unverified. It stated that the connector did not acquire
or compute source GPA. Source conflicts, study-agreement matching and unverified
allocation remained unresolved. Desktop's final response included course names
and quantities despite the requested minimal output; none of those values were
copied into the new aggregate evidence. This is owner-supplied client evidence,
not direct native UI or model-usage inspection.

The owner then used Peppi's sign-out action in Desktop's isolated window. Their
final client summary reports `SESSION_EXPIRED` for the retained approved progress
query and `SIGN_IN_NEEDED` for the retained cursor, with no records. Disconnect
and status reported signed out, idle, an empty queue and `cleanup_pending=false`.
Both subsequent anonymous connect calls remained `awaiting_login` with sign-in
needed and did not advance historical verification. The final disconnect closed
the anonymous window and status again reported signed out, idle, no waiting calls
and no cleanup pending. No reconnect occurred before the refusal checks. Desktop
did not establish its cursor's remaining TTL; the timely Code cursor check above
supplies that separate evidence.

### Completed local dev2 candidate

The three original cleanup findings and reproduced follow-up cases are closed
by failing-before/passing-after regressions, the final 356-test required-Firefox
run, actual stdio interruption tests, source-only Sonnet reviews and completed
live/client acceptance. The final source/test/build fingerprint remains
`d1935228841da27c7ea3ef3a0eb81a13b61a5f01e9e344c32de2ac956ffea424`.
Only documentation and ignored aggregate evidence changed after that test run.
The final documentation-only build is inspected again for metadata, source
correspondence and private-reference markers; its SHA-256 manifest is retained
alongside the local wheel/source artifacts rather than embedded inside them.

The live acceptance includes explicitly refused failed reads, not an assertion
that the university or every client interaction was error-free. Their unresolved
causes and the interrupted private driver remain above. Natural expiry, a real
second account and hosted CI remain unverified. Broader platform/institution
support, license selection, security contact, independent human review and
publication remain separate release gates. No publication was authorized or run.
## Chrome candidate verification — 4 October 2026

The owner requested installed Google Chrome support before license/public-release
decisions. Dev3 adds explicit `--mode live --browser chrome`; Firefox remains the
default. Synthetic/imported behavior, tool names and arguments, acquisition
routes, discrepancy assessments and the corrected cleanup guard are preserved.
No client configuration was silently switched to Chrome.

On this Windows host, Google Chrome 154.0.8037.98 and ChromeDriver 154.0.8037.92
were used with Selenium 4.43.0. Driver provisioning was a separate network step;
the actual fictional tests required cached drivers and made university requests
only in the separate planned real-account acceptance session.

The first expanded matrix had 394 passes and two failures. Chrome's timed-out
read left cleanup pending. Fixed-category fictional diagnostics established
Windows errors 3/145 on a 264-character path within a nested profile. A standalone
long-file ownership regression failed before the fix. Windows extended-length
filesystem APIs now validate/remove these files without changing the owned root,
marker protocol, retry count or ten-second budget. Long-path junction refusal,
unrelated-target protection, locked files and marker restoration also passed.

The other initial failure was the Firefox EOF observer's captured-process
liveness assertion. It passed in isolation; its underlying cause was not
established. Fixture observers now prove membership in the exact owned Windows
job instead of treating every PPID descendant as owned. This changes test
infrastructure only. Core worker/driver/browser membership is mandatory, and an
observer job handle is closed before testing kill-on-job-close behavior.

The corrected `python tools/release_check.py` run passed **398 tests in 706.05
seconds**, requiring both browser installations, without skips. Wheel-core,
wheel-live and sdist-core offline clean installations each passed dependency and
official MCP stdio checks. Source inspection covered 102 files; the wheel had 41
members and the source archive 110. The tested production/test/build fingerprint
was `c9e38a0ba43dbbfa278edec502241be73e9b6c34be552382ee6ae5633899bed0`.
Critical installed Chrome/worker/storage sources matched tested source bytes.
The selected private PDF was not re-read for this automated run.

The initial inspected dev3 wheel hash was
`7012b9be8a3a907918647fe38ab3536ba5f333c8a5790c8a79a6641691a108aa`;
the initial source archive hash was
`98a94f07dfa38a0efee371fd79d872a9b2262f094f81ddd672ce4f360ca2d409`.
Documentation-only final artifacts are recorded separately after live acceptance.
Historical dev1/dev2 artifacts and acceptance claims remain intact.

An outside-checkout, separately installed dev3 SDK client discovered all eight
tools, began signed out and opened a fresh headed Incognito Chrome window with
`awaiting_login`. The owner completed normal HAKA/MFA sign-in. Live transcript
checks passed for both rights: complete pagination, exact source-credit
reconciliation, cached continuation provenance and fresh repeated reads matching
every returned achievement field except acquisition provenance.

The first selected HOPS read returned `SOURCE_UNAVAILABLE` after successful
version discovery. No records or stale result were returned, and historical
status still reported the session connected and idle. The precise network/source
cause was not established. A separate controlled fresh check is recorded below;
there was no automatic retry or sign-in loop.

That controlled check passed separate version discovery and explicit plan/progress
reads for all three versions across both rights. Assessments remained first in
the response, preserved the approved version's partial source conflict, separated
unresolved matching from source consistency, and retained unverified curriculum
limitations. Decimal discrepancy differences, row references and fresh provenance
were verified. No GPA or graduation requirement was inferred. Personal records,
opaque identifiers and cursors stayed in the local client process's memory.

After owner sign-out, the retained selected-plan progress read returned
`SESSION_EXPIRED` without data. The retained transcript cursor then returned
`SIGN_IN_NEEDED` without data at 182.66 seconds of age, within its 300-second TTL.
Disconnect reported signed out, idle and `cleanup_pending: false`.

Two anonymous reconnect calls required fresh sign-in and did not restore the old
session. Final disconnect completed, the SDK client/server exited successfully,
and an independent count found zero entries in the dedicated connector runtime
directory. This evidence uses the official stdio client and one authorized
account on Windows; everyday browser profiles were not used.

Final documentation-only wheel/source rebuilds are audited with the unchanged
tested code fingerprint. Their hashes are recorded in the external local
`dist/SHA256SUMS.dev3.txt` manifest and ignored verification receipt, avoiding a
self-referential source-archive hash. A separately installed final wheel receives
dependency, stdio, anonymous Chrome restart and profile-removal checks.

Chrome in fresh Codex/Claude chats has not been separately verified.
Hosted CI, real second-account switching and natural expiry remain unverified.

## README presentation — 8 October 2026

The README adds an original generated wordmark, a centered introduction,
section links and static Python/Windows/read-only/experimental badges, following
the header layout of [Torium](https://github.com/ahnl/torium). A local browser
preview verified the logo and all four badge images loaded and that the tools
navigation reached its heading. Markdown rendering, local documentation links,
section targets, configuration parsing and wheel/source README metadata passed.

The source distribution now explicitly includes the public logo. Release
inspection permits only that exact relative path and its inspected SHA-256;
unselected PNGs, modified artwork and private reference markers remain rejected.
All eight new asset-inspection regressions passed. The resulting code/test/tool
fingerprint is `fc0f9d6c347b71a0c90f8bf2a508c83662e586f3d3c76d2ac0479f64c31aa592`.

Application package files still match the accepted dev3 wheel byte for byte.
The historical artifacts and hash manifest remain unchanged; documentation-check
builds and their hashes are stored separately in ignored verification storage.
The 398-test browser matrix and live acceptance above were not repeated for this
presentation change. [Generation prompts](assets/logo-prompts.md) accompany the
artwork; no additional client, institution or release support is claimed.

## MIT license and README disclaimer — 8 October 2026

The owner selected MIT. The repository now contains the standard license text,
with a 2026 Peppi MCP contributors copyright notice. Package metadata declares
the SPDX expression `MIT` and explicitly includes `LICENSE`. The README adds a
linked MIT badge, a license section and a Torium-style independent-project
disclaimer linking the Peppi consortium and University of Lapland.

Local documentation-check builds passed: both wheel and source metadata report
`License-Expression: MIT` and `License-File: LICENSE`, and both archives contain
the exact repository license. Rendered section targets, local links, JSON/config
parsing, archive privacy inspection and packaged README correspondence passed.
A local browser preview verified the original logo and all five badges loaded.
An offline clean wheel installation passed `pip check`; installed metadata and
license contents matched the repository.
The source fingerprint is
`d389df1070025186f01bd63a7d3e1552be3c139d1317321094ac646c5fa99f34`.

Application package files remain byte-for-byte identical to the accepted dev3
wheel. Historical candidate artifacts remain unchanged; the new documentation
builds and hashes are stored separately in ignored verification storage. The
browser regression matrix and live acceptance were not repeated for licensing
and documentation changes. Security contact, independent human review and
publication remain separate decisions; this work does not publish the project.

## Security reporting policy — 8 October 2026

The owner selected GitHub private vulnerability reporting. Root `SECURITY.md`
records the latest maintained candidate, private report contents, safe local
reproduction guidance and best-effort handling without a guaranteed deadline.
The README links the policy, and the source manifest explicitly includes it.
[The activation checklist](security-reporting.md) covers repository setup,
maintainer notifications and report-form availability.

Markdown rendering, relative links, maintained-version correspondence, public
source privacy inspection and documentation-check packaging passed. Both the
policy and setup guide are included in the source distribution. Application
package files and historical accepted artifacts remain unchanged; no browser
regressions or live acceptance were repeated for this documentation change.

There is no configured GitHub remote. Private reporting is not enabled or
verified, and no test report or external message was sent. The contact choice
is complete; activating and verifying the reporting channel remains a release
step under separate repository publication authorization.

## First public alpha preparation — 9 October 2026

The intended first public prerelease is `0.1.0a1`, tagged `v0.1.0a1`, under
`dheikari/peppi-mcp`. `dev0`–`dev3` remain internal candidates. Root contribution
and changelog documents, the fictional installed-package walkthrough and alpha
release notes are included in the source distribution. The original logo/header
and dated historical acceptance records remain intact.

All four version references agree. Thirty-four added release-evidence tests
cover version disagreement, missing documents, altered metadata/license/README
and missing, changed or unexpected packaged source; together with the eight
existing artwork checks, all 42 focused cases passed. The collected required
Firefox/Chrome matrix now contains 440 cases, from the previous 406 baseline.

The initial full run returned **438 passed, 2 failed in 758.76 seconds**, without
skips. Both failures were at Firefox startup: the first mapping test returned
`BROWSER_UNAVAILABLE`, and the forced-termination fixture did not reach its
startup checkpoint within its 20-second wait. Both unchanged cases subsequently
passed in isolation, **2 passed in 26.29 seconds**. No runtime, assertion or
deadline was changed to make them pass; the underlying startup cause was not
established. A complete unchanged rerun was required before local preparation
was accepted. The current installed browsers are Firefox 157.0.1 and Chrome
155.0.8059.39; earlier live acceptance remains scoped to the older listed versions.

The advisory scan refreshed on 9 October covered 51 pinned distributions and
reported no known vulnerabilities or skipped distributions. The license inventory
was refreshed without dependency upgrades or suppressed advisories.

A fresh source archive copy outside the checkout passed pinned installation,
dependency checks and the installed fictional demo. The captured output discovers
four tools, returns a 15.5-credit total, leaves an ambiguous total unresolved,
verifies expected error codes and reports clean stdio shutdown. No HAKA session,
HOPS acquisition, university request or recording was used for that demo.
The 36 application files match the accepted dev3 package after the version export
and LF line-ending normalization; academic behavior is unchanged.

Privacy inspection of the intended 114 public files and preliminary alpha
archives passed, including the selected private PDF's markers checked in memory
locally. The private reference, environments, imports, authentication/profile
storage, ignored diagnostics and historical artifacts are excluded. No private
author email was found. Public file/parent inspection found no reparse points.
GitHub account identity and its provided no-reply address were verified before
staging; author settings apply to this repository only. Exact staged bytes match
the audited working tree. There was no earlier committed history.

PowerShell's Markdown renderer and independent HTML parsing verified 23 documents,
109 local links, JSON examples and 11 PowerShell examples. A local browser preview
loaded the original logo and all five badges without horizontal overflow. The
demo's rendered JSON matches the installed capture. Historical accepted dev3
artifact hashes are unchanged. Final alpha hashes belong in the external local
manifest and receipt after documentation is frozen, not inside the source archive.

No GitHub repository was created, history pushed or release published during
local preparation. Hosted CI and private reporting/notification activation remain
pending publication authorization. Natural expiry, real second-account switching,
Chrome in fresh assistant chats and independent human review remain unverified.

The unchanged complete `python tools/release_check.py` rerun passed **440 tests
in 719.87 seconds**, requiring both browsers without skips. Wheel-core, wheel-live
and source-core offline clean installations passed dependency checks and actual
official-client stdio smoke tests outside the checkout. The code/test/release-tool
fingerprint was `86ecb66a396a11f30f7f5ce06164820a159415eb4f39133fef65ef4c7e945340`.
The inspected wheel had 42 members; the source archive had 122. The reference
marker check passed without retaining or printing private values.

Final documentation-only packages are re-inspected against the committed public
tree and receive final clean-install/stdin checks and an external SHA-256
manifest. The external receipt binds the complete source revision and public-tree
fingerprint to those artifacts; earlier code-only fingerprints do not identify
documentation. This is local alpha acceptance, not evidence of hosted CI or a
published release. No additional live-account acceptance is claimed.

## Initial GitHub push and workflow correction — 9 October 2026

The owner authorized publication and personally pushed the reviewed initial
commit `3af00c5f242f311fb6a115ecfd25b83544267ec2`. The remote `main` reference
matches that local revision, and GitHub associates the commit with `dheikari`.
Repository-local author and committer settings use the verified GitHub no-reply
address; global Git settings were not changed.

The [initial hosted run](https://github.com/dheikari/peppi-mcp/actions/runs/37952609801)
failed workflow validation at line 39; no test job ran. PyYAML 6.0.3, installed
only in the separate audit environment, reproduced the same scanner error on
the original file. Converting the wheel-download command to a YAML literal block
makes it parse as a string without changing its PowerShell command, triggers,
read-only permissions or required browser checks. Hosted acceptance of the
corrected workflow remains pending the owner's next push.

The correction passed 42 focused packaging/artwork regressions. Both the YAML
structure and all six PowerShell workflow scripts parse; the download command
is unchanged. Rendering and independent parsing checked 23 Markdown documents,
114 local links, JSON examples and 11 PowerShell examples. The application/test/
tool/lock fingerprint remains identical to the locally accepted 440-test run.

[Private reporting](security-reporting.md) is enabled. The anonymous public report
link, owner-view private form, All Activity subscription and Watching notification
channels were verified. No report was submitted; non-owner authenticated form
submission and actual notification delivery remain untested. No release or tag
has been created.

## First executing hosted matrix — 9 October 2026

The [hosted run for `f25c982`](https://github.com/dheikari/peppi-mcp/actions/runs/37954638304)
executed the required Firefox/Chrome suite: **435 passed, 5 failed in 973.76
seconds**, without skips. Packaging, clean installations and the advisory step
did not run after pytest failed. The trace shows hosted Python 3.12.10; local
acceptance used 3.12.14.

One failure was the initial Chrome `connect_personal` call returning a retryable
error with timeout wording. Its full code and stage were truncated by the test
assertion; the underlying startup cause remains unestablished. Chrome provisioning
had downloaded its driver, whereas Firefox provisioning also launched its browser.
The Chrome step now runs the existing credential-free local isolation probe before
the full matrix. The production 30-second deadline and all required checks remain
unchanged. Unexpected tool outcomes now report a fixed, recognized code without
printing payloads or arbitrary source error strings.

Four startup interruption cases reached their final PPID-descendant assertion
after verifying that the captured owned process handles had exited and profiles
were absent. The identity of the remaining descendant was not captured, so it
must not be classified as a leaked browser or a harmless OS helper on this
evidence. The fixture already establishes ownership through an exact named
Windows job; the final observer now checks that job for late children as well
as the captured process identities, rather than claiming every server descendant.
An actual Windows regression rejects both a captured survivor and a late owned
child, then succeeds with an unrelated child still running and untouched.

All eight related cases passed locally unchanged before correction, **8 passed
in 58.19 seconds**. The observer, safe diagnostics, Chrome probe and affected
stdio cases then passed together, **12 passed in 62.39 seconds**. Three added
regressions bring the required matrix to 443 collected cases.

The complete corrected local release command passed **443 tests in 683.15
seconds**, with both browsers required and no skips. Source/package privacy
inspection and wheel-core, wheel-live and source-core offline installations
passed, including actual official-client MCP stdio checks. The selected private
reference was checked locally in memory; no private markers were printed or
uploaded. The code/test/tool/lock fingerprint is
`69f8f5f3cc9f6753bd1df46b8db93821b220d39749e92f7ea55657500b7407d9`.
The inspected wheel had 42 members and source archive 123. Final documentation
is rebuilt and audited separately against the committed tree; final artifact
hashes remain in its external receipt and manifest.

The corrected hosted matrix must still pass before release. No application
logic or dependency versions were changed, and no new live-account acceptance
is claimed. The original hosted failure remains part of the evidence.
