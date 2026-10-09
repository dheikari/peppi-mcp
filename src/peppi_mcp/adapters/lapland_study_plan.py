"""Strict projection of the observed Finnish HOPS Tarkastelu view.

Only recorded row identities and source status are normalized. No equivalence,
choice rule or requirement is inferred from a title or credit total.
"""

import hashlib
import json
import re
from decimal import Decimal
from urllib.parse import parse_qs, urlsplit

from pydantic import ValidationError

from peppi_mcp.errors import PeppiError
from peppi_mcp.study_plan_models import CreditRange, PlanListing, PlanNode, PlanSnapshot, PlanVersion

PLAN_URL = "https://opiskelija-lay.peppi4.lapit.csc.fi/group/opiskelijan-tyopoyta-yo/hops"
PORTLET = "PersonalCurriculumStudentPortlet_WAR_personalcurriculumportlet"
PREFIX = "_" + PORTLET + "_"
NUMBER = r"\d+(?:[,.]\d+)?"
RANGE = rf"{NUMBER}(?:\s*-\s*{NUMBER})?"

# The observed version links are ordinary render requests (lifecycle=0).
# Never accept action/resource URLs, hosts, credentials or caller-built URLs.
def version_key(url):
    parts, base = urlsplit(url), urlsplit(PLAN_URL)
    query = parse_qs(parts.query, keep_blank_values=True)
    expected = {"p_p_id": PORTLET, "p_p_lifecycle": "0", "p_p_state": "normal", "p_p_mode": "view",
                PREFIX + "struts.portlet.action": "/personalcurriculum/index",
                PREFIX + "struts.portlet.mode": "view"}
    key = PREFIX + "plannedPersonalCurriculumId"
    if ((parts.scheme, parts.netloc, parts.path) != (base.scheme, base.netloc, base.path)
            or parts.fragment or set(query) != set(expected) | {key}
            or any(query[k] != [v] for k, v in expected.items())
            or len(query[key]) != 1 or not re.fullmatch(r"[1-9][0-9]{0,17}", query[key][0])):
        raise PeppiError("PERSONAL_VIEW_INVALID", "The HOPS version link is outside the verified read operation.")
    return query[key][0]


PLAN_METADATA = r"""
const text=e=>e?.textContent.replace(/\s+/g,' ').trim() || '';
const headers=[...document.querySelectorAll('h2')].filter(e=>/ Hops-versio: /.test(text(e)));
const buttons=[...document.querySelectorAll('button')].filter(e=>text(e)==='Valitse HOPS-versio');
const active=[...document.querySelectorAll('#hops-navi a[aria-current="page"]')];
const right=[...document.querySelectorAll('#info-data a[href]')].filter(e=>{
 const u=new URL(e.href,location.href); return u.pathname==='/delegate/object-redirect/entitlement-info';
});
if(headers.length!==1 || buttons.length!==1 || active.length!==1 || text(active[0])!=='Tarkastelu' || right.length!==1)
 return {invalid:true};
const rightUrl=new URL(right[0].href,location.href);
return {header:text(headers[0]), current_url:active[0].href,
 study_right_key:rightUrl.searchParams.get('entitlementId'),
 versions:[...buttons[0].parentElement.querySelectorAll('ul.dropdown-menu a')].map(e=>({url:e.href,label:text(e)}))};
"""

