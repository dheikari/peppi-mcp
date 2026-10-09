"""Release evidence must fail closed when packaging omits or changes it."""
import pytest

from tools import release_check as release


@pytest.fixture
def source(tmp_path):
    for name in (*release.RELEASE_DOCUMENTS, "LICENSE", "pyproject.toml",
                 "src/peppi_mcp/__init__.py", "tools/smoke_installed.py"):
        destination = tmp_path/name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((release.ROOT/name).read_bytes())
    return tmp_path


def package(source, wheel):
    prefix = f"peppi_mcp-{release.VERSION}"
    metadata = (f"Name: peppi-mcp\nVersion: {release.VERSION}\nLicense-Expression: MIT\n"
                "License-File: LICENSE\nDescription-Content-Type: text/markdown\n\n").encode()
    metadata += (source/"README.md").read_bytes()
    if wheel:
        return {f"{prefix}.dist-info/METADATA": metadata,
                f"{prefix}.dist-info/licenses/LICENSE": (source/"LICENSE").read_bytes(),
                "peppi_mcp/__init__.py": (source/"src/peppi_mcp/__init__.py").read_bytes()}
    return {f"{prefix}/{name}": (source/name).read_bytes()
            for name in (*release.RELEASE_DOCUMENTS, "LICENSE", "src/peppi_mcp/__init__.py")} | {f"{prefix}/PKG-INFO": metadata}


def test_source_version_and_license_evidence_agrees(source):
    release.validate_source_metadata(source)


@pytest.mark.parametrize("name", ["pyproject.toml", "src/peppi_mcp/__init__.py", "tools/smoke_installed.py", "release_version"])
def test_each_version_reference_must_agree(source, monkeypatch, name):
    if name == "release_version":
        monkeypatch.setattr(release, "VERSION", "0.1.0a2")
    else:
        path = source/name
        path.write_bytes(path.read_bytes().replace(release.VERSION.encode(), b"0.1.0a2"))
    with pytest.raises(AssertionError):
        release.validate_source_metadata(source)


@pytest.mark.parametrize("name", ["CONTRIBUTING.md", "CHANGELOG.md"])
def test_missing_release_document_blocks_source_validation(source, name):
    (source/name).unlink()
    with pytest.raises(AssertionError, match="Required release document"):
        release.validate_source_metadata(source)


def test_source_license_cannot_be_replaced_by_a_different_notice(source):
    (source/"LICENSE").write_text("MIT License\nFICTIONAL replacement notice\n")
    with pytest.raises(AssertionError, match="license text"):
        release.validate_source_metadata(source)


@pytest.mark.parametrize("wheel", [True, False])
def test_complete_packaged_evidence_passes(source, wheel):
    release.validate_packaged_evidence(package(source, wheel), wheel=wheel, root=source)


@pytest.mark.parametrize("wheel", [True, False])
@pytest.mark.parametrize("defect", ["metadata", "version", "license_expression", "license_file", "license_contents", "readme", "missing_source", "changed_source", "unexpected_source"])
def test_packaging_evidence_defects_are_rejected(source, wheel, defect):
    files = package(source, wheel)
    metadata = next(name for name in files if name.endswith(("/METADATA", "/PKG-INFO")))
    license = next(name for name in files if name.endswith("/LICENSE"))
    code = next(name for name in files if name.endswith("/__init__.py"))
    if defect == "metadata":
        del files[metadata]
    elif defect == "version":
        files[metadata] = files[metadata].replace(f"Version: {release.VERSION}".encode(), b"Version: 0.1.0a2")
    elif defect == "license_expression":
        files[metadata] = files[metadata].replace(b"License-Expression: MIT", b"License-Expression: BSD-3-Clause")
    elif defect == "license_file":
        files[metadata] = files[metadata].replace(b"License-File: LICENSE\n", b"")
    elif defect == "license_contents":
        files[license] += b"FICTIONAL altered license"
    elif defect == "readme":
        files[metadata] += b"FICTIONAL outdated description"
    elif defect == "missing_source":
        del files[code]
    elif defect == "changed_source":
        files[code] += b"# FICTIONAL changed code"
    else:
        files[code.replace("__init__.py", "private_diagnostic.py")] = b"# FICTIONAL unexpected module"
    with pytest.raises(AssertionError):
        release.validate_packaged_evidence(files, wheel=wheel, root=source)


@pytest.mark.parametrize("name", release.RELEASE_DOCUMENTS)
def test_release_documents_must_be_present_in_source_archive(source, name):
    files = package(source, False)
    del files[f"peppi_mcp-{release.VERSION}/{name}"]
    with pytest.raises(AssertionError, match="omits or changes"):
        release.validate_packaged_evidence(files, wheel=False, root=source)
