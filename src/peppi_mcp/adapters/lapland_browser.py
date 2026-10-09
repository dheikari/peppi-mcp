"""Observed Lapland browser reader. All driver calls run in the owned worker."""

import hashlib
import json
import os
import re
import time
from datetime import datetime, timezone
from urllib.parse import urlsplit

from peppi_mcp.adapters.lapland_transcript_view import TRANSCRIPT_URL, normalize_transcript_view
from peppi_mcp.adapters.lapland_study_plan import PLAN_URL, PLAN_METADATA, COLLECT_PLAN, normalize_plan, parse_listing, version_key
from peppi_mcp.errors import PeppiError
from peppi_mcp.browser_runtime import open_browser
from peppi_mcp.adapters.public_catalogue import retry_delay
from peppi_mcp.services.live import Identity, SourceRight

ORIGIN = "https://opiskelija-lay.peppi4.lapit.csc.fi"
TRANSCRIPT_PATH = urlsplit(TRANSCRIPT_URL).path
RIGHTS_PATH = "/delegate/studyentitlements?groupByCollection=true"
MAX_SOURCE_BYTES = 4 * 1024 * 1024

# This executes only on the verified Peppi origin. Redirects never follow the
# identity provider during a read, so an old SSO session cannot silently re-login.
FETCH = r"""
const [path, method, limit, done] = arguments;
const controller = new AbortController();
const timer = setTimeout(() => controller.abort(), 12000);
(async () => {
  try {
    const response = await fetch(path, {method, credentials:'same-origin',
      redirect:'manual', cache:'no-store', signal:controller.signal});
    if (response.type === 'opaqueredirect') return done({redirect:true});
    if ([429,503].includes(response.status)) return done({status:response.status,retry_after:response.headers.get('Retry-After')});
    const reader = response.body.getReader();
    const chunks=[]; let size=0;
    while(true) {
      const {done:ended,value}=await reader.read();
      if(ended) break;
      size+=value.length;
      if(size>limit) { await reader.cancel(); return done({too_large:true}); }
      chunks.push(value);
    }
    const bytes=new Uint8Array(size); let offset=0;
    for(const chunk of chunks) { bytes.set(chunk,offset); offset+=chunk.length; }
    const type=response.headers.get('content-type') || '';
    // Peppi advertises ISO-8859-1 for its delegate responses.
    const encoding=/charset\s*=\s*ISO-8859-1/i.test(type)?'windows-1252':'utf-8';
    done({status:response.status,type,text:new TextDecoder(encoding,{fatal:true}).decode(bytes)});
  } catch(error) { done({network_error:true}); }
  finally { clearTimeout(timer); }
})();
"""

RIGHT_LABELS = r"""
const [html, rights] = arguments;
const doc = new DOMParser().parseFromString(html,'text/html');
return rights.map(right => {
  const section=doc.getElementById('transcript-entitlement-'+right.id);
  const label=section?.querySelector('.sub-page-header a > span:not(.small)');
  const text=label?.textContent || right.name;
  return text.split(right.key).join('').replace(/\s+/g,' ').replace(/\s+,/g,',').trim();
});
"""

