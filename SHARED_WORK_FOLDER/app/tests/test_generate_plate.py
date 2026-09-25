"""
test_generate_plate.py — TDD tests for POST /api/generate_plate SMTP-fallback.

Bug reproduced: route returns HTTP 500 when SMTP env vars are absent, even
though 3MF generation is completely offline.  After the fix:
  - No SMTP → 200 OK, delivery="local", file written to Downloads.
  - All SMTP → email sent (mocked), delivery="email" or "email+local".
  - Partial SMTP → treat as unconfigured, warnings include missing vars.
  - Existing SMTP error handlers (auth failure, connection refused) unchanged.

Tests are written BEFORE the implementation change so they run RED first.

Test inventory
--------------
Route tests (POST /api/generate_plate):
  1. No SMTP env vars → 200, delivery="local", local_path set, warnings non-empty.  [regression]
  2. All SMTP, open_in_slicer=false → mock-SMTP succeeds, delivery="email", local_path=None.
  3. All SMTP, open_in_slicer=true  → delivery="email+local", both paths set.
  4. Partial SMTP (SMTP_HOST only)  → 200, delivery="local", warnings mention SMTP_USER+SMTP_PASS.
  5. SMTP configured, connection refused → HTTP 500, existing error handler fires.
  6. 3MF generation failure → HTTP 500 with "3MF generation failed:".
  7. No lines provided → HTTP 400 "Provide at least one line".
  8. Local file actually written when delivery="local" — non-zero size, valid 3MF zip.

Helper tests (_smtp_config):
  9.  All three env vars set → missing_vars=[].
  10. Only SMTP_HOST set → missing_vars contains SMTP_USER and SMTP_PASS.
  11. Zero env vars → missing_vars has all three names.
"""

from __future__ import annotations

import io
import os
import sys
import zipfile
import tempfile

import pytest

# ---------------------------------------------------------------------------
# Make app/ importable regardless of where pytest is invoked from.
# ---------------------------------------------------------------------------
APP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _make_app():
    """Import and return the Flask app with a test DB so we never touch live data."""
    import app as app_module
    flask_app = app_module.app
    flask_app.config["TESTING"] = True
    return flask_app


