"""
test_gps_collapse.py  —  v4.60 · GPS backend panel collapse tests
Bug→TDD: RED written first against pre-v4.60 editor.html (no wrapper div),
then GREEN after adding #gps-backend-body + toggle handler.

Since there is no JS runtime in the Python test suite, tests use:
  1. HTML structure assertions (regex / string search over the served page).
  2. JS code-shape guards (regex over the inline JS) to confirm the toggle
     binding and init call are present.

Test numbers continue from Phase 2 (T1-T15 used).  This file: T16-T20.
"""
import os
import re
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def editor_html_source():
    """Return the raw text of editor.html from the templates folder."""
    here = os.path.dirname(__file__)
    tpl_path = os.path.join(here, "..", "templates", "editor.html")
    with open(tpl_path, encoding="utf-8") as f:
        return f.read()


@pytest.fixture()
def app_client(tmp_path, monkeypatch):
    """Flask test client with a temp DB so the live DB is never touched."""
    tmp_db = str(tmp_path / "workspace.db")
    import app as _app_module
    monkeypatch.setattr(_app_module, "DB_PATH", tmp_db)
    _app_module.app.config["TESTING"] = True
    with _app_module.app.test_client() as client:
        yield client


# ──────────────────────────────────────────────────────────────────────────────
# T16: Structure — #gps-backend-body wrapper exists
# ──────────────────────────────────────────────────────────────────────────────

class TestGpsBackendBodyStructure:

    def test_wrapper_div_exists(self, editor_html_source):
        """T16a: editor.html has a div with id="gps-backend-body"."""
        assert 'id="gps-backend-body"' in editor_html_source, (
            "Expected div#gps-backend-body in editor.html — "
            "add the collapse wrapper around the GPS controls."
        )

    def test_wrapper_has_x_show_gps_enabled(self, editor_html_source):
        """T16b: the wrapper div uses x-show="gpsEnabled" for visibility control."""
        # Must have id + x-show on the same element (within a reasonable window)
        pattern = r'id="gps-backend-body"[^>]*x-show="gpsEnabled"|x-show="gpsEnabled"[^>]*id="gps-backend-body"'
        assert re.search(pattern, editor_html_source), (
            "div#gps-backend-body must declare x-show=\"gpsEnabled\"."
        )

    def test_checkbox_not_inside_body_wrapper(self, editor_html_source):
        """T16c: the 'Use GPS backend' checkbox appears BEFORE #gps-backend-body.

        This verifies the checkbox stays visible when the panel is collapsed.
        We check that the checkbox input line comes before the body-div opening.
        """
        checkbox_pos = editor_html_source.find('x-model="gpsEnabled"')
        body_pos = editor_html_source.find('id="gps-backend-body"')
        assert checkbox_pos != -1, "Could not find gpsEnabled checkbox in editor.html"
        assert body_pos != -1, "Could not find #gps-backend-body in editor.html"
        assert checkbox_pos < body_pos, (
            "The gpsEnabled checkbox must appear BEFORE (outside) the "
            "#gps-backend-body wrapper — checkbox should always be visible."
        )

    def test_gps_controls_inside_body_wrapper(self, editor_html_source):
        """T16d: GPS controls (file picker, sliders, map canvas, preview) are
        inside #gps-backend-body (i.e. they appear after it in the source)."""
        body_pos = editor_html_source.find('id="gps-backend-body"')
        assert body_pos != -1, "div#gps-backend-body not found"

        controls = [
            'x-ref="gpsMapCanvas"',         # map canvas
            'x-model="gpsFile"',            # GPS file picker
            'x-model.number="gpsVertExag"', # vert exag slider
            'x-model.number="gpsApproachM"',# approach input
            'x-model.number="gpsGridSize"', # gridSize dropdown
            'gpsPreviewDataUrl',            # live preview img
        ]
        for ctrl in controls:
            pos = editor_html_source.find(ctrl)
            assert pos != -1, f"Control not found in editor.html: {ctrl}"
            assert pos > body_pos, (
                f"Control '{ctrl}' must appear AFTER div#gps-backend-body "
                f"(i.e. inside the wrapper)."
            )

    def test_heading_outside_body_wrapper(self, editor_html_source):
        """T16e: The 'GPS Backend' heading h3 appears BEFORE #gps-backend-body.

        The heading should remain visible even when the panel is collapsed.
        """
        heading_pos = editor_html_source.find('>GPS Backend<')
        body_pos = editor_html_source.find('id="gps-backend-body"')
        assert heading_pos != -1, "GPS Backend heading not found in editor.html"
        assert body_pos != -1, "div#gps-backend-body not found"
        assert heading_pos < body_pos, (
            "The 'GPS Backend' heading must appear BEFORE #gps-backend-body "
            "(heading stays visible when the panel is collapsed)."
        )


