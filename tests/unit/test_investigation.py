import json
import threading
from types import SimpleNamespace

from peppi_mcp.investigate import NetworkObservation, ORIGIN, safe_route, shape


def observer():
    observation = object.__new__(NetworkObservation)
    observation.rows = []
    observation.lock = threading.Lock()
    return observation


def event(url, *, content_type="application/json"):
    return SimpleNamespace(params={
        "request": {"url": url, "method": "GET", "headers": [
            {"name": "Cookie", "value": {"type": "string", "value": "PRIVATE_COOKIE"}},
            {"name": "Authorization", "value": {"type": "string", "value": "PRIVATE_BEARER"}}]},
        "response": {"status": 200, "mimeType": content_type},
    })


def test_network_metadata_drops_credentials_and_parameter_values():
    observation = observer()
    observation.receive(event(ORIGIN + "/records/123456?p_auth=PRIVATE_CSRF&studyRight=PRIVATE_RIGHT"))
    report = observation.report()
    serialized = json.dumps(report)
    assert len(report) == 1 and "PRIVATE" not in serialized
    assert report[0]["route"] == "/records/{id}"
    assert report[0]["query_names"] == ["p_auth", "studyRight"]
    assert report[0]["credential_header_names"] == ["Authorization", "Cookie"]


def test_identity_provider_other_origins_assets_and_bad_events_are_ignored():
    observation = observer()
    for url in ["https://haka.funet.fi/shibboleth/WAYF", ORIGIN + ".example.invalid/records", "https://example.invalid/"]:
        observation.receive(event(url))
    observation.receive(event(ORIGIN + "/image.png", content_type="image/png"))
    observation.receive(SimpleNamespace(params={"request": {}}))
    assert observation.report() == []


def test_network_metadata_is_bounded():
    observation = observer()
    for index in range(250):
        observation.receive(event(ORIGIN + "/records/" + str(index)))
    assert len(observation.report()) == 200


def test_shape_does_not_return_scalar_personal_values():
    data = {"student": "PRIVATE_NAME", "records": [{"title": "PRIVATE_COURSE", "credits": 5}]}
    assert "PRIVATE" not in json.dumps(shape(data))
    assert safe_route(ORIGIN + "/record/abcdef123456?p_auth=SECRET") == "/record/{id}"
    assert safe_route(ORIGIN + "/delegate/user-image/fictional.name") == "/delegate/user-image/{account}"
