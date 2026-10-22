"""Create a clean, checksummed CodeOS source ZIP without local configuration."""
import argparse
import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = {"node_modules", "dist", "__pycache__", ".pytest_cache", ".ruff_cache",
    ".git", ".venv", "venv", ".codex"}
MANIFEST = "docs/SOURCE-MANIFEST.json"


def included(path):
    relative = path.relative_to(ROOT)
    return (path.is_file() and not path.is_symlink()
        and not any(part in EXCLUDED for part in relative.parts)
        and not (path.name.startswith(".env") and path.name != ".env.example")
        and not path.name.endswith((".pyc", ".log", ".db", ".sqlite", ".sqlite3", ".zip"))
        and relative.as_posix() != MANIFEST)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    files = {p.relative_to(ROOT).as_posix(): p.read_bytes() for p in sorted(ROOT.rglob("*")) if included(p)}
    manifest = {"algorithm": "sha256", "files": {
        name: {"sha256": hashlib.sha256(data).hexdigest(), "size_bytes": len(data)}
        for name, data in files.items()}}
    files[MANIFEST] = (json.dumps(manifest, indent=2) + "\n").encode()
    with zipfile.ZipFile(args.output, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in files.items():
            archive.writestr("CodeOS-AI/" + name, data)
    with zipfile.ZipFile(args.output) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("Archive CRC verification failed.")
        for name, spec in manifest["files"].items():
            data = archive.read("CodeOS-AI/" + name)
            if len(data) != spec["size_bytes"] or hashlib.sha256(data).hexdigest() != spec["sha256"]:
                raise RuntimeError("Archive source verification failed: " + name)
    print(json.dumps({"archive": str(args.output.resolve()), "source_files": len(manifest["files"]),
        "size_bytes": args.output.stat().st_size,
        "sha256": hashlib.sha256(args.output.read_bytes()).hexdigest(), "integrity": "passed"}, indent=2))


if __name__ == "__main__":
    main()
