# Claude client setup and acceptance

Claude Code and Claude Desktop chat are distinct local stdio consumers. A test
of one does not establish the other. The browser connector runs on this Windows
computer and still requires owner-completed HAKA/MFA for every server session.

The local stdio connector is not a hosted connector for claude.ai or mobile.
No remote bridge, shared session, or authentication export is provided.

Dev3 can launch Google Chrome with `--mode live --browser chrome`. Append
`"--browser", "chrome"` to the selected installed environment's MCP arguments.
That environment must contain dev3 or later; the earlier accepted dev2 package
supports Firefox only. Client checks recorded below remain evidence for their
specific version/browser combinations, not automatic Chrome chat acceptance.

## Claude Code

Install the package with its optional live extra into a Python 3.12 environment
using the [normal setup instructions](../README.md). Register the environment's
Python executable from the directory where the server should be available:

```powershell
claude mcp add --transport stdio --scope local peppi -- 'C:\path\to\venv\Scripts\python.exe' -m peppi_mcp --mode live
```

Inspect `/mcp` in a new Claude Code session. Choose the desired model explicitly;
the candidate acceptance uses `claude-sonnet-5-5` (Sonnet 5.5).

The server advertises `anthropic/maxResultSizeChars=500000` for the two HOPS tools.
This is Anthropic's documented maximum for keeping a necessary large text result
inline in Claude Code. It preserves the tool arguments and result fields. Other
tools retain their default limits. A larger plan may still exceed the client
ceiling; the annotation is not an unlimited-output guarantee.

Without that annotation, the original candidate's selected HOPS response failed
with `TOOL_RESULT_TOO_LARGE` in the persistence-free Claude Code acceptance
session. Normal Claude Code sessions can save oversized results to a local
tool-result file. This client behavior is separate from the server's memory-only
live snapshots. See Anthropic's [MCP output limits](https://code.claude.com/docs/en/mcp#mcp-output-limits-and-warnings)
and [per-tool annotation](https://code.claude.com/docs/en/mcp#raise-the-limit-for-a-specific-tool).

## Claude Desktop chat

Open Desktop's Developer settings and edit its local MCP configuration. Preserve
existing server entries and preferences. Add an entry using the installed Python
environment, for example:

```json
{
  "mcpServers": {
    "peppi": {
      "command": "C:\\path\\to\\venv\\Scripts\\python.exe",
      "args": ["-m", "peppi_mcp", "--mode", "live"],
      "env": {"PYTHONUTF8": "1"}
    }
  }
}
```

Fully quit and reopen Desktop so it reloads the server. Confirm the server and
tools in Developer settings or the chat's connector picker. A Windows Store
installation can use its package's redirected Roaming directory; use the config
opened by the installed app rather than assuming the conventional path.
Anthropic describes [local Desktop MCP](https://support.claude.com/en/articles/10949351-getting-started-with-local-mcp-servers-on-claude-desktop)
separately from [remote connectors](https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp).

The Code-specific output annotation does not establish Desktop's output limits.
Verify actual selected HOPS responses in Desktop before claiming support.

## Acceptance sequence

Use personal-browser calls sequentially. Wait for each response before another
call; overlapping calls can correctly return `PERSONAL_BUSY` after the bounded
queue wait. The server does not perform automatic read or login retries.

1. Ask to connect and list study rights using Peppi. Complete sign-in personally
   in the connector's isolated Firefox window and then confirm to the assistant.
2. Read completed achievements and credit summaries for each selected right.
   Follow all pagination cursors, retain acquisition times, and repeat an initial
   query to check freshness.
3. Discover recorded HOPS versions and explicitly select each version before a
   plan or progress comparison. Ask about conflicting totals, remaining credits,
   and any source GPA. Preserve partial status and unverified degree rules.
   These tools do not acquire GPA or verified degree-credit requirements. Say
   the connector did not provide them; do not claim that Peppi lacks them.
   Unmatched records establish unresolved matching, not absence from HOPS.
   Require explicit evidence in the selected version for outside-plan allocation.
4. Sign out in the connector window and confirm that new reads and a retained
   cursor are refused. Disconnect and inspect the historical status for idle,
   empty queue and cleanup outcome.
   Acquire the retained cursor immediately before sign-out, rather than before
   a long HOPS sequence: snapshots expire after five minutes. Keep cursor values
   in the client context instead of printing them in the answer.

MCP records received by either Claude client are available to Anthropic for
processing under the account's applicable policies. The connector keeps HAKA
passwords and session cookies inside the owned browser. It cannot control the
client's retention, conversation history, or training settings.

Runtime results and current support claims are in [verification.md](verification.md)
and [compatibility.md](compatibility.md). The separate [source review](claude-review.md)
identified cleanup defects in dev1. Dev2 includes corrections and requires its
own verification and focused client acceptance before release readiness.
