"""Selection and privacy errors cannot fall back to another browser/profile."""
import json
import sys
import pytest

from peppi_mcp.config import Config, parse_config
from peppi_mcp.errors import PeppiError
from peppi_mcp import browser_runtime


@pytest.mark.parametrize("values", [{"browser":"chrome"}, {"mode":"live","browser":"edge"},
    {"mode":"imported","browser":"firefox","profile":"x","snapshot":"import:x"}])
def test_browser_selection_is_explicit_and_live_only(values):
    with pytest.raises(ValueError, match="CONFIGURATION_ERROR"):
        Config(**values)


def test_cli_defaults_and_explicit_chrome(monkeypatch):
    monkeypatch.delenv("PEPPI_MCP_MODE", raising=False)
    monkeypatch.setattr(sys,"argv",["peppi-mcp","--mode","live"])
    assert parse_config().browser is None
    monkeypatch.setattr(sys,"argv",["peppi-mcp","--mode","live","--browser","chrome"])
    assert parse_config().browser == "chrome"


def test_missing_chrome_does_not_launch_firefox(monkeypatch, tmp_path):
    pytest.importorskip("selenium")
    monkeypatch.setattr(browser_runtime,"chrome_binary",lambda: None)
    monkeypatch.setattr(browser_runtime,"open_firefox",lambda **kwargs: pytest.fail("Silent browser fallback"))
    with pytest.raises(PeppiError) as error:
        browser_runtime.open_browser("chrome",profile_root=tmp_path)
    assert error.value.code == "BROWSER_UNAVAILABLE"
    assert not list(tmp_path.iterdir())


def test_chrome_private_options_and_secret_safe_failed_start(monkeypatch, tmp_path):
    webdriver = pytest.importorskip("selenium.webdriver")
    from selenium.common.exceptions import WebDriverException
    monkeypatch.setattr(browser_runtime,"chrome_binary",lambda: tmp_path / "chrome.exe")
    monkeypatch.setenv("CHROME_LOG_FILE", "PRIVATE_SECRET")
    captured = {}
    def fail(**kwargs):
        captured.update(kwargs)
        raise WebDriverException("PRIVATE_SECRET https://private.example/credential")
    monkeypatch.setattr(webdriver,"Chrome",fail)
    with pytest.raises(PeppiError) as error:
        browser_runtime.open_chrome(profile_root=tmp_path)
    assert error.value.code == "BROWSER_UNAVAILABLE" and "PRIVATE_SECRET" not in error.value.message
    options = captured["options"].to_capabilities()["goog:chromeOptions"]
    assert "--remote-debugging-pipe" in options["args"] and "--incognito" in options["args"]
    assert str(tmp_path / "chrome-profile") in next(a for a in options["args"] if a.startswith("--user-data-dir="))
    assert options["prefs"]["profile.password_manager_enabled"] is False
    assert "CHROME_LOG_FILE" not in captured["service"].env
    assert options.get("detach", False) is False
    with pytest.raises(PeppiError):
        browser_runtime.open_chrome(profile_root=tmp_path)

