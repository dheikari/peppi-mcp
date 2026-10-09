"""Connector-owned Firefox startup, using a disposable private profile."""

import os
import subprocess
from pathlib import Path

from peppi_mcp.errors import PeppiError


def open_firefox(*, headless=False, profile_root=None):
    try:
        from selenium import webdriver
        from selenium.webdriver.firefox.options import Options
        from selenium.webdriver.firefox.service import Service
        from selenium.common.exceptions import WebDriverException
    except ImportError:
        raise PeppiError("BROWSER_DEPENDENCY_MISSING", "Install the project with the optional [live] extra.") from None
    binary = Path(os.environ.get("PROGRAMFILES", r"C:\Program Files")) / "Mozilla Firefox" / "firefox.exe"
    if not binary.is_file():
        raise PeppiError("BROWSER_UNAVAILABLE", "This Windows connector requires Firefox installed in Program Files/Mozilla Firefox.")
    os.environ["SE_AVOID_STATS"] = "true"
    options = Options()
    options.binary_location = str(binary)
    options.enable_bidi = True
    options.page_load_strategy = "eager"
    options.accept_insecure_certs = False
    options.set_preference("browser.privatebrowsing.autostart", True)
    options.set_preference("signon.rememberSignons", False)
    options.set_preference("browser.cache.disk.enable", False)
    options.set_preference("browser.sessionstore.resume_from_crash", False)
    if headless:
        options.add_argument("-headless")
    # No existing profile is supplied: geckodriver creates a disposable one.
    try:
        service_args = ["--profile-root", str(profile_root)] if profile_root is not None else []
        driver = webdriver.Firefox(options=options, service=Service(log_output=subprocess.DEVNULL, service_args=service_args))
    except WebDriverException:
        raise PeppiError("BROWSER_UNAVAILABLE", "Firefox could not start. Verify its Program Files installation and allow Selenium Manager to obtain geckodriver; see the live setup instructions.") from None
    try:
        driver.set_page_load_timeout(20)
        driver.set_script_timeout(20)
    except BaseException:
        driver.quit()
        raise
    return driver
