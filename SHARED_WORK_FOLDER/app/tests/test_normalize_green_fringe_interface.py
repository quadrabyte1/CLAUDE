"""
test_normalize_green_fringe_interface.py — Task 780.

Tests for _normalize_green_fringe_interface:
  N1  Boundary cells (d=0) receive exact green Z.
  N2  Cells beyond the blend band are untouched.
  N3  Intermediate cells follow the cosine curve within tolerance.
  N4  Function is a no-op when the entire grid is outside the band.

Run:
    cd /Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER
    python -m pytest app/tests/test_normalize_green_fringe_interface.py \
                     app/tests/test_default_fringe_inherits_green_boundary.py -v
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
    spec = importlib.util.spec_from_file_location("gsd_norm_test", GSD_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _make_synthetic_setup(gsd, grid_res: int = 40):
    """Return a synthetic fringe grid + green boundary pair.

    Green boundary: a unit circle at the origin, scaled so its radius is
    ~30 mm.  Fringe grid: (grid_res x grid_res) over ±89 mm.

    Returns
    -------
    GX, GY : (grid_res, grid_res) meshgrid in mm
    green_bnd_mm : (N, 2) boundary points
    bnd_z_uniform : (N,) all set to TARGET_Z
    bnd_z_tilted  : (N,) linearly varying 5–10 mm across the boundary
    TARGET_Z : float
    W_mm : float  — blend band width used
    """
    half = gsd.PRINT_SIZE_MM / 2.0 + gsd.FRINGE_XY_EXPANSION_MM / 2.0
    xs = np.linspace(-half, half, grid_res)
    ys = np.linspace(-half, half, grid_res)
    GX, GY = np.meshgrid(xs, ys)

    # Green boundary: circle of radius 30 mm, 128 points
    r_green = 30.0
    n_bnd = 128
    angles = np.linspace(0, 2 * math.pi, n_bnd, endpoint=False)
    green_bnd_mm = np.column_stack([r_green * np.cos(angles),
                                    r_green * np.sin(angles)])

    TARGET_Z = 7.0
    bnd_z_uniform = np.full(n_bnd, TARGET_Z)

    bnd_z_tilted = 5.0 + 5.0 * (green_bnd_mm[:, 0] + r_green) / (2.0 * r_green)

    cell_side_mm = (2.0 * half) / 20.0
    W_mm = gsd.FRINGE_BLEND_CELLS * cell_side_mm

    return GX, GY, green_bnd_mm, bnd_z_uniform, bnd_z_tilted, TARGET_Z, W_mm


class TestNormaliseBoundaryExact:
    """N1: cells ON the green boundary receive exact green Z."""

    def test_boundary_cells_receive_green_z(self):
        gsd = _load_gsd()
        assert hasattr(gsd, "_normalize_green_fringe_interface"), (
            "_normalize_green_fringe_interface not found in gradient_surface_diagnostic"
        )

        GX, GY, green_bnd_mm, bnd_z_uniform, _, TARGET_Z, W_mm = _make_synthetic_setup(gsd)

        # TPS surface: uniform flat at a value DIFFERENT from TARGET_Z
        TPS_INITIAL = 4.0
        z_tps_in = np.full(GX.shape, TPS_INITIAL)

        z_out = gsd._normalize_green_fringe_interface(
            z_tps=z_tps_in,
            grid_x=GX,
            grid_y=GY,
            green_bnd_mm=green_bnd_mm,
            bnd_z=bnd_z_uniform,
        )

        # Find grid points whose XY is within 2 mm of the boundary (d ≈ 0).
        from scipy.spatial import cKDTree
        kd = cKDTree(green_bnd_mm)
        pts = np.column_stack([GX.ravel(), GY.ravel()])
        dists, _ = kd.query(pts, k=1)
        dists = dists.reshape(GX.shape)

        on_boundary = dists < 2.0
        assert on_boundary.any(), "No grid points within 2 mm of boundary — increase grid_res"

        z_boundary = z_out[on_boundary]
        assert np.allclose(z_boundary, TARGET_Z, atol=0.05), (
            f"N1 FAILED: cells at d<2mm expected Z≈{TARGET_Z} mm, "
            f"got range [{float(z_boundary.min()):.3f}, {float(z_boundary.max()):.3f}]"
        )


class TestNormaliseOutsideBandUntouched:
    """N2: cells beyond blend_cells distance are not modified."""

    def test_outside_band_unchanged(self):
        gsd = _load_gsd()

        GX, GY, green_bnd_mm, bnd_z_uniform, _, TARGET_Z, W_mm = _make_synthetic_setup(gsd)

        TPS_INITIAL = 3.5
        z_tps_in = np.full(GX.shape, TPS_INITIAL)

        z_out = gsd._normalize_green_fringe_interface(
            z_tps=z_tps_in,
            grid_x=GX,
            grid_y=GY,
            green_bnd_mm=green_bnd_mm,
            bnd_z=bnd_z_uniform,
        )

        from scipy.spatial import cKDTree
        kd = cKDTree(green_bnd_mm)
        pts = np.column_stack([GX.ravel(), GY.ravel()])
        dists, _ = kd.query(pts, k=1)
        dists = dists.reshape(GX.shape)

        outside_band = dists >= W_mm
        assert outside_band.any(), "No grid points outside blend band — increase W_mm or grid extent"

        assert np.allclose(z_out[outside_band], TPS_INITIAL, atol=1e-9), (
            f"N2 FAILED: cells outside blend band should be unchanged at {TPS_INITIAL} mm, "
            f"max deviation = {float(np.abs(z_out[outside_band] - TPS_INITIAL).max()):.6f}"
        )


class TestNormaliseCosineCurve:
    """N3: intermediate cells follow the cosine blend formula within tolerance."""

    def test_intermediate_cells_follow_cosine(self):
        gsd = _load_gsd()

        GX, GY, green_bnd_mm, bnd_z_uniform, _, TARGET_Z, W_mm = _make_synthetic_setup(gsd)

        TPS_INITIAL = 2.0  # clearly different from TARGET_Z=7.0
        z_tps_in = np.full(GX.shape, TPS_INITIAL)

        z_out = gsd._normalize_green_fringe_interface(
            z_tps=z_tps_in,
            grid_x=GX,
            grid_y=GY,
            green_bnd_mm=green_bnd_mm,
            bnd_z=bnd_z_uniform,
        )

        from scipy.spatial import cKDTree
        kd = cKDTree(green_bnd_mm)
        pts = np.column_stack([GX.ravel(), GY.ravel()])
        dists, _ = kd.query(pts, k=1)
        dists = dists.reshape(GX.shape)

        # Test cells at mid-band: 40-60% of W_mm
        mid_band = (dists >= 0.40 * W_mm) & (dists < 0.60 * W_mm)
        if not mid_band.any():
            pytest.skip("No grid points in 40-60% of blend band at this grid_res")

        d_mid = dists[mid_band]
        z_mid_expected = (
            (1.0 - 0.5 * (1.0 + np.cos(np.pi * d_mid / W_mm))) * TPS_INITIAL
            + 0.5 * (1.0 + np.cos(np.pi * d_mid / W_mm)) * TARGET_Z
        )
        z_mid_actual = z_out[mid_band]

        assert np.allclose(z_mid_actual, z_mid_expected, atol=1e-6), (
            f"N3 FAILED: intermediate cells deviate from cosine formula. "
            f"Max deviation = {float(np.abs(z_mid_actual - z_mid_expected).max()):.8f}"
        )


class TestNormaliseNoOpOutsideAll:
    """N4: when green boundary is very far, nothing changes."""

    def test_noop_when_all_outside_band(self):
        gsd = _load_gsd()

        GX, GY, _, _, _, _, W_mm = _make_synthetic_setup(gsd)

        # Put green boundary far outside the fringe grid (radius 500 mm)
        n_bnd = 64
        angles = np.linspace(0, 2 * math.pi, n_bnd, endpoint=False)
        far_bnd = np.column_stack([500.0 * np.cos(angles), 500.0 * np.sin(angles)])
        far_bnd_z = np.full(n_bnd, 9.0)

        TPS_INITIAL = 5.5
        z_tps_in = np.full(GX.shape, TPS_INITIAL)

        z_out = gsd._normalize_green_fringe_interface(
            z_tps=z_tps_in,
            grid_x=GX,
            grid_y=GY,
            green_bnd_mm=far_bnd,
            bnd_z=far_bnd_z,
        )

        assert np.allclose(z_out, TPS_INITIAL, atol=1e-9), (
            f"N4 FAILED: all grid points are outside the blend band but z_out changed. "
            f"Max deviation = {float(np.abs(z_out - TPS_INITIAL).max()):.6f}"
        )