COLLECT = r"""
const key=arguments[0];
const visible=e=>!!e && e.getClientRects().length>0 && getComputedStyle(e).visibility!=='hidden';
const section=document.getElementById('transcript-entitlement-'+key);
const selected=document.querySelector('input[name="filter.status"]:checked');
const collection=document.getElementById('showEntitlementCollection');
if(!section || !visible(section) || selected?.value!=='COMPLETED' || collection?.checked)
  return {pending:true};
const text=e=>e?.textContent.replace(/\s+/g,' ').trim() || '';
const summary=text(section.querySelector(':scope > .sub-page-header .small'));
const match=summary.match(/^Suoritettuja opintoja:\s*(\d+)\s*kpl,\s*suoritettu laajuus:\s*(\d+(?:[,.]\d+)?)$/);
if(!match) return {invalid:true};
const rows=[];
for(const row of section.querySelectorAll('tr')) {
  if(!visible(row) || row.classList.contains('headers') || !row.querySelector('.column-code')) continue;
  // Ungraded group headings carry no course code/date/grade. Graded unsupported
  // row kinds remain in the projection so the normalizer rejects them.
  if(!row.classList.contains('course_unit') && !text(row.querySelector('.column-grade'))) continue;
  const state=row.querySelector('.column-state [aria-label]');
  rows.push({row_type:row.classList.contains('course_unit')?'course_unit':'unsupported',
    visible:true,source_status:state?.getAttribute('aria-label') || '',
    course_code:text(row.querySelector('.column-code')),
    title:text(row.querySelector('.column-name')),credits:text(row.querySelector('.column-credits')),
    grade:text(row.querySelector('.column-grade')),
    assessment_date:text(row.querySelector('.column-assessmentdate')),
    additional_info:text(row.querySelector('.column-specialinfo'))});
}
return {url:location.origin+location.pathname,study_right_id:key,visible:true,
  reported_count:Number(match[1]),reported_credits:match[2],rows};
"""


def parse_principal(html):
    signed = re.findall(r"isSignedIn\s*:\s*function\s*\(\)\s*\{\s*return\s*(true|false)\s*;", html)
    ids = re.findall(r"""getUserId\s*:\s*function\s*\(\)\s*\{\s*return\s*['"](\d+)['"]\s*;""", html)
    if signed == ["false"]:
        raise PeppiError("SIGN_IN_NEEDED", "The server reports a signed-out session.")
    if signed != ["true"] or len(ids) != 1 or ids[0] == "0":
        raise PeppiError("PERSONAL_VIEW_INVALID", "The fresh server response does not establish an authenticated account.")
    return hashlib.sha256(ids[0].encode()).hexdigest()


def parse_rights(raw):
    """Validate the observed schema without treating labels as identity."""
    try:
        if not isinstance(raw, dict) or set(raw) != {"entitlementCollections", "entitlements", "otherEntitlementsTitle"}:
            raise ValueError
        collections, others = raw["entitlementCollections"], raw["entitlements"]
        if not isinstance(collections, list) or not isinstance(others, list) or len(collections) > 100:
            raise ValueError
        groups = []
        for collection in collections:
            if not isinstance(collection, dict) or set(collection) != {"name", "entitlements"}:
                raise ValueError
            groups.append(collection["entitlements"])
        groups.extend([[right] for right in others])
        flat, links = [], {}
        for group in groups:
            if not isinstance(group, list) or len(group) > 100:
                raise ValueError
            for right in group:
                if (not isinstance(right, dict) or set(right) != {"id", "key", "name", "oldEntitlement", "selected"}
                        or not isinstance(right["id"], str) or not re.fullmatch(r"[1-9][0-9]{0,17}", right["id"])
                        or not isinstance(right["key"], str) or not 1 <= len(right["key"]) <= 100
                        or not isinstance(right["name"], str) or not 1 <= len(right["name"]) <= 300
                        or type(right["selected"]) is not bool or type(right["oldEntitlement"]) is not bool):
                    raise ValueError
                if right["oldEntitlement"]:
                    raise PeppiError("CAPABILITY_UNAVAILABLE", "Historic study-right navigation has not been verified for this reader.")
                flat.append(right)
            for right in group:
                links[right["id"]] = tuple(item["id"] for item in group if item["id"] != right["id"])
        if not 0 < len(flat) <= 100 or len({right["id"] for right in flat}) != len(flat):
            raise ValueError
        if sum(right["selected"] for right in flat) != 1:
            raise ValueError
        return flat, links
    except PeppiError:
        raise
    except (ValueError, TypeError, KeyError):
        raise PeppiError("PERSONAL_VIEW_INVALID", "The study-right response has an unsupported structure.") from None


