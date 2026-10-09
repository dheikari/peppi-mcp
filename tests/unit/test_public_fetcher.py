import io
from datetime import datetime, timezone
from email.message import Message
from urllib.error import HTTPError, URLError

import pytest

from peppi_mcp.adapters.public_catalogue import HOST, MAX_BYTES, NoRedirect, PublicFetcher, retry_delay
from peppi_mcp.errors import PeppiError


class Response(io.BytesIO):
    status = 200

    def __init__(self, body=b'{}', content_type="application/json"):
        super().__init__(body)
        self.headers = Message()
        self.headers["Content-Type"] = content_type


class Opener:
    def __init__(self, response):
        self.response, self.calls = response, []

    def open(self, request, timeout):
        self.calls.append((request, timeout))
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def test_fixed_host_get_and_unicode_encoding():
    opener = Opener(Response(b'{"fraction":2.5}'))
    result = PublicFetcher(opener=opener).fetch("/api/lu/units/%C3%A4%C3%B6%C5%A1/COURSE_UNIT")
    assert str(result["fraction"]) == "2.5"
    request, timeout = opener.calls[0]
    assert request.full_url.startswith(HOST + "/api/") and request.method == "GET" and request.data is None
    assert timeout == 8 and "Authorization" not in request.headers and "Cookie" not in request.headers
    assert NoRedirect().redirect_request(None, None, 302, None, None, "https://other.invalid") is None


@pytest.mark.parametrize("path", ["https://other.invalid", "/api/course/../private", "/api/course/1?other=2", "/api/course/1#part", "/api/course/1/", "/api/course/1\n"])
def test_unobserved_paths_never_reach_network(path):
    opener = Opener(Response())
    with pytest.raises(PeppiError):
        PublicFetcher(opener=opener).fetch(path)
    assert not opener.calls


@pytest.mark.parametrize("response,code", [
    (Response(b'<html>login</html>', "text/html"), "SOURCE_CHANGED"),
    (Response(b'{broken'), "SOURCE_CHANGED"), (Response(b'{"x":NaN}'), "SOURCE_CHANGED"),
    (Response(b' ' * (MAX_BYTES + 1)), "SOURCE_TOO_LARGE"),
    (TimeoutError("secret"), "SOURCE_TIMEOUT"), (URLError("secret"), "SOURCE_UNAVAILABLE"),
])
def test_response_failures_are_bounded_and_safe(response, code):
    with pytest.raises(PeppiError) as error:
        PublicFetcher(opener=Opener(response)).fetch("/api/course/101")
    assert error.value.code == code and "secret" not in error.value.message


@pytest.mark.parametrize("status,code", [(302, "SOURCE_REDIRECT_BLOCKED"), (401, "SOURCE_ACCESS_DENIED"), (403, "SOURCE_ACCESS_DENIED"), (404, "NOT_FOUND"), (500, "SOURCE_UNAVAILABLE")])
def test_http_status_errors(status, code):
    opener = Opener(HTTPError(HOST, status, "private response", Message(), None))
    with pytest.raises(PeppiError) as error:
        PublicFetcher(opener=opener).fetch("/api/course/101")
    assert error.value.code == code


def test_retry_after_cooldown_and_one_second_spacing():
    clock = [0.0]
    def sleep(seconds):
        clock[0] += seconds
    headers = Message()
    headers["Retry-After"] = "120"
    opener = Opener(HTTPError(HOST, 429, "rate limited", headers, None))
    fetcher = PublicFetcher(opener=opener, monotonic=lambda: clock[0], sleep=sleep)
    for _ in range(2):
        with pytest.raises(PeppiError) as error:
            fetcher.fetch("/api/course/101")
        assert error.value.code == "RATE_LIMITED" and error.value.retry_after_seconds == 120
    assert len(opener.calls) == 1
    clock[0] = 121
    opener.response = Response()
    fetcher.fetch("/api/course/101")
    opener.response = Response()
    fetcher.fetch("/api/course/101")
    assert clock[0] == 122
    now = datetime(2026, 10, 3, tzinfo=timezone.utc)
    assert retry_delay("Sat, 03 Oct 2026 00:02:00 GMT", now) == 120
    assert retry_delay("invalid", now) == 60
    assert retry_delay("9999999", now) == 86400
