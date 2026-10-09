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

Latest local alpha verification passed on 9 October 2026: **443 tests**, both browsers
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
The owner authorized publication and pushed the reviewed initial revision
`3af00c5f242f311fb6a115ecfd25b83544267ec2` to the public
[repository](https://github.com/dheikari/peppi-mcp). GitHub attributes it to
`dheikari`. Private reporting and notification settings are verified as described
in [the reporting record](security-reporting.md).

The [first hosted run](https://github.com/dheikari/peppi-mcp/actions/runs/37952609801)
was rejected before any job ran: workflow line 39 used an unquoted YAML scalar
containing `--only-binary=:all:`. An independent YAML parser reproduced the
failure. Changing that command to a literal block preserves its exact command
and required checks; the corrected workflow parses locally and was accepted
after the owner's push.

The owner pushed the correction. The [first executing hosted matrix](https://github.com/dheikari/peppi-mcp/actions/runs/37954638304)
finished with 435 passing and five failing tests. Its initial Chrome connection
error and overly broad process observer are detailed in
[the verification record](verification.md#first-executing-hosted-matrix--9-october-2026).
Twelve focused cases passed locally with the observer/readiness corrections.
The full corrected local release command then passed **443 tests in 683.15
seconds**, requiring both browsers without skips, package inspection, three
offline clean installations and actual stdio checks. The corrected hosted matrix
must still pass. These changes are
confined to test infrastructure, CI provisioning and documentation; application
behavior and dependency pins are unchanged.

No tag or release has been created. The final prerelease remains gated on a
successful hosted run, refreshed artifacts and downloaded release-asset hashes.
