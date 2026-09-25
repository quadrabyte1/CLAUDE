"""
test_config_backup.py — V3.23 config export/import + auto-snapshot tests.

Bug→TDD discipline: these tests were written BEFORE any V3.23 implementation.
All tests in this file should FAIL on the V3.22 codebase and PASS on V3.23.

Running against a temp DB is mandatory — never touch the live scanner.db.
Each test sets MOVIESCANNER_DB_PATH to a tmp_path fixture path.
"""

import importlib
import io
import json
import os
import re
import shutil
import sqlite3
import sys
import time
from pathlib import Path

import pytest


# ── Helpers ────────────────────────────────────────────────────────────────

def _make_app(tmp_path: Path):
    """Import (or re-import) app with MOVIESCANNER_DB_PATH pointed at a fresh
    temp DB.  Returns the Flask test client.

    Each call re-imports the module so module-level side effects (_init_db,
    _reconcile_orphaned_runs, _integrity_check) run against the temp DB.
    """
    db_path = str(tmp_path / "scanner.db")
    os.environ["MOVIESCANNER_DB_PATH"] = db_path

    # Force a clean re-import so module-level code runs against the fresh DB.
    for mod_name in list(sys.modules.keys()):
        if mod_name == "MovieScanner.app" or mod_name.endswith(".app"):
            # Only evict the MovieScanner app, not everything
            pass
    if "MovieScanner.app" in sys.modules:
        del sys.modules["MovieScanner.app"]
    # Also handle plain "app" if imported that way
    app_mod_key = None
    for k in list(sys.modules.keys()):
        if k == "app" and hasattr(sys.modules[k], "APP_VERSION"):
            app_mod_key = k
            break
    if app_mod_key:
        del sys.modules[app_mod_key]

    # Ensure MovieScanner/ is importable as a directory
    ms_dir = os.path.join(os.path.dirname(__file__), "..")
    ms_dir = os.path.abspath(ms_dir)
    repo_root = os.path.dirname(ms_dir)
    for p in [ms_dir, repo_root]:
        if p not in sys.path:
            sys.path.insert(0, p)

    import app as ms_app  # type: ignore
    importlib.reload(ms_app)

    ms_app.app.config["TESTING"] = True
    ms_app.app.config["WTF_CSRF_ENABLED"] = False
    client = ms_app.app.test_client()
    return ms_app, client, db_path


def _seed_config(db_path: str) -> None:
    """Insert the essential config rows that indicate a healthy DB."""
    conn = sqlite3.connect(db_path)
    for k, v in [
        ("tags",           '["Action","Drama"]'),
        ("exclude_tags",   '["Horror"]'),
        ("min_rating",     "7.5"),
        ("omdb_api_key",   "test-key-abc"),
        ("min_votes",      "500"),
        ("min_year",       "2024"),
    ]:
        conn.execute(
            "INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", (k, v)
        )
    conn.commit()
    conn.close()


def _seed_dismissed(db_path: str, tconsts: list) -> None:
    conn = sqlite3.connect(db_path)
    for t in tconsts:
        conn.execute(
            "INSERT OR REPLACE INTO dismissed_tconsts (tconst) VALUES (?)", (t,)
        )
    conn.commit()
    conn.close()


def _backup_dir(db_path: str) -> Path:
    """Return the expected backups directory for a given db_path."""
    return Path(db_path).parent / "backups"


# ══════════════════════════════════════════════════════════════════════════════
# Layer 1 — Snapshot tests
# ══════════════════════════════════════════════════════════════════════════════

