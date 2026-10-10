# Moodle and Sisu MCP design references

The reviewed README and authentication implementations do not document explicit
vendor or university approval for either MCP. Moodle's documented web-service
framework and a working user login are technical access evidence, not endorsement
of the repository. Sisu's comment about verification at TUNI describes testing,
not an approval statement. Absence of such a statement does not prove that the
author lacks permission or that a separate approval letter is required.

| Reference | Inspected revision | Most relevant source |
|---|---|---|
| [ink-waffle/moodle-mcp](https://github.com/ink-waffle/moodle-mcp) | `719538eccd866bedbe2419879214d83a955474e4` | `auth.ts`, `ws.ts`, `browser.ts`, `config.ts`, `tools/site.ts`, `tools/raw.ts` |
| [ink-waffle/sisu-mcp](https://github.com/ink-waffle/sisu-mcp) | `c20eccd2f264b2a63fb28c3ce36d22a33fcc29ac` | `auth.ts`, `api.ts`, `browser.ts`, `config.ts`, `tools/site.ts`, `tools/raw.ts` |

## What their code actually does

[Moodle authentication](https://github.com/ink-waffle/moodle-mcp/blob/719538eccd866bedbe2419879214d83a955474e4/src/auth.ts)
first checks the site's mobile web-service configuration. It can exchange a
password for a token or use an interactive browser session and Moodle's mobile
launch mechanism. Browser login can return a waiting result and resume when the
client calls connect again. The [connection implementation](https://github.com/ink-waffle/moodle-mcp/blob/719538eccd866bedbe2419879214d83a955474e4/src/tools/site.ts)
queries available web-service functions and reports missing capabilities. The
repository also implements submissions and other writes; those are outside this
Peppi project's read-only scope.

[Sisu authentication](https://github.com/ink-waffle/sisu-mcp/blob/c20eccd2f264b2a63fb28c3ce36d22a33fcc29ac/src/auth.ts)
selects Shibboleth service-session cookies from its configured browser, exchanges
them at `/ori/preauth`, and keeps the resulting short-lived JWT in memory. Its
comments identify TUNI as the verified deployment. [Connection management](https://github.com/ink-waffle/sisu-mcp/blob/c20eccd2f264b2a63fb28c3ce36d22a33fcc29ac/src/tools/site.ts)
reuses a login tab and separates connect, status and disconnect. The
[API client](https://github.com/ink-waffle/sisu-mcp/blob/c20eccd2f264b2a63fb28c3ce36d22a33fcc29ac/src/api.ts)
uses Sisu's service families and can renew a rejected JWT once. None of these
Sisu endpoints, schemas or token lifetimes has been established for Peppi.

Both use `@ink-waffle/study-browser` to manage or attach to a browser. Their config
modules persist tokens/cookies in local JSON files. The repositories' package
metadata declares MIT; no root LICENSE file was listed in the inspected trees.
Any future code reuse needs a separate attribution/license review. This comparison
adopts design ideas only. Peppi MCP's own code is licensed under [MIT](../LICENSE);
that grant does not cover third-party code.

## Decisions for Peppi milestone 4

| Pattern | Peppi decision |
|---|---|
| Check capabilities before claiming a connection | Implemented readiness reporting distinguishes an unverified route from missing sign-in; advertise only verified tools |
| Human finishes browser login; connect resumes | Use this interaction if the verified Peppi route needs a browser. Return a bounded waiting state and reuse only the connector-owned login tab |
| Distinct connect/status/disconnect | Plan explicit lifecycle operations after a real adapter exists. Local disconnect must state whether it clears local credentials/cache or also revokes a server session |
| Source-specific token exchange | Discover the actual Peppi method; never try Moodle or Sisu endpoint names on Peppi |
| Scoped credentials | Use the minimum necessary service credential/session and an appropriate Windows credential store if persistence is needed; do not copy the JSON-secret storage pattern |
| Renewable access | Refresh only through a verified supported mechanism. Expiry requires a clear sign-in-needed result; no repeated login or silent authentication fallback |
| Browser profile reuse | Keep Peppi access deliberately scoped; no scanning the user's everyday browser or importing a shared multi-service profile by default |
| Caches and account selection | Bind to authenticated account, institution and study right; invalidate/separate on account change. Hostname alone is not account identity |
| Raw API convenience tools | Keep named, schema-checked operations with allowlisted destinations. GET alone or a function-name pattern does not prove a request is read-only |
| Dynamic personal reads | Future live tools must read through a session-aware adapter rather than retain the startup snapshot forever |

The observed Peppi HAKA/SAML entry makes the Sisu browser-assisted design relevant.
It does not prove a Peppi token exchange, private API or suitable automation
conditions. [The live-access evidence and acceptance audit](live-personal-access.md)
remain authoritative for what still needs verification. A university reply is one
way to resolve the gap; relevant installation documentation and verified access
conditions may also establish a route. The reference repositories alone do not.
