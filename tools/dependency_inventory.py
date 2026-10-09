"""Report installed metadata for the pinned project dependencies, without paths."""
import importlib.metadata as metadata
from pathlib import Path

root = Path(__file__).resolve().parents[1]
names = {line.split("==")[0] for filename in ("requirements-live.lock","requirements-dev.lock")
         for line in (root/filename).read_text().splitlines() if "==" in line}
lines = ["# Dependency inventory", "", "Declared installed metadata for the pinned Windows Python 3.12 environment.",
         "Project code is licensed under MIT. This records upstream declarations; dependency-license compatibility and redistribution requirements remain separate checks.", "",
         "| Distribution | Version | Declared license |", "|---|---|---|"]
for name in sorted(names,key=str.lower):
    info = metadata.metadata(name)
    license = info.get("License-Expression") or "; ".join(x.removeprefix("License :: OSI Approved :: ") for x in (info.get_all("Classifier") or []) if x.startswith("License ::")) or info.get("License") or "not declared"
    license = " ".join(license.split()).replace("|","/")[:200]
    lines.append(f"| {name} | {metadata.version(name)} | {license} |")
destination = root/"docs"/"dependencies.md"
# Refreshing license metadata is not an advisory scan. Keep dated evidence
# recorded from an actual scan without manufacturing a new clean result.
previous = destination.read_text(encoding="utf-8") if destination.exists() else ""
evidence = previous.partition("\n## Advisory findings\n")[2] or "\nNo advisory scan has been recorded.\n"
lines += ["", "## Advisory findings", evidence]
destination.write_text("\n".join(lines),encoding="utf-8")
