import socket

import pytest

from peppi_mcp.adapters.synthetic import SyntheticSource
from peppi_mcp.config import Config
from peppi_mcp.personal_access import personal_access_readiness
from peppi_mcp.server import Application


def test_available_live_mode_does_not_claim_an_immutable_mode_session(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Readiness reporting must not attempt sign-in or network discovery")
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    app = Application(SyntheticSource())
    status = app.call("get_connection_status", {}).structured_content["data"]
    assert status["personal_connection"] == "not_enabled"
    assert status["sign_in_needed"] is False  # Immutable mode does not open a personal session.
    readiness = status["personal_access"]
    assert readiness["state"] == "live_mode_available" and readiness["live_data_verified"] is True
    assert readiness["client_authentication"] and readiness["supported_personal_routes"] == ["browser_session_json_rights_and_rendered_transcript"]
    assert readiness["observed_browser_sign_in"]["verification_scope"] == "owner_completed_isolated_browser_sign_in"
    assert readiness["observed_browser_sign_in"]["is_current_health_check"] is False
    assert readiness["live_data_verification_scope"] == "mcp_adapter"
    observation = readiness["observed_personal_ui"]
    assert observation["verification_scope"] == "owner_signed_in_read_only_inspection"
    assert observation["completed_fields_reconciled_with_import"] is True
    assert observation["repeated_page_read_verified"] is True
    assert observation["is_current_health_check"] is False
    assert observation["establishes_mcp_session"] is False
    assert "list_enrolments" not in app.tools
    assert app.call("list_enrolments", {}).structured_content["error"]["code"] == "CAPABILITY_UNAVAILABLE"


def test_readiness_reports_do_not_share_mutable_evidence():
    one = personal_access_readiness()
    one["supported_personal_routes"].append("invented")
    one["observed_browser_sign_in"]["verification_scope"] = "untrue"
    one["observed_personal_ui"]["observed_components"].append("invented")
    two = personal_access_readiness()
    assert two["supported_personal_routes"] == ["browser_session_json_rights_and_rendered_transcript"]
    assert two["observed_browser_sign_in"]["verification_scope"] == "owner_completed_isolated_browser_sign_in"
    assert "invented" not in two["observed_personal_ui"]["observed_components"]


def test_live_mode_is_opt_in_and_disallows_import_selection():
    assert Config(mode="live").mode == "live"
    with pytest.raises(ValueError, match="import selection"):
        Config(mode="live", profile="fictional")
