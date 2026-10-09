"""Real browser DOM execution on wholly fictional content."""
from datetime import datetime, timezone
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import pytest

from peppi_mcp.adapters.lapland_study_plan import COLLECT_PLAN, PLAN_METADATA, PREFIX, normalize_plan, parse_listing
from tests.plan_fixtures import version_url


def test_plan_tree_metadata_agreement_hidden_rows_and_filter_loading(browser_factory):
    url = escape(version_url(), quote=True)
    html = f'''<!doctype html><meta charset="utf-8"><h2>Fiction2026 Hops-versio: 2 (DRAFT)</h2>
      <div><button>Valitse HOPS-versio</button><ul class="dropdown-menu"><li><a href="{url}">2 DRAFT (voi muokata)</a></li></ul></div>
      <ul id="hops-navi"><li><a aria-current="page" href="{url}">Tarkastelu</a></li></ul>
      <div id="info-data"><a href="https://opiskelija-lay.peppi4.lapit.csc.fi/delegate/object-redirect/entitlement-info?view=entitlement&amp;entitlementId=101">Private details</a></div>
      <div id="filter-options"><input name="filter.status" value="ALL" type="radio" checked style="display:none">
      <input name="filter.status" value="COMPLETED" type="radio"></div><div id="small-loader" style="display:none">Loading</div>
      <div id="summary-data"><div class="info"><i data-content="0,5 op suorituksia&lt;br/&gt;0 op hopsin ulkopuoliset opinnot&lt;br/&gt;1 op suunniteltu laajuus&lt;br/&gt;1 op tavoitelaajuus"></i></div><span id="total">0,5</span></div>
      <div id="structure"><section class="hops-scope-details">HOPSin laajuus 1 / 1 op</section>
      <section class="lu-container"><div class="panel-heading"><h4 class="study-header"><button onclick="openLearningUnitInfoModal('STUDY_MODULE', 'TEST-M', 'STUDY_MODULE', '', '501', '1'); return false;"><span class="lu-name">Fictional module</span></button></h4>
      <section><span class="tipover-e" data-content="0,5 op suorituksia&lt;br/&gt;1 op suunniteltu laajuus&lt;br/&gt;1 op tavoitelaajuus"></span></section></div>
      <div class="collapse" id="children"><table><tbody><tr class="lu-container">
      <td class="table-cell-status"><i class="indicator compulsory"></i><span class="status" aria-label="Suoritettu"></span></td>
      <td class="table-cell-name"><button onclick="openLearningUnitInfoModal('COURSE_UNIT', 'TEST101', 'STUDY_MODULE', '', '501', '2'); return false;"><span class="lu-name">Fictional Ä course</span></button></td>
      <td class="table-cell-credits">0,5 op</td><td class="table-cell-accomplishments"><span class="tipover-e" data-content="PRIVATE_ASSESSOR">HYV</span><span class="sr-only">PRIVATE_ASSESSOR</span></td>
      <td><button data-thread-id="LU-TEST101-SE101-EDU100">Note</button></td></tr></tbody></table></div></section></div>'''
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html;charset=utf-8")
            self.end_headers()
            self.wfile.write(html.encode())
    server = ThreadingHTTPServer(("127.0.0.1",0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    driver = browser_factory()
    try:
        origin = f"http://127.0.0.1:{server.server_port}"
        driver.get(origin + "/fictional-hops")
        listing = parse_listing(driver.execute_script(PLAN_METADATA),expected_right="101",retrieved_at=datetime.now(timezone.utc))
        observation = driver.execute_script(COLLECT_PLAN)
        assert "PRIVATE_ASSESSOR" not in str(observation)
        result = normalize_plan(observation, listing)
        assert result.nodes[1].title == "Fictional Ä course" and result.nodes[1].grade == "HYV"
        assert result.source_total_credits == result.nodes[1].planned_credits.minimum
        driver.execute_script("document.querySelector('tr.lu-container').style.display='none'")
        assert driver.execute_script(COLLECT_PLAN) == {"invalid":True}
        driver.execute_script("document.querySelector('tr.lu-container').style.display=''; document.querySelector('#children').style.display='none'")
        assert driver.execute_script(COLLECT_PLAN) == {"pending":True}
        driver.execute_script("document.querySelector('#children').style.display=''; document.querySelector('input[value=COMPLETED]').click()")
        assert driver.execute_script(COLLECT_PLAN) == {"pending":True}
        driver.execute_script("document.querySelector('input[value=ALL]').click(); document.querySelector('#small-loader').style.display='block'")
        assert driver.execute_script(COLLECT_PLAN) == {"pending":True}
        driver.execute_script("document.querySelector('#small-loader').style.display='none'")
        agreement_url = origin + "/fictional-hops?" + PREFIX + "plannedStructureRowId=2&" + PREFIX + "studyEntitlementId=101"
        call = "egdialog('courseInfo', localizedText('assessment.statustip.containsContract'), '" + agreement_url + "',courseInfoOptions);"
        driver.execute_script("document.querySelector('.table-cell-name button').setAttribute('onclick', arguments[0])", call)
        driver.execute_script("document.querySelector('.table-cell-name button').innerHTML='<span class=lu-name></span>Fictional agreement course'")
        agreement = normalize_plan(driver.execute_script(COLLECT_PLAN),listing).nodes[1]
        assert agreement.source_relation == "study_agreement" and agreement.title == "Fictional agreement course"
        # A real agreement can use a separate icon control before the named one.
        driver.execute_script("""
            const cell=document.querySelector('.table-cell-name');
            cell.querySelector('button').innerHTML='<i aria-label="Agreement"></i>';
            const named=document.createElement('button');
            named.setAttribute('onclick', "openLearningUnitInfoModal('COURSE_UNIT', 'TEST101', 'STUDY_MODULE', '', '501', '2'); return false;");
            named.innerHTML='<span class="lu-name">Fictional named course</span>';
            cell.appendChild(named);
        """)
        agreement = normalize_plan(driver.execute_script(COLLECT_PLAN),listing).nodes[1]
        assert agreement.source_relation == "study_agreement" and agreement.title == "Fictional named course"
        driver.execute_script("document.querySelector('.table-cell-name button').setAttribute('onclick', arguments[0])", call.replace("studyEntitlementId=101", "studyEntitlementId=102"))
        assert driver.execute_script(COLLECT_PLAN) == {"invalid":True}
    finally:
        driver.quit()
        server.shutdown()
        server.server_close()
        thread.join(2)