COLLECT_PLAN = r"""
const root=document.getElementById('structure');
const visible=e=>!!e && e.getClientRects().length>0 && getComputedStyle(e).visibility!=='hidden';
const text=e=>e?.textContent.replace(/\s+/g,' ').trim() || '';
const checked=[...document.querySelectorAll('#filter-options input:checked')];
if(!visible(root) || visible(document.getElementById('small-loader')) || !checked.length ||
 checked.some(e=>!(e.value==='' || e.value==='ALL'))) return {pending:true};
if([...root.querySelectorAll('.collapse')].some(e=>!visible(e))) return {pending:true};
const elems=[...root.querySelectorAll('.lu-container')];
if(!elems.length || elems.length>1000 || elems.some(e=>!visible(e))) return {invalid:true};
const prefix='_PersonalCurriculumStudentPortlet_WAR_personalcurriculumportlet_';
const active=document.querySelector('#hops-navi a[aria-current="page"]');
const selectedPlan=active?new URL(active.href).searchParams.get(prefix+'plannedPersonalCurriculumId'):null;
const rightLink=document.querySelector('#info-data a[href*="/delegate/object-redirect/entitlement-info?"]');
const selectedRight=rightLink?new URL(rightLink.href).searchParams.get('entitlementId'):null;
function args(e){
 const nameCell=e.tagName==='TR'?e.querySelector(':scope > .table-cell-name'):e.querySelector(':scope > .panel-heading .study-header');
 // Agreement information can be an icon button before the actual named control.
 const button=nameCell?.querySelector('.lu-name')?.closest('button') || nameCell?.querySelector('button');
 const call=button?.getAttribute('onclick') || '';
 const match=call.match(/^openLearningUnitInfoModal\('([^']*)', '([^']*)', '([^']*)', '([^']*)', '(\d+)', '(\d+)'\); return false;$/);
 const agreementButton=[...nameCell?.querySelectorAll('button') || []].find(b=>(b.getAttribute('onclick')||'').startsWith("egdialog('courseInfo', localizedText('assessment.statustip.containsContract')"));
 if(match && !agreementButton) return {values:match.slice(1),title:text(button.querySelector('.lu-name')),relation:'ordinary'};
 // An observed agreement-backed course uses a read-only information dialog.
 // Read identifiers from its existing link; never execute or request this URL.
 const agreement=(agreementButton?.getAttribute('onclick') || call).match(/^egdialog\('courseInfo', localizedText\('assessment.statustip.containsContract'\), '([^']*)',courseInfoOptions\);$/);
 if(!agreement || e.tagName!=='TR') return null;
 const url=new URL(agreement[1],location.href);
 const rowKey=url.searchParams.get(prefix+'plannedStructureRowId');
 const rightKey=url.searchParams.get(prefix+'studyEntitlementId');
 const note=e.querySelector('[data-thread-id]')?.getAttribute('data-thread-id')?.match(/^LU-([A-Za-z0-9_.:-]+)-SE(\d+)-EDU\d+$/);
 if(url.origin!==location.origin || url.pathname!==location.pathname || !/^\d+$/.test(rowKey||'') ||
    rightKey!==selectedRight || !note || note[2]!==selectedRight || !selectedPlan) return null;
 if(match && (match[5]!==selectedPlan || match[6]!==rowKey || match[2]!==note[1] || match[1]!=='COURSE_UNIT')) return null;
 return {values:['COURSE_UNIT',note[1],'','',''+selectedPlan,rowKey],title:text(button.querySelector('.lu-name')) || text(button),relation:'study_agreement'};
}
const map=new Map(elems.map(e=>[e,args(e)]));
if([...map.values()].some(x=>!x)) return {invalid:true};
const nodes=elems.map(e=>{
 const a=map.get(e), parent=e.parentElement.closest('.lu-container');
 const group=e.tagName!=='TR';
 const summary=group?e.querySelector(':scope > .panel-heading section .tipover-e')?.getAttribute('data-content'):null;
 const indicator=e.querySelector(':scope > .table-cell-status .indicator');
 return {id:a.values[5],plan_key:a.values[4],source_kind:a.values[0],source_relation:a.relation,course_code:a.values[1],title:a.title,
 parent_id:parent?map.get(parent)?.values[5]:null,group,summary,
 requirement:indicator?.className || '',status:text(e.querySelector(':scope > .table-cell-status .status')),
 source_status:e.querySelector(':scope > .table-cell-status .status')?.getAttribute('aria-label') || '',
 credits:group?null:text(e.querySelector(':scope > .table-cell-credits')),
 grade:group?null:text(e.querySelector(':scope > .table-cell-accomplishments > .tipover-e'))};
});
return {nodes, node_count:elems.length,
 summary:document.querySelector('#summary-data .info [data-content]')?.getAttribute('data-content'),
 total:text(document.querySelector('#summary-data #total')),
 scope:text(root.querySelector('.hops-scope-details'))};
"""


