# Alpha release preparation

Target: `dheikari/peppi-mcp`, MIT, experimental GitHub prerelease `0.1.0a1`,
tag `v0.1.0a1`. No PyPI upload or new academic capabilities are included.
Local preparation comes before the owner's authorization to publish.

## Intended release notes

First experimental Peppi MCP prerelease: read-only study rights, completed
achievements, credit reconciliation, saved HOPS versions and conservative
progress comparison for the Finnish University of Lapland student views.
Windows/Python 3.12, isolated Firefox by default, explicit Chrome support.
Includes fictional/imported modes and an opt-in experimental public catalogue.

Sign in yourself for each server run. Source conflicts remain partial results;
unresolved matching does not establish outside-plan status. The connector does
not acquire GPA or verified graduation requirements and cannot decide eligibility.
Clients/providers may retain returned study records. See [privacy](../README.md#privacy-cleanup-and-failures),
[the changelog](../CHANGELOG.md) and [the fictional demo](demo.md).

Natural expiry, real second-account switching, Chrome in fresh assistant chats
and independent human review remain unverified. Previous live acceptance is
version-scoped; the alpha changes version/release evidence, not academic behavior.

## Publication sequence

1. Finish required local Firefox/Chrome checks, privacy inspection, three clean
   installations, advisory/license review and installed demo/documentation checks.
2. Inspect the exact staged tree; commit with the verified owner's GitHub-provided
   no-reply email configured in this repository only. Review revision, files,
   notes and final artifact hashes with the owner before publication authorization.
3. After authorization, inspect any existing target repository before creating or
   pushing. Never overwrite unrelated contents or force-push.
4. Activate and verify [private vulnerability reporting and monitored notifications](security-reporting.md).
   Pending notices remain until that check succeeds.
5. Require the final commit's hosted Windows CI to pass both browsers. The workflow
   uses read-only permissions and official actions pinned to verified full commits.
6. Create a draft experimental prerelease with only the audited wheel, source
   archive and SHA-256 manifest. Download and verify assets before publishing.
   Commit changes require affected checks and artifacts to be refreshed.

The final local receipt and checksum manifest stay outside the public source
tree. This avoids embedding a source archive's own hash inside itself. A Git
revision identifies the full documentation/source tree; the older code-only
fingerprint is supplementary evidence. Historical candidates/artifacts remain local.

## Current state

Local alpha verification passed on 9 October 2026: **440 tests**, both browsers
required, no skips; wheel-core, wheel-live and source-core offline installations,
dependency checks, actual MCP stdio smoke tests and the installed fictional demo.
The full public tree and packages passed privacy inspection, including the
owner-selected private reference checked in memory locally. The separate advisory
scan reported no known vulnerabilities among the 51 pinned distributions.

The initial full run had two Firefox startup failures; both passed unchanged in
isolation and in the subsequent complete run. Their underlying cause remains
unestablished and is retained in the verification history. No deadlines or checks
were weakened, and no application fix was needed for the successful run.

Final local source revision and artifact hashes are recorded outside the public
tree in the publication review receipt and `dist/SHA256SUMS.0.1.0a1.txt`.
GitHub publication, hosted CI, private reporting activation and downloaded release
asset checks have not occurred. The intended repository and tag URLs remain
destinations, not claims that they already exist.