class TestAutoSnapshot:

    def test_config_save_creates_snapshot(self, tmp_path):
        """T01 — Posting to /config triggers a DB snapshot in db/backups/."""
        ms_app, client, db_path = _make_app(tmp_path)
        bdir = _backup_dir(db_path)

        # No snapshots yet
        assert not bdir.exists() or list(bdir.glob("scanner_*.db")) == []

        resp = client.post("/config", data={
            "min_rating": "7.0",
            "min_votes": "100",
            "min_year": "2026",
        }, follow_redirects=True)
        assert resp.status_code == 200

        snapshots = sorted(bdir.glob("scanner_*.db"))
        assert len(snapshots) >= 1, "Expected at least one snapshot after /config POST"

    def test_snapshot_filename_pattern(self, tmp_path):
        """T02 — Snapshot filename matches scanner_YYYYMMDD_HHMMSS.db."""
        ms_app, client, db_path = _make_app(tmp_path)

        client.post("/config", data={
            "min_rating": "7.0",
            "min_votes": "100",
            "min_year": "2026",
        }, follow_redirects=True)

        bdir = _backup_dir(db_path)
        snapshots = sorted(bdir.glob("scanner_*.db"))
        assert len(snapshots) >= 1
        # Filename must match scanner_YYYYMMDD_HHMMSS.db
        pattern = re.compile(r"^scanner_\d{8}_\d{6}\.db$")
        for s in snapshots:
            assert pattern.match(s.name), f"Bad filename: {s.name}"

    def test_snapshot_rotation_keeps_20(self, tmp_path):
        """T03 — After 21 saves, only 20 snapshots remain (oldest deleted)."""
        ms_app, client, db_path = _make_app(tmp_path)

        # Seed some pre-existing fake snapshots (21 total after our saves)
        bdir = _backup_dir(db_path)
        bdir.mkdir(parents=True, exist_ok=True)
        for i in range(20):
            fake = bdir / f"scanner_2026090{i % 10}_12000{i}.db"
            shutil.copy(db_path, str(fake))
            time.sleep(0.01)  # ensure distinct mtimes

        assert len(list(bdir.glob("scanner_*.db"))) == 20

        # One more save should trigger rotation → still 20
        client.post("/config", data={
            "min_rating": "8.0",
            "min_votes": "200",
            "min_year": "2026",
        }, follow_redirects=True)

        snapshots = sorted(bdir.glob("scanner_*.db"))
        assert len(snapshots) == 20, (
            f"Expected 20 snapshots after rotation; got {len(snapshots)}"
        )

    def test_snapshot_dir_created_lazily(self, tmp_path):
        """T04 — backups/ dir is created by the first snapshot (does not need
        to pre-exist)."""
        ms_app, client, db_path = _make_app(tmp_path)
        bdir = _backup_dir(db_path)
        assert not bdir.exists(), "Pre-condition: backups dir should not exist"

        client.post("/config", data={
            "min_rating": "7.0",
            "min_votes": "100",
            "min_year": "2026",
        }, follow_redirects=True)

        assert bdir.is_dir(), "backups/ dir was not created"

    def test_snapshot_is_valid_sqlite(self, tmp_path):
        """T05 — The snapshot is a readable SQLite DB with a config table."""
        ms_app, client, db_path = _make_app(tmp_path)
        _seed_config(db_path)

        client.post("/config", data={
            "min_rating": "7.5",
            "min_votes": "500",
            "min_year": "2025",
        }, follow_redirects=True)

        bdir = _backup_dir(db_path)
        snapshots = sorted(bdir.glob("scanner_*.db"))
        assert snapshots
        snap = snapshots[-1]
        conn = sqlite3.connect(str(snap))
        row = conn.execute("SELECT 1 FROM config LIMIT 1").fetchone()
        conn.close()
        assert row is not None, "Snapshot DB has no config rows"

    def test_snapshot_not_taken_on_failed_transaction(self, tmp_path, monkeypatch):
        """T06 — If the DB commit raises, no snapshot is written.

        We monkeypatch the internal commit call on the connection object to
        simulate a DB write failure and assert no file lands in backups/.
        """
        ms_app, client, db_path = _make_app(tmp_path)
        bdir = _backup_dir(db_path)

        original_conn = ms_app._conn

        def _failing_conn():
            c = original_conn()
            original_commit = c.commit

            def boom():
                raise sqlite3.OperationalError("simulated commit failure")

            c.commit = boom
            return c

        monkeypatch.setattr(ms_app, "_conn", _failing_conn)

        try:
            client.post("/config", data={
                "min_rating": "7.0",
                "min_votes": "100",
                "min_year": "2026",
            }, follow_redirects=True)
        except Exception:
            pass  # The route may 500 — that's fine for this test

        if bdir.exists():
            snapshots = list(bdir.glob("scanner_*.db"))
            assert len(snapshots) == 0, (
                "No snapshot should be written when the DB commit fails"
            )


# ══════════════════════════════════════════════════════════════════════════════
# Layer 2 — Export tests
# ══════════════════════════════════════════════════════════════════════════════

