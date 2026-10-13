"""
test_grid_mode_switch_task774.py — Pipeline coverage for the 3-position
gridMode switch introduced in task 774 (v5.34).

Spec (Thomas, 2026-10-12):
  - gridMode = "delta"    → value is additive offset over Poisson-nearest default
                           (legacy behavior; ±20 mm clamp).
  - gridMode = "absolute" → value REPLACES the Poisson default; clamp to [0, 30]
                           mm; floor at BASE_THICKNESS_MM.
  - gridMode = "off"      → ignore gridCellHeights entirely; result equals a pure
                           Poisson fit (same as empty gridCellHeights). Stored
                           values are preserved on disk — the pipeline simply
                           doesn't consume them.

Also verifies backward compatibility: an EGM with gridCellHeights but no
gridMode key behaves exactly like the pre-v5.34 "delta" code path.

Run:
    cd /Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER
    python -m pytest app/tests/test_grid_mode_switch_task774.py -v
"""
from __future__ import annotations

import importlib.util
import math
import sys
from pathlib import Path

import numpy as np
import pytest

APP_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(APP_DIR))

GSD_PATH = APP_DIR / "gradient_surface_diagnostic.py"


def _load_gsd():
    spec = importlib.util.spec_from_file_location("gsd_task774", GSD_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _make_circular_green_pts(cx_px, cy_px, r_px, n=64):
    return [
        {"x": cx_px + r_px * math.cos(2 * math.pi * i / n),
         "y": cy_px + r_px * math.sin(2 * math.pi * i / n)}
        for i in range(n)
    ]


def _base_egm(cx_px=300.0, cy_px=300.0, r_px=105.0, n=64,
              grid_cell_heights=None, grid_mode=None):
    egm = {
        "course": "TestCourse",
        "hole": "99",
        "image": "dummy.png",
        "imageSize": {"width": 600, "height": 600},
        "elevationRange": 14.5,
        "greenScale": 1.0,
        "polygons": [{"name": "Green", "type": "green",
                      "points": _make_circular_green_pts(cx_px, cy_px, r_px, n)}],
        "fringeBoundaryHeights": [],
        "elevationSpikes": [],
    }
    if grid_cell_heights is not None:
        egm["gridCellHeights"] = grid_cell_heights
    if grid_mode is not None:
        egm["gridMode"] = grid_mode
    return egm


def _tps_at_cell(gsd, egm, cell_idx, bnd_z_val=3.0, grid_res=60):
    """Evaluate the TPS surface at the given cell's centre."""
    cx_px, cy_px, r_px = 300.0, 300.0, 105.0
    green_pts_px = np.array(
        [(p["x"], p["y"]) for p in egm["polygons"][0]["points"]], dtype=np.float64
    )
    scale, centroid_px = gsd._compute_px_to_mm(green_pts_px, egm)
    green_bnd_px = gsd.interpolate_catmull_rom(egm["polygons"][0]["points"])
    green_bnd_mm = gsd._px_to_mm_2d(green_bnd_px.copy(), scale, centroid_px)

    half = gsd.PRINT_SIZE_MM / 2.0 + gsd.FRINGE_XY_EXPANSION_MM / 2.0
    cell_side = 2.0 * half / 20.0

    GX, GY = np.meshgrid(
        np.linspace(-half, half, grid_res),
        np.linspace(-half, half, grid_res),
    )

    bnd_z = np.full(len(green_bnd_mm), bnd_z_val)

    z_tps = gsd._build_tps_grid_height_field(
        egm_data=egm,
        green_bnd_mm=green_bnd_mm,
        bnd_z=bnd_z,
        grid_x=GX,
        grid_y=GY,
    )

    col = cell_idx % 20
    row = cell_idx // 20
    cell_cx = -half + (col + 0.5) * cell_side
    cell_cy = -half + (row + 0.5) * cell_side
    dist_sq = (GX - cell_cx) ** 2 + (GY - cell_cy) ** 2
    ni = np.unravel_index(np.argmin(dist_sq), dist_sq.shape)
    return float(z_tps[ni]), z_tps


# ===========================================================================
# M1  Backward compat: missing gridMode == "delta"
# ===========================================================================

class TestBackwardCompatMissingMode:
    """M1: gridMode absent → behaves identically to explicit 'delta'."""

    def test_missing_mode_equals_delta(self):
        gsd = _load_gsd()
        # Cell 210 (centre of frame) raised +10 mm over Poisson default 3.0
        egm_missing = _base_egm(grid_cell_heights={"210": 10.0})
        egm_delta = _base_egm(grid_cell_heights={"210": 10.0}, grid_mode="delta")

        z_missing, _ = _tps_at_cell(gsd, egm_missing, 210)
        z_delta, _ = _tps_at_cell(gsd, egm_delta, 210)

        assert abs(z_missing - z_delta) < 1e-6, (
            f"Missing gridMode ({z_missing:.4f}) must behave identically to "
            f"explicit delta ({z_delta:.4f})"
        )


# ===========================================================================
# M2  Delta mode (regression)
# ===========================================================================

class TestDeltaMode:
    """M2: Delta mode preserves pre-v5.34 behavior — val is additive offset."""

    def test_delta_raises_cell_toward_sum(self):
        gsd = _load_gsd()
        # Poisson baseline 3.0; delta +10 → resolved cell Z should be near 13 mm.
        # TPS smoothing means we check the TPS value AT the cell centre is lifted
        # substantially above the 3 mm baseline.
        egm = _base_egm(grid_cell_heights={"210": 10.0}, grid_mode="delta")
        z_at_cell, _ = _tps_at_cell(gsd, egm, 210, bnd_z_val=3.0)
        assert z_at_cell > 7.0, (
            f"Delta mode: cell 210 Z = {z_at_cell:.3f} mm; expected > 7 "
            f"(baseline 3 + delta 10)"
        )

    def test_delta_clamps_to_plus_minus_20(self):
        """Delta mode: val outside ±20 is defensively clamped at the pipeline."""
        gsd = _load_gsd()
        # 500 mm delta would be absurd; must be clamped to +20.
        egm_big = _base_egm(grid_cell_heights={"210": 500.0}, grid_mode="delta")
        egm_cap = _base_egm(grid_cell_heights={"210": 20.0}, grid_mode="delta")
        z_big, _ = _tps_at_cell(gsd, egm_big, 210)
        z_cap, _ = _tps_at_cell(gsd, egm_cap, 210)
        assert abs(z_big - z_cap) < 1e-6, (
            f"Delta clamp broken: val=500 → {z_big:.4f}; val=20 → {z_cap:.4f} "
            "(should be identical)"
        )


# ===========================================================================
# M3  Absolute mode
# ===========================================================================

class TestAbsoluteMode:
    """M3: Absolute mode — val REPLACES the Poisson default, clamped to [0,30]."""

    def test_absolute_replaces_not_adds(self):
        """val=10 in absolute mode → cell Z near 10 (not 13 as in delta)."""
        gsd = _load_gsd()
        egm_abs = _base_egm(grid_cell_heights={"210": 10.0}, grid_mode="absolute")
        egm_delta = _base_egm(grid_cell_heights={"210": 10.0}, grid_mode="delta")
        z_abs, _ = _tps_at_cell(gsd, egm_abs, 210, bnd_z_val=3.0)
        z_delta, _ = _tps_at_cell(gsd, egm_delta, 210, bnd_z_val=3.0)
        # Delta produces baseline+val ≈ 13; absolute replaces with val ≈ 10.
        # z_delta should be strictly greater than z_abs when both > baseline.
        assert z_delta > z_abs + 1.5, (
            f"Absolute mode must differ from delta: z_abs={z_abs:.3f}, "
            f"z_delta={z_delta:.3f}. Expected delta > absolute by ~3 mm."
        )

    def test_absolute_clamps_to_30(self):
        """Absolute mode: val > 30 → clamped at 30."""
        gsd = _load_gsd()
        egm_big = _base_egm(grid_cell_heights={"210": 999.0}, grid_mode="absolute")
        egm_cap = _base_egm(grid_cell_heights={"210": 30.0}, grid_mode="absolute")
        z_big, _ = _tps_at_cell(gsd, egm_big, 210)
        z_cap, _ = _tps_at_cell(gsd, egm_cap, 210)
        assert abs(z_big - z_cap) < 1e-6, (
            f"Absolute upper clamp broken: val=999 → {z_big:.4f}; "
            f"val=30 → {z_cap:.4f} (should be identical)"
        )

    def test_absolute_clamps_to_zero_floor(self):
        """Absolute mode: val < 0 → clamped at 0, then floored at BASE_THICKNESS_MM."""
        gsd = _load_gsd()
        egm_neg = _base_egm(grid_cell_heights={"210": -50.0}, grid_mode="absolute")
        egm_zero = _base_egm(grid_cell_heights={"210": 0.0}, grid_mode="absolute")
        z_neg, _ = _tps_at_cell(gsd, egm_neg, 210)
        z_zero, _ = _tps_at_cell(gsd, egm_zero, 210)
        assert abs(z_neg - z_zero) < 1e-6, (
            f"Absolute lower clamp broken: val=-50 → {z_neg:.4f}; "
            f"val=0 → {z_zero:.4f} (should be identical)"
        )

    def test_absolute_resolved_at_base_thickness_floor(self):
        """Absolute val=0 → resolved cell Z is BASE_THICKNESS_MM (TPS may smooth)."""
        gsd = _load_gsd()
        # When Poisson baseline is 3.0 and the override cell is forced to BASE
        # (1.5), TPS near the cell should be depressed below baseline.
        egm_abs = _base_egm(grid_cell_heights={"210": 0.0}, grid_mode="absolute")
        z_at, _ = _tps_at_cell(gsd, egm_abs, 210, bnd_z_val=3.0)
        assert z_at < 3.0, (
            f"Absolute val=0 at cell 210 → Z={z_at:.3f}; expected < 3.0 "
            "(TPS should pull toward BASE_THICKNESS_MM floor at the override)"
        )
        assert z_at >= gsd.BASE_THICKNESS_MM - 0.5, (
            f"Z={z_at:.3f} dropped below BASE_THICKNESS_MM floor "
            f"({gsd.BASE_THICKNESS_MM}) — floor not enforced"
        )


# ===========================================================================
# M4  Off mode
# ===========================================================================

class TestOffMode:
    """M4: Off mode — gridCellHeights is ignored by the pipeline. Result equals
    the pure Poisson fit (same as empty gridCellHeights)."""

    def test_off_mode_matches_empty_grid(self):
        """gridMode='off' with values set produces same surface as empty grid."""
        gsd = _load_gsd()
        egm_off = _base_egm(
            grid_cell_heights={"210": 20.0, "100": 15.0, "0": -10.0},
            grid_mode="off",
        )
        egm_empty = _base_egm(grid_cell_heights={})

        _, z_off = _tps_at_cell(gsd, egm_off, 210)
        _, z_empty = _tps_at_cell(gsd, egm_empty, 210)

        # Entire TPS surface must match within floating-point tolerance.
        np.testing.assert_allclose(
            z_off, z_empty, atol=1e-6,
            err_msg="Off mode must produce identical TPS to empty gridCellHeights"
        )

    def test_off_mode_preserves_values_in_egm(self):
        """Off mode doesn't delete gridCellHeights — it just doesn't consume them.
        This is a contract check: the pipeline must not mutate the EGM dict."""
        gsd = _load_gsd()
        stored = {"210": 20.0, "100": 15.0}
        egm_off = _base_egm(grid_cell_heights=dict(stored), grid_mode="off")

        _tps_at_cell(gsd, egm_off, 210)

        # EGM must still carry the values untouched after pipeline consumption.
        assert egm_off.get("gridCellHeights") == stored, (
            "Off mode must not mutate gridCellHeights on the EGM "
            f"(got {egm_off.get('gridCellHeights')!r}, expected {stored!r})"
        )

    def test_off_mode_differs_from_delta(self):
        """Off mode must produce different TPS than delta when overrides are set."""
        gsd = _load_gsd()
        egm_off = _base_egm(grid_cell_heights={"210": 15.0}, grid_mode="off")
        egm_delta = _base_egm(grid_cell_heights={"210": 15.0}, grid_mode="delta")

        z_off, _ = _tps_at_cell(gsd, egm_off, 210)
        z_delta, _ = _tps_at_cell(gsd, egm_delta, 210)

        assert z_delta - z_off > 5.0, (
            f"Off vs delta didn't diverge enough: z_off={z_off:.3f}, "
            f"z_delta={z_delta:.3f} — expected delta higher by many mm"
        )


# ===========================================================================
# M5  Unknown mode falls back to delta
# ===========================================================================

class TestUnknownModeFallback:
    """M5: unknown gridMode values collapse to 'delta' (defensive)."""

    def test_garbage_mode_collapses_to_delta(self):
        gsd = _load_gsd()
        egm_bad = _base_egm(grid_cell_heights={"210": 10.0}, grid_mode="banana")
        egm_delta = _base_egm(grid_cell_heights={"210": 10.0}, grid_mode="delta")

        z_bad, _ = _tps_at_cell(gsd, egm_bad, 210)
        z_delta, _ = _tps_at_cell(gsd, egm_delta, 210)

        assert abs(z_bad - z_delta) < 1e-6, (
            f"Unknown gridMode must fall back to delta: "
            f"bad={z_bad:.4f}, delta={z_delta:.4f}"
        )
