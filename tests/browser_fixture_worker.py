"""Test-only bootstrap: shipped worker and browser, wired to local fiction."""
import os
import json
from pathlib import Path
from typing import Literal
from peppi_mcp import browser_worker
from peppi_mcp.adapters import lapland_browser, lapland_study_plan, lapland_transcript_view
from peppi_mcp.browser_runtime import open_browser

origin = os.environ["PEPPI_FIXTURE_ORIGIN"]
assert origin.startswith("http://127.0.0.1:")
lapland_browser.ORIGIN = origin
lapland_browser.TRANSCRIPT_URL = origin + lapland_browser.TRANSCRIPT_PATH
lapland_transcript_view.TRANSCRIPT_URL = lapland_browser.TRANSCRIPT_URL
lapland_transcript_view._View.model_fields["url"].annotation = Literal[lapland_browser.TRANSCRIPT_URL]
lapland_transcript_view._View.model_rebuild(force=True)
lapland_study_plan.PLAN_URL = origin + "/group/opiskelijan-tyopoyta-yo/hops"
lapland_browser.PLAN_URL = lapland_study_plan.PLAN_URL
lapland_browser.LaplandBrowser._plan_listing.__defaults__ = (lapland_study_plan.PLAN_URL,)
# Preserve the production fresh-read contract; omit request spacing only for
# local fixtures, which never contact a university or identity provider.
lapland_browser.LaplandBrowser._spacing = lambda self: None
def open_local(self):
    self.driver = open_browser(self.browser_name, headless=True, profile_root=os.environ["PEPPI_OWNED_PROFILE_ROOT"])
    record = os.environ.get("PEPPI_FIXTURE_PROCESS_RECORD")
    if record:
        Path(record).write_text(json.dumps({
            "driver_pid": self.driver.service.process.pid,
            "browser_pid": self.driver.capabilities["moz:processID" if self.browser_name == "firefox" else "goog:processID"],
            "worker_pid": os.getpid(),
            "fixture_job_name": Path(record).with_suffix(".job").read_text(),
        }))
    self.driver.get(origin)
lapland_browser.LaplandBrowser.open = open_local
browser_worker.main()
