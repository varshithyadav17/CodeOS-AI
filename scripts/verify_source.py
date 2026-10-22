"""Verify the packaged source before installing dependencies or editing it."""
import hashlib
import json
from pathlib import Path, PurePosixPath

root = Path(__file__).resolve().parents[1]
manifest = json.loads((root / "docs/SOURCE-MANIFEST.json").read_text())
errors = []
for name, spec in manifest["files"].items():
    relative = PurePosixPath(name)
    if relative.is_absolute() or ".." in relative.parts or "\\" in name:
        raise SystemExit("Invalid manifest path.")
    path = root / name
    if not path.is_file() or path.is_symlink():
        errors.append(name + ": missing or symlink")
    elif path.stat().st_size != spec["size_bytes"] or hashlib.sha256(path.read_bytes()).hexdigest() != spec["sha256"]:
        errors.append(name + ": changed")
if errors:
    raise SystemExit("Source verification failed:\n" + "\n".join(errors))
print(f"Verified {len(manifest['files'])} packaged source files.")
