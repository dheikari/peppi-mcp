"""Explicit browser selection; every Chrome launch uses an owned fresh profile."""

import os
import subprocess
from pathlib import Path

from peppi_mcp.errors import PeppiError
from peppi_mcp.firefox_runtime import open_firefox


def chrome_binary():
    candidates = [Path(os.environ.get("PROGRAMFILES", r"C:\Program Files")),
                  Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"))]
    if os.environ.get("LOCALAPPDATA"):
        candidates.append(Path(os.environ["LOCALAPPDATA"]))
    return next((root / "Google/Chrome/Application/chrome.exe" for root in candidates
                 if (root / "Google/Chrome/Application/chrome.exe").is_file()), None)


def open_chrome(*, headless=False, profile_root):
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
        from selenium.common.exceptions import WebDriverException
    except ImportError:
        raise PeppiError("BROWSER_DEPENDENCY_MISSING", "Install the project with the optional [live] extra.") from None
    binary = chrome_binary()
    if binary is None:
        raise PeppiError("BROWSER_UNAVAILABLE", "Install Google Chrome in its standard Windows installation location; see the live setup instructions.")
    # The backend supplies a validated RuntimeLease, never a caller's normal
    # browser profile. Refuse reuse even within this lease after failed startup.
    try:
        root = Path(profile_root)
        profile = root / "chrome-profile"
        profile.mkdir(exist_ok=False)
    except (TypeError, OSError):
        raise PeppiError("BROWSER_UNAVAILABLE", "Chrome requires a fresh connector-owned profile. Disconnect before reconnecting.") from None
    os.environ["SE_AVOID_STATS"] = "true"
    options = Options()
    options.binary_location = str(binary)
    options.page_load_strategy = "eager"
    options.accept_insecure_certs = False
    for argument in (f"--user-data-dir={profile}", "--incognito", "--remote-debugging-pipe",
                     "--no-first-run", "--no-default-browser-check", "--disable-sync",
                     "--disable-background-networking", "--disable-breakpad", "--disable-logging"):
        options.add_argument(argument)
    if headless:
        options.add_argument("--headless=new")
    options.add_experimental_option("prefs", {"credentials_enable_service": False,
        "profile.password_manager_enabled": False, "autofill.profile_enabled": False,
        "autofill.credit_card_enabled": False, "download.default_directory": str(profile / "downloads")})
    environment = dict(os.environ)
    environment.pop("CHROME_LOG_FILE", None)
    try:
        driver = webdriver.Chrome(options=options, service=Service(log_output=subprocess.DEVNULL, env=environment))
    except WebDriverException:
        raise PeppiError("BROWSER_UNAVAILABLE", "Chrome could not start. Verify its installation and allow Selenium Manager to obtain a matching ChromeDriver; see the live setup instructions.") from None
    try:
        driver.set_page_load_timeout(20)
        driver.set_script_timeout(20)
    except BaseException:
        driver.quit()
        raise
    return driver


def open_browser(browser, *, headless=False, profile_root=None):
    if browser == "firefox":
        return open_firefox(headless=headless, profile_root=profile_root)
    if browser == "chrome":
        return open_chrome(headless=headless, profile_root=profile_root)
    raise ValueError("Unsupported browser selection")
