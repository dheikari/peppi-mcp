# Claude review of the local candidate

Reviewed 4 October 2026, at the owner's request. Claude Code 2.1.288 used
`claude-sonnet-5-5`; both initialization and model-usage metadata confirmed the
requested model. No model substitution was used.

The reviewer received an audited copy of the `0.1.0.dev1` source distribution,
including implementation, fictional tests, documentation and CI. Read, Glob and
Grep were its only enabled tools. It could not execute commands, edit the
candidate, access live MCP tools or read outside the review directory. Private
records, credentials, browser profiles and diagnostic harnesses were excluded.
The source fingerprint matched the Milestone 6 candidate:

```
185a65e073467ab85a5f3fd5609a0c656e8ccd756bbb75761ddeca69fb4cacb9
```

This is a separate AI code review followed by implementer triage. It is not a
human security audit, certification, or proof of the absence of vulnerabilities.
The original report and private verification driver remain in ignored storage.

## Findings reproduced in dev1

Three credential-free local reproductions used fictional browser objects and
owned test directories. All three demonstrated the suspect behavior in the
unchanged candidate. Passing these reproductions means the defects were
observed; it does not mean they were fixed or added to the regression baseline.

| Finding | Reproduction and impact | Relevant implementation |
|---|---|---|
| Pending profile cleanup is forgotten on reconnect | Simulated removal failure left an owned directory behind. A subsequent connection reported `cleanup_pending=false` while that directory still existed. Recovery preserves a directory whose owner process remains alive. | `services/live.py` cleanup/connect assignments; `adapters/firefox_process.py` removal failure; `runtime_storage.py` live-owner recovery |
| Concurrent close can report a false cleanup failure | Two close calls overlapped a transient removal failure. One removed the directory, while the other lost the shared lease reference and ultimately reported pending cleanup. | `adapters/firefox_process.py:close` |
| Cancelling a cleanup waiter releases the cleanup guard early | Native asyncio cancellation cleared `_cleanup_task` while cleanup still ran. A new connection opened, then the old cleanup failure overwrote its status. | `services/live.py:close` |

## Dev2 correction and verification

The three corrected-behavior regressions were run before implementation; all
three failed against the unchanged dev1 source, confirming each reported defect.
They now pass in `tests/unit/test_cleanup_regressions.py`.

Dev2 shares cleanup tasks across callers, retains retired backends/leases on
failure, and leaves task guards owned by their completion callbacks. Generation
checks protect state publication. Reconnect is blocked while cleanup runs; after
a completed failure it attempts one explicit bounded recovery and otherwise
returns `PERSONAL_CLEANUP_PENDING`. Profiles are removed only after owned process
termination is verified. Removal keeps its ownership marker through partial
failure, and slow filesystem work remains tracked on a daemon worker.

Targeted tests also passed for real Windows file locks, cancellation during
partial startup, uncertain job termination, cleanup deadline expiry, late daemon
completion, stale cursors and recovery through actual browser/stdio boundaries.
The first corrected candidate passed 343 tests and all three clean installations.
Sonnet 5.5 then re-reviewed its audited source in 164.5 seconds using only Read,
Glob and Grep; initialization and final usage metadata confirmed the exact model.
It judged all three original findings corrected. The reviewed source fingerprint
was `d047073ccd7259b51c70164e26a9e9e3f446a8955ee24c6e37f98c66cbcaa314`.

Two follow-up lifecycle cases were reproduced locally: shutdown cancellation
could be swallowed and begin a hung recovery await; failed marker creation could
leave an untracked new directory. Corrections propagate cleanup-task cancellation
and roll back only newly created empty initialization directories; unsuccessful
rollback carries its lease into the retained cleanup registry. Regressions passed
for these corrections; the full rerun and follow-up reviews are recorded below.

A permanently hung filesystem operation intentionally blocks reconnect until
verified cleanup or server restart. A fictional never-returning daemon worker
already has a process-exit/recovery test; the reviewer overlooked that coverage.
Unknown/invalid ownership remains fail-closed: automated recovery will not delete
it. Persistent failures require owner inspection, now explained in troubleshooting.
Returning SIGN_IN_NEEDED for a disconnected active read is the established MCP
contract, separately from cancellation of its caller. Other low-priority static
observations are follow-ups, not reproduced disclosure or deletion failures.

Corrected-candidate SDK, fresh Codex, fresh Claude Code and owner-assisted fresh
Desktop lifecycle acceptance passed. Historical dev1 normal-path checks were
preserved separately and did not substitute for corrected-candidate checks.

## Findings needing context or further evidence