class TestConfigExport:

    def test_export_returns_200_with_attachment(self, tmp_path):
        """T07 — GET /config/export returns 200, Content-Disposition attachment,
        and application/json content-type."""
        ms_app, client, db_path = _make_app(tmp_path)
        _seed_config(db_path)

        resp = client.get("/config/export")
        assert resp.status_code == 200
        cd = resp.headers.get("Content-Disposition", "")
        assert "attachment" in cd, f"Expected attachment disposition; got: {cd!r}"
        ct = resp.headers.get("Content-Type", "")
        assert "application/json" in ct, f"Expected JSON content-type; got: {ct!r}"

    def test_export_has_required_top_level_keys(self, tmp_path):
        """T08 — Exported JSON has version, exported_at, config, dismissed_tconsts."""
        ms_app, client, db_path = _make_app(tmp_path)
        _seed_config(db_path)

        resp = client.get("/config/export")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        for key in ("version", "exported_at", "config", "dismissed_tconsts"):
            assert key in data, f"Missing key {key!r} in export"

    def test_export_version_is_v1(self, tmp_path):
        """T09 — Exported JSON version field is 'v1'."""
        ms_app, client, db_path = _make_app(tmp_path)
        resp = client.get("/config/export")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["version"] == "v1"

    def test_export_config_contains_seeded_values(self, tmp_path):
        """T10 — Exported config dict contains the seeded key/value pairs."""
        ms_app, client, db_path = _make_app(tmp_path)
        _seed_config(db_path)

        resp = client.get("/config/export")
        data = json.loads(resp.data)
        cfg = data["config"]
        assert cfg.get("omdb_api_key") == "test-key-abc"
        assert cfg.get("min_rating") == "7.5"

    def test_export_dismissed_tconsts_list(self, tmp_path):
        """T11 — dismissed_tconsts in export matches the rows in dismissed_tconsts."""
        ms_app, client, db_path = _make_app(tmp_path)
        _seed_dismissed(db_path, ["tt1234567", "tt7654321"])

        resp = client.get("/config/export")
        data = json.loads(resp.data)
        exported = set(data["dismissed_tconsts"])
        assert "tt1234567" in exported
        assert "tt7654321" in exported

    def test_export_round_trip_config_matches_db(self, tmp_path):
        """T12 — Round-trip: seed → export → verify export config == DB config."""
        ms_app, client, db_path = _make_app(tmp_path)
        _seed_config(db_path)

        resp = client.get("/config/export")
        data = json.loads(resp.data)
        exported_cfg = data["config"]

        # Re-read from DB
        conn = sqlite3.connect(db_path)
        db_cfg = {r[0]: r[1] for r in conn.execute(
            "SELECT key, value FROM config"
        ).fetchall()}
        conn.close()

        for k, v in db_cfg.items():
            assert exported_cfg.get(k) == v, (
                f"Mismatch for key {k!r}: export has {exported_cfg.get(k)!r}, "
                f"DB has {v!r}"
            )


# ══════════════════════════════════════════════════════════════════════════════
# Layer 2 — Import tests
# ══════════════════════════════════════════════════════════════════════════════

