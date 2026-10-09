"""Redacted route metadata helpers; no browser startup or command evaluator."""

import re
import threading
from urllib.parse import parse_qs, urlsplit


ORIGIN = "https://opiskelija-lay.peppi4.lapit.csc.fi"


def shape(value, depth=0):
    if depth > 5:
        return type(value).__name__
    if isinstance(value, dict):
        return {key: shape(item, depth + 1) for key, item in list(value.items())[:80]}
    if isinstance(value, list):
        return {"type": "array", "count": len(value), "item": shape(value[0], depth + 1) if value else None}
    return type(value).__name__


def safe_route(url):
    path = urlsplit(url).path
    if path.startswith("/delegate/user-image/"):
        return "/delegate/user-image/{account}"
    return re.sub(r"[0-9a-fA-F]{8,}|\d+", "{id}", path)


class NetworkObservation:
    def __init__(self, driver):
        from selenium.webdriver.common.bidi.network import NetworkEvent
        from selenium.webdriver.common.bidi.common import command_builder
        self.rows = []
        self.lock = threading.Lock()
        # Subscribe passively; do not intercept or modify login/network traffic.
        self.connection = driver.network.conn
        self.connection.add_callback(NetworkEvent("network.responseCompleted"), self.receive)
        self.connection.execute(command_builder("session.subscribe", {"events": ["network.responseCompleted"]}))

    def receive(self, event):
        try:
            request, response = event.params["request"], event.params["response"]
            url = request["url"]
            if urlsplit(url).netloc != urlsplit(ORIGIN).netloc:
                return
            content_type = response.get("mimeType", "")
            if not any(kind in content_type for kind in ("html", "json", "text/plain")):
                return
            row = {"method": request["method"], "route": safe_route(url),
                   "query_names": sorted(parse_qs(urlsplit(url).query)),
                   "status": response["status"], "content_type": content_type,
                   "credential_header_names": sorted(header["name"] for header in request.get("headers", [])
                       if header["name"].lower() in {"cookie", "authorization", "x-csrf-token"})}
            with self.lock:
                self.rows.append(row)
                del self.rows[:-200]
        except Exception:
            pass  # Raw BiDi diagnostics may contain credentials.

    def report(self):
        with self.lock:
            return list(self.rows)



