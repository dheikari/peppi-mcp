"""Private local worker protocol, not an MCP tool or network listener."""

import json
import os
import sys
from dataclasses import asdict

from peppi_mcp.adapters.lapland_browser import LaplandBrowser
from peppi_mcp.errors import PeppiError
from peppi_mcp.services.live import Identity, SourceRight
from peppi_mcp.worker_protocol import MAX_REQUEST, MAX_REPLY, decode, validate_request


def main():
    browser = LaplandBrowser(browser=os.environ.get("PEPPI_BROWSER", "firefox"))
    try:
        while line := sys.stdin.buffer.readline(MAX_REQUEST + 1):
            try:
                request = validate_request(decode(line, MAX_REQUEST))
            except Exception:
                break  # Invalid framing is fatal, never echo an untrusted ID.
            try:
                action = request["action"]
                if action == "close":
                    break
                if action == "open":
                    browser.open()
                    data = {"opened": True}
                elif action == "check":
                    data = asdict(browser.check())
                elif action in {"read", "list_plans", "read_plan"}:
                    right = SourceRight(**request["right"])
                    identity = Identity(request["identity"]["principal"],
                        tuple(SourceRight(**item) for item in request["identity"]["rights"]))
                    if action == "read_plan":
                        response = browser.read_plan(right, identity, request["plan_key"])
                    else:
                        response = getattr(browser, action)(right, identity)
                    data = response.model_dump(mode="json")
                else:
                    raise ValueError
                reply = {"ok": True, "data": data}
            except PeppiError as exc:
                reply = {"ok": False, "code": exc.code, "message": exc.message, "retryable": exc.retryable, "retry_after_seconds": exc.retry_after_seconds}
            except Exception as exc:
                # Classify without serializing exception text (which may contain
                # a private URL, response, or session identifier).
                from selenium.common.exceptions import InvalidSessionIdException, NoSuchWindowException
                from selenium.common.exceptions import TimeoutException
                fatal = isinstance(exc, (InvalidSessionIdException, NoSuchWindowException, TimeoutException))
                known = {"ElementNotInteractableException", "ElementClickInterceptedException",
                         "JavascriptException", "TimeoutException", "NoSuchElementException",
                         "InvalidSessionIdException", "NoSuchWindowException", "WebDriverException"}
                fatal = fatal or type(exc).__name__ == "WebDriverException" or type(exc).__name__ not in known
                category = type(exc).__name__ if type(exc).__name__ in known else "internal adapter error"
                reply = {"ok": False, "code": "BROWSER_UNAVAILABLE" if fatal else "PERSONAL_VIEW_INVALID",
                         "message": "Browser operation failed (" + category + "); source and credential details were omitted.",
                         "retryable": False, "retry_after_seconds": None}
            reply.update(id=request["id"], action=request["action"])
            encoded = json.dumps(reply, ensure_ascii=True) + "\n"
            if len(encoded.encode()) > MAX_REPLY:
                break
            sys.stdout.write(encoded)
            sys.stdout.flush()
    finally:
        browser.close()


if __name__ == "__main__":
    main()
