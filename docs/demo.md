# Fictional terminal demo

This example demonstrates **MCP → server → fictional source**, with no university
account, browser, recording or AI-provider account. It does not demonstrate HOPS
or university authentication. Live access is a separate opt-in flow requiring
your own HAKA/MFA sign-in in an isolated browser.

## Walkthrough

After the repository is published, use Git, Windows PowerShell and CPython 3.12:

```powershell
git clone --branch v0.1.0a1 --depth 1 https://github.com/dheikari/peppi-mcp.git
cd peppi-mcp
python --version
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.lock
.\.venv\Scripts\python.exe -m pip install --no-build-isolation --no-deps .
.\.venv\Scripts\python.exe -c "import peppi_mcp; print(peppi_mcp.__version__)"
.\.venv\Scripts\python.exe -m peppi_mcp.demo
```

The version command should print `0.1.0a1`. Installation downloads pinned
dependencies; the default demo itself makes no network requests. Use a full
Python 3.12 executable path for the first two Python commands if necessary.
No environment activation is required. A downloaded alpha source archive can
replace the clone step; run the remaining commands in its extracted directory.

## Captured output

Captured on 9 October 2026 from a clean installed `0.1.0a1` source package
outside the checkout, using the pinned dependencies. Every record is fictional.

```json
{
  "transport": "stdio subprocess",
  "server": "peppi-mcp",
  "protocol_version": "2026-07-28",
  "tools": [
    "get_connection_status",
    "list_study_rights",
    "list_achievements",
    "get_credit_summary"
  ],
  "mode": "synthetic",
  "demo_main_credits": "15.5",
  "ambiguous_total": null,
  "invalid_input": "INVALID_ARGUMENT",
  "unsupported_capability": "CAPABILITY_UNAVAILABLE",
  "client_shutdown": "completed"
}
```

The client discovers four tools, checks a **15.5-credit** fictional total and
leaves an ambiguous total unresolved (`null`). `INVALID_ARGUMENT` and
`CAPABILITY_UNAVAILABLE` are expected successful checks of error handling.
`client_shutdown: completed` means the client closed the stdio server cleanly.
Protocol negotiation may differ with a future SDK; this candidate pins its SDK.

## Short project description

Peppi MCP is an experimental, MIT-licensed connector that lets an MCP assistant
read study records through an isolated browser and the student's own sign-in.
Its Lapland implementation preserves conflicting source totals and unresolved
course matching rather than inventing graduation requirements. A credential-free
terminal demo exercises the real MCP transport using fictional data.

This description is prepared for an application or LinkedIn post; no post has
been sent. See [the README](../README.md) for supported scope and privacy limits.
