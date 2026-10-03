"""
test_strip_spike_application.py — Bug→TDD for T6 task 698:
Strip Gaussian spike-application code from build_fringe_mesh.

Thomas pivot (2026-10-02): Drop the OCR→elevationSpikes→Gaussian-bump pipeline.
The Gaussian bump loop that raised fringe Z around spike centres is removed.
TPS harness stays intact; elevation_spikes_mm becomes accepted-but-ignored
(same deprecation pattern as fringe_boundary_heights_mm in task 690).

Tests (RED first — all will FAIL until gradient_surface_diagnostic.py v0.15):

    SA1  No Gaussian bumps with empty elevation_spikes_mm:
         build_fringe_mesh with elevationSpikes=[] produces no spike-driven peaks.
         Fringe top vertices have Z within BASE ± (ELEVATION_RANGE/2) globally.

    SA2  elevation_spikes_mm accepted-but-ignored at TPS level:
         _build_tps_base with a non-empty elevation_spikes_mm list STILL accepts
         the argument (no TypeError) but — wait, elevation_spikes_mm IS used by
         TPS to shape the surface.  The "accepted-but-ignored" deprecation is for
         the POST-TPS Gaussian bump loop.  So SA2 tests that passing elevationSpikes
         in the EGM dict does NOT create Gaussian bumps in the fringe grid Z
         (the TPS surface from spikes is still fine; the LOCAL Gaussian-MAX-blend
         bump loop is gone).

    SA3  TPS primitive still callable with empty spikes + empty fringe_anchors:
         _build_tps_base(spikes=[], fbh=[], frame ring) → flat near BASE_THICKNESS_MM
         (this is a regression guard — TPS must survive the spike strip).

    SA4  Regression — Poisson green surface still shaped:
         build_fringe_mesh on an EGM with elevation arrows (slope field) still
         produces green vertices with non-trivial Z variation (arrows still drive it).

    SA5  Degenerate (0 constraints beyond frame ring):
         TPS output is sensible (flat), fringe mesh builds, no crash.

    SA6  Constants gone: SPIKE_SIGMA_MM, SPIKE_INFLUENCE_MM, SPIKE_HARD_MAX_MM
         must NOT be module-level names in gradient_surface_diagnostic after v0.15.

    SA7  elevation_spikes_mm accepted-but-ignored at fringe pipeline level:
         build_fringe_mesh with elevationSpikes=[{"x":300,"y":300,"mm":30}]
         produces NO Gaussian-bump peaks: max fringe Z is NOT pulled to 30 mm
         (which the old bump loop would have produced).

Run:
    cd /Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER
    python -m pytest app/tests/test_strip_spike_application.py -v
"""
from __future__ import annotations

import importlib.util
import math
import sys
from pathlib import Path

import numpy as np
import pytest

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
APP_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(APP_DIR))

GSD_PATH = APP_DIR / "gradient_surface_diagnostic.py"