def invalid(message="The HOPS view has an unsupported structure or language."):
    return PeppiError("PERSONAL_VIEW_INVALID", message)


def parse_listing(raw, *, expected_right, retrieved_at):
    stage = "context"
    try:
        if raw.get("invalid") or raw["study_right_key"] != expected_right:
            raise PeppiError("STUDY_CONTEXT_CHANGED", "The HOPS view does not establish the requested study right.")
        versions = []
        stage = "version selector"
        if not 0 < len(raw["versions"]) <= 100:
            raise ValueError
        for entry in raw["versions"]:
            key = version_key(entry["url"])
            match = re.fullmatch(r"([1-9][0-9]*) (DRAFT(?: \(voi muokata\))?|Hyväksytty)", entry["label"])
            if not match:
                raise ValueError
            versions.append(PlanVersion(id=key, version=int(match[1]), source_status="DRAFT" if match[2].startswith("DRAFT") else "Hyväksytty"))
        current = version_key(raw["current_url"])
        stage = "selected version header"
        header = re.fullmatch(r"(.{1,300}) Hops-versio: ([1-9][0-9]*) \((DRAFT|Hyväksytty)\)", raw["header"])
        selected = next(v for v in versions if v.id == current)
        if not header or (int(header[2]), header[3]) != (selected.version, selected.source_status):
            raise ValueError
        return PlanListing(study_right_key=expected_right, current_plan_id=current, current_plan_name=header[1],
                           versions=tuple(versions), retrieved_at=retrieved_at)
    except PeppiError:
        raise
    except (ValueError, TypeError, KeyError, StopIteration, ValidationError):
        raise invalid("Unsupported HOPS " + stage + "; source values were omitted.") from None


def credits(value):
    if not re.fullmatch(RANGE, value):
        raise ValueError
    parts = [Decimal(p.strip().replace(",", ".")) for p in value.split("-")]
    return CreditRange(minimum=parts[0], maximum=parts[-1])


def lines(value):
    # Only the observed numeric summaries are accepted, never arbitrary markup.
    return [re.sub(r"\s+", " ", p).strip() for p in re.split(r"<br\s*/?>", value) if p.strip()]


def labelled(line, label, *, scalar=False):
    match = re.fullmatch(rf"({RANGE}) op {re.escape(label)}", line)
    if not match:
        raise ValueError
    result = credits(match[1])
    if scalar:
        if result.minimum != result.maximum:
            raise ValueError
        return result.minimum
    return result