- Read-only academic access includes observed presentation-state selection:
  selecting a study right and the completed filter can issue POST requests.
  The mechanism table already documents these operations. The route allowlist
  applies to explicit connector fetches; page navigation and page JavaScript are
  additional surfaces. The review did not establish an academic-record mutation.
  Whether the selected-right preference persists beyond this session remains
  unverified. Explain the presentation-state scope plainly in release guidance.
- The 30-second progress deadline has limited measured margin. The review's
  statement that no timing evidence existed was incorrect: Milestone 6 recorded
  21.81–28.06 seconds and the fresh Codex call took 23.77 seconds. Preserve the
  agreed authentication checks, request spacing and timeout contract while
  investigating safe ways to reduce acquisition cost. Do not adopt suggestions
  to weaken context verification or retain an interrupted browser operation.
- The local Selenium control endpoints, inherited Windows directory permissions,
  unnecessary BiDi configuration, large-tree calculation cost and cosmetic
  label changes merit focused follow-up. They were not reproduced security
  failures in this review.
- Version pins are not hash locks. Action tags, browser provisioning and Selenium
  Manager downloads require their stated supply-chain limits. Hosted CI remains
  unverified. The generated metadata the reviewer noticed came from the extracted
  source distribution used for review, rather than an unexpected repository file.
- Several proposed missing tests already have related coverage, including
  concurrent lease ownership and real junction protection. Match every proposed
  test to the actual gap before expanding the suite.

## Scope of the conclusions

The reviewer found no cross-account disclosure path or arbitrary deletion in its
static inspection. That observation is bounded by what it inspected and is not a
guarantee. Real second-account switching, natural expiry, hosted CI and broader
platform/institution support remain unverified.

Claude client acceptance is a separate runtime check. Its result belongs in
[verification.md](verification.md) and [compatibility.md](compatibility.md); the
source-only reviewer did not perform that check. License selection, security
contact and publication authorization remain owner decisions.


The second Sonnet re-review (301.8 seconds; 12 Read, 2 Glob, 4 Grep; exact Sonnet
5.5 confirmed) found two further recovery cases, reproduced before correction:
retained initialization leases could not recover their own empty directory after
rollback failure, and failure to start the daemon thread left an unresolved future.
Dev2 now retries only the original in-memory lease's filesystem identity, using
non-recursive removal and refusing nonempty/replaced directories. Thread-start
failure clears the unstarted job and returns a fixed safe error.

The suggestion to sweep markerless empty directories at startup was not adopted:
the agreed boundary requires verified ownership and protects unrelated directories.
Startup still preserves those entries; owner inspection is required. Tests cover
that refusal explicitly. The full candidate run and focused follow-up review
verified these last corrections before live acceptance.


The final focused Sonnet 5.5 source pass (44.5 seconds; 2 Read, 3 Grep) found no
concrete remaining correctness defect in the reproduced fixes. The independent
final run passed 352 required-Firefox tests, three clean installations and
artifact/privacy inspection. The original three confirmed findings and reproduced
follow-up cases are closed by these regressions, subject to planned final live
acceptance. Optional hypotheses remain bounded observations, not new safety claims.
See verification.md for the final fingerprint and remaining release gates.

The final audit then added four real stdio startup interruption cases. Sonnet's
source-only coverage pass (40.2 seconds; 3 Read, 4 Grep; exact 5.5 model confirmed)
found no concrete correctness defect in them. It identified direct process-exit
and graceful-EOF coverage gaps, which were strengthened with query-only OS process
handles and assertions before fixture release. Fresh-server recovery now also
asserts no source requests, and the local fixture confirms handler completion.
The focused transport run passed all six cases; final release verification is
recorded separately. These are test changes, not another production cleanup fix.

The follow-up source review (34.5 seconds; 3 Read, 1 Grep; exact Sonnet 5.5
confirmed) found those explicit coverage gaps closed and no concrete defect in
the changed assertions. The final frozen run passed 356 required-Firefox tests,
artifact/privacy inspection and three clean installations. The reviewer read
the changed tests, not the production cleanup bodies again, and executed nothing.
Optional timing/process-race and diagnostic hypotheses have no reproduction and
remain follow-ups. Final SDK, fresh Codex/Code and owner-assisted Desktop
lifecycle acceptance passed; the exact scope and observed failed attempts are
in verification.md. The original three findings and reproduced follow-up cases
are closed. [Private security-reporting activation](security-reporting.md),
independent human review and publication remain separate gates. The owner
selected MIT and GitHub private reporting on 8 October 2026; the dated review
evidence above is unchanged.
