"""A public README logo must not exempt unrelated images from privacy checks."""
import pytest

from tools.release_check import ROOT, VERSION, inspect_file


@pytest.mark.parametrize("name", [
    "docs/assets/peppi-mcp-logo.png",
    f"peppi_mcp-{VERSION}/docs/assets/peppi-mcp-logo.png",
])
def test_selected_logo_passes_source_and_distribution_inspection(name):
    inspect_file(name, (ROOT / "docs/assets/peppi-mcp-logo.png").read_bytes(), [])


@pytest.mark.parametrize("name", [
    "docs/assets/screenshot.png",
    "docs/assets/peppi-mcp-logo-copy.png",
    "private/docs/assets/peppi-mcp-logo.png",
    "unrelated/docs/assets/peppi-mcp-logo.png",
])
def test_unselected_images_remain_rejected_even_with_the_same_content(name):
    with pytest.raises(AssertionError):
        inspect_file(name, (ROOT / "docs/assets/peppi-mcp-logo.png").read_bytes(), [])


def test_replacing_logo_with_other_content_requires_new_inspection():
    content = (ROOT / "docs/assets/peppi-mcp-logo.png").read_bytes()
    with pytest.raises(AssertionError):
        inspect_file("docs/assets/peppi-mcp-logo.png", content + b"FICTIONAL-SECRET", [])


def test_selected_logo_still_checks_private_reference_markers():
    content = (ROOT / "docs/assets/peppi-mcp-logo.png").read_bytes()
    with pytest.raises(AssertionError):
        inspect_file("docs/assets/peppi-mcp-logo.png", content, [content[:8]])