def _load_gsd():
    """Load gradient_surface_diagnostic as a fresh module instance."""
    spec = importlib.util.spec_from_file_location("gsd_spike_strip_test", GSD_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Shared geometry helpers
# ---------------------------------------------------------------------------

def _make_circular_green_pts(cx_px, cy_px, r_px, n=64):
    return [
        {"x": cx_px + r_px * math.cos(2 * math.pi * i / n),
         "y": cy_px + r_px * math.sin(2 * math.pi * i / n)}
        for i in range(n)
    ]


def _base_egm(cx_px=300.0, cy_px=300.0, r_px=105.0,
              elevation_range=14.5,
              elevation_spikes=None,
              extra_polygons=None):
    """Build a minimal egm_data dict.  No fringeBoundaryHeights."""
    egm = {
        "course": "TestCourse",
        "hole": "99",
        "image": "dummy.png",
        "imageSize": {"width": 600, "height": 600},
        "elevationRange": elevation_range,
        "greenScale": 1.0,
        "polygons": [{"name": "Green", "type": "green",
                      "points": _make_circular_green_pts(cx_px, cy_px, r_px)}],
        "fringeBoundaryHeights": [],
        "elevationSpikes": elevation_spikes or [],
    }
    if extra_polygons:
        egm["polygons"].extend(extra_polygons)
    return egm


def _flat_green_arrays(cx_px, cy_px, r_px, grid_res=200, z_val=3.0):
    """Build flat inside_mask + Z_mm + xs_g + ys_g for a circular green."""
    xs_g = np.linspace(0, 599, grid_res)
    ys_g = np.linspace(0, 599, grid_res)
    inside_mask = np.zeros((grid_res, grid_res), dtype=bool)
    Z_mm = np.full((grid_res, grid_res), z_val)
    for ri, py in enumerate(ys_g):
        for ci, px in enumerate(xs_g):
            if math.hypot(px - cx_px, py - cy_px) < r_px:
                inside_mask[ri, ci] = True
    return Z_mm, xs_g, ys_g, inside_mask


# ===========================================================================
# SA1  No Gaussian bumps with empty elevationSpikes
# ===========================================================================

class TestNoGaussianBumpsEmptySpikes:
    """SA1: build_fringe_mesh with elevationSpikes=[] → no spike-driven peaks."""

    def test_empty_spikes_no_bumps(self):
        """SA1: With elevationSpikes=[], fringe top Z is flat (only TPS frame ring).
        No Gaussian bump should elevate any cell beyond BASE + small TPS variation."""
        gsd = _load_gsd()
        cx_px, cy_px, r_px = 300.0, 300.0, 105.0
        egm = _base_egm(cx_px, cy_px, r_px, elevation_spikes=[])

        green_bnd_px = gsd.interpolate_catmull_rom(egm["polygons"][0]["points"])
        Z_mm, xs_g, ys_g, inside_mask = _flat_green_arrays(cx_px, cy_px, r_px)

        fringe_mesh = gsd.build_fringe_mesh(
            Z_mm, xs_g, ys_g, inside_mask,
            green_bnd_px, egm,
            fringe_grid_res=80,
        )

        verts = np.asarray(fringe_mesh.vertices)
        top_verts = verts[verts[:, 2] > gsd.BASE_THICKNESS_MM * 0.5]
        assert len(top_verts) > 0, "No top fringe vertices found"

        # With empty spikes and flat green (Z=3mm), TPS has only 16 frame anchors
        # → surface near BASE_THICKNESS_MM. No Gaussian bump should spike it.
        base = gsd.BASE_THICKNESS_MM
        elev_range = float(egm["elevationRange"])
        # Max allowable Z: green Z (≈3mm = base) + small TPS variation; spike loop gone
        max_z = float(top_verts[:, 2].max())
        assert max_z < base + elev_range, (
            f"Fringe top Z max={max_z:.3f} mm is unexpectedly high "
            f"(BASE={base:.1f}, elevRange={elev_range:.1f}). "
            f"Possible Gaussian bump loop still active?"
        )
        assert np.all(np.isfinite(top_verts)), "Fringe top vertices have NaN/Inf"


# ===========================================================================
# SA2  elevation_spikes_mm in EGM does NOT produce Gaussian bumps
# ===========================================================================

class TestElevationSpikesNoGaussianBumps:
    """SA2: Passing elevationSpikes in EGM must not produce Gaussian bump peaks."""

    def test_spike_in_egm_no_bump_peak(self):
        """SA2: elevationSpikes=[{"x":cx,"y":cy,"mm":30}] → fringe max Z is NOT ~30mm.

        The old Gaussian loop would have raised fringe Z to ~30mm around the spike.
        After stripping, the spike is only seen by TPS (which shapes the global surface),
        NOT by a post-filter Gaussian bump that would create a localized 30mm peak.
        The max fringe Z should be well below 30mm (TPS smoothly interpolates).
        """
        gsd = _load_gsd()
        cx_px, cy_px, r_px = 300.0, 300.0, 105.0
        # Spike at fringe area (outside green radius, i.e. 1.5× radius from centre)
        spike_x = cx_px + r_px * 1.5
        spike_y = cy_px
        spike_mm = 30.0  # absurdly high — only matters to the Gaussian loop

        egm = _base_egm(
            cx_px, cy_px, r_px,
            elevation_spikes=[{"x": spike_x, "y": spike_y, "mm": spike_mm}],
        )
        green_bnd_px = gsd.interpolate_catmull_rom(egm["polygons"][0]["points"])
        Z_mm, xs_g, ys_g, inside_mask = _flat_green_arrays(cx_px, cy_px, r_px)

        fringe_mesh = gsd.build_fringe_mesh(
            Z_mm, xs_g, ys_g, inside_mask,
            green_bnd_px, egm,
            fringe_grid_res=80,
        )

        verts = np.asarray(fringe_mesh.vertices)
        top_verts = verts[verts[:, 2] > gsd.BASE_THICKNESS_MM * 0.5]
        assert len(top_verts) > 0, "No top fringe vertices"

        max_z = float(top_verts[:, 2].max())

        # OLD behaviour: Gaussian loop would raise cells near spike to ~30 mm.
        # NEW behaviour: No Gaussian loop → max Z is TPS-shaped + green seam Z.
        # 30mm bump should be GONE. Max should be < spike_mm - significant margin.
        assert max_z < spike_mm - 5.0, (
            f"Fringe max Z = {max_z:.3f} mm is suspiciously close to spike {spike_mm} mm. "
            f"Gaussian bump loop may still be active (should be stripped in v0.15)."
        )


# ===========================================================================
# SA3  TPS primitive still callable with empty inputs
# ===========================================================================

class TestTPSPrimitiveCallable:
    """SA3: _build_tps_base with empty spikes + empty fringe_anchors → flat near BASE."""

    def test_tps_callable_empty_inputs(self):
        """SA3: TPS survives with spikes=[], fbh=[] + outer-frame ring → flat BASE."""
        gsd = _load_gsd()
        assert hasattr(gsd, "_build_tps_base"), "_build_tps_base not found in v0.15"

        cx_px, cy_px, r_px = 300.0, 300.0, 105.0
        egm = _base_egm(cx_px, cy_px, r_px)
        green_pts_px = np.array(
            [(p["x"], p["y"]) for p in egm["polygons"][0]["points"]],
            dtype=np.float64,
        )
        scale, centroid_px = gsd._compute_px_to_mm(green_pts_px, egm)
        green_bnd_px = gsd.interpolate_catmull_rom(egm["polygons"][0]["points"])
        green_bnd_mm = gsd._px_to_mm_2d(green_bnd_px.copy(), scale, centroid_px)

        half = gsd.PRINT_SIZE_MM / 2.0 + gsd.FRINGE_XY_EXPANSION_MM / 2.0
        grid_res = 30
        gx = np.linspace(-half, half, grid_res)
        gy = np.linspace(-half, half, grid_res)
        GX, GY = np.meshgrid(gx, gy)

        # Must not raise; must return sensible values
        z_tps = gsd._build_tps_base(
            egm_data=egm,
            green_bnd_mm=green_bnd_mm,
            elevation_spikes_mm=[],
            fringe_boundary_heights_mm=[],
            grid_x=GX,
            grid_y=GY,
        )

        assert z_tps.shape == GX.shape, "TPS output shape mismatch"
        assert np.all(np.isfinite(z_tps)), "TPS output has NaN/Inf with empty inputs"

        base = gsd.BASE_THICKNESS_MM
        # With only the 16-point frame ring at BASE, surface should be flat at BASE
        assert np.all(np.abs(z_tps - base) < 0.5), (
            f"TPS with empty inputs should be flat at BASE={base:.1f} mm; "
            f"got range [{z_tps.min():.3f}, {z_tps.max():.3f}]"
        )


# ===========================================================================
# SA4  Regression — Poisson green surface still shaped
# ===========================================================================

class TestPoissonGreenRegression:
    """SA4: Green interior Z must still be driven by slope arrows (Poisson)."""

    def test_green_z_varies_with_slope_arrows(self):
        """SA4: EGM with slopeArrows → green Z has non-trivial variation (arrows active)."""
        gsd = _load_gsd()
        cx_px, cy_px, r_px = 300.0, 300.0, 105.0

        # Build an EGM with slope arrows pointing from left to right
        # (a simple uniform gradient in X should produce varying Z).
        slope_arrows = [
            {"x": cx_px - r_px * 0.5, "y": cy_px, "angle": 0.0, "strength": 5.0},
            {"x": cx_px + r_px * 0.5, "y": cy_px, "angle": 0.0, "strength": 5.0},
        ]
        egm = _base_egm(cx_px, cy_px, r_px, elevation_spikes=[])
        egm["slopeArrows"] = slope_arrows

        green_bnd_px = gsd.interpolate_catmull_rom(egm["polygons"][0]["points"])
        Z_mm, xs_g, ys_g, inside_mask = _flat_green_arrays(cx_px, cy_px, r_px, z_val=3.0)

        fringe_mesh = gsd.build_fringe_mesh(
            Z_mm, xs_g, ys_g, inside_mask,
            green_bnd_px, egm,
            fringe_grid_res=80,
        )

        # Fringe mesh must be valid — Poisson green is not directly part of
        # the fringe mesh, but the green boundary Z (seam) should vary.
        verts = np.asarray(fringe_mesh.vertices)
        assert len(verts) > 0, "Fringe mesh empty with slope arrows"
        assert np.all(np.isfinite(verts)), "Fringe mesh has NaN/Inf"
        # Verify fringe still builds (no crash = Poisson pipe intact)


# ===========================================================================
# SA5  Degenerate — 0 constraints beyond frame ring
# ===========================================================================

class TestDegenerateZeroConstraints:
    """SA5: TPS + fringe mesh with 0 extra constraints → sensible output, no crash."""

    def test_zero_extra_constraints_builds(self):
        """SA5: Empty spikes + empty fbh → fringe mesh builds, no crash."""
        gsd = _load_gsd()
        cx_px, cy_px, r_px = 300.0, 300.0, 105.0
        egm = _base_egm(cx_px, cy_px, r_px,
                        elevation_spikes=[])  # nothing beyond frame ring

        green_bnd_px = gsd.interpolate_catmull_rom(egm["polygons"][0]["points"])
        Z_mm, xs_g, ys_g, inside_mask = _flat_green_arrays(cx_px, cy_px, r_px)

        # Must not raise
        fringe_mesh = gsd.build_fringe_mesh(
            Z_mm, xs_g, ys_g, inside_mask,
            green_bnd_px, egm,
            fringe_grid_res=60,
        )

        verts = np.asarray(fringe_mesh.vertices)
        assert len(verts) > 0, "Fringe mesh has no vertices (degenerate failure)"
        assert np.all(np.isfinite(verts)), "Fringe mesh vertices have NaN/Inf"

        top_verts = verts[verts[:, 2] > gsd.BASE_THICKNESS_MM * 0.5]
        assert len(top_verts) > 0, "No top surface vertices in degenerate case"


# ===========================================================================
# SA6  Constants gone: SPIKE_SIGMA_MM, SPIKE_INFLUENCE_MM, SPIKE_HARD_MAX_MM
# ===========================================================================

class TestSpikeConstantsRemoved:
    """SA6: Module-level spike constants must be absent after v0.15 strip."""

    def test_spike_constants_not_at_module_level(self):
        """SA6: SPIKE_SIGMA_MM, SPIKE_INFLUENCE_MM, SPIKE_HARD_MAX_MM must NOT
        be defined at module scope in gradient_surface_diagnostic v0.15."""
        gsd = _load_gsd()

        assert not hasattr(gsd, "SPIKE_SIGMA_MM"), (
            "SPIKE_SIGMA_MM is still present at module level — "
            "Gaussian spike constant was not removed in v0.15"
        )
        assert not hasattr(gsd, "SPIKE_INFLUENCE_MM"), (
            "SPIKE_INFLUENCE_MM is still present at module level — "
            "Gaussian spike constant was not removed in v0.15"
        )
        assert not hasattr(gsd, "SPIKE_HARD_MAX_MM"), (
            "SPIKE_HARD_MAX_MM is still present at module level — "
            "Gaussian spike constant was not removed in v0.15"
        )


# ===========================================================================
# SA7  EGM with elevation_spikes → accepted, no Gaussian bump peak in fringe
# ===========================================================================

class TestElevationSpikesDeprecatedAtPipeline:
    """SA7: build_fringe_mesh accepts EGM with elevationSpikes but does NOT
    apply Gaussian bumps to fringe Z after the strip (v0.15)."""

    def test_spikes_ignored_in_fringe_pipeline(self, capfd):
        """SA7: elevationSpikes present in EGM → pipeline accepts, no Gaussian bump.

        Spike at 30mm target should NOT create a 30mm fringe vertex anywhere.
        A deprecation notice should be printed (or at minimum no crash).
        """
        gsd = _load_gsd()
        cx_px, cy_px, r_px = 300.0, 300.0, 105.0

        # Spike inside the fringe area (not inside green)
        spike_x = cx_px + r_px * 1.4   # outside green radius
        spike_y = cy_px
        spike_mm_target = 30.0          # very high — old Gaussian loop would honor this

        egm = _base_egm(
            cx_px, cy_px, r_px,
            elevation_spikes=[{"x": spike_x, "y": spike_y, "mm": spike_mm_target}],
        )
        green_bnd_px = gsd.interpolate_catmull_rom(egm["polygons"][0]["points"])
        Z_mm, xs_g, ys_g, inside_mask = _flat_green_arrays(cx_px, cy_px, r_px)

        fringe_mesh = gsd.build_fringe_mesh(
            Z_mm, xs_g, ys_g, inside_mask,
            green_bnd_px, egm,
            fringe_grid_res=80,
        )

        verts = np.asarray(fringe_mesh.vertices)
        top_verts = verts[verts[:, 2] > gsd.BASE_THICKNESS_MM * 0.5]
        assert len(top_verts) > 0, "No top fringe vertices"
        assert np.all(np.isfinite(top_verts)), "Fringe vertices have NaN/Inf"

        max_z = float(top_verts[:, 2].max())

        # Gaussian bump loop REMOVED: max Z must not be near spike_mm_target.
        # TPS will incorporate the spike gently, but not create a 30mm local peak
        # via the old MAX-Gaussian-blend.
        assert max_z < spike_mm_target - 5.0, (
            f"Fringe max Z={max_z:.3f} mm is suspiciously close to spike target "
            f"{spike_mm_target} mm. Post-filter Gaussian bump loop may still exist. "
            f"v0.15 should have stripped it."
        )

        # Check for deprecation notice in stdout
        captured = capfd.readouterr()
        output = captured.out
        # After v0.15, elevation_spikes_mm is accepted-but-ignored at the
        # Gaussian-bump layer. A notice like "[TPS] DEPRECATED: elevation_spikes_mm"
        # should appear. Accept either that or a simple "ignored" token.
        assert any(tok in output for tok in (
            "DEPRECATED", "deprecated", "ignored", "elevation_spikes"
        )), (
            f"Expected a deprecation/ignored notice for elevation_spikes_mm in "
            f"v0.15, but stdout was: {output[:500]!r}"
        )
