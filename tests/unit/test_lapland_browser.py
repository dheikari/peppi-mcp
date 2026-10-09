import json

import pytest

from peppi_mcp.adapters.lapland_browser import LaplandBrowser, ORIGIN, RIGHTS_PATH, TRANSCRIPT_PATH, parse_principal, parse_rights
from peppi_mcp.errors import PeppiError


def account_html(principal="101", signed=True):
    return '<script>var themeDisplay={getUserId: function(){return "' + principal + '";},isSignedIn: function(){return ' + str(signed).lower() + ';}};</script>'


def rights_json():
    return {"entitlementCollections": [{"name": "Fictional collection", "entitlements": [
        {"id": "101", "key": "FICT001", "name": "Fictional bachelor's", "oldEntitlement": False, "selected": True},
        {"id": "102", "key": "FICT002", "name": "Fictional master's", "oldEntitlement": False, "selected": False}]}],
        "entitlements": [], "otherEntitlementsTitle": "Other rights"}


class Driver:
    current_url = ORIGIN + TRANSCRIPT_PATH

    def __init__(self, replies):
        self.replies = iter(replies)
        self.requests = []

    def execute_async_script(self, script, path, method, limit):
        self.requests.append((path, method))
        return next(self.replies)

    def execute_script(self, script, html, rights):
        return [right["name"] for right in rights]


def html_reply(principal="101", signed=True):
    return {"status": 200, "type": "text/html", "text": account_html(principal, signed)}


def json_reply(data=None):
    return {"status": 200, "type": "application/json", "text": json.dumps(data or rights_json())}


def browser(replies):
    result = LaplandBrowser(Driver(replies))
    result._spacing = lambda: None
    return result


def test_fresh_account_checked_on_both_sides_of_rights_read():
    result = browser([html_reply(), json_reply(), html_reply()])
    identity = result.check()
    assert len(identity.rights) == 2 and identity.rights[0].linked_keys == ("102",)
    assert len(identity.principal) == 64 and identity.principal != "101"
    assert result.driver.requests == [(TRANSCRIPT_PATH, "GET"), (RIGHTS_PATH, "POST"), (TRANSCRIPT_PATH, "GET")]
    changed = browser([html_reply(), json_reply(), html_reply("202")])
    with pytest.raises(PeppiError) as exc:
        changed.check()
    assert exc.value.code == "STUDY_CONTEXT_CHANGED"


@pytest.mark.parametrize("reply,code", [
    ({"redirect": True}, "SIGN_IN_NEEDED"),
    ({"status": 401}, "SIGN_IN_NEEDED"),
    ({"status": 403}, "ACCESS_DENIED"),
    ({"too_large": True}, "SOURCE_TOO_LARGE"),
    ({"network_error": True}, "SOURCE_UNAVAILABLE"),
    ({"status": 500}, "SOURCE_UNAVAILABLE"),
    (html_reply(signed=False), "SIGN_IN_NEEDED"),
    ({"status": 200, "type": "text/html", "text": "<form>Login</form>"}, "PERSONAL_VIEW_INVALID"),
])
def test_authentication_and_source_failures_are_not_empty_success(reply, code):
    with pytest.raises(PeppiError) as exc:
        browser([reply]).check()
    assert exc.value.code == code


def test_unexpected_origin_and_unapproved_path_make_no_fetch():
    result = browser([])
    result.driver.current_url = "http://" + ORIGIN.split("://")[1] + TRANSCRIPT_PATH
    with pytest.raises(PeppiError) as exc:
        result.check()
    assert exc.value.code == "SIGN_IN_NEEDED" and not result.driver.requests
    result.driver.current_url = ORIGIN + TRANSCRIPT_PATH
    with pytest.raises(PeppiError) as exc:
        result._fetch("/unverified-api")
    assert exc.value.code == "SOURCE_REDIRECT_BLOCKED" and not result.driver.requests
    for path, method in [(TRANSCRIPT_PATH, "POST"), (RIGHTS_PATH, "GET")]:
        with pytest.raises(PeppiError) as exc:
            result._fetch(path, method)
        assert exc.value.code == "SOURCE_REDIRECT_BLOCKED" and not result.driver.requests


@pytest.mark.parametrize("mutation", ["duplicates", "no_selected", "multiple_selected", "new_field", "invalid_id", "historic"])
def test_rights_schema_cannot_hide_ambiguity(mutation):
    data = rights_json()
    items = data["entitlementCollections"][0]["entitlements"]
    if mutation == "duplicates":
        items[1]["id"] = items[0]["id"]
    elif mutation == "no_selected":
        items[0]["selected"] = False
    elif mutation == "multiple_selected":
        items[1]["selected"] = True
    elif mutation == "new_field":
        items[0]["unreviewed"] = "value"
    elif mutation == "invalid_id":
        items[0]["id"] = "../../another-account"
    else:
        items[0]["oldEntitlement"] = True
    with pytest.raises(PeppiError):
        parse_rights(data)


