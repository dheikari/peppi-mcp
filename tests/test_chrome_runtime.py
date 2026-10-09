"""Chrome isolation on local fiction; lifecycle failures run through stdio."""
import pytest


def test_new_context_has_no_previous_browser_state(browser_case, browser_factory):
    from tests.local_peppi import local_peppi
    with local_peppi() as (origin, state):
        driver = browser_factory()
        assert driver.capabilities["browserName"] == browser_case
        assert driver.capabilities["acceptInsecureCerts"] is False
        driver.get(origin)
        driver.execute_script("document.cookie='fictional=PRIVATE_SECRET; path=/'; localStorage.setItem('fictional','PRIVATE_SECRET')")
        assert driver.execute_script("return document.cookie")
        first = driver.capabilities.get("chrome", {}).get("userDataDir") or driver.capabilities.get("moz:profile")
        driver.quit()
        next_driver = browser_factory()
        next_driver.get(origin)
        assert next_driver.execute_script("return document.cookie") == ""
        assert next_driver.execute_script("return localStorage.getItem('fictional')") is None
        second = next_driver.capabilities.get("chrome", {}).get("userDataDir") or next_driver.capabilities.get("moz:profile")
        assert first and second and first != second