class LaplandBrowser:
    method = "browser_session_json_rights_and_rendered_transcript"

    def __init__(self, driver=None, *, browser="firefox"):
        self.browser_name = browser
        self.driver = driver
        self._last_request = 0.0
        self._plan_urls = {}

    def open(self):
        self.driver = open_browser(self.browser_name, profile_root=os.environ.get("PEPPI_OWNED_PROFILE_ROOT"))
        self.driver.get(ORIGIN)

    def _origin(self):
        if self.driver is None:
            raise PeppiError("BROWSER_UNAVAILABLE", "The connector browser is closed.")
        current, expected = urlsplit(self.driver.current_url), urlsplit(ORIGIN)
        if (current.scheme, current.netloc) != (expected.scheme, expected.netloc):
            raise PeppiError("SIGN_IN_NEEDED", "Complete sign-in in the connector-owned browser window.")

    def _spacing(self):
        delay = 1 - (time.monotonic() - self._last_request)
        if delay > 0:
            time.sleep(delay)
        self._last_request = time.monotonic()

    def _fetch(self, path, method="GET"):
        self._origin()
        allowed = (path, method) in {(TRANSCRIPT_PATH, "GET"), (RIGHTS_PATH, "POST")} or (
            method == "POST" and re.fullmatch(r"/delegate/studyentitlements\?selectedEntitlementId=[1-9][0-9]{0,17}", path))
        if method == "GET" and path.split("?", 1)[0] == urlsplit(PLAN_URL).path:
            if "?" in path:
                version_key(ORIGIN + path)
            allowed = True
        if not allowed:
            raise PeppiError("SOURCE_REDIRECT_BLOCKED", "The operation is outside the verified Peppi read routes.")
        self._spacing()
        data = self.driver.execute_async_script(FETCH, path, method, MAX_SOURCE_BYTES)
        if data.get("redirect") or data.get("status") == 401:
            raise PeppiError("SIGN_IN_NEEDED", "The authenticated read requires sign-in.")
        if data.get("status") == 403:
            raise PeppiError("ACCESS_DENIED", "Peppi denied this personal read.")
        if data.get("status") in (429, 503):
            raise PeppiError("RATE_LIMITED", "Peppi requested a pause; no automatic retry was made.", retryable=True,
                             retry_after_seconds=retry_delay(data.get("retry_after"), datetime.now(timezone.utc)))
        if data.get("too_large"):
            raise PeppiError("SOURCE_TOO_LARGE", "The source response exceeded the personal-read size limit.")
        if data.get("network_error") or data.get("status") != 200:
            raise PeppiError("SOURCE_UNAVAILABLE", "The personal source could not be read.", retryable=True)
        return data

    def _rights(self):
        response = self._fetch(RIGHTS_PATH, "POST")
        if "json" not in response["type"]:
            if re.search(r"isSignedIn\s*:\s*function\s*\(\)\s*\{\s*return\s*false", response["text"]):
                raise PeppiError("SIGN_IN_NEEDED", "The source returned its signed-out page.")
            raise PeppiError("PERSONAL_VIEW_INVALID", "The study-right source did not return JSON.")
        try:
            return parse_rights(json.loads(response["text"]))
        except json.JSONDecodeError:
            raise PeppiError("PERSONAL_VIEW_INVALID", "The study-right response could not be decoded.") from None

    def check(self):
        html = self._fetch(TRANSCRIPT_PATH)
        if "html" not in html["type"]:
            raise PeppiError("PERSONAL_VIEW_INVALID", "The account-check response is not an HTML document.")
        principal = parse_principal(html["text"])
        rights, links = self._rights()
        labels = self.driver.execute_script(RIGHT_LABELS, html["text"], rights)
        if len(labels) != len(rights) or any(not isinstance(label, str) or not 1 <= len(label) <= 300 for label in labels):
            raise PeppiError("PERSONAL_VIEW_INVALID", "Study-right labels could not be established.")
        after = parse_principal(self._fetch(TRANSCRIPT_PATH)["text"])
        if after != principal:
            raise PeppiError("STUDY_CONTEXT_CHANGED", "The account changed during the study-context check.")
        return Identity(principal, tuple(SourceRight(right["id"], label, links[right["id"]]) for right, label in zip(rights, labels)))

    def read(self, right, identity):
        from selenium.common.exceptions import NoSuchElementException, TimeoutException, StaleElementReferenceException
        try:
            return self._read(right, identity)
        except (NoSuchElementException, StaleElementReferenceException):
            raise PeppiError("PERSONAL_VIEW_INVALID", "The transcript controls changed or are unavailable. Reload the transcript before retrying.") from None
        except TimeoutException:
            self._origin()
            raise PeppiError("PERSONAL_VIEW_INCOMPLETE", "The selected transcript did not finish loading. No records were returned.") from None

    def _read(self, right, identity):
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        self._origin()
        rights, _ = self._rights()
        target = next((item for item in rights if item["id"] == right.key), None)
        if target is None:
            raise PeppiError("STUDY_CONTEXT_CHANGED", "The requested right is no longer in this authenticated account.")
        if not target["selected"]:
            self._fetch("/delegate/studyentitlements?selectedEntitlementId=" + right.key, "POST")
        self._spacing()
        self.driver.get(TRANSCRIPT_URL)
        self._origin()
        wait = WebDriverWait(self.driver, 10, poll_frequency=.2)
        wait.until(lambda driver: driver.find_elements(By.CSS_SELECTOR, "#transcript .transcript-entitlement-div"))
        collection = self.driver.find_elements(By.ID, "showEntitlementCollection")
        if collection and collection[0].is_selected():
            self.driver.execute_script("arguments[0].click()", collection[0])
        # Additional date/timing restrictions must not silently narrow coverage.
        narrowed = self.driver.find_elements(By.CSS_SELECTOR,
            'input[name^="filter.timing"]:checked')
        if narrowed:
            raise PeppiError("PERSONAL_VIEW_INCOMPLETE", "Remove timing filters in the connector's transcript view before retrying.")
        completed = self.driver.find_element(By.CSS_SELECTOR, 'input[name="filter.status"][value="COMPLETED"]')
        if not completed.is_selected():
            self._spacing()
            # Peppi styles the native input as non-interactable. Its DOM click
            # dispatches the normal filter event; do not merely set checked.
            self.driver.execute_script("arguments[0].click()", completed)
        last_error = None
        until = time.monotonic() + 10
        previous = None
        while time.monotonic() < until:
            self._origin()
            view = self.driver.execute_script(COLLECT, right.key)
            if view.get("invalid"):
                last_error = PeppiError("PERSONAL_VIEW_INVALID", "The transcript summary has an unsupported layout or language.")
                previous = None
            elif not view.get("pending"):
                serialized = json.dumps(view, ensure_ascii=False)
                try:
                    snapshot = normalize_transcript_view(serialized, expected_study_right=right.key,
                        retrieved_at=datetime.now(timezone.utc))
                    if serialized == previous:
                        return snapshot
                    previous = serialized
                except PeppiError as exc:
                    if exc.code not in {"PERSONAL_VIEW_INCOMPLETE", "PERSONAL_VIEW_INVALID"}:
                        raise
                    last_error = exc
                    previous = None
            else:
                previous = None
            time.sleep(.2)
        raise last_error or PeppiError("PERSONAL_VIEW_INCOMPLETE", "The complete selected transcript did not become visible.")

    def close(self):
        self._plan_urls.clear()
        if self.driver:
            driver, self.driver = self.driver, None
            driver.quit()

    def _plan_page(self, url, identity):
        # Fresh nonredirecting authentication preflight before a rendered read.
        path = url.removeprefix(ORIGIN)
        fresh = self._fetch(path)
        if "html" not in fresh["type"] or parse_principal(fresh["text"]) != identity.principal:
            raise PeppiError("STUDY_CONTEXT_CHANGED", "The account changed while opening HOPS.")
        self._spacing()
        self.driver.get(url)
        self._origin()
        if parse_principal(self.driver.page_source) != identity.principal:
            raise PeppiError("STUDY_CONTEXT_CHANGED", "The rendered HOPS belongs to another account.")

    def _plan_listing(self, right, identity, url=PLAN_URL):
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        rights, _ = self._rights()
        target = next((r for r in rights if r["id"] == right.key), None)
        if target is None:
            raise PeppiError("STUDY_CONTEXT_CHANGED", "The requested HOPS right is no longer available.")
        if not target["selected"]:
            self._fetch("/delegate/studyentitlements?selectedEntitlementId=" + right.key, "POST")
        self._plan_page(url, identity)
        WebDriverWait(self.driver, 8).until(lambda d: d.find_elements(By.ID, "structure"))
        raw = self.driver.execute_script(PLAN_METADATA)
        listing = parse_listing(raw, expected_right=right.key, retrieved_at=datetime.now(timezone.utc))
        # Retain only observed version locations, never plan records. A selected
        # version can be refreshed directly instead of rendering the default
        # plan first on every read. Its fresh metadata still verifies membership.
        self._plan_urls = {key: value for key, value in self._plan_urls.items() if key[0] != right.key}
        self._plan_urls.update({(right.key, version_key(v["url"])): v["url"] for v in raw["versions"]})
        return listing, raw

    def list_plans(self, right, identity):
        listing, _ = self._plan_listing(right, identity)
        return listing

    def read_plan(self, right, identity, plan_key):
        url = self._plan_urls.get((right.key, plan_key))
        if url is None:
            raise PeppiError("PLAN_NOT_FOUND", "Select a recorded HOPS version returned for this study right.")
        listing, _ = self._plan_listing(right, identity, url)
        if listing.current_plan_id != plan_key:
            raise PeppiError("STUDY_CONTEXT_CHANGED", "The requested HOPS version is no longer the rendered version.")
        # Filtering and collapsing are local view operations; no plan edits.
        self.driver.execute_script("""
            for(const e of document.querySelectorAll('#filter-options input')) {
              if((e.value==='' || e.value==='ALL') && !e.checked) e.click();
            }
        """)
        until, previous, last_error = time.monotonic() + 8, None, None
        while time.monotonic() < until:
            self._origin()
            self.driver.execute_script("""
                for(const b of document.querySelectorAll('#structure .panel-heading button.collapse-button[aria-expanded="false"]')) b.click();
            """)
            listing = parse_listing(self.driver.execute_script(PLAN_METADATA), expected_right=right.key,
                                    retrieved_at=datetime.now(timezone.utc))
            if listing.current_plan_id != plan_key:
                raise PeppiError("STUDY_CONTEXT_CHANGED", "The selected HOPS version changed during acquisition.")
            view = self.driver.execute_script(COLLECT_PLAN)
            try:
                snapshot = normalize_plan(view, listing)
                if snapshot.id == previous:
                    after, _ = self._rights()
                    if not any(r["id"] == right.key and r["selected"] for r in after):
                        raise PeppiError("STUDY_CONTEXT_CHANGED", "The selected right changed while reading HOPS.")
                    return snapshot
                previous = snapshot.id
            except PeppiError as exc:
                if exc.code not in {"PERSONAL_VIEW_INVALID", "PERSONAL_VIEW_INCOMPLETE"}:
                    raise
                last_error, previous = exc, None
            time.sleep(.2)
        raise last_error or PeppiError("PERSONAL_VIEW_INCOMPLETE", "The full HOPS did not become stable and visible.")
