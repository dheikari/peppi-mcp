"""Credential-free Windows release checks. Dependency downloads are separate."""
import argparse
import ast
import hashlib
import json
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import venv
import zipfile
from email.parser import BytesParser
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.1.0a1"
RELEASE_DOCUMENTS = ("README.md", "SECURITY.md", "CONTRIBUTING.md", "CHANGELOG.md", "docs/demo.md", "docs/release-alpha.md")
MIT_LICENSE_SHA256 = "a20526f108ee53ba6b6bb5fb4f60d09929df0c1fb3a257b46128c46ea017a134"
# Public artwork is explicitly selected and pinned; unrelated images still fail
# the privacy inspection. A logo replacement needs a new inspected fingerprint.
PUBLIC_ASSETS = {
    "docs/assets/peppi-mcp-logo.png": "f37fe4053eff4fe1529fb7b47d91f994cd36639fe46d7cac6c389b4e006dfdf2",
}


def run(*args, cwd=ROOT):
    subprocess.run([str(a) for a in args],cwd=cwd,check=True)


def code_fingerprint():
    files = [p for folder in ("src", "tests", "tools") for p in (ROOT/folder).rglob("*.py")]
    files += [ROOT/name for name in ("pyproject.toml","requirements-dev.lock","requirements-live.lock")]
    digest = hashlib.sha256()
    for path in sorted(files):
        digest.update(str(path.relative_to(ROOT)).encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def inspect_file(name, content, markers):
    path = PurePosixPath(name.replace("\\","/"))
    assert not path.is_absolute() and ".." not in path.parts, name
    assert not set(path.parts) & {".verification","private","imports","credentials",".git","runtime"}, name
    asset_name = str(path).removeprefix(f"peppi_mcp-{VERSION}/")
    public_asset = asset_name in PUBLIC_ASSETS
    if public_asset:
        assert hashlib.sha256(content).hexdigest() == PUBLIC_ASSETS[asset_name], "Public artwork differs from the inspected asset"
    assert not any(part.startswith(".venv") or part.endswith((".pdf",".jpg",".pem",".p12",".pfx",".key",".log",".db")) or (part.endswith(".png") and not public_asset) or ".sqlite" in part for part in path.parts), name
    lower = content.lower()
    assert (b"c:" + b"\\users\\") not in lower and (b"c:" + b"/users/") not in lower, name
    assert (b"-----begin " + b"private key-----") not in lower, name
    assert not any(marker in content for marker in markers), "Selected private reference marker found"


def validate_source_metadata(root=ROOT):
    project = tomllib.loads((root/"pyproject.toml").read_text(encoding="utf-8"))["project"]
    exported = next(node.value.value for node in ast.parse((root/"src/peppi_mcp/__init__.py").read_text(encoding="utf-8")).body
                    if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "__version__" for t in node.targets))
    assert project["version"] == exported == VERSION, "Project, runtime and release versions disagree"
    smoke = ast.parse((root/"tools/smoke_installed.py").read_text(encoding="utf-8"))
    smoke_versions = [node.test.comparators[0].value for node in ast.walk(smoke)
                      if isinstance(node, ast.Assert) and isinstance(node.test, ast.Compare)
                      and isinstance(node.test.left, ast.Attribute) and node.test.left.attr == "__version__"
                      and isinstance(node.test.comparators[0], ast.Constant)]
    assert smoke_versions == [VERSION], "Installed smoke-check version disagrees"
    assert project["license"] == "MIT" and project["license-files"] == ["LICENSE"], "Source MIT metadata is missing or inconsistent"
    assert hashlib.sha256((root/"LICENSE").read_bytes().replace(b"\r\n", b"\n")).hexdigest() == MIT_LICENSE_SHA256, "Source MIT license text differs"
    for name in RELEASE_DOCUMENTS:
        assert (root/name).is_file(), "Required release document is missing: " + name


def validate_packaged_evidence(files, *, wheel, source_names=(), root=ROOT):
    prefix = f"peppi_mcp-{VERSION}"
    metadata_path = f"{prefix}.dist-info/METADATA" if wheel else f"{prefix}/PKG-INFO"
    assert metadata_path in files, "Required package metadata is missing"
    metadata = BytesParser().parsebytes(files[metadata_path])
    assert metadata["Name"] == "peppi-mcp" and metadata["Version"] == VERSION, "Packaged name/version disagrees"
    assert metadata["License-Expression"] == "MIT" and metadata.get_all("License-File") == ["LICENSE"], "Packaged MIT metadata is missing or inconsistent"
    license_path = f"{prefix}.dist-info/licenses/LICENSE" if wheel else f"{prefix}/LICENSE"
    assert files.get(license_path) == (root/"LICENSE").read_bytes(), "Packaged license differs or is missing"
    assert metadata["Description-Content-Type"] == "text/markdown", "Packaged README type is missing"
    assert metadata.get_payload(decode=True).decode("utf-8").replace("\r\n", "\n").strip() == (root/"README.md").read_text(encoding="utf-8").strip(), "Packaged README differs"
    package = root/"src/peppi_mcp"
    for path in package.rglob("*"):
        if path.is_file() and "__pycache__" not in path.parts and path.suffix in (".py", ".json"):
            relative = path.relative_to(root/"src").as_posix()
            name = relative if wheel else f"{prefix}/src/{relative}"
            assert files.get(name) == path.read_bytes(), "Required packaged source differs or is missing: " + relative
    if not wheel:
        for name in set(source_names) | set(RELEASE_DOCUMENTS):
            assert files.get(f"{prefix}/{name}") == (root/name).read_bytes(), "Source distribution omits or changes: " + name
    for name, content in files.items():
        relative = name if wheel else name.removeprefix(prefix + "/")
        if wheel and name.startswith("peppi_mcp/"):
            source = root/"src"/name
        elif not wheel:
            assert name.startswith(prefix + "/"), "Unexpected source archive root"
            source = root/relative
        else:
            continue
        if "peppi_mcp.egg-info" in source.parts or relative in ("PKG-INFO", "setup.cfg"):
            continue
        assert source.is_file() and source.read_bytes() == content, "Unexpected or changed packaged source: " + name


