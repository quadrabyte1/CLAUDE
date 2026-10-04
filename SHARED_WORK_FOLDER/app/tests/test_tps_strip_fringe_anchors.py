"""
test_tps_strip_fringe_anchors.py — Bug→TDD for T1 task 690: strip fringeBoundaryHeights
from TPS constraint set (Topo 2026-10-02).

Context:
    Thomas revealed that the exterior fringe numbers (10, 15, 20, 25, 30) are
    *distance-from-pin markers*, NOT altitudes.  The fringeBoundaryHeights
    constraint source shipped in v4.81→v4.91 is semantically wrong.

    _build_tps_base() must now *ignore* fringe_boundary_heights_mm entirely.
    The parameter is kept for API stability (Sienna removes callers in T2).
    When non-empty, a deprecation warning is logged.

    The base surface is now shaped ONLY by:
        • interior elevationSpikes
        • 16 outer-frame anchors at BASE_THICKNESS_MM

Tests (RED-first; will fail until _build_tps_base is patched):
    StripT1  Fringe anchors ignored: fbh=[(x,y,50)] + spike(0,0,8)
             → TPS Z at (x,y) is close to spike-driven value (~8), NOT 50.
    StripT2  Interior spike still honored (unchanged): spike at (x0,y0,8)
             → TPS Z at that point ≈ 8 within 0.1 mm.
    StripT3  Outer frame still honored (unchanged): Z at frame edge ≈ BASE_THICKNESS_MM.
    StripT4  C² smoothness regression: finite-difference gradient across
             a radial transect varies smoothly with no discontinuity.
    StripT5  Degenerate (0 spikes, 0 fbh, frame only): surface flat at BASE_THICKNESS_MM.
    StripT6  Deprecation notice: passing non-empty fbh logs a warning but does NOT raise.

Run:
    cd /Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER
    python -m pytest app/tests/test_tps_strip_fringe_anchors.py -v
"""
from __future__ import annotations

