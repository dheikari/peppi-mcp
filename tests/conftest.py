import pytest

from peppi_mcp.adapters.synthetic import SyntheticSource


def pytest_addoption(parser):
    parser.addoption("--require-browser", action="store_true", help="Fail instead of skipping required Windows browser checks")
    parser.addoption("--require-chrome", action="store_true", help="Fail instead of skipping required Windows Chrome checks")
    parser.addoption("--browser-tests", choices=("firefox", "chrome", "both"), default="both", help="Local browser fixture matrix")


def pytest_sessionstart(session):
    if session.config.getoption("--require-browser") or session.config.getoption("--require-chrome"):
        import os
        os.environ["SE_OFFLINE"] = "true"
        from tests.test_firefox_runtime import AVAILABLE
        if session.config.getoption("--require-browser") and not AVAILABLE:
            raise pytest.UsageError("Required live test runtime is missing: install [live] and Firefox on Windows.")
        if session.config.getoption("--require-chrome") and not browser_available("chrome"):
            raise pytest.UsageError("Required Chrome runtime is missing: install [live] and Google Chrome on Windows.")


def browser_available(name):
    import importlib.util
    import os
    from peppi_mcp.browser_runtime import chrome_binary
    from tests.test_firefox_runtime import AVAILABLE
    return AVAILABLE if name == "firefox" else os.name == "nt" and importlib.util.find_spec("selenium") is not None and chrome_binary() is not None


@pytest.fixture(params=("firefox", "chrome"))
def browser_case(request, monkeypatch):
    name = request.param
    selection = request.config.getoption("--browser-tests")
    if selection not in ("both", name):
        pytest.skip("Browser excluded by explicit test selection")
    if not browser_available(name):
        pytest.skip("Optional Windows browser runtime is not installed")
    monkeypatch.setenv("PEPPI_TEST_BROWSER", name)
    return name


@pytest.fixture
def browser_factory(browser_case, tmp_path):
    from peppi_mcp.browser_runtime import open_browser
    from peppi_mcp.runtime_storage import RuntimeLease
    drivers, leases = [], []
    def launch():
        lease = RuntimeLease(root=tmp_path / "runtime", recover=False)
        leases.append(lease)
        driver = open_browser(browser_case, headless=True, profile_root=lease.path)
        drivers.append(driver)
        return driver
    yield launch
    for driver in drivers:
        process = driver.service.process
        if process is not None and process.poll() is None:
            driver.quit()
    for lease in leases:
        assert lease.close(), "Fictional owned browser profile cleanup failed"


@pytest.fixture
def snapshot():
    return SyntheticSource().snapshot()
