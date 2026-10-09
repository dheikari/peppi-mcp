"""Wholly fictional Peppi HTTP source. Never used by production entry points."""
import json
import time
from contextlib import contextmanager
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from urllib.parse import parse_qs, urlencode, urlsplit

from peppi_mcp.adapters.lapland_browser import RIGHTS_PATH, TRANSCRIPT_PATH
from peppi_mcp.adapters.lapland_study_plan import PREFIX, PORTLET
from tests.unit.test_lapland_browser import account_html, rights_json

PLAN_PATH = "/group/opiskelijan-tyopoyta-yo/hops"


def version_url(origin, key):
    return origin + PLAN_PATH + "?" + urlencode({"p_p_id":PORTLET,"p_p_lifecycle":"0","p_p_state":"normal","p_p_mode":"view",
        PREFIX+"plannedPersonalCurriculumId":key,PREFIX+"struts.portlet.action":"/personalcurriculum/index",PREFIX+"struts.portlet.mode":"view"})


def transcript(state):
    sections = []
    for right in ("101", "102"):
        rows = "".join(f'''<tr class="course_unit" {'hidden' if state['fault']=='hidden' and i==2 else ''}>
          <td class="column-state"><i aria-label="Suoritettu"></i></td><td class="column-code">TEST{i}</td>
          <td class="column-name">Fictional course {i}</td><td class="column-credits">0,5</td>
          <td class="column-grade">5</td><td class="column-assessmentdate">03.01.2026</td><td class="column-specialinfo">-</td></tr>''' for i in range(3))
        count = "4" if state["fault"] == "count" else "3"
        if state["fault"] == "zero": count, rows = "0", ""
        total = "0" if state["fault"] == "zero" else "1,5"
        summary = "" if state["fault"] == "missing_zero" else f"Suoritettuja opintoja: {count} kpl, suoritettu laajuus: {total}"
        sections.append(f'''<section id="transcript-entitlement-{right}" class="transcript-entitlement-div" {'hidden' if right!=state['right'] else ''}>
          <h4 class="sub-page-header"><a><span>Fictional degree</span><span class="small">{summary}</span></a></h4><table>{rows}</table></section>''')
    return '<input name="filter.status" type="radio" value="COMPLETED" checked><div id="transcript">' + "".join(sections) + '</div>'


def hops(state, origin, query):
    right = state["right"]
    choices = ("501", "502") if right == "101" else ("601",)
    key = parse_qs(query).get(PREFIX+"plannedPersonalCurriculumId", [choices[0]])[0]
    if state["fault"] == "removed": choices = choices[:1]
    if state["fault"] == "wrong_right": right = "102" if right=="101" else "101"
    if state["fault"] == "wrong_version": key = choices[0]
    approved = key == "502"
    label = "1 Hyväksytty" if approved else ("2 DRAFT" if right=="101" else "1 DRAFT")
    status, version = ("Hyväksytty", 1) if approved else ("DRAFT", 2 if right=="101" else 1)
    url = escape(version_url(origin, key), quote=True)
    menu = "".join(f'<li><a href="{escape(version_url(origin,k),quote=True)}">{("1 Hyväksytty" if k=="502" else "2 DRAFT" if k=="501" else "1 DRAFT")}</a></li>' for k in choices)
    total = "2" if state["fault"] == "conflict" else "1,5"
    title = "Changed fiction" if state["fault"] == "plan_changed" and state["hops_reads"] >= 3 else "Fictional module"
    courses = "".join(f'''<tr class="lu-container"><td class="table-cell-status"><i class="indicator compulsory"></i><span class="status" aria-label="Suoritettu"></span></td>
       <td class="table-cell-name"><button onclick="openLearningUnitInfoModal('COURSE_UNIT', 'TEST{i}', 'STUDY_MODULE', '', '{key}', '{i+2}'); return false;"><span class="lu-name">Fictional course {i}</span></button></td>
       <td class="table-cell-credits">0,5 op</td><td class="table-cell-accomplishments"><span class="tipover-e" data-content="PRIVATE_ASSESSOR">5</span></td></tr>''' for i in range(3))
    loader = "block" if state["fault"] == "loading" else "none"
    return f'''<h2>FICTION Hops-versio: {version} ({status})</h2>
      <div><button>Valitse HOPS-versio</button><ul class="dropdown-menu">{menu}</ul></div>
      <ul id="hops-navi"><li><a aria-current="page" href="{url}">Tarkastelu</a></li></ul>
      <div id="info-data"><a href="{origin}/delegate/object-redirect/entitlement-info?view=entitlement&amp;entitlementId={right}">Private details</a></div>
      <div id="filter-options"><input type="radio" name="filter.status" value="ALL" checked></div><div id="small-loader" style="display:{loader}">Loading</div>
      <div id="summary-data"><div class="info"><i data-content="{total} op suorituksia&lt;br/&gt;0 op hopsin ulkopuoliset opinnot&lt;br/&gt;3 op suunniteltu laajuus&lt;br/&gt;3 op tavoitelaajuus"></i></div><span id="total">{total}</span></div>
      <div id="structure"><section class="hops-scope-details">HOPSin laajuus 3 / 3 op</section>
      <section class="lu-container"><div class="panel-heading"><h4 class="study-header"><button onclick="openLearningUnitInfoModal('STUDY_MODULE', 'TEST-M', 'STUDY_MODULE', '', '{key}', '1'); return false;"><span class="lu-name">{title}</span></button></h4>
      <section><span class="tipover-e" data-content="1,5 op suorituksia&lt;br/&gt;3 op suunniteltu laajuus&lt;br/&gt;3 op tavoitelaajuus"></span></section></div><div class="collapse"><table>{courses}</table></div></section></div>'''