# ──────────────────────────────────────────────────────────────────────────────
# T17: JS code-shape — x-transition directives present on the wrapper
# ──────────────────────────────────────────────────────────────────────────────

class TestGpsBackendBodyTransition:

    def test_enter_transition_declared(self, editor_html_source):
        """T17a: x-transition:enter is declared on the body wrapper."""
        # Extract the div opening tag for #gps-backend-body
        match = re.search(
            r'id="gps-backend-body"(.*?)>', editor_html_source, re.DOTALL
        )
        assert match, "div#gps-backend-body not found"
        tag_content = match.group(0)
        assert "x-transition:enter" in tag_content, (
            "div#gps-backend-body should have x-transition:enter for a 150ms "
            "fade-in animation."
        )

    def test_leave_transition_declared(self, editor_html_source):
        """T17b: x-transition:leave is declared on the body wrapper."""
        match = re.search(
            r'id="gps-backend-body"(.*?)>', editor_html_source, re.DOTALL
        )
        assert match, "div#gps-backend-body not found"
        tag_content = match.group(0)
        assert "x-transition:leave" in tag_content, (
            "div#gps-backend-body should have x-transition:leave for a 150ms "
            "fade-out animation."
        )


# ──────────────────────────────────────────────────────────────────────────────
# T18: Served page — /editor route includes the wrapper div
# ──────────────────────────────────────────────────────────────────────────────

class TestServedEditorPage:

    def test_served_page_has_gps_backend_body(self, app_client):
        """T18: GET /editor returns HTML containing div#gps-backend-body."""
        resp = app_client.get("/editor")
        assert resp.status_code == 200
        html = resp.data.decode("utf-8", errors="replace")
        assert 'id="gps-backend-body"' in html, (
            "Served /editor page must contain div#gps-backend-body."
        )

    def test_served_page_gps_checkbox_before_body(self, app_client):
        """T18b: In the served HTML, the gpsEnabled checkbox precedes the body wrapper."""
        resp = app_client.get("/editor")
        assert resp.status_code == 200
        html = resp.data.decode("utf-8", errors="replace")
        checkbox_pos = html.find('x-model="gpsEnabled"')
        body_pos = html.find('id="gps-backend-body"')
        assert checkbox_pos != -1 and body_pos != -1
        assert checkbox_pos < body_pos, (
            "Checkbox must precede #gps-backend-body in served HTML."
        )


# ──────────────────────────────────────────────────────────────────────────────
# T19: Persistence — gpsEnabled state initialisation in loadProject / startNew
# ──────────────────────────────────────────────────────────────────────────────

class TestGpsEnabledPersistence:

    def test_load_project_sets_gps_enabled_true(self, editor_html_source):
        """T19a: loadProject() assigns gpsEnabled from gpsBackend.enabled (true path)."""
        # Verify the JS line that sets gpsEnabled from loaded data is present
        assert "this.gpsEnabled  = gps.enabled === true;" in editor_html_source or \
               "this.gpsEnabled = gps.enabled === true;" in editor_html_source, (
            "loadProject() must set this.gpsEnabled from gps.enabled."
        )

    def test_start_new_project_resets_gps_enabled_false(self, editor_html_source):
        """T19b: startNewProject() resets gpsEnabled to false."""
        # The startNewProject reset block should set gpsEnabled to false
        assert "this.gpsEnabled   = false;" in editor_html_source or \
               "this.gpsEnabled = false;" in editor_html_source, (
            "startNewProject() must reset this.gpsEnabled = false."
        )

    def test_gps_enabled_default_is_false_in_data(self, editor_html_source):
        """T19c: The Alpine data initializer declares gpsEnabled: false as default."""
        assert "gpsEnabled: false," in editor_html_source, (
            "The data() object must initialize gpsEnabled: false so new "
            "projects and page-loads start with the panel collapsed."
        )


# ──────────────────────────────────────────────────────────────────────────────
# T20: APP_VERSION is v4.60
# ──────────────────────────────────────────────────────────────────────────────

class TestAppVersionBump:

    def test_app_version_is_v4_60(self):
        """T20: APP_VERSION in app.py is v4.60."""
        here = os.path.dirname(__file__)
        app_py = os.path.join(here, "..", "app.py")
        with open(app_py, encoding="utf-8") as f:
            src = f.read()
        assert 'APP_VERSION = "v4.60"' in src, (
            'app.py APP_VERSION must be "v4.60" — bump it from v4.59.'
        )
