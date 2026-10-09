# Recorded HOPS and progress

The experimental Windows live connector reads the Finnish University of Lapland
HOPS **Tarkastelu** view. It exposes saved plan versions, their displayed tree,
and a conservative comparison with the selected right's completed transcript.
It does not edit HOPS or determine degree completion or graduation eligibility.

## Tools

1. Connect and select an ID returned by `list_study_rights`.
2. Call `get_study_plan` with `study_right_id` only. The response lists recorded
   versions with opaque IDs, source version numbers and status. It identifies
   the current view but requires an explicit selection before returning a tree.
3. Call `get_study_plan` again with that `study_right_id` and a returned `plan_id`.
4. Call `get_study_progress` with the same two identifiers for a fresh comparison.

Draft and approved plans are distinct. No default version is silently chosen for
progress. IDs are bound to the connection and study right; reconnect and discover
them again after disconnect, account change or server restart. Synthetic and
imported modes continue to report these capabilities unavailable.

The selected tree includes stable source row relationships mapped to opaque
session IDs, course codes, titles, mandatory/optional/unknown classifications,
source completion states, credit ranges, group targets and outside-plan markers.
The plan's displayed name is preserved; it is not asserted to identify an entire
curriculum or all of its regulations. Source text is untrusted data.

Version 0.1.0.dev1 adds a typed assessment before detailed records, with separate
source-consistency and comparison statuses, scoped discrepancies, compared
quantities and exact decimal differences. Unmapped achievements include their
credits but are not automatically classified as outside-plan studies. See
[the assessment contract](hardening.md).

## Observed acquisition contract

Inspection on 3 October 2026 found a server-rendered HOPS page at
`/group/opiskelijan-tyopoyta-yo/hops`. The saved-version menu uses GET render links
with `p_p_lifecycle=0`, `p_p_mode=view`, the personal-curriculum student portlet,
`plannedPersonalCurriculumId`, `/personalcurriculum/index`, and portlet mode `view`.
Only this exact observed URL shape is accepted. No new bearer token or structured
HOPS API was established. The existing authenticated browser session is reused.

The fresh page's study-right information link establishes the requested right;
the active Tarkastelu link, header version/status and ordinary row references
must agree on the selected plan. Ordinary information controls supply learning
unit type, course code, plan ID and planned-structure row ID. They are parsed as
data and never evaluated. Agreement-backed rows use a different information
link: their row/right references and the row's explicit learning-unit marker
must agree with the selected context. Agreement contents and equivalences remain
unverified; this adapter does not request the agreement dialog.

The collector resets view filters, expands existing group controls, waits for
two identical validated projections, and checks that every collected row and
group is visible. It rejects loading, hidden or unsupported rows and unknown
identity/credit formats. It bounds the tree to 1,000 nodes and the projection to
1 MiB. Node IDs must be unique; parents must occur before their children.

After discovery, reads navigate directly to the observed selected-version URL.
Each read still verifies fresh account, right and version metadata; the retained
URL is not evidence that the plan remains accessible. This avoids unnecessarily
loading the default plan before each selected-version refresh.

Root group credit totals are compared against the HOPS sidebar. The sidebar's
completion total **includes** outside-plan credits; the connector derives the
inside-plan subtotal by subtraction and checks both against root groups. A
discrepancy retains both source values, marks the view partial, and appears in
`source_reconciliation_issues`. This occurred on an inspected approved version;
its cause is not inferred. The completed-transcript reader still rejects count
or credit discrepancies. Decimal arithmetic preserves comma fractions. Credit
ranges remain ranges.

Provenance covers the unfiltered rendered tree of the selected recorded version.
There is no independent server record count or verified complete curriculum-rule
feed. Agreement rules, alternative routes, substitutions and transfer eligibility
are not inferred from labels or totals. Missing or changed markup fails explicitly.

## Progress and uncertainty

Progress reads the selected plan, acquires a fresh reconciled transcript, then
reads the plan again. A changed plan projection fails with `PLAN_CHANGED`.
Fresh account checks bracket the operation, and the existing 30-second deadline,
serialized browser worker and authentication-loss cleanup remain in effect.
No plan snapshot is retained after a request; version identity and observed-URL
mappings contain no plan records and are cleared on disconnect. Timeout messages
identify a fixed operation stage without exposing source values or credentials.

Only a unique exact course code with agreeing completion state, grade and exact
credits can match a completed course. Matching titles are insufficient. Repeated
plan allocations, multiple transcript candidates, conflicting grades/credits,
unknown completion states, agreements, transfers and module/replacement
relationships remain unresolved. Unmatched achievements are returned explicitly.

Group credits are reconciled with matched descendant courses without adding
module and course credits together. Even when credits reconcile, group requirement
satisfaction remains unresolved because a credit target does not establish which
electives, alternatives or substitutions are accepted. Studies outside HOPS remain
separate. `degree_requirements_satisfied` and `graduation_eligibility` are always
null; `source_credits_reconciled` describes accounting only.

The university's [HOPS guide](https://blogi.eoppimispalvelut.fi/peppiopaslay/ohjekeskus/opiskelijalle/opintojen-suunnittelu-ja-hops/hops/)
describes saved-version selection. Its
[FAQ](https://blogi.eoppimispalvelut.fi/peppiopaslay/ohjekeskus/opiskelijalle/usein-kysytyt-kysymykset/usein-kysytyt-kysymykset-pepista/)
also explains that plans are study-right-specific and some older students have
an initially empty plan. These guides provide context; live source evidence
defines the supported reader contract.

## Verification

Fictional tests cover explicit version selection, wrong account/right/version,
tree completeness, duplicate/cyclic/missing parents, source-total discrepancies,
credit ranges, outside studies, agreement rows, conflicts, transfers/modules,
same-title mismatches, plan changes, expiry and timeout. Real Firefox executes
the collector against fictional HTML with hidden rows, filters and loading states.
The stdio client exercises both new tools. Actual-account and installation
evidence is recorded in [verification.md](verification.md).