def test_principal_never_comes_from_an_ambiguous_or_anonymous_page():
    for html in (account_html("0"), account_html() + account_html("202"), "<html/>"):
        with pytest.raises(PeppiError):
            parse_principal(html)


def test_completed_filter_waits_for_old_rows_to_be_replaced(monkeypatch):
    import copy
    from peppi_mcp.adapters.lapland_browser import COLLECT
    from peppi_mcp.services.live import Identity, SourceRight
    from tests.unit.test_lapland_transcript_view import observation
    good = observation()
    good["study_right_id"] = "101"
    old = copy.deepcopy(good)
    old["rows"][0].update(source_status="Fictional pending status", grade="")
    projections = iter([old, old, {"pending":True}, good, good])
    class Control:
        def is_selected(self):
            return False
    class FixtureDriver:
        current_url = ORIGIN + TRANSCRIPT_PATH
        def get(self, url):
            assert url == self.current_url
        def find_elements(self, by, selector):
            return [object()] if selector == "#transcript .transcript-entitlement-div" else []
        def find_element(self, by, selector):
            return Control()
        def execute_script(self, script, argument):
            if script == COLLECT:
                return next(projections)
            assert script == "arguments[0].click()"
    reader = LaplandBrowser(FixtureDriver())
    reader._rights = lambda: ([{"id":"101","selected":True}], {})
    reader._spacing = lambda: None
    monkeypatch.setattr("peppi_mcp.adapters.lapland_browser.time.sleep", lambda seconds: None)
    right = SourceRight("101", "Fictional degree")
    result = reader.read(right, Identity("fictional-account", (right,)))
    assert len(result.achievements) == 2


@pytest.mark.parametrize("failure", [None, "account", "right", "version", "removed"])
def test_selected_plan_refresh_uses_observed_url_and_revalidates_context(monkeypatch, failure):
    from datetime import datetime, timedelta, timezone
    from peppi_mcp.adapters.lapland_study_plan import PLAN_URL, PLAN_METADATA, COLLECT_PLAN
    from peppi_mcp.services.live import Identity, SourceRight
    from tests.plan_fixtures import metadata, projection, version_url

    class Clock:
        value = datetime(2026, 1, 1, tzinfo=timezone.utc)

        @classmethod
        def now(cls, zone):
            cls.value += timedelta(seconds=1)
            return cls.value.astimezone(zone)

    monkeypatch.setattr("peppi_mcp.adapters.lapland_browser.datetime", Clock)

    class PlanDriver:
        current_url = ORIGIN + TRANSCRIPT_PATH
        page_source = account_html()
        failure = None

        def __init__(self):
            self.navigations = []

        def get(self, url):
            self.current_url = url
            self.navigations.append(url)

        def find_elements(self, by, selector):
            assert selector == "structure"
            return [object()]

        def execute_async_script(self, script, path, method, limit):
            if path == RIGHTS_PATH:
                return json_reply()
            return html_reply("202" if self.failure == "account" else "101")

        def execute_script(self, script):
            if script == PLAN_METADATA:
                raw = metadata("102" if self.failure == "right" else "101")
                if self.current_url == version_url("502") and self.failure != "version":
                    raw.update(current_url=version_url("502"), header="FICTION2026 Hops-versio: 1 (Hyväksytty)")
                if self.failure == "removed":
                    raw["versions"] = raw["versions"][:1]
                return raw
            if script == COLLECT_PLAN:
                raw = projection()
                for node in raw["nodes"]:
                    node["plan_key"] = "502"
                return raw
            return None  # Local filter and collapse controls.

        def quit(self): pass

    driver = PlanDriver()
    reader = LaplandBrowser(driver)
    reader._spacing = lambda: None
    monkeypatch.setattr("peppi_mcp.adapters.lapland_browser.time.sleep", lambda _: None)
    right = SourceRight("101", "Fictional degree")
    identity = Identity(parse_principal(account_html()), (right,))
    with pytest.raises(PeppiError, match="Select a recorded HOPS version"):
        reader.read_plan(right, identity, "502")
    assert not driver.navigations
    reader.list_plans(right, identity)
    driver.failure = failure
    if failure:
        with pytest.raises(PeppiError):
            reader.read_plan(right, identity, "502")
    else:
        first = reader.read_plan(right, identity, "502")
        second = reader.read_plan(right, identity, "502")
        assert first.id == second.id and second.listing.retrieved_at > first.listing.retrieved_at
        assert driver.navigations == [PLAN_URL, version_url("502"), version_url("502")]
        with pytest.raises(PeppiError):
            reader.read_plan(SourceRight("102", "Other right"), identity, "502")
    reader.close()
    assert not reader._plan_urls
