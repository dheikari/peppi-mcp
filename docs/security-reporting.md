# Security reporting setup

## Current status — 8 October 2026

The owner selected GitHub private vulnerability reporting. [SECURITY.md](../SECURITY.md)
defines the channel, maintained candidate, safe report contents and best-effort
response policy. No public email address is needed for this choice.

The repository has no configured GitHub remote. Private reporting, report-form
availability and maintainer notifications have **not** been enabled or verified.
The contact decision is complete; channel activation remains pending.

## Activation checklist

When the GitHub repository is created under separate publication authorization:

1. Confirm its owner and URL; add the verified repository/reporting link to
   `SECURITY.md`. GitHub private vulnerability reporting is available for public
   repositories.
2. In repository **Settings**, open **Advanced Security** under **Security and
   quality** and enable **Private vulnerability reporting**.
3. Configure the maintainer's repository watch settings for **Security alerts**
   or **All Activity**. Check account notification preferences so reports reach
   a channel the maintainer actually monitors.
4. Verify the repository's **Security and quality → Advisories** page shows
   **Report a vulnerability**, and that the private reporting form opens. An
   account without repository administration privileges should also check form
   availability. Opening the form does not require submitting a report.
5. Record the date, repository URL and checks actually completed here. Remove
   the local-only notice from `SECURITY.md` only after activation is verified.
   Finish these checks before announcing the release or uploading a package.

Use GitHub's current instructions for
[enabling private reporting and notifications](https://docs.github.com/en/code-security/how-tos/report-and-fix-vulnerabilities/configure-vulnerability-reporting/configure-for-a-repository).
GitHub recognizes a root `SECURITY.md` as a
[repository security policy](https://docs.github.com/en/code-security/how-tos/report-and-fix-vulnerabilities/configure-vulnerability-reporting/add-security-policy).

## Handling reports

Keep discussion and reproductions private until disclosure is agreed. Assess
impact and affected versions, reproduce with fictional data, add meaningful
regressions, and verify the fix through the relevant browser/MCP boundary.
Ask for a sanitized reproduction instead of collecting a reporter's credentials
or private university records. Track unresolved findings explicitly.

Coordinate the release and public advisory with the reporter. Public summaries,
test fixtures and artifacts must contain no private records or authentication
material. A dependency advisory needs its own assessment; MIT licensing and
passing tests do not resolve it automatically.
