"""Actual browser checks using only fictional local content, no Peppi login."""

import importlib.util
import os
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import pytest

from peppi_mcp.firefox_runtime import open_firefox
from peppi_mcp.adapters.lapland_browser import COLLECT, FETCH
from peppi_mcp.adapters.lapland_transcript_view import TRANSCRIPT_URL, normalize_transcript_view
from peppi_mcp.errors import PeppiError
from peppi_mcp.adapters.lapland_browser import LaplandBrowser, TRANSCRIPT_PATH, RIGHTS_PATH


AVAILABLE = importlib.util.find_spec("selenium") is not None and (
    Path(os.environ.get("PROGRAMFILES", r"C:\Program Files")) / "Mozilla Firefox/firefox.exe").is_file()


@pytest.mark.skipif(not AVAILABLE, reason="Optional Windows Firefox runtime is not installed")
def test_real_browser_private_profile_and_fictional_dom():
    driver = open_firefox(headless=True)
    profile = Path(driver.capabilities["moz:profile"])
    try:
        assert "rust_mozprofile" in profile.name
        assert driver.capabilities["acceptInsecureCerts"] is False
        driver.get("data:text/html,<title>Fictional Peppi test</title><main><p>Visible row</p><p hidden>Hidden row</p></main>")
        assert driver.title == "Fictional Peppi test"
        assert driver.execute_script("return [...document.querySelectorAll('p')].filter(p=>p.getClientRects().length).map(p=>p.textContent)") == ["Visible row"]
        driver.execute_script("window.fictionalTransientState = 'only-this-context'")
    finally:
        driver.quit()
    assert not profile.exists(), "The driver must remove its disposable profile on clean shutdown"


def test_real_fetch_fresh_accounts_redirects_and_denial_on_local_fiction(browser_factory):
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from threading import Thread
    from tests.unit.test_lapland_browser import account_html, rights_json
    state = {"account": "101", "status": 200, "signed": True, "redirect": False}
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def do_GET(self):
            if state["redirect"]:
                self.send_response(302)
                self.send_header("Location", "/fictional-login")
                self.end_headers()
                return
            self.send_response(state["status"])
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(account_html(state["account"], state["signed"]).encode())
        def do_POST(self):
            assert self.path == RIGHTS_PATH
            self.send_response(200)
            self.send_header("Content-Type", "application/json;charset=ISO-8859-1")
            self.end_headers()
            self.wfile.write(json.dumps(rights_json()).encode())
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    driver = browser_factory()
    try:
        local_origin = f"http://127.0.0.1:{server.server_port}"
        driver.get(local_origin + TRANSCRIPT_PATH)
        reader = LaplandBrowser(driver)
        # Test-only origin substitution. Production accepts the fixed HTTPS Peppi
        # origin only; no external requests are made by this fixture.
        reader._origin = lambda: None
        reader._spacing = lambda: None
        first = reader.check()
        state["account"] = "202"
        second = reader.check()
        assert first.principal != second.principal and first.rights == second.rights
        for changes, code in [({"signed":False}, "SIGN_IN_NEEDED"),
                              ({"signed":True,"status":403}, "ACCESS_DENIED"),
                              ({"status":200,"redirect":True}, "SIGN_IN_NEEDED")]:
            state.update(changes)
            with pytest.raises(PeppiError) as error:
                reader.check()
            assert error.value.code == code
    finally:
        driver.quit()
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_real_dom_collection_preserves_hidden_and_incomplete_evidence(browser_factory):
    # Fictional HTML modeled on the observed structure; no real page is saved.
    row = """<tr class="course_unit"><td class="column-state"><i aria-label="Suoritettu"></i></td>
      <td class="column-code">TEST101</td><td class="column-name">Fictional Ä course</td>
      <td class="column-credits">0,5</td><td class="column-grade">HYV</td>
      <td class="column-assessmentdate">03.01.2026</td><td class="column-specialinfo">-</td></tr>"""
    html = """<input type="radio" name="filter.status" value="COMPLETED" style="display:none"
      onclick="window.filterEventObserved=true">
      <input type="checkbox" id="showEntitlementCollection">
      <div id="transcript"><section id="transcript-entitlement-101" class="transcript-entitlement-div">
      <h4 class="sub-page-header"><a><span>Fictional degree</span><span class="small">
      Suoritettuja opintoja: 1 kpl, suoritettu laajuus: 0,5</span></a></h4><table>""" + row + """</table></section>
      <section id="transcript-entitlement-102" class="transcript-entitlement-div" style="display:none">
      <table>""" + row + "</table></section></div>"
    driver = browser_factory()
    try:
        driver.get("data:text/html;charset=utf-8," + quote(html))
        from selenium.webdriver.common.by import By
        control = driver.find_element(By.CSS_SELECTOR, 'input[name="filter.status"][value="COMPLETED"]')
        assert not control.is_displayed() and not control.is_selected()
        driver.execute_script("arguments[0].click()", control)
        assert control.is_selected() and driver.execute_script("return window.filterEventObserved")
        observation = driver.execute_script(COLLECT, "101")
        assert len(observation["rows"]) == 1 and observation["rows"][0]["title"] == "Fictional Ä course"
        # Only this fictional test substitutes its data: URL for the source URL.
        observation["url"] = TRANSCRIPT_URL
        snapshot = normalize_transcript_view(json.dumps(observation), expected_study_right="101",
            retrieved_at=datetime.now(timezone.utc))
        assert str(snapshot.achievements[0].credits) == "0.5"
        assert driver.execute_script(COLLECT, "102") == {"pending": True}
        driver.execute_script("document.querySelector('#transcript-entitlement-101 tr').style.display='none'")
        missing = driver.execute_script(COLLECT, "101")
        missing["url"] = TRANSCRIPT_URL
        with pytest.raises(PeppiError) as exc:
            normalize_transcript_view(json.dumps(missing), expected_study_right="101", retrieved_at=datetime.now(timezone.utc))
        assert exc.value.code == "PERSONAL_VIEW_INCOMPLETE"
        driver.execute_script("document.querySelector('.small').textContent='Suoritettuja opintoja: 0 kpl, suoritettu laajuus: 0'")
        empty = driver.execute_script(COLLECT, "101")
        empty["url"] = TRANSCRIPT_URL
        assert not normalize_transcript_view(json.dumps(empty), expected_study_right="101",
            retrieved_at=datetime.now(timezone.utc)).achievements
    finally:
        driver.quit()