def normalize_plan(raw, listing):
    stage = "projection bounds"
    try:
        if raw.get("pending"):
            raise PeppiError("PERSONAL_VIEW_INCOMPLETE", "The unfiltered HOPS tree did not finish loading.")
        if raw.get("invalid") or len(json.dumps(raw)) > 1024 * 1024:
            raise ValueError
        if raw["node_count"] != len(raw["nodes"]) or not 0 < raw["node_count"] <= 1000:
            raise ValueError
        stage = "sidebar credit summary"
        summary = lines(raw["summary"])
        if len(summary) != 4:
            raise ValueError
        # The sidebar's completion total includes studies outside HOPS. This
        # was reconciled against root groups on the actual populated right.
        total_completed = labelled(summary[0], "suorituksia", scalar=True)
        outside = labelled(summary[1], "hopsin ulkopuoliset opinnot", scalar=True)
        if outside > total_completed:
            raise ValueError
        completed = total_completed - outside
        planned = labelled(summary[2], "suunniteltu laajuus")
        target = labelled(summary[3], "tavoitelaajuus")
        total = re.fullmatch(rf"({NUMBER})", raw["total"])
        stage = "scope and headline credits"
        scope = re.fullmatch(rf"HOPSin laajuus ({RANGE}) / ({RANGE}) op", raw["scope"])
        if not total or not scope or credits(scope[1]) != planned or credits(scope[2]) != target:
            raise ValueError
        nodes, by_id = [], {}
        kinds = {"COURSE_UNIT": "course", "STUDY_MODULE": "module", "CATEGORY": "category", "OFFERING": "offering"}
        requirements = {"indicator compulsory": "mandatory", "indicator optional": "optional", "": "unknown"}
        for row in raw["nodes"]:
            stage = "row identity and hierarchy"
            if row["plan_key"] != listing.current_plan_id or not re.fullmatch(r"[1-9][0-9]{0,17}", row["id"]):
                raise PeppiError("STUDY_CONTEXT_CHANGED", "HOPS rows do not belong to the selected recorded version.")
            if type(row["group"]) is not bool or row["group"] == (row["source_kind"] == "COURSE_UNIT"):
                raise ValueError
            parent = by_id.get(row["parent_id"])
            if row["parent_id"] is not None and (parent is None or parent.kind == "course"):
                raise ValueError
            external = parent.outside_plan if parent else False
            node_completed = None
            node_target = None
            if row["group"]:
                stage = "group credit summary"
                group = lines(row["summary"])
                node_completed = labelled(group[0], "suorituksia", scalar=True)
                if len(group) == 2:
                    planned_node = labelled(group[1], "ulkopuolinen laajuus")
                    if parent is not None:
                        raise ValueError
                    external = True
                elif len(group) == 3:
                    planned_node = labelled(group[1], "suunniteltu laajuus")
                    node_target = labelled(group[2], "tavoitelaajuus")
                else:
                    raise ValueError
            else:
                stage = "course credit format"
                match = re.fullmatch(rf"(?:Muutettu laajuus )?({RANGE}) op", row["credits"])
                if not match:
                    raise ValueError
                planned_node = credits(match[1])
            stage = "learning-unit kind"
            kind = kinds[row["source_kind"]]
            stage = "requirement marker"
            requirement = requirements[row["requirement"]]
            stage = "row model"
            node = PlanNode(id=row["id"], parent_id=row["parent_id"], course_code=row["course_code"], title=row["title"],
                kind=kind, source_relation=row.get("source_relation", "ordinary"),
                requirement=requirement, source_status=row["source_status"],
                completed=row["source_status"] == "Suoritettu", outside_plan=external, planned_credits=planned_node,
                target_credits=node_target, source_completed_credits=node_completed, grade=row["grade"] or None)
            if node.id in by_id:
                raise invalid("Duplicate HOPS row identity; source values were omitted.")
            nodes.append(node)
            by_id[node.id] = node
        roots = [n for n in nodes if n.parent_id is None]
        stage = "root credit reconciliation"
        if any(n.source_completed_credits is None for n in roots):
            raise ValueError
        discrepancies = []
        if sum(n.source_completed_credits for n in roots if not n.outside_plan) != completed:
            discrepancies.append("inside_plan_groups")
        if sum(n.source_completed_credits for n in roots if n.outside_plan) != outside:
            discrepancies.append("outside_plan_groups")
        if credits(total[1]).minimum != completed + outside:
            discrepancies.append("headline_total")
        return PlanSnapshot(id="plan:" + hashlib.sha256(json.dumps(raw, sort_keys=True).encode()).hexdigest(), listing=listing,
            nodes=tuple(nodes), source_completed_credits=completed, source_outside_credits=outside,
            planned_credits=planned, target_credits=target, source_total_credits=credits(total[1]).minimum,
            reconciliation_issues=tuple(discrepancies))
    except PeppiError:
        raise
    except ValidationError as exc:
        fields = sorted({str(error["loc"][0]) for error in exc.errors(include_input=False, include_url=False)
                         if error["loc"] and str(error["loc"][0]) in PlanNode.model_fields})
        detail = " (" + ", ".join(fields) + ")" if fields else ""
        if "title" in fields and stage == "row model":
            title = row.get("title")
            detail += "; " + ("empty" if title == "" else "overlong" if isinstance(title, str) and len(title) > 500 else "invalid") + " title"
            detail += " in " + ("agreement" if row.get("source_relation") == "study_agreement" else "ordinary") + (" group" if row.get("group") else " course")
        raise invalid("Unsupported HOPS " + stage + detail + "; source values were omitted.") from None
    except (ValueError, TypeError, KeyError, IndexError, ValidationError):
        raise invalid("Unsupported HOPS " + stage + "; source values were omitted.") from None
