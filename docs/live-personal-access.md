# Live personal access

Checked 3 October 2026. The opt-in Windows connector uses a disposable Firefox
session. Synthetic and imported modes retain their immutable data paths.
Actual MCP reads, study-right selection, pagination, repeated freshness and private
reference comparison passed. Signing out caused a retained cursor to fail with
`SESSION_EXPIRED`; see [verification](verification.md).

Dev3 adds `--mode live --browser chrome` for installed Google Chrome on Windows.
The default remains Firefox. Both choices use the same observed Peppi mechanism
below, fresh HAKA sign-in and owned temporary storage; there is no token exchange
or transport fallback. Chrome's `--user-data-dir` points inside the owned lease
and is never your everyday profile. See Google's
[ChromeOptions documentation](https://developer.chrome.com/docs/chromedriver/capabilities)
and the separate Chrome evidence in verification.md. Earlier Firefox findings
remain historical evidence and do not by themselves establish Chrome acceptance.

## Observed mechanism and production choice

The owner completed normal University of Lapland HAKA/MFA in a connector-owned
window. Public entry is https://opiskelija-lay.peppi4.lapit.csc.fi/. The observed
flow uses HAKA/Shibboleth/SAML discovery and the university identity provider.
No separate bearer token or Peppi token exchange was observed. Liferay `p_auth`
is not treated as an independent API credential; Sisu's `/ori/preauth` is not used.
The [reference projects](reference-mcps.md) informed lifecycle design only.

Production uses **browser-session JSON rights and rendered transcript records**:

| Operation | Observed method and route | Mapping and authentication |
|---|---|---|
| Fresh account verification | GET `/group/opiskelijan-tyopoyta-yo/suoritusote` | Fresh HTML must have one signed-in Liferay marker and one nonzero account ID |
| Available rights | POST `/delegate/studyentitlements?groupByCollection=true`, empty body | JSON collection and standalone entitlement arrays; IDs, selection and linked collection membership |
| Select own right | POST `/delegate/studyentitlements?selectedEntitlementId={id}`, empty body | ID must come from the current authenticated selector; changes selected UI context only |
| Completed achievements | Navigate transcript, select `Suoritettu`, read visible section | The observed filter performs a same-page portlet POST returning HTML; no suitable achievement JSON route was established |

These operations were observed in the isolated browser's network traffic and
verified in that context. Requests carried a Cookie header. Replaying the bounded
rights read with the same browser's same-origin fetch succeeded without copying
cookie values or adding a separate token. Cookie names/attributes were not
established: WebDriver's cookie listing was empty despite the observed header.
No credentials, response bodies, browser state, HARs or personal fixtures are
saved by the application. Discovery reports retain bounded redacted metadata only.

The selector schema is validated exactly: `entitlementCollections` groups contain
`name` and `entitlements`; top-level `entitlements` contains standalone rights.
Each right has `id`, `key`, `name`, `oldEntitlement`, and `selected`. Exactly one is
selected. Historic navigation and unexpected fields fail explicitly. Raw account
and right IDs remain internal; externally visible right IDs are session-scoped.
Student-code text is removed from labels. Display names never establish identity.

No supported third-party API contract or university automation guidance has been
established. The [university inquiry](university-inquiry.md) remains unsent and
independent of this implementation. The observed route is experimental and may
change with portal releases. There is one production mechanism; schema or auth
failures never trigger another transport or synthetic-data substitution.

## Browser/runtime decision

Playwright 1.63.0's managed Chromium and Firefox both failed before navigation
with Windows error 14001 and SideBySide assembly events. Their root cause is not
established. The owner selected isolated Firefox. Selenium 4.43.0 with installed
Firefox 157.0 and geckodriver 0.37.1 successfully launched a disposable private
profile and reached authenticated Peppi. `[live]` therefore installs Selenium;
Playwright and managed Chromium are not required or claimed compatible.

The installed Firefox executable is used with a new private profile, never the
owner's everyday profile. Password saving, disk cache and crash-session restore
are disabled. Geckodriver removes its temporary profile on clean shutdown; hard
process termination can leave temporary browser files, but the connector never
loads them on reconnect. No authentication state or profile is exported.

## Session and read boundaries

Server startup opens no browser. `connect_personal` creates one owned window and
returns `awaiting_login`; the owner completes HAKA/MFA and calls it again. A fresh
server response must verify the account before it returns `connected`. Repeated
connects reuse the same window. `disconnect_personal` discards session identity,
records and cursors and closes the owned worker/browser tree. A restart requires
a new session. Status reports the last verification time, not a current health check.

An async lock serializes personal operations. Synchronous WebDriver calls stay
in one worker process/thread; a Windows job object contains its child processes
and terminates only that tree during cleanup. Server shutdown shields cleanup
from cancellation. Authenticated operations have a 30-second deadline, with
bounded worker cleanup afterward. No automatic login loop or stale-data fallback
exists. Normal human sign-in redirects are allowed; authenticated fetch redirects
are rejected, and connector data fetches accept only the observed method/path pairs.

Fresh account checks bracket acquisition and study-right discovery. An account or
available-right change invalidates all records and cursors. The requested right
must belong to that verified account and match the normalized source section.
Auth loss, denial, browser closure, timeout and cancellation discard the connection.
Unexpected layouts return an error rather than an empty result.

## Completed transcript mapping and completeness

The collector disables the linked collection view, selects the requested right
and explicitly selects the completed filter. Timing restrictions are rejected.
Only visible rows in `#transcript-entitlement-{id}` are eligible. Hidden sections,
header/subtotal rows and expanded-but-unloaded content are not achievements.

The section summary must give an explicit completed record count and exact decimal
credit total. The collector waits for a stable, reconciled projection. Missing
rows or a mismatched sum fail; an empty result requires explicit zero count and
zero credits. The existing normalizer maps code, title, credits, grade, assessment
date and completion status. Unsupported annotations, graded module layouts or
unknown statuses fail rather than being stripped. Shared duplicate/module credit
rules remain in effect; ambiguous repeated completions withhold a total.

Acquisition time, transcript URL, source mode and completeness scope accompany
results. Achievement IDs are derived observation IDs; stable upstream IDs, grading
scales and replacement relationships are not established. Only completed-course
coverage is advertised; other status filters return `CAPABILITY_UNAVAILABLE`.

Each initial query acquires a fresh snapshot. Pagination retains up to eight
snapshots for five minutes in memory. Signed cursors bind connection, right,
filter, page size and snapshot. A continuation first verifies the session, then
returns its original acquisition time and cached provenance. Expiry, eviction,
disconnection and context changes invalidate continuation access.

## Verification limits

HOPS reading extends this same browser/session boundary with saved-version GET
render links. It requires explicit plan selection and retains uncertainty about
curriculum rules and agreements. See [HOPS and progress](study-plan-progress.md)
for the separate mapping and source completeness scope.

Fictional tests cover two account identities, multiple rights, hidden/incomplete
rows, count/credit mismatches, HTTP-200 login content, redirects, denial, account
changes, cursor scope/expiry/eviction, concurrency, timeout and cancellation.
Actual Firefox and Chrome fixtures test fresh HTTP responses and DOM visibility locally.
Real cross-account switching needs a second authorized account and remains
unverified. Natural expiry and real access denial are distinct from simulated
failures. Exact live-account results and final installation checks belong in
[verification.md](verification.md); no private transcript values belong here.