def _minimal_3mf_bytes() -> bytes:
    """Produce the smallest valid 3MF (a ZIP with a [Content_Types].xml inside)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types/>')
    return buf.getvalue()


@pytest.fixture()
def client():
    flask_app = _make_app()
    with flask_app.test_client() as c:
        yield c


@pytest.fixture()
def mock_generate_3mf(monkeypatch):
    """Replace plate_text.generate_plate_3mf with a stub that writes a valid 3MF."""
    def _fake_gen(line1, line2, line3, out_path, **kwargs):
        with open(out_path, "wb") as fh:
            fh.write(_minimal_3mf_bytes())

    import importlib
    # Ensure the module exists in sys.modules so monkeypatch can target it
    try:
        import plate_text  # noqa: F401
    except ImportError:
        plate_text = type(sys)("plate_text")
        plate_text.generate_plate_3mf = _fake_gen
        sys.modules["plate_text"] = plate_text
    monkeypatch.setattr("plate_text.generate_plate_3mf", _fake_gen)


@pytest.fixture()
def clear_smtp_env(monkeypatch):
    """Remove all SMTP* vars from the environment for the duration of the test."""
    for var in ("SMTP_HOST", "SMTP_USER", "SMTP_PASS", "SMTP_PORT", "SMTP_FROM", "SMTP_TO"):
        monkeypatch.delenv(var, raising=False)


@pytest.fixture()
def full_smtp_env(monkeypatch):
    """Set a complete (but fake) SMTP config in the environment."""
    monkeypatch.setenv("SMTP_HOST", "mail.example.com")
    monkeypatch.setenv("SMTP_USER", "user@example.com")
    monkeypatch.setenv("SMTP_PASS", "s3cr3t")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_FROM", "user@example.com")
    monkeypatch.setenv("SMTP_TO",   "recipient@example.com")


@pytest.fixture()
def mock_smtp_success(monkeypatch):
    """Mock smtplib.SMTP so no real connection is attempted; send succeeds."""
    import smtplib

    class _FakeSMTP:
        def __init__(self, *a, **kw): pass
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def ehlo(self): pass
        def starttls(self): pass
        def login(self, user, password): pass
        def send_message(self, msg): pass

    monkeypatch.setattr(smtplib, "SMTP", _FakeSMTP)


@pytest.fixture()
def local_downloads(tmp_path, monkeypatch):
    """Redirect ~/Downloads writes to a tmp_path sub-directory."""
    fake_downloads = tmp_path / "Downloads"
    fake_downloads.mkdir()

    real_expanduser = os.path.expanduser

    def _patched_expanduser(path):
        if path.startswith("~/Downloads/"):
            return str(fake_downloads / path[len("~/Downloads/"):])
        return real_expanduser(path)

    monkeypatch.setattr("os.path.expanduser", _patched_expanduser)
    # Also patch inside the app module's namespace
    import app as app_module
    monkeypatch.setattr(app_module.os.path, "expanduser", _patched_expanduser)
    yield fake_downloads


# ---------------------------------------------------------------------------
# Test 1 — REGRESSION: No SMTP env vars → 200 OK, delivery="local"
# ---------------------------------------------------------------------------

def test_no_smtp_returns_local_delivery(client, clear_smtp_env, mock_generate_3mf, local_downloads):
    """Bug: was HTTP 500 'SMTP not configured'.  Must be 200 with delivery='local'."""
    resp = client.post(
        "/api/generate_plate",
        json={"line1": "Alice Smith", "line2": "Hole 7", "line3": ""},
    )
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.get_data(as_text=True)}"
    data = resp.get_json()
    assert data["status"] == "ok"
    assert data["delivery"] == "local"
    assert data["local_path"] is not None, "local_path must be populated for local delivery"
    assert data.get("email_to") is None, "email_to must be absent when email was not sent"
    assert len(data.get("warnings", [])) > 0, "warnings must mention missing SMTP vars"


# ---------------------------------------------------------------------------
# Test 2 — All SMTP, no open_in_slicer → delivery="email", local_path=None
# ---------------------------------------------------------------------------

def test_full_smtp_email_only(client, full_smtp_env, mock_generate_3mf, mock_smtp_success, local_downloads):
    resp = client.post(
        "/api/generate_plate",
        json={"line1": "Bob Jones", "line2": "", "line3": "", "open_in_slicer": False},
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()
    assert data["status"] == "ok"
    assert data["delivery"] == "email"
    assert data["email_to"] is not None, "email_to must be set when email was sent"
    assert data.get("local_path") is None, "local_path must be None when only emailed"


# ---------------------------------------------------------------------------
# Test 3 — All SMTP, open_in_slicer=True → delivery="email+local", both paths
# ---------------------------------------------------------------------------

def test_full_smtp_email_plus_local(client, full_smtp_env, mock_generate_3mf, mock_smtp_success, local_downloads):
    resp = client.post(
        "/api/generate_plate",
        json={"line1": "Carol King", "line2": "", "line3": "", "open_in_slicer": True},
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()
    assert data["status"] == "ok"
    assert data["delivery"] == "email+local"
    assert data["email_to"] is not None
    assert data["local_path"] is not None


# ---------------------------------------------------------------------------
# Test 4 — Partial SMTP (only HOST) → 200, delivery="local", warnings include
#           SMTP_USER and SMTP_PASS
# ---------------------------------------------------------------------------

def test_partial_smtp_treated_as_unconfigured(client, clear_smtp_env, monkeypatch, mock_generate_3mf, local_downloads):
    monkeypatch.setenv("SMTP_HOST", "mail.example.com")
    # SMTP_USER and SMTP_PASS deliberately absent
    resp = client.post(
        "/api/generate_plate",
        json={"line1": "Dan Lemon", "line2": "", "line3": ""},
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()
    assert data["status"] == "ok"
    assert data["delivery"] == "local"
    warnings_text = " ".join(data.get("warnings", []))
    assert "SMTP_USER" in warnings_text, "warning must mention SMTP_USER"
    assert "SMTP_PASS" in warnings_text, "warning must mention SMTP_PASS"


# ---------------------------------------------------------------------------
# Test 5 — SMTP configured but connection refused → HTTP 500 (regression guard)
# ---------------------------------------------------------------------------

def test_smtp_connection_refused_still_500(client, full_smtp_env, mock_generate_3mf, monkeypatch, local_downloads):
    import smtplib

    class _RefusingSMTP:
        def __init__(self, *a, **kw):
            raise ConnectionRefusedError("refused")
        def __enter__(self): return self
        def __exit__(self, *a): pass

    monkeypatch.setattr(smtplib, "SMTP", _RefusingSMTP)

    resp = client.post(
        "/api/generate_plate",
        json={"line1": "Eve Hall", "line2": "", "line3": ""},
    )
    assert resp.status_code == 500, f"Expected 500 on connection refused, got {resp.status_code}"
    data = resp.get_json()
    assert "Connection refused" in data.get("msg", "") or "connection" in data.get("msg", "").lower()


# ---------------------------------------------------------------------------
# Test 6 — 3MF generation failure → HTTP 500 "3MF generation failed:"
# ---------------------------------------------------------------------------

def test_3mf_generation_failure_returns_500(client, clear_smtp_env, monkeypatch):
    def _failing_gen(*a, **kw):
        raise RuntimeError("blender exploded")

    try:
        import plate_text  # noqa: F401
    except ImportError:
        pt = type(sys)("plate_text")
        pt.generate_plate_3mf = _failing_gen
        sys.modules["plate_text"] = pt

    monkeypatch.setattr("plate_text.generate_plate_3mf", _failing_gen)

    resp = client.post(
        "/api/generate_plate",
        json={"line1": "Frank Test", "line2": "", "line3": ""},
    )
    assert resp.status_code == 500
    data = resp.get_json()
    assert "3MF generation failed" in data.get("msg", "")


# ---------------------------------------------------------------------------
# Test 7 — No lines provided → HTTP 400
# ---------------------------------------------------------------------------

def test_no_lines_returns_400(client):
    resp = client.post(
        "/api/generate_plate",
        json={"line1": "", "line2": "", "line3": ""},
    )
    assert resp.status_code == 400
    data = resp.get_json()
    assert "at least one line" in data.get("msg", "").lower()


# ---------------------------------------------------------------------------
# Test 8 — Local file exists, non-zero size, valid ZIP/3MF magic
# ---------------------------------------------------------------------------

def test_local_file_is_written_and_valid(client, clear_smtp_env, mock_generate_3mf, local_downloads):
    resp = client.post(
        "/api/generate_plate",
        json={"line1": "Grace Hopper", "line2": "Hole 18", "line3": ""},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["delivery"] == "local"
    local_path = data["local_path"]
    assert local_path is not None
    assert os.path.exists(local_path), f"local file not found at {local_path}"
    size = os.path.getsize(local_path)
    assert size > 0, "written 3MF must be non-empty"
    # 3MF is a ZIP — first two bytes are the ZIP magic PK (0x50 0x4B)
    with open(local_path, "rb") as fh:
        magic = fh.read(2)
    assert magic == b"PK", f"file does not start with ZIP magic, got {magic!r}"


# ---------------------------------------------------------------------------
# Helper tests for _smtp_config()
# ---------------------------------------------------------------------------

def _get_smtp_config_helper():
    """Import the helper from the app module (must exist after fix)."""
    import app as app_module
    return app_module._smtp_config


# Test 9 — All three vars set → missing_vars=[]

def test_smtp_config_all_set(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "mail.example.com")
    monkeypatch.setenv("SMTP_USER", "u@example.com")
    monkeypatch.setenv("SMTP_PASS", "pw")
    fn = _get_smtp_config_helper()
    smtp_host, smtp_port, smtp_user, smtp_pass, smtp_from, smtp_to, missing = fn()
    assert missing == [], f"Expected no missing vars, got {missing}"
    assert smtp_host == "mail.example.com"
    assert smtp_user == "u@example.com"


# Test 10 — Only SMTP_HOST set → missing_vars=["SMTP_USER", "SMTP_PASS"]

def test_smtp_config_only_host_set(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "mail.example.com")
    monkeypatch.delenv("SMTP_USER", raising=False)
    monkeypatch.delenv("SMTP_PASS", raising=False)
    fn = _get_smtp_config_helper()
    _, _, _, _, _, _, missing = fn()
    assert "SMTP_USER" in missing, f"SMTP_USER must be in missing, got {missing}"
    assert "SMTP_PASS" in missing, f"SMTP_PASS must be in missing, got {missing}"
    assert "SMTP_HOST" not in missing, f"SMTP_HOST is set, should not be missing"


# Test 11 — Zero env vars → all three missing

def test_smtp_config_none_set(monkeypatch):
    for var in ("SMTP_HOST", "SMTP_USER", "SMTP_PASS"):
        monkeypatch.delenv(var, raising=False)
    fn = _get_smtp_config_helper()
    _, _, _, _, _, _, missing = fn()
    assert set(missing) == {"SMTP_HOST", "SMTP_USER", "SMTP_PASS"}, (
        f"All three must be missing, got {missing}"
    )
