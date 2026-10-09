# Architecture and recorded decisions

Milestones 1–6, 3 October 2026. Keep four boundaries:

```text
bundled synthetic JSON -> SyntheticSource -> validated Snapshot
                                                |
                                  deterministic study services
                                                |
                              validated MCP handlers -> stdio client
```

1. **Source access:** `StudySource.snapshot()` is the small adapter interface.
   `SyntheticSource` reads an installed package resource, with no caller-provided
   path. `PublicFetcher` reads only observed catalogue routes; `PublicCatalogue`
   validates and normalizes public records and owns its cache. `ImportedSource`
   reads one explicitly selected private SQLite snapshot. A separate local CLI
   invokes the bounded PDF worker and verified layout parser before atomic storage.
   LivePersonal serializes async session operations; FirefoxProcess owns a bounded
   IPC worker, and LaplandBrowser reads the verified selector and visible transcript.
2. **Normalization:** frozen Pydantic records represent study rights,
   achievements, module-component links and provenance. Snapshot validation
   rejects unknown study contexts and mixed source modes within a context.
   The initial model intentionally does not pretend to represent enrolments or
   a complete curriculum. Separate public schemas describe observed course and
   offering fields without inventing personal-study semantics.
3. **Calculations:** pure services select a study right, paginate source rows and
   compute explainable totals. They make no I/O or LLM calls.
