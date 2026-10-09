"""Private bounded worker envelope; no public fault controls or arbitrary commands."""
import json

MAX_REQUEST = 65536
MAX_REPLY = 2 * 1024 * 1024
ACTIONS = {"open", "close", "check", "read", "list_plans", "read_plan"}
SAFE_ERRORS = {
    "SIGN_IN_NEEDED": "Complete sign-in in the connector-owned browser window.",
    "ACCESS_DENIED": "Peppi denied this personal read.",
    "STUDY_CONTEXT_CHANGED": "The authenticated account, right or plan context changed. Reconnect and select it again.",
    "BROWSER_UNAVAILABLE": "The connector browser failed or an operation was interrupted. Verify the selected Firefox/geckodriver or Google Chrome/ChromeDriver installation, then reconnect.",
    "BROWSER_DEPENDENCY_MISSING": "Install the optional [live] extra and the documented selected browser runtime.",
    "PERSONAL_VIEW_INVALID": "The personal source has an unsupported layout or schema; no records were returned.",
    "PERSONAL_VIEW_INCOMPLETE": "The selected unfiltered view did not become complete; no records were returned.",
    "CAPABILITY_UNAVAILABLE": "This source operation is not supported by the verified reader.",
    "SOURCE_REDIRECT_BLOCKED": "The operation is outside the verified Peppi read routes.",
    "SOURCE_TOO_LARGE": "The personal response exceeded the configured size limit.",
    "SOURCE_UNAVAILABLE": "The personal source could not be read. No stale result was substituted.",
    "PLAN_NOT_FOUND": "Discover recorded versions again and explicitly select one for this connection and right.",
    "RATE_LIMITED": "Peppi requested a pause; no automatic retry was made.",
}


def decode(line, limit):
    if not line or len(line) > limit or not line.endswith(b"\n"):
        raise ValueError
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError
            result[key] = value
        return result
    def invalid(_): raise ValueError
    value = json.loads(line.decode("utf-8"), object_pairs_hook=unique, parse_constant=invalid)
    if not isinstance(value, dict):
        raise ValueError
    return value


def validate_request(value):
    action = value.get("action")
    if (type(value.get("id")) is not int or not 0 < value["id"] < 2**53 or action not in ACTIONS):
        raise ValueError
    expected = {"id", "action"}
    if action in {"read", "list_plans", "read_plan"}:
        expected |= {"right", "identity"}
    if action == "read_plan":
        expected.add("plan_key")
    if set(value) != expected:
        raise ValueError
    return value


def validate_reply(reply, request):
    if (type(reply.get("id")) is not int or reply["id"] != request["id"]
            or reply.get("action") != request["action"] or type(reply.get("ok")) is not bool):
        raise ValueError
    if reply["ok"]:
        if set(reply) != {"id", "action", "ok", "data"} or not isinstance(reply["data"], dict):
            raise ValueError
    else:
        if (set(reply) != {"id", "action", "ok", "code", "message", "retryable", "retry_after_seconds"}
                or reply["code"] not in SAFE_ERRORS
                or not isinstance(reply["message"], str) or len(reply["message"]) > 500
                or type(reply["retryable"]) is not bool
                or (reply["retry_after_seconds"] is not None and
                    (type(reply["retry_after_seconds"]) is not int or not 1 <= reply["retry_after_seconds"] <= 86400))):
            raise ValueError
    return reply
