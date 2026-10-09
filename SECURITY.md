# Security policy

## Private reporting channel

Use [GitHub private vulnerability reporting](https://github.com/dheikari/peppi-mcp/security/advisories/new)
for this repository. Reporting is enabled; the public report link, private form
and maintainer notification settings were checked on 9 October 2026. See the
[verification record](docs/security-reporting.md) for the scope of those checks.

Alternatively, open the repository's **Security and quality**
tab, select **Advisories**, and choose **Report a vulnerability**. If the button is
missing, private reporting is unavailable; do not publish sensitive details in an
issue, discussion or pull request. No fallback email address is configured.

## What to report

Report suspected security defects in Peppi MCP, including:

- Credentials, session data or personal records leaking through errors, logs or artifacts.
- Records returned after sign-out, disconnect or an account/context change.
- Cleanup removing unrelated files or processes, or reusing surviving authentication.
- Operations escaping the verified read-only boundary or acquiring unintended access.

Ordinary installation problems and feature requests belong in public issues
once the repository is available. Use fictional examples and remove personal
information from those reports too.

## Information to include

- Package version or source revision, operating system, browser and MCP client.
- A concise description of the issue and its possible impact.
- Minimal reproduction steps, preferably using fictional local fixtures.
- Expected and observed behavior, including fixed error codes or operation stages.
- Any relevant workaround and whether the issue is reproducible.

Do not send passwords, MFA codes, cookies, tokens, browser profiles, HAR files,
raw authenticated page source or unredacted study records. A private report is
not a reason to include credentials. If a report needs more evidence, agree on
a redacted or fictional reproduction with the maintainer first.

Keep testing local to the connector and fictional fixtures. This policy does
not authorize probing university infrastructure or accessing another person's
account. Problems in Peppi or HAKA itself should go through the institution's
own reporting process; this project cannot resolve upstream security defects.

## Maintained versions and response

Security fixes currently target the latest experimental candidate,
`0.1.0a1`. Older internal development candidates do not receive separate backports.
There is no stable release yet. The verified live scope is Windows and
University of Lapland, using the explicitly selected Firefox or Chrome browser.

Reports are handled on a best-effort basis; there is no guaranteed response or
fix deadline. The maintainer will assess the report privately, seek a safe
reproduction, and coordinate a fix and disclosure with the reporter. Public
advisories and regression fixtures must omit credentials and personal records.

Maintainer setup and the activation status are recorded in
[security reporting setup](docs/security-reporting.md).