def audit(reference=None):
    validate_source_metadata()
    markers = []
    if reference:
        from peppi_mcp.adapters.lapland_transcript import parse_pdf
        from peppi_mcp.import_store import MAX_DOCUMENT_BYTES, outside_repository
        with outside_repository(reference).open("rb") as stream: raw = stream.read(MAX_DOCUMENT_BYTES+1)
        snapshot = parse_pdf(raw,study_right_id="private-reference")
        markers = [hashlib.sha256(raw).hexdigest().encode()]
        markers += [v.encode() for r in snapshot.achievements for v in (r.course_id,r.title)]
    names = sorted(set(filter(None, subprocess.check_output(["git","ls-files","-z","--cached","--others","--exclude-standard"],cwd=ROOT).decode().split("\0"))))
    tree = hashlib.sha256()
    for name in names:
        content = (ROOT/name).read_bytes()
        inspect_file(name,content,markers)
        tree.update(name.encode() + b"\0" + content + b"\0")
    revision = subprocess.run(["git", "rev-parse", "--verify", "HEAD"],cwd=ROOT,capture_output=True,text=True)
    dirty = bool(subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=all"],cwd=ROOT))
    report = {"version":VERSION,"source_files":len(names),"public_tree_sha256":tree.hexdigest(),
              "source_revision":revision.stdout.strip() if revision.returncode == 0 else None,"source_tree_clean":not dirty,
              "selected_private_reference_checked":bool(reference),"artifacts":{}}
    for artifact in (ROOT/"dist"/f"peppi_mcp-{VERSION}-py3-none-any.whl",ROOT/"dist"/f"peppi_mcp-{VERSION}.tar.gz"):
        if artifact.suffix == ".whl":
            with zipfile.ZipFile(artifact) as archive:
                assert len(archive.namelist()) == len(set(archive.namelist())), "Duplicate wheel members"
                files = {n:archive.read(n) for n in archive.namelist() if not n.endswith("/")}
        else:
            with tarfile.open(artifact) as archive:
                assert all(m.isfile() or m.isdir() for m in archive.getmembers())
                assert len(archive.getnames()) == len(set(archive.getnames())), "Duplicate source archive members"
                files = {m.name:archive.extractfile(m).read() for m in archive.getmembers() if m.isfile()}
        for name, content in files.items():
            inspect_file(name,content,markers)
            if name.endswith("peppi_mcp/investigate.py"):
                assert b"def main(" not in content and b"execute_script" not in content, "Discovery harness must not ship"
        validate_packaged_evidence(files,wheel=artifact.suffix==".whl",source_names=names)
        report["artifacts"][artifact.name] = {"sha256":hashlib.sha256(artifact.read_bytes()).hexdigest(),"members":len(files)}
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts-only",action="store_true",help="Rebuild/audit after documentation-only edits; do not rerun passed tests")
    parser.add_argument("--reference-pdf",type=Path,help="Optional deliberately selected private reference outside repository; no contents printed")
    args = parser.parse_args()
    fingerprint = code_fingerprint()
    if not args.artifacts_only:
        run(sys.executable,"-m","pytest","-q","--require-browser","--require-chrome")
        if code_fingerprint() != fingerprint:
            raise SystemExit("Code changed during verification; rerun against a stable source tree.")
    run(sys.executable,"-m","build","--no-isolation")
    report = audit(args.reference_pdf)
    report["code_fingerprint"] = fingerprint
    if not args.artifacts_only:
        wheelhouse = ROOT/".verification"/"wheelhouse"
        if not wheelhouse.is_dir(): raise SystemExit("Download the pinned dependency wheels before running offline installation checks.")
        for mode, archive in (("core","whl"),("live","whl"),("core","tar.gz")):
            with tempfile.TemporaryDirectory(prefix="peppi-install-check-") as temp:
                destination = Path(temp)
                venv.EnvBuilder(with_pip=True).create(destination/"venv")
                python = destination/"venv"/"Scripts"/"python.exe"
                artifact = next(p for p in (ROOT/"dist").glob(f"peppi_mcp-{VERSION}*.{archive}"))
                requirement = str(artifact) + ("[live]" if mode=="live" else "")
                run(python,"-m","pip","install","--no-index","--find-links",wheelhouse,requirement,cwd=destination)
                run(python,"-m","pip","check",cwd=destination)
                run(python,ROOT/"tools"/"smoke_installed.py",mode,cwd=destination)
        report["clean_installations"] = ["wheel_core","wheel_live","sdist_core"]
    (ROOT/".verification").mkdir(exist_ok=True)
    (ROOT/".verification"/"release-check.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report,indent=2))


if __name__ == "__main__": main()