@contextmanager
def local_peppi():
    state = {"account":"101", "right":"101", "fault":"", "hops_reads":0, "requests":[],
             "transcript_reads":0, "change_account_at":None, "delay":0}
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def do_GET(self):
            state["requests"].append(("GET", self.path))
            path = urlsplit(self.path)
            # Test-owned synchronization, never a production fault control.
            if path.path == "/" and state.get("startup_entered"):
                state["startup_entered"].set()
                try:
                    if state["startup_release"].wait(45):
                        self.send_response(200)
                        self.end_headers()
                        self.wfile.write(b"Fictional held startup")
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                    pass
                finally:
                    if state.get("startup_finished"):
                        state["startup_finished"].set()
                return
            if path.path == TRANSCRIPT_PATH:
                state["transcript_reads"] += 1
                if state["transcript_reads"] == state["change_account_at"]:
                    state["account"] = "202"
                time.sleep(state["delay"])
            fault = state["fault"]
            if fault in {"denied","rate_limited","redirect"}:
                self.send_response({"denied":403,"rate_limited":429,"redirect":302}[fault])
                if fault=="rate_limited": self.send_header("Retry-After","1")
                if fault=="redirect": self.send_header("Location","/fictional-login")
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-Type","text/html;charset=utf-8")
            self.end_headers()
            body = account_html(state["account"], signed=fault!="signed_out")
            if path.path == PLAN_PATH:
                state["hops_reads"] += 1
                body += hops(state, origin, path.query)
            else:
                body += transcript(state)
            if fault=="malformed": body = "<html>PRIVATE_SECRET unsupported source</html>"
            if fault=="oversized": body = "X" * (4*1024*1024+1)
            try: self.wfile.write(('<!doctype html><meta charset="utf-8">'+body).encode())
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError): pass
        def do_POST(self):
            state["requests"].append(("POST",self.path))
            time.sleep(state["delay"])
            query = parse_qs(urlsplit(self.path).query)
            if urlsplit(self.path).path != "/delegate/studyentitlements":
                self.send_response(405); self.end_headers(); return
            if "selectedEntitlementId" in query: state["right"] = query["selectedEntitlementId"][0]
            data = rights_json()
            for r in data["entitlementCollections"][0]["entitlements"]:
                r["selected"] = r["id"] == state["right"]
                r["name"] = "Identical fictional display name"
            self.send_response(200)
            self.send_header("Content-Type","application/json;charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(data).encode())
    server = ThreadingHTTPServer(("127.0.0.1",0), Handler)
    origin = f"http://127.0.0.1:{server.server_port}"
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try: yield origin, state
    finally:
        server.shutdown(); server.server_close(); thread.join(2)
