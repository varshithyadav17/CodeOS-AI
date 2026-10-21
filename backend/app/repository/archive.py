"""Validate archives before storing or extracting. Never execute uploaded code."""
from __future__ import annotations
import hashlib
import re
import stat
import zipfile
from pathlib import Path, PurePosixPath
from ..config import settings


class UnsafeZipError(ValueError):
    pass


SENSITIVE_NAMES = {".env", ".npmrc", ".pypirc", "id_rsa", "id_ed25519", "credentials", "credentials.json"}


def is_sensitive(path: str):
    name = PurePosixPath(path).name.lower()
    return (name in SENSITIVE_NAMES or (name.startswith(".env.") and name not in {".env.example", ".env.sample", ".env.template"})
        or name.endswith((".pem", ".key", ".p12", ".pfx")))


def normalized_path(name: str) -> str:
    if not name or "\\" in name or "\x00" in name or re.match(r"^[A-Za-z]:", name):
        raise UnsafeZipError("Archive contains an invalid path.")
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or any(":" in p for p in path.parts):
        raise UnsafeZipError("Archive contains a path outside its repository.")
    if len(name) > 1000 or len(path.parts) > 40:
        raise UnsafeZipError("Archive path is too deep or too long.")
    return path.as_posix().rstrip("/")


def validate_archive(path: Path):
    try:
        with zipfile.ZipFile(path) as archive:
            entries = archive.infolist()
            if not entries or len(entries) > settings.MAX_FILES:
                raise UnsafeZipError("Archive is empty or has too many entries.")
            total, seen, folded, files = 0, set(), set(), set()
            for info in entries:
                name = normalized_path(info.filename)
                mode = info.external_attr >> 16
                kind = stat.S_IFMT(mode)
                if kind not in {0, stat.S_IFREG, stat.S_IFDIR}:
                    raise UnsafeZipError("Archive links and special files are not supported.")
                if info.flag_bits & 1:
                    raise UnsafeZipError("Encrypted archives are not supported.")
                if name in seen or name.casefold() in folded:
                    raise UnsafeZipError("Archive contains duplicate or case-conflicting paths.")
                seen.add(name)
                folded.add(name.casefold())
                if not info.is_dir():
                    files.add(name)
                total += info.file_size
                if total > settings.MAX_EXTRACT_BYTES:
                    raise UnsafeZipError("Archive expanded size exceeds the configured limit.")
                if info.file_size > 1024**2 and info.file_size > max(info.compress_size, 1) * settings.MAX_COMPRESSION_RATIO:
                    raise UnsafeZipError("Archive compression ratio exceeds the configured limit.")
            for name in seen:
                if any(str(parent) in files for parent in PurePosixPath(name).parents):
                    raise UnsafeZipError("Archive contains a file/directory path conflict.")
    except (zipfile.BadZipFile, NotImplementedError, OSError) as exc:
        raise UnsafeZipError("Invalid or unsupported ZIP archive.") from exc


def safe_extract(path: Path, dest: Path):
    validate_archive(path)
    dest.mkdir(parents=True, exist_ok=True)
    total = 0
    with zipfile.ZipFile(path) as archive:
        for info in archive.infolist():
            name = normalized_path(info.filename)
            target = dest / name
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            try:
                with archive.open(info) as src, target.open("xb") as output:
                    while block := src.read(1024 * 1024):
                        total += len(block)
                        if total > settings.MAX_EXTRACT_BYTES:
                            raise UnsafeZipError("Archive extraction exceeded its size limit.")
                        output.write(block)
            except (zipfile.BadZipFile, RuntimeError) as exc:
                raise UnsafeZipError("Archive integrity check failed.") from exc


def sha256(path: Path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def archive_tree(root: Path, output: Path):
    total, count = 0, 0
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(root.rglob("*")):
            rel = path.relative_to(root)
            if ".git" in rel.parts or path.is_symlink() or not path.is_file():
                continue
            count += 1
            total += path.stat().st_size
            if count > settings.MAX_FILES or total > settings.MAX_EXTRACT_BYTES:
                raise UnsafeZipError("GitHub repository exceeds configured file/size limits.")
            archive.write(path, rel.as_posix())
    if output.stat().st_size > settings.MAX_ARCHIVE_BYTES:
        raise UnsafeZipError("GitHub archive exceeds the configured size limit.")
    validate_archive(output)


def read_source(archive_path: Path, archive_name: str):
    normalized_path(archive_name)
    with zipfile.ZipFile(archive_path) as archive:
        try:
            info = archive.getinfo(archive_name)
        except KeyError:
            raise FileNotFoundError("Source file was not found in the archive.")
        if info.file_size > settings.MAX_SOURCE_BYTES:
            raise ValueError("Source file exceeds the preview size limit.")
        data = archive.read(info)
        if b"\x00" in data:
            raise ValueError("Binary files cannot be previewed.")
        return data.decode("utf-8", errors="replace")
