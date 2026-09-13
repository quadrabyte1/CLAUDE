"""iCloud Voice Memos placeholder handling and mtime-stable checks.

Key facts from Mori's iOS scoping doc:
- Voice Memos uses CloudKit (private container), NOT CloudDocs/iCloud Drive.
  So `.icloud` placeholder stubs are *unlikely* — but we defend against them
  anyway since the underlying daemon behaviour could change.
- Files are materialised by `voicememod` into the group container.
- FDA is required; without it, `os.listdir` on the group container raises
  PermissionError. We catch this and log clearly rather than crash-looping.

Debounce rule (from scoping §1):
  Only process a .m4a when:
    1. mtime has not changed for DEBOUNCE_SECONDS, AND
    2. file size > MIN_FILE_BYTES (10 KB).

iCloud placeholder detection:
  A file named `foo.m4a.icloud` is a Data-less placeholder. We call
  `brctl download <path>` to materialise it, then wait for the real .m4a.
"""

from __future__ import annotations

import logging
import os
import subprocess
import time
from pathlib import Path

log = logging.getLogger(__name__)

# Suffix used by iCloud Drive for undownloaded placeholders.
# CloudKit materialises directly (no stub expected), but we guard anyway.
_ICLOUD_SUFFIX = ".icloud"


def list_m4a_files(recordings_dir: Path) -> list[Path]:
    """List all .m4a files in *recordings_dir*, degrading gracefully on FDA errors.

    Returns an empty list (not an exception) when the directory is
    inaccessible — this lets cold-boot sweeps and the watcher continue
    operating without crashing when FDA has not yet been granted.
    """
    try:
        return sorted(recordings_dir.glob("**/*.m4a"))
    except PermissionError:
        log.error(
            "FDA required: cannot read Voice Memos at %s. "
            "Grant Full Disk Access to the sprite-watcher binary in "
            "System Settings → Privacy & Security → Full Disk Access, "
            "then reload the launchd agent.",
            recordings_dir,
        )
        return []
    except OSError as exc:
        log.error("Cannot read recordings directory %s: %s", recordings_dir, exc)
        return []


def is_icloud_placeholder(path: Path) -> bool:
    """Return True if *path* looks like an iCloud placeholder stub."""
    return path.name.endswith(_ICLOUD_SUFFIX)


def trigger_icloud_download(path: Path) -> bool:
    """Call `brctl download` on an iCloud placeholder.

    Returns True if the command succeeded (exit 0). The file may still
    take seconds to materialise; callers must poll until the real .m4a
    appears.
    """
    real_path = Path(str(path).removesuffix(_ICLOUD_SUFFIX))
    log.info("icloud: requesting download for %s via brctl", real_path)
    try:
        result = subprocess.run(
            ["brctl", "download", str(path)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            log.warning(
                "brctl download failed for %s: %s", path, result.stderr.strip()
            )
            return False
        return True
    except FileNotFoundError:
        log.warning("brctl not found — iCloud download not triggered for %s", path)
        return False
    except subprocess.TimeoutExpired:
        log.warning("brctl download timed out for %s", path)
        return False


def is_mtime_stable(path: Path, debounce_seconds: float, min_bytes: int) -> bool:
    """Return True when *path* passes the mtime-stable + size check.

    The check:
      1. File must exist and not be a placeholder.
      2. Size must exceed *min_bytes*.
      3. mtime must not have changed in the last *debounce_seconds*.
         (We sample mtime now; the caller's event loop must have already
         waited debounce_seconds since the first observation — or call
         this after a poll interval.)

    This function does NOT sleep. The caller's event loop does the waiting.
    """
    try:
        stat = path.stat()
    except OSError:
        return False

    if stat.st_size < min_bytes:
        log.debug("debounce: %s too small (%d B < %d B)", path.name, stat.st_size, min_bytes)
        return False

    age = time.time() - stat.st_mtime
    if age < debounce_seconds:
        log.debug(
            "debounce: %s mtime only %.1f s ago (need %.1f s stable)",
            path.name,
            age,
            debounce_seconds,
        )
        return False

    return True


def archive_audio(source: Path, archive_root: Path, uuid: str) -> Path:
    """Copy *source* .m4a into archive_root/YYYY/MM/<uuid>.m4a.

    Never deletes the original. Returns the archive path.

    Uses a write-to-temp-then-rename pattern within the same directory to
    avoid half-written archives if the process is killed mid-copy.
    """
    import shutil
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    dest_dir = archive_root / now.strftime("%Y") / now.strftime("%m")
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{uuid}.m4a"

    if dest.exists():
        log.debug("archive: %s already exists, skipping copy", dest)
        return dest

    # Write to temp then rename (atomic within same directory/filesystem).
    tmp = dest.parent / f".{uuid}.m4a.tmp"
    try:
        shutil.copy2(str(source), str(tmp))
        os.rename(tmp, dest)
    except Exception:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        raise

    log.info("archive: %s → %s", source.name, dest)
    return dest