class TestConfigImport:

    def _make_payload(self, config: dict, dismissed: list) -> bytes:
        return json.dumps({
            "version": "v1",
            "exported_at": "2026-09-24T00:00:00Z",
            "config": config,
            "dismissed_tconsts": dismissed,
        }).encode()

    def test_import_replaces_config(self, tmp_path):
        """T13 — POST /config/import with valid JSON replaces config rows."""
        ms_app, client, db_path = _make_app(tmp_path)

        payload = self._make_payload(
            config={"min_rating": "9.0", "omdb_api_key": "imported-key"},
            dismissed=["tt9999999"],
        )

        resp = client.post(
            "/config/import",
            data={"file": (io.BytesIO(payload), "backup.json")},
            content_type="multipart/form-data",
        )
        # Accept redirect or 200
        assert resp.status_code in (200, 302)

        conn = sqlite3.connect(db_path)
        cfg = {r[0]: r[1] for r in conn.execute(
            "SELECT key, value FROM config"
        ).fetchall()}
        conn.close()
        assert cfg.get("min_rating") == "9.0"
        assert cfg.get("omdb_api_key") == "imported-key"

    def test_import_replaces_dismissed_tconsts(self, tmp_path):
        """T14 — Import clears old dismissed_tconsts and inserts the payload's list."""
        ms_app, client, db_path = _make_app(tmp_path)
        _seed_dismissed(db_path, ["tt0000001", "tt0000002"])

        payload = self._make_payload(
            config={"min_rating": "7.0"},
            dismissed=["tt9999999"],
        )
        client.post(
            "/config/import",
            data={"file": (io.BytesIO(payload), "backup.json")},
            content_type="multipart/form-data",
        )

        conn = sqlite3.connect(db_path)
        rows = {r[0] for r in conn.execute(
            "SELECT tconst FROM dismissed_tconsts"
        ).fetchall()}
        conn.close()
        assert "tt9999999" in rows, "Imported tconst should be in dismissed_tconsts"
        assert "tt0000001" not in rows, "Old tconst should be gone after import"

    def test_import_takes_snapshot_before_replacing(self, tmp_path):
        """T15 — Import takes a snapshot BEFORE replacing config (rollback safety)."""
        ms_app, client, db_path = _make_app(tmp_path)
        _seed_config(db_path)
        bdir = _backup_dir(db_path)

        count_before = len(list(bdir.glob("scanner_*.db"))) if bdir.exists() else 0

        payload = self._make_payload(
            config={"min_rating": "8.0"},
            dismissed=[],
        )
        client.post(
            "/config/import",
            data={"file": (io.BytesIO(payload), "backup.json")},
            content_type="multipart/form-data",
        )

        count_after = len(list(bdir.glob("scanner_*.db"))) if bdir.exists() else 0
        assert count_after > count_before, (
            "Import should take a snapshot before overwriting config"
        )

    def test_import_malformed_json_returns_400(self, tmp_path):
        """T16 — Malformed JSON body → HTTP 400."""
        ms_app, client, db_path = _make_app(tmp_path)

        resp = client.post(
            "/config/import",
            data={"file": (io.BytesIO(b"this is not json {{{"), "bad.json")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400

    def test_import_wrong_version_returns_400(self, tmp_path):
        """T17 — Wrong version field (e.g. 'v99') → HTTP 400."""
        ms_app, client, db_path = _make_app(tmp_path)

        payload = json.dumps({
            "version": "v99",
            "exported_at": "2026-09-24T00:00:00Z",
            "config": {},
            "dismissed_tconsts": [],
        }).encode()

        resp = client.post(
            "/config/import",
            data={"file": (io.BytesIO(payload), "backup.json")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400

    def test_import_missing_top_level_keys_returns_400(self, tmp_path):
        """T18 — Missing required top-level keys → HTTP 400."""
        ms_app, client, db_path = _make_app(tmp_path)

        # Missing 'config' and 'dismissed_tconsts'
        payload = json.dumps({"version": "v1"}).encode()
        resp = client.post(
            "/config/import",
            data={"file": (io.BytesIO(payload), "backup.json")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400

    def test_import_no_file_returns_400(self, tmp_path):
        """T19 — POST /config/import with no file → HTTP 400."""
        ms_app, client, db_path = _make_app(tmp_path)

        resp = client.post("/config/import", data={}, content_type="multipart/form-data")
        assert resp.status_code == 400

    def test_import_form_page_returns_200(self, tmp_path):
        """T20 — GET /config/import_form returns a page with a file input."""
        ms_app, client, db_path = _make_app(tmp_path)

        resp = client.get("/config/import_form")
        assert resp.status_code == 200
        body = resp.data.decode()
        assert 'type="file"' in body or "file" in body.lower()


# ══════════════════════════════════════════════════════════════════════════════
# Layer 3 — Integrity check tests
# ══════════════════════════════════════════════════════════════════════════════

class TestIntegrityCheck:

    def test_missing_essential_keys_sets_banner_flag(self, tmp_path):
        """T21 — When essential config keys are absent, index() context includes
        config_integrity_warning=True."""
        ms_app, client, db_path = _make_app(tmp_path)

        # Delete the essential keys from the DB so the check triggers
        conn = sqlite3.connect(db_path)
        conn.execute("DELETE FROM config WHERE key IN ('tags','exclude_tags','min_rating','omdb_api_key')")
        conn.commit()
        conn.close()

        resp = client.get("/")
        assert resp.status_code == 200
        body = resp.data.decode()
        # The banner should appear in the rendered HTML
        assert "Config appears reset" in body or "config_integrity_warning" in body or \
               "Restore from most-recent snapshot" in body

    def test_all_essential_keys_present_no_banner(self, tmp_path):
        """T22 — When all essential config keys exist, no integrity banner is shown."""
        ms_app, client, db_path = _make_app(tmp_path)
        _seed_config(db_path)

        # omdb_api_key is the one key seeded by _seed_config that the check cares about
        resp = client.get("/")
        assert resp.status_code == 200
        body = resp.data.decode()
        assert "Config appears reset" not in body

    def test_restore_from_snapshot_route_exists(self, tmp_path):
        """T23 — GET /config/restore_latest either restores or returns a useful
        response (not 404/500) when a snapshot exists."""
        ms_app, client, db_path = _make_app(tmp_path)
        _seed_config(db_path)

        # Create a snapshot first
        client.post("/config", data={
            "min_rating": "7.0",
            "min_votes": "100",
            "min_year": "2026",
        }, follow_redirects=True)

        resp = client.post("/config/restore_latest", follow_redirects=True)
        # Must be 200 (after redirect) or direct 200/204 — definitely not 404/500
        assert resp.status_code not in (404, 500), (
            f"restore_latest returned {resp.status_code}"
        )

    def test_restore_from_snapshot_replaces_config(self, tmp_path):
        """T24 — restore_latest replaces config with the snapshot's content."""
        ms_app, client, db_path = _make_app(tmp_path)
        _seed_config(db_path)  # sets min_rating=7.5

        # Take a snapshot that captures min_rating=7.5
        client.post("/config", data={
            "min_rating": "7.5",
            "min_votes": "500",
            "min_year": "2024",
        }, follow_redirects=True)

        # Now overwrite min_rating to something different
        conn = sqlite3.connect(db_path)
        conn.execute("INSERT OR REPLACE INTO config (key,value) VALUES ('min_rating','1.0')")
        conn.commit()
        conn.close()

        # Restore
        client.post("/config/restore_latest", follow_redirects=True)

        conn = sqlite3.connect(db_path)
        val = conn.execute(
            "SELECT value FROM config WHERE key='min_rating'"
        ).fetchone()
        conn.close()
        # After restore, min_rating should be back to what was in the snapshot (not 1.0)
        assert val is not None
        assert val[0] != "1.0", "Restore did not overwrite the tampered config value"


# ══════════════════════════════════════════════════════════════════════════════
# Layer 4 — Regression: APP_VERSION
# ══════════════════════════════════════════════════════════════════════════════

class TestRegression:

    def test_app_version_is_v3_23(self, tmp_path):
        """T25 — APP_VERSION must be V3.23 (version bump from V3.22)."""
        ms_app, client, db_path = _make_app(tmp_path)
        assert ms_app.APP_VERSION == "V3.23", (
            f"Expected V3.23, got {ms_app.APP_VERSION!r}"
        )

    def test_index_renders(self, tmp_path):
        """T26 — GET / returns 200 (smoke test — basic render must not break)."""
        ms_app, client, db_path = _make_app(tmp_path)
        resp = client.get("/")
        assert resp.status_code == 200

    def test_config_save_still_works(self, tmp_path):
        """T27 — POST /config still redirects to index after V3.23 changes."""
        ms_app, client, db_path = _make_app(tmp_path)
        resp = client.post("/config", data={
            "min_rating": "7.5",
            "min_votes": "200",
            "min_year": "2026",
        })
        assert resp.status_code in (200, 302)

    def test_dismiss_still_works(self, tmp_path):
        """T28 — POST /matches/<tconst>/dismiss returns 204 (no regression)."""
        ms_app, client, db_path = _make_app(tmp_path)

        # Seed a match row so dismiss has something to write
        conn = sqlite3.connect(db_path)
        conn.execute(
            "INSERT OR IGNORE INTO titles "
            "(tconst, title_type, primary_title) VALUES (?, ?, ?)",
            ("tt1111111", "movie", "Test Movie"),
        )
        conn.execute(
            "INSERT OR IGNORE INTO runs (id, status, phase) VALUES (1, 'done', 'done')"
        )
        conn.execute(
            "INSERT OR IGNORE INTO matches "
            "(tconst, primary_title, start_year, title_type, rating, num_votes, run_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("tt1111111", "Test Movie", 2024, "movie", 7.8, 5000, 1),
        )
        conn.commit()
        conn.close()

        resp = client.post("/matches/tt1111111/dismiss")
        assert resp.status_code == 204

    def test_header_contains_export_link(self, tmp_path):
        """T29 — The rendered index page contains a link or button for Export config."""
        ms_app, client, db_path = _make_app(tmp_path)
        resp = client.get("/")
        body = resp.data.decode()
        assert "/config/export" in body, (
            "Expected /config/export link in the page header"
        )

    def test_header_contains_import_link(self, tmp_path):
        """T30 — The rendered index page contains a link or button for Import config."""
        ms_app, client, db_path = _make_app(tmp_path)
        resp = client.get("/")
        body = resp.data.decode()
        assert "/config/import_form" in body, (
            "Expected /config/import_form link in the page header"
        )