4. **MCP:** official SDK 2.3.0 low-level `Server`, with Pydantic-generated argument
   schemas and explicit strict validation before dispatch. This choice permits
   uniform machine-readable errors in `structuredContent` and `isError`, including
   bad arguments. The [SDK low-level guidance](https://py.sdk.modelcontextprotocol.io/advanced/low-level-server/)
   requires this layer to validate arguments itself. Transport framing stays
   with the SDK. Tests check the boundary through a separate client process.

## Data and calculation contract

- Each personal-data success labels synthetic, imported, live or cached mode.
  Provenance retains source ID, institution, study right, retrieval/import time,
  optional source update/issue time, checksum, document page/line, completeness
  and warnings. Imported timestamps do not imply a live retrieval.
- Credits are bounded finite `Decimal` values, transmitted as decimal strings.
  Original grade and grading-scale strings are preserved. The PDF adapter maps
  only verified grade/legend combinations to completion status; missing or
  unsupported source fields are not guessed.
- Exact duplicate source rows collapse by identifier; conflicting rows remain
  unresolved. Matching titles never establish equivalence.
- Failed, planned and incomplete records do not add completed credits.
- Unknown completion status withholds an overall total. Printed ungraded groups
  are separate source subtotals; mismatches with linked rows also withhold a total.
- A simple explicit replacement within the same credit group can supersede an
  earlier row. Missing targets, cycles/chains and conflicting mappings withhold
  the total. Repeatable courses need a future source-specific policy.
- An explicitly linked completed module is represented by its completed
  non-module components only when their sum reconciles. Missing coverage,
  nested modules or discrepancies remain unresolved. No module/component double
  counting is silently accepted.
- Repeated course IDs or credit groups without a unique replacement remain
  ambiguous, including transfers that overlap an existing achievement.
- `known_subtotal` is the sum of confidently countable rows. `total_credits` is
  null when source coverage is partial/unknown or a relationship is unresolved.
  An unresolved subtotal is not an overall degree total or guaranteed lower bound.
- Source-reported totals stay separate from calculations. When both are available,
  return their difference; a discrepancy warning does not invent its cause.
  Missing dates/grades remain null with warnings rather than being fabricated.
- No graduation or enrolment eligibility decisions are made.

These policies are tested on fiction. The supported PDF mapping was additionally
checked against a deliberately selected real document; [imports.md](imports.md)
defines the verified subset and unresolved semantics. Transfer/correction mapping
from this PDF format is not advertised as verified.

## Tool boundary

Four tools are advertised by default, all read-only, non-destructive, idempotent
and closed-world for the selected immutable snapshot. The opt-in adds three read-only public
tools with open-world annotations. Code enforces behavior; annotations are
only hints. Planned capabilities appear as unavailable in connection status and
are omitted from discovery. Known unavailable names return `CAPABILITY_UNAVAILABLE`
when called directly; unknown names return `UNKNOWN_TOOL`.

Arguments forbid additional fields and coercion: `"2"` and `true` are not valid
integer limits. Explicit study-right selection prevents silent combining.
Achievement pages contain at most 100 rows. Cursors bind an offset to the exact
snapshot and selected filters; changed snapshots, filters and malformed cursors
return `INVALID_CURSOR`. Cursors are opaque continuation tokens, not authorization
tokens. Study-right and tool definitions fit single bounded pages. Models cap
study rights at 100, achievements at 1,000 and printed groups at 200. Summary
responses contain at most one decision per unique achievement/group within those
bounds. No arbitrary file, SQL, script or URL operation is available through MCP.

| Code/state | Meaning in this milestone |
|---|---|
| `INVALID_ARGUMENT` | Missing/wrong/extra argument or out-of-range limit |
| `INVALID_CURSOR` | Continuation does not match source and filters |
| `CURSOR_EXPIRED` | Public snapshot expired or evicted; restart the query |
| `SOURCE_CHANGED` | Unexpected JSON, content type or schema; no rows silently skipped |
| `SOURCE_TOO_LARGE` | Response exceeds 2 MiB; refine the query |
| `SOURCE_TIMEOUT` / `SOURCE_UNAVAILABLE` | Read failed; no stale fallback |
| `SOURCE_ACCESS_DENIED` / `SOURCE_REDIRECT_BLOCKED` | No authentication or redirect attempted |
| `NOT_FOUND` | Public endpoint returned HTTP 404 |
| `RATE_LIMITED` | Honor `retry_after_seconds`; adapter also enforces the pause |
| `STUDY_RIGHT_NOT_FOUND` | Context not present in configured source |
| `CAPABILITY_UNAVAILABLE` | Proposed capability has no implementation |
| `UNKNOWN_TOOL` | Unknown tool name |
| `INTERNAL_ERROR` | Unexpected failure; raw records and exceptions withheld |
| Empty `items` with `ok=true` | Valid source query with zero matching records |
| `partial` / `unresolved` summary | Data exists, but no trustworthy overall total |

Authentication, expired sessions and access denial are not simulated as successful
empty results. An internal async session service now distinguishes sign-in needed,
session ended, access denied, context changed, browser failure and operation timeout.
Its backend contract requires fresh identity checks before and after acquisition,
and before returning a cached continuation. Production `--mode live` uses the
owned Firefox worker; [live-personal-access.md](live-personal-access.md) defines
the observed routes, lifecycle, process containment and source mapping. The MCP protocol itself retains its
standard JSON-RPC errors for malformed protocol messages.

## Recorded HOPS boundary

Live mode additionally advertises `get_study_plan` and `get_study_progress`.
Immutable modes stay unchanged. Version discovery precedes explicit selection;
opaque IDs bind the connection, study right and recorded source version. Typed
plan records preserve the tree, source credit ranges and unresolved relationships.
Progress compares unique exact course codes and brackets the transcript read with
matching HOPS projections. No plan records are cached between requests. See
[the acquisition and comparison contract](study-plan-progress.md).

The additive typed assessment precedes detailed records and separates source
consistency, transcript comparison and unverified curriculum rules. Fixed
explanations retain compared quantities and decimal differences. The bounded
personal scheduler, generation checks, strict worker IPC and disposable runtime
ownership are described in [hardening.md](hardening.md).

## Privacy and storage decisions

Explicit imports use a private immutable SQLite store outside repositories and
application directories, separated by profile and study context. Original PDFs
are not stored or changed. Source bytes/checksums, parser version and context
define snapshot identity; exact reimports retain the first timestamp. Newer
snapshots require explicit startup selection and never merge automatically.
See [retention and import limits](imports.md). No credentials, account discovery,
background schedule or LLM calls are needed. Public network access is opt-in.
Live browser sessions and personal pagination snapshots are ephemeral; no credential store is implemented.

Source text is data. It cannot select tools, paths, scripts or network hosts.
Keep responses minimal; never include passwords, cookies, identity documents or
unnecessary personal fields. Sending a result to a cloud client exposes that
selected data to its provider. Local execution does not change that flow.

Operational logging is stderr-only and avoids raw arguments and records. See
[MCP stdio guidance](https://modelcontextprotocol.io/docs/develop/build-server).
The [MCP security guidance](https://modelcontextprotocol.io/specification/draft/basic/security_best_practices)
is a reference for later authentication and deployment work; this server has no
HTTP listener, token forwarding or remote authorization surface.

## Public catalogue boundary

Only observed paths on `https://opinto-opas-lay.peppi4.lapit.csc.fi` are accepted.
Queries contain 3–80 letters/numbers/spaces/underscores/hyphens, escaped as a path
segment; course IDs contain 1–12 digits. No redirects, proxy environment settings,
cookies or credentials are used. TLS certificate verification stays enabled.

Reads are serialized with at least one second between request starts, no automatic
retries, an eight-second socket timeout and a 20-second deadline checked between
64 KiB reads. A blocking read can last until its socket timeout. Responses are
limited to 2 MiB; source lists to 1,000 rows and descriptive strings to 40,000
characters. HTTP 429/503 triggers a bounded `Retry-After` cooldown, defaulting to
60 seconds. The SDK event loop dispatches handlers through worker threads.

Validated responses occupy at most 32 in-memory cache entries for five minutes.
No disk cache or stale-on-error substitution exists. Public cursors are signed
and bound to the snapshot, query, date filters, collection and page size. They
cannot silently fetch a replacement snapshot and are not authorization tokens.

Public provenance includes source URL, retrieval/expiry times, mode and response
completeness. Ambiguous `createdAt` is not used as an update time. Search count
discrepancies mark a response partial; a matching count means complete only for
the received response. Offerings have unknown completeness because the endpoint
provides no total. An empty offerings list requires a successfully validated course.

Epoch milliseconds convert through `Europe/Helsinki` with pinned timezone data,
including DST. Inclusive overlap retains records with uncertain dates and marks
them unknown. `date_phase` is calculated as of the snapshot date; collection and
unknown cancellation status stay separate. Enrolment windows do not establish
eligibility or available places. Reservations and instructor lists are not
separately normalized. Multilingual source sections remain inert source strings.

## Claude client boundary

The two live HOPS tools advertise Anthropic's `maxResultSizeChars` metadata,
bounded at 500,000 characters, while synthetic/imported tools keep their existing
metadata. This changes the client's large-result handling, not arguments, record
fields, acquisition, authentication or the 30-second operation deadline. Clients
receive guidance to make personal reads sequentially. Claude Code can still save
oversized results to its own tool-result files; that storage is outside the
connector's memory-only cache and cleanup scope.

Instruction text distinguishes unavailable observations from absent source
figures: these tools do not acquire a GPA or verified degree-credit requirement.
Unmatched records remain unresolved matching unless the selected source version
explicitly establishes an allocation. Typed assessments and provenance remain
the evidence; model wording is not additional source data.

The later source review reproduced three cleanup edge cases, recorded in
[claude-review.md](claude-review.md). The corrected dev2 lifecycle retains
retired backends until process termination and profile removal are verified.
Service and backend cleanup tasks own their guards; cancellation of a joining
caller cannot release them. Cleanup shares an absolute deadline, and tracked
daemon filesystem work can outlast its ten-second wait without permitting a new
browser. Explicit disconnect retries retained leases; connect blocks until all
owned cleanup and startup recovery are verified. Markers survive partial removal.
Candidate verification, review and live acceptance are tracked separately.


A retained live lease also stores its original filesystem identity. It may retry
non-recursive removal of that same empty directory when final marker restoration
or initialization rollback failed. Replaced/nonempty directories are refused.
This in-memory proof is never reconstructed from a markerless path at startup.
Failure to start the daemon worker clears its unstarted future for explicit retry.

## Explicit browser selection (dev3)

`--mode live --browser chrome` selects installed Google Chrome; omitted selection
uses Firefox. The historical `FirefoxProcess` class now owns either worker tree
without changing its corrected cleanup implementation. The validated browser
choice is passed to the private worker; no browser is opened during server
startup and no failure switches browsers. Status exposes the configured
`personal_browser` without I/O.

ChromeDriver starts Chrome with a unique `chrome-profile` beneath the existing
owned runtime lease, incognito mode, a debugging pipe rather than a Chrome
debugging port, password saving disabled and logs suppressed. The profile cannot
be reused even after failed startup. The owning Windows job contains the worker,
driver and browser descendants. Stop/verify-before-delete, retained cleanup
leases, blocked reconnection and abandoned recovery apply to both browsers.
The same page adapter and observed read routes serve both engines.

Windows filesystem validation and removal use extended-length paths. This keeps
nested Chrome files beyond the legacy path limit visible to ownership and
reparse-point checks and to recursive removal. Public lease paths and markers
retain their ordinary form. Long-path handling neither authorizes a different
directory nor follows a junction. The existing cleanup deadline, retry count,
retained-resource registry and cancellation guards are unchanged.
