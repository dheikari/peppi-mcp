# Troubleshooting the live connector

| Result | What to do |
|---|---|
| `awaiting_login` | Complete HAKA/MFA in the connector's separate selected browser window, then call connect again. An everyday browser sign-in is separate. |
| `SIGN_IN_NEEDED` / `SESSION_EXPIRED` | Connect again, sign in and rediscover rights/plan IDs. Old cursors and IDs do not authorize a new connection. |
| `PERSONAL_BUSY` | Wait for the active call to complete before another personal read. Status and disconnect remain responsive; do not loop automatic retries. |
| `PERSONAL_READ_TIMEOUT` | The active read reached 30 seconds; its session is discarded. Reconnect before retrying. Queue waiting and cleanup have separate bounds. |
| `RATE_LIMITED` | Honor `retry_after_seconds`. No request is sent during the server's cooldown and no automatic retry occurs. |
| `PERSONAL_VIEW_INVALID` / `PERSONAL_VIEW_INCOMPLETE` | No trustworthy read was returned. Check the supported Finnish view and report the fixed code/stage; do not paste private page source, cookies or HAR files. |
| `PLAN_CHANGED` | The plan changed during comparison; begin a fresh selected-version query. |
| Partial HOPS assessment | Inspect source conflicts and each compared quantity. An arithmetic explanation does not establish agreement or degree completion. |
| `BROWSER_DEPENDENCY_MISSING` | Install the `[live]` extra for Windows, including Selenium and pywin32. |
| `BROWSER_UNAVAILABLE` | Check the explicitly selected browser: Firefox/geckodriver or Google Chrome/matching ChromeDriver. Allow Selenium Manager's separate driver download. No fallback or everyday profile is used. |
| `PERSONAL_CLEANUP_PENDING` | A bounded recovery attempt did not verify cleanup. Retry `disconnect_personal` explicitly before connecting; no replacement browser or saved authentication is used. |
| `cleanup_pending=true` | The session is discarded but cleanup remains unresolved. If status says `closing`, wait for tracked filesystem work; otherwise retry disconnect. A later startup recovers only proven abandoned owned directories. Do not broadly delete Firefox profiles or temporary folders. |

The robot and striped Firefox address bar identify an automated browser. They
are expected in the connector-owned window. No academic-record write tool is
available. Publication, university correspondence and independent review remain
separate from local troubleshooting.

For a suspected security defect, follow [the private reporting policy](../SECURITY.md).
Ordinary public troubleshooting reports should contain fixed error codes and
fictional reproductions, never credentials, profiles or personal study records.

## Claude client checks

See [claude-setup.md](claude-setup.md) for separate Code and Desktop configuration.
The installed live server annotates both HOPS tools to accommodate Claude Code's
large text-result threshold. An older build can return `TOOL_RESULT_TOO_LARGE` in
the persistence-free acceptance client. Verify the installed build rather than
raising unrelated global limits or omitting plan records.

Wait for each personal-browser tool response before starting another read.
Overlapping calls can return `PERSONAL_BUSY` after the five-second queue wait.
Leave the isolated browser window on the connector-controlled page during reads;
closing it or changing its context can interrupt acquisition. Complete HAKA/MFA
personally only when the server is awaiting sign-in.

`SOURCE_UNAVAILABLE` means a source request failed or returned an unexpected HTTP
status; no cached result is substituted. `BROWSER_UNAVAILABLE` discards the
session. Report the observed code and browser behavior before diagnosing a
client incompatibility. Do not loop retries or automatically reconnect. Status
is historical and cannot prove the current authentication state.

A live dev2 transcript read has returned `PERSONAL_VIEW_INCOMPLETE` between
successful passes. It returned no records and preserved the usable session;
a later explicitly requested fresh pass succeeded. That observation does not
establish its underlying cause. Keep the fixed error code and acquisition stage
when reporting such failures. An assistant must not substitute an earlier result
or run a retry loop to make an incomplete view look successful.

The ten-second cleanup budget bounds the wait, separately from the active read
deadline. A Windows filesystem call can continue on its tracked daemon worker;
status remains responsive and reconnect remains blocked until it finishes. A
failed removal retains its exact owned lease and preserves its marker when
possible. Only a retained live lease can retry its same verified empty filesystem
directory if its marker is missing; startup will not infer ownership from emptiness. Cancelled cleanup callers do not reset that budget or release its guard.

If filesystem work never returns, stop that connector server and start it again;
the daemon does not prevent exit, and the next start attempts abandoned-profile
recovery. A directory with a missing or invalid ownership marker, or an unknown
entry in the dedicated runtime root, is deliberately preserved and blocks live
connection. Inspect its origin and permissions yourself. Only an owner-confirmed
disposable entry may be moved out of that root; automated cleanup never guesses
ownership or removes another live connector's directory.