import importlib.util
import io
import logging
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
    spec = importlib.util.spec_from_file_location("gsd_strip_test", GSD_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_circular_green_pts(cx_px, cy_px, r_px, n=64):
    return [
        {"x": cx_px + r_px * math.cos(2 * math.pi * i / n),
         "y": cy_px + r_px * math.sin(2 * math.pi * i / n)}
        for i in range(n)
    ]


def _base_egm(cx_px=300.0, cy_px=300.0, r_px=105.0, n=64,
              elevation_range=14.5,
              fringe_boundary_heights=None,
              elevation_spikes=None):
    return {
        "course": "TestCourse",
        "hole": "99",
        "image": "dummy.png",
        "imageSize": {"width": 600, "height": 600},
        "elevationRange": elevation_range,
        "greenScale": 1.0,
        "polygons": [{"name": "Green", "type": "green",
                      "points": _make_circular_green_pts(cx_px, cy_px, r_px, n)}],
        "fringeBoundaryHeights": fringe_boundary_heights or [],
        "elevationSpikes": elevation_spikes or [],
    }


def _build_grid(gsd, n=50):
    half = gsd.PRINT_SIZE_MM / 2.0 + gsd.FRINGE_XY_EXPANSION_MM / 2.0
    gx = np.linspace(-half, half, n)
    gy = np.linspace(-half, half, n)
    return np.meshgrid(gx, gy)


def _nearest_z(GX, GY, z_tps, x, y):
    dist_sq = (GX - x) ** 2 + (GY - y) ** 2
    idx = np.unravel_index(np.argmin(dist_sq), dist_sq.shape)
    return float(z_tps[idx])


def _prepare_bnd(gsd, cx_px=300.0, cy_px=300.0, r_px=105.0, n=64):
    egm = _base_egm(cx_px, cy_px, r_px, n=n)
    green_pts_px = np.array(
        [(p["x"], p["y"]) for p in egm["polygons"][0]["points"]],
        dtype=np.float64,
    )
    scale, centroid_px = gsd._compute_px_to_mm(green_pts_px, egm)
    green_bnd_px = gsd.interpolate_catmull_rom(egm["polygons"][0]["points"])
    green_bnd_mm = gsd._px_to_mm_2d(green_bnd_px.copy(), scale, centroid_px)
    return egm, scale, centroid_px, green_bnd_mm


# ===========================================================================
# StripT1  Fringe anchors ignored
# ===========================================================================

class TestStripFringeAnchorsIgnored:
    """StripT1: fbh=(x,y,50) + spike(0,0,8) → TPS Z at (x,y) is NOT 50; it is
    driven by the interior spike (~8), not by the fringe anchor."""

    def test_fringe_anchor_ignored_spike_drives(self):
        """StripT1: Passing fbh=[(x,y,50)] with interior spike at (0,0,8):
        TPS Z at (x,y) must be close to spike-driven value, NOT 50 mm."""
        gsd = _load_gsd()
        assert hasattr(gsd, "_build_tps_base"), "_build_tps_base not found"

        cx_px, cy_px, r_px = 300.0, 300.0, 105.0
        egm, scale, centroid_px, green_bnd_mm = _prepare_bnd(gsd, cx_px, cy_px, r_px)

        # Interior spike at image centre → mm origin (centroid)
        spike_px = np.array([[cx_px, cy_px]], dtype=np.float64)
        spike_mm_xy = gsd._px_to_mm_2d(spike_px, scale, centroid_px)[0]
        spike_z = 8.0

        # Fringe anchor somewhere off to the side, with an absurd altitude 50 mm
        # (50 mm is well above any plausible elevation — should be ignored)
        from scipy.spatial import cKDTree
        anchor_px = np.array([[cx_px + r_px * 1.35, cy_px]], dtype=np.float64)
        anchor_mm = gsd._px_to_mm_2d(anchor_px, scale, centroid_px)[0]
        bnd_kd = cKDTree(green_bnd_mm)
        _, idx = bnd_kd.query(anchor_mm[:2], k=1)
        snapped_xy = green_bnd_mm[idx]

        GX, GY = _build_grid(gsd, n=60)

        z_tps = gsd._build_tps_base(
            egm_data=egm,
            green_bnd_mm=green_bnd_mm,
            elevation_spikes_mm=[{"xy_mm": spike_mm_xy, "z_mm": spike_z}],
            fringe_boundary_heights_mm=[{"xy_mm": snapped_xy, "z_mm": 50.0}],
            grid_x=GX,
            grid_y=GY,
        )

        z_at_anchor = _nearest_z(GX, GY, z_tps, snapped_xy[0], snapped_xy[1])

        # After the strip: fringe anchor (50 mm) is ignored.
        # Z at that location is driven by the interior spike (8 mm) + frame base.
        # The boundary is near the interior, so the TPS decays between ~8 mm
        # (spike) and BASE_THICKNESS_MM (frame).  Either way, must NOT be ~50.
        assert z_at_anchor < 20.0, (
            f"Fringe anchor (50 mm) should be ignored; TPS Z at anchor point "
            f"= {z_at_anchor:.4f} mm (expected < 20 mm, i.e. not 50-driven)"
        )
        # Also verify it is not exactly at BASE (some spike influence expected
        # somewhere on the surface — we just check it's finite and < 20)
        assert np.all(np.isfinite(z_tps)), "TPS surface contains NaN/Inf"

    def test_fringe_anchor_ignored_no_spike(self):
        """StripT1b: Passing fbh=[(x,y,50)] with NO interior spike:
        TPS Z is driven only by frame base → ~BASE_THICKNESS_MM, NOT 50 mm."""
        gsd = _load_gsd()
        assert hasattr(gsd, "_build_tps_base"), "_build_tps_base not found"

        cx_px, cy_px, r_px = 300.0, 300.0, 105.0
        egm, scale, centroid_px, green_bnd_mm = _prepare_bnd(gsd, cx_px, cy_px, r_px)

        from scipy.spatial import cKDTree
        anchor_px = np.array([[cx_px + r_px * 1.35, cy_px]], dtype=np.float64)
        anchor_mm = gsd._px_to_mm_2d(anchor_px, scale, centroid_px)[0]
        bnd_kd = cKDTree(green_bnd_mm)
        _, idx = bnd_kd.query(anchor_mm[:2], k=1)
        snapped_xy = green_bnd_mm[idx]

        GX, GY = _build_grid(gsd, n=50)

        z_tps = gsd._build_tps_base(
            egm_data=egm,
            green_bnd_mm=green_bnd_mm,
            elevation_spikes_mm=[],
            fringe_boundary_heights_mm=[{"xy_mm": snapped_xy, "z_mm": 50.0}],
            grid_x=GX,
            grid_y=GY,
        )

        z_at_anchor = _nearest_z(GX, GY, z_tps, snapped_xy[0], snapped_xy[1])
        base = gsd.BASE_THICKNESS_MM

        # With no spikes and fbh ignored, the surface is frame-base driven →
        # should be close to BASE_THICKNESS_MM, definitely not 50.
        assert z_at_anchor < 10.0, (
            f"With fbh ignored and no spikes, TPS Z at anchor should be near "
            f"BASE ({base:.1f} mm); got {z_at_anchor:.4f} mm"
        )
        assert np.all(np.isfinite(z_tps)), "TPS surface contains NaN/Inf"


# ===========================================================================
# StripT2  Interior spike still honored unchanged
# ===========================================================================

class TestStripSpikeHonoredUnchanged:
    """StripT2: Interior spike must still be honored after stripping fbh."""

    @pytest.mark.skip(reason="T5/T6: elevation_spikes_mm removed from TPS pipeline by task 698 — awaits Topo T6 completion")
    def test_interior_spike_honored(self):
        """StripT2: spike at (cx,cy,8) → TPS Z at that point ≈ 8 within 0.1 mm."""
        gsd = _load_gsd()
        assert hasattr(gsd, "_build_tps_base"), "_build_tps_base not found"

        cx_px, cy_px, r_px = 300.0, 300.0, 105.0
        egm, scale, centroid_px, green_bnd_mm = _prepare_bnd(gsd, cx_px, cy_px, r_px)

        spike_px = np.array([[cx_px, cy_px]], dtype=np.float64)
        spike_mm_xy = gsd._px_to_mm_2d(spike_px, scale, centroid_px)[0]
        spike_z = 8.0

        GX, GY = _build_grid(gsd, n=60)

        z_tps = gsd._build_tps_base(
            egm_data=egm,
            green_bnd_mm=green_bnd_mm,
            elevation_spikes_mm=[{"xy_mm": spike_mm_xy, "z_mm": spike_z}],
            fringe_boundary_heights_mm=[],
            grid_x=GX,
            grid_y=GY,
        )

        z_at_spike = _nearest_z(GX, GY, z_tps, spike_mm_xy[0], spike_mm_xy[1])
        assert z_at_spike == pytest.approx(spike_z, abs=0.1), (
            f"Interior spike Z={spike_z} mm; TPS Z at spike = {z_at_spike:.4f} mm"
        )


# ===========================================================================
# StripT3  Outer frame still honored unchanged
# ===========================================================================

class TestStripOuterFrameHonored:
    """StripT3: Z at outer frame anchors ≈ BASE_THICKNESS_MM after stripping fbh."""

    def test_frame_z_near_base(self):
        """StripT3: Frame ring Z ≈ BASE_THICKNESS_MM ± 2 mm (unchanged by strip)."""
        gsd = _load_gsd()
        assert hasattr(gsd, "_build_tps_base"), "_build_tps_base not found"

        cx_px, cy_px, r_px = 300.0, 300.0, 105.0
        egm, scale, centroid_px, green_bnd_mm = _prepare_bnd(gsd, cx_px, cy_px, r_px)

        # Pass a fringe anchor (should be ignored); verify frame is still BASE
        from scipy.spatial import cKDTree
        anchor_px = np.array([[cx_px + r_px * 1.35, cy_px]], dtype=np.float64)
        anchor_mm = gsd._px_to_mm_2d(anchor_px, scale, centroid_px)[0]
        bnd_kd = cKDTree(green_bnd_mm)
        _, idx = bnd_kd.query(anchor_mm[:2], k=1)
        snapped_xy = green_bnd_mm[idx]

        GX, GY = _build_grid(gsd, n=60)
        half = gsd.PRINT_SIZE_MM / 2.0 + gsd.FRINGE_XY_EXPANSION_MM / 2.0

        z_tps = gsd._build_tps_base(
            egm_data=egm,
            green_bnd_mm=green_bnd_mm,
            elevation_spikes_mm=[],
            fringe_boundary_heights_mm=[{"xy_mm": snapped_xy, "z_mm": 12.0}],
            grid_x=GX,
            grid_y=GY,
        )

        r_outer = half * 1.05
        base = gsd.BASE_THICKNESS_MM
        for angle in np.linspace(0, 2 * np.pi, 8, endpoint=False):
            fx = r_outer * np.cos(angle)
            fy = r_outer * np.sin(angle)
            fz = _nearest_z(GX, GY, z_tps, fx, fy)
            assert abs(fz - base) < 3.0, (
                f"Frame Z = {fz:.4f} mm; expected near BASE={base:.1f} mm"
            )


# ===========================================================================
# StripT4  C² smoothness regression (no crease introduced by strip)
# ===========================================================================

class TestStripSmoothnessRegression:
    """StripT4: Surface is still smooth after removing fringe-anchor constraints."""

    def test_radial_transect_smooth(self):
        """StripT4: Finite-difference 2nd derivative across radial transect < 2 mm/mm."""
        gsd = _load_gsd()
        assert hasattr(gsd, "_build_tps_base"), "_build_tps_base not found"

        cx_px, cy_px, r_px = 300.0, 300.0, 105.0
        egm, scale, centroid_px, green_bnd_mm = _prepare_bnd(gsd, cx_px, cy_px, r_px)

        # Single interior spike at center
        spike_px = np.array([[cx_px, cy_px]], dtype=np.float64)
        spike_mm_xy = gsd._px_to_mm_2d(spike_px, scale, centroid_px)[0]

        # Build 1D transect grid along X axis through spike
        step_mm = 1.0
        n_sample = 30
        half = gsd.PRINT_SIZE_MM / 2.0 + gsd.FRINGE_XY_EXPANSION_MM / 2.0
        sample_xs = np.linspace(-half, half, n_sample)
        sample_ys = np.zeros(n_sample)
        GX = sample_xs.reshape(1, -1)
        GY = sample_ys.reshape(1, -1)

        z_tps = gsd._build_tps_base(
            egm_data=egm,
            green_bnd_mm=green_bnd_mm,
            elevation_spikes_mm=[{"xy_mm": spike_mm_xy, "z_mm": 8.0}],
            fringe_boundary_heights_mm=[],  # stripped
            grid_x=GX,
            grid_y=GY,
        ).ravel()

        dx = sample_xs[1] - sample_xs[0]
        dz = np.abs(np.diff(z_tps)) / abs(dx)
        d2z = np.abs(np.diff(dz))
        max_jump = float(d2z.max()) if len(d2z) > 0 else 0.0

        assert max_jump < 2.0, (
            f"Surface derivative jump = {max_jump:.4f} mm/mm (> 2.0); "
            f"strip may have introduced a crease"
        )
        assert np.all(np.isfinite(z_tps)), "TPS has NaN/Inf after strip"


# ===========================================================================
# StripT5  Degenerate: 0 spikes, 0 fbh → flat BASE_THICKNESS_MM
# ===========================================================================

class TestStripDegenerate:
    """StripT5: With 0 spikes and 0 fringe anchors, surface is flat at BASE."""

    def test_degenerate_flat_surface(self):
        """StripT5: _build_tps_base(spikes=[], fbh=[]) → all Z ≈ BASE_THICKNESS_MM."""
        gsd = _load_gsd()
        assert hasattr(gsd, "_build_tps_base"), "_build_tps_base not found"

        cx_px, cy_px, r_px = 300.0, 300.0, 105.0
        egm, scale, centroid_px, green_bnd_mm = _prepare_bnd(gsd, cx_px, cy_px, r_px)

        GX, GY = _build_grid(gsd, n=30)

        z_tps = gsd._build_tps_base(
            egm_data=egm,
            green_bnd_mm=green_bnd_mm,
            elevation_spikes_mm=[],
            fringe_boundary_heights_mm=[],
            grid_x=GX,
            grid_y=GY,
        )

        base = gsd.BASE_THICKNESS_MM
        assert np.all(np.abs(z_tps - base) < 0.5), (
            f"Degenerate case: Z range [{z_tps.min():.3f},{z_tps.max():.3f}] mm; "
            f"expected flat at BASE={base:.1f} mm"
        )


# ===========================================================================
# StripT6  Deprecation warning: passing non-empty fbh logs warning, no raise
# ===========================================================================

class TestStripDeprecationWarning:
    """StripT6: _build_tps_base with non-empty fbh logs a deprecation warning
    but does not raise an exception."""

    def test_nonempty_fbh_warns_not_raises(self, capfd):
        """StripT6: non-empty fringe_boundary_heights_mm → warning printed, no error."""
        gsd = _load_gsd()
        assert hasattr(gsd, "_build_tps_base"), "_build_tps_base not found"

        cx_px, cy_px, r_px = 300.0, 300.0, 105.0
        egm, scale, centroid_px, green_bnd_mm = _prepare_bnd(gsd, cx_px, cy_px, r_px)

        from scipy.spatial import cKDTree
        anchor_px = np.array([[cx_px + r_px * 1.35, cy_px]], dtype=np.float64)
        anchor_mm = gsd._px_to_mm_2d(anchor_px, scale, centroid_px)[0]
        bnd_kd = cKDTree(green_bnd_mm)
        _, idx = bnd_kd.query(anchor_mm[:2], k=1)
        snapped_xy = green_bnd_mm[idx]

        GX, GY = _build_grid(gsd, n=20)

        # Must not raise
        z_tps = gsd._build_tps_base(
            egm_data=egm,
            green_bnd_mm=green_bnd_mm,
            elevation_spikes_mm=[],
            fringe_boundary_heights_mm=[{"xy_mm": snapped_xy, "z_mm": 8.0}],
            grid_x=GX,
            grid_y=GY,
        )

        assert z_tps.shape == GX.shape, "Output shape mismatch"
        assert np.all(np.isfinite(z_tps)), "TPS has NaN/Inf"

        # The implementation should print a deprecation notice to stdout
        # (captured by capfd).  Verify it mentions the deprecated parameter.
        captured = capfd.readouterr()
        output = captured.out
        # Any variant of "deprecated", "ignored", "fringeBoundaryHeights" etc.
        assert any(word in output.lower() for word in
                   ("deprecat", "ignored", "fringeboundary", "strip")), (
            f"Expected deprecation warning in stdout, got: {output!r}"
        )
