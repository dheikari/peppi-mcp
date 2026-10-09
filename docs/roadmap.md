# Roadmap after the first investigation

Work in reviewable milestones. This is separate from Vire and My Dashboard;
never change their files, processes, databases, schedules or permissions.

| Phase | Current status | Next work and exit condition |
|---|---|---|
| 0: Feasibility | Initial bounded investigation complete; unresolved access dependencies documented | Obtain public API conditions and personal-access clarification; inspect a deliberately supplied export |
| 1: Synthetic MCP | Implemented and locally verified | Maintain strict schemas, conservative summaries and real stdio regressions |
| 2: Public catalogue | Experimental opt-in adapter implemented and verified through real MCP | No supported API/usage contract; upstream completeness and cancellation status remain explicit unknowns |
| 3: Imported records | Finnish PDF parser, local CLI and imported MCP verified against a deliberately supplied redacted source | One layout only; unverified transfer/correction markers and other layouts fail explicitly |
| 4: Live personal access | Experimental Windows connector implemented and verified through actual MCP | Maintain observed session/DOM contracts; real second-account switching and natural expiry remain unverified; see live-personal-access.md |
| 5: Study plan/progress | Experimental recorded HOPS reader and conservative comparison implemented; all three versions verified through installed MCP | Preserve explicit selection and source discrepancies; agreement/elective/equivalence rules and degree eligibility remain unresolved; see study-plan-progress.md |
| 6: Read-only hardening | Local dev2 candidate verified: 356 tests, three clean installations, artifact inspection, scoped Sonnet re-review, live SDK and fresh Codex/Claude lifecycle acceptance passed | Maintain the reproduced cleanup regressions and documented compatibility/failure limits; see claude-review.md |
| 7: Public release | Local `0.1.0a1` preparation: 440 required Firefox/Chrome tests, three clean installations, privacy/package inspection and fictional demo passed; MIT selected; no publication | Obtain publication authorization, activate reporting and pass hosted CI; independent human review remains unavailable/unverified |
| 8: Optional extensions | Deferred | Additional institutions/platforms, verified calendars, mutations or remote hosting each need separate design/testing |

## Completed public course milestone

The server now searches public courses, reads details and lists current/past
offerings with local pagination and date filters. Browser comparison confirmed
a course's title/credits/descriptions and a historical offering's dates and
enrolment window. Real public data now passes through MCP, satisfying the broader
**initial prototype** criterion. The public adapter remains experimental.

No supported third-party API contract or quota was found; absence of a contract
is not a blanket permission claim. Search reported 259 matches while returning
224 records, so upstream pagination/completeness cannot be assumed. The adapter
exposes counts and uncertainty, uses bounded modest requests, and stops on access
denial or redirects. Cancellation status remains unknown. See the access and
verification reports for the exact scope.

## Completed import scope and next concrete milestone

A deliberately supplied redacted transcript now imports locally and answers
achievement/credit queries through MCP. Source fields and printed subtotals were
compared with the document. [Import instructions](imports.md) define the supported
layout, provenance, safe failures and immutable snapshot policy.

The completed live personal scope is study rights, completed achievements and credit summaries. The owner selected a browser-assisted
fallback while the [university inquiry](university-inquiry.md) remains a separate,
unsent activity. Investigate Peppi's own session/read mechanism; do not assume it
shares Sisu's API-token exchange. A missing reply is not itself a stop condition.
Document actual access restrictions, support limits and maintenance requirements.

## Personal-access dependencies

Additional import variants require deliberately selected examples outside this
repository. Preserve originals privately and verify text/layout before adding
support. Fictional tests cover ambiguity, failed/unknown rows, module coverage,
reimport, newer snapshot selection, missing fields and malformed input. Unverified
corrections/transfers fail or remain unresolved; they are not inferred.

For live access, identify a supported destination and authentication conditions.
The user completes HAKA/MFA in the legitimate flow. Never ask for passwords or
cookies in chat, distribute shared credentials, bypass access restrictions, retry
login repeatedly or silently change authentication methods. Separate/clear caches
on account changes. Verify signed-out, expired and denied states, pagination,
interruptions and agreement with the owner's Peppi view. Imports alone do not
complete this objective.

For progress, require a selected recorded plan or curriculum version. Cover
elective groups, substitutions, transfers, modules, alternative routes, unmapped
achievements and conflicting information. A transcript alone is not a degree audit.

The recorded-HOPS milestone now exposes saved versions, a selected rendered tree,
and a fresh transcript comparison through two live tools. Real packaged MCP checks
covered both study rights and all three recorded versions. One approved view has
conflicting source totals and is explicitly partial; agreements and curriculum
choice rules remain unresolved. This completes the bounded read-only milestone,
not a degree-eligibility engine. See [HOPS scope](study-plan-progress.md).

## Release and later actions

Keep CI synthetic and credential-free. Before release, inspect source, Git
history, wheels, source archives, metadata and extracted contents. Test documented
commands from a clean copy. [Contribution guidance](../CONTRIBUTING.md),
[changelog](../CHANGELOG.md), dependency/license inventory and troubleshooting
accompany the [alpha preparation](release-alpha.md). The owner selected GitHub private
vulnerability reporting; its [activation and notification checks](security-reporting.md)
remain pending until a GitHub repository exists.
The owner selected MIT for project code. The owner chooses the reviewer and separately authorizes
publication to GitHub, package/registry upload or external provider review calls.
Local tests are not independent review.

No enrolment, withdrawal or plan edits are in scope. Future mutations require an
exact preview, explicit supported confirmation, fresh preflight data, duplicate
prevention, verified outcome and recovery from an unknown outcome without blind
resubmission. Do not use real enrolments as disposable tests. Remote hosting
requires its own authentication, authorization and deployment design.

At each milestone report: what works, the evidence actually checked, limitations,
the next concrete step and any owner decision/access needed. Do not mark the
live personal integration or public release complete based on this synthetic work.
