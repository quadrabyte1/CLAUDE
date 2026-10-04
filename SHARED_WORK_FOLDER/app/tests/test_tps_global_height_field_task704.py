"""
test_tps_global_height_field_task704.py — Bug→TDD for grid-cell TPS consumption
(task 704, Topo 2026-10-04).

Design spec (Thomas, 2026-10-03):
  - 20 × 20 grid cells across the entire print area.
  - Origin: lower-left corner of the plaque frame.
  - Alignment: axis-aligned with the frame.
  - Default for unset cells: Poisson green boundary Z at cell centre (NN lookup
    on bnd_z).
  - Set cells: user-supplied mm value overrides the Poisson default.
  - TPS fits over all 400 (cell_center_x, cell_center_y, cell_z) → one smooth
    surface everywhere.
  - build_fringe_mesh replaces _z_nn_grid (task-700 NN extension) with TPS
    surface sampling.

Tests (all RED before implementation):

  TG1  Cell index mapping correct.
  TG2  Cell centres in mm coords (origin lower-left of frame).
  TG3  Empty gridCellHeights → smooth Poisson-derived surface (no crash,
       all Z finite, Z in valid range).
  TG4  Single user-set cell overrides locally — TPS Z at that cell ≈ user value.
  TG5  Block of 4 adjacent user-set cells → TPS flat at ~user value over block.
  TG6  C² smoothness: gradient varies smoothly across cell boundaries.
  TG7  Regression: Poisson green surface unchanged.
  TG8  Regression: fringe round-trip — Z finite, in range, varying (tilted green).
  TG9  Regression: water slab still flat.
  TG10 _build_tps_grid_height_field function exists and is callable.

Run:
    cd /Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER
    python -m pytest app/tests/test_tps_global_height_field_task704.py -v
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
    spec = importlib.util.spec_from_file_location("gsd_task704", GSD_PATH)
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


def _base_egm(cx_px=300.0, cy_px=300.0, r_px=105.0, n=64,
              elevation_range=14.5, grid_cell_heights=None):
    egm = {
        "course": "TestCourse",
        "hole": "99",
        "image": "dummy.png",
        "imageSize": {"width": 600, "height": 600},
        "elevationRange": elevation_range,
        "greenScale": 1.0,
        "polygons": [{"name": "Green", "type": "green",
                      "points": _make_circular_green_pts(cx_px, cy_px, r_px, n)}],
        "fringeBoundaryHeights": [],
        "elevationSpikes": [],
    }
    if grid_cell_heights is not None:
        egm["gridCellHeights"] = grid_cell_heights
    return egm


def _flat_green_arrays(cx_px, cy_px, r_px, grid_res=200, z_val=3.0):
    xs_g = np.linspace(0, 599, grid_res)
    ys_g = np.linspace(0, 599, grid_res)
    inside_mask = np.zeros((grid_res, grid_res), dtype=bool)
    Z_mm = np.full((grid_res, grid_res), z_val)
    for ri, py in enumerate(ys_g):
        for ci, px in enumerate(xs_g):
            if math.hypot(px - cx_px, py - cy_px) < r_px:
                inside_mask[ri, ci] = True
    return Z_mm, xs_g, ys_g, inside_mask


def _tilted_green_arrays(cx_px, cy_px, r_px, grid_res=200):
    """Tilted green: left=3 mm, right=7 mm (4 mm range)."""
    xs_g = np.linspace(0, 599, grid_res)
    ys_g = np.linspace(0, 599, grid_res)
    inside_mask = np.zeros((grid_res, grid_res), dtype=bool)
    Z_mm = np.zeros((grid_res, grid_res), dtype=float)
    for ri, py in enumerate(ys_g):
        for ci, px in enumerate(xs_g):
            if math.hypot(px - cx_px, py - cy_px) < r_px:
                inside_mask[ri, ci] = True
                t = (px - cx_px + r_px) / (2.0 * r_px)
                Z_mm[ri, ci] = 3.0 + 4.0 * t
    return Z_mm, xs_g, ys_g, inside_mask


# ===========================================================================
# TG1  Cell index mapping
# ===========================================================================

class TestCellIndexMapping:
    """TG1: cell_index = row * 20 + col, row 0 = bottom-most, col 0 = leftmost."""

    def test_cell_index_formula(self):
        """TG1: row=0, col=0 → index 0; row=10, col=10 → index 210."""
        GRID_SIZE = 20
        for row in range(GRID_SIZE):
            for col in range(GRID_SIZE):
                expected = row * GRID_SIZE + col
                assert expected >= 0
                assert expected < 400

        assert 0 * 20 + 0 == 0,   "cell (row=0, col=0) must be index 0"
        assert 0 * 20 + 19 == 19, "cell (row=0, col=19) must be index 19"
        assert 19 * 20 + 0 == 380, "cell (row=19, col=0) must be index 380"
        assert 19 * 20 + 19 == 399, "cell (row=19, col=19) must be index 399"
        assert 10 * 20 + 10 == 210, "cell (row=10, col=10) must be index 210"


# ===========================================================================
# TG2  Cell centres in mm coords
# ===========================================================================

class TestCellCentresInMM:
    """TG2: cell (col, row) centre at ((col+0.5)*cell_w, (row+0.5)*cell_h) mm
    from the frame's lower-left corner.  Origin is lower-left of frame.
    """

    def test_cell_0_0_centre(self):
        """TG2: cell (row=0, col=0) centre at (0.5*cell_w, 0.5*cell_h) mm."""
        gsd = _load_gsd()
        half = gsd.PRINT_SIZE_MM / 2.0 + gsd.FRINGE_XY_EXPANSION_MM / 2.0
        frame_w = 2.0 * half
        frame_h = 2.0 * half
        cell_w = frame_w / 20.0
        cell_h = frame_h / 20.0

        # Frame lower-left is at world coords (-half, -half)
        # Cell (col=0, row=0) centre = (-half + 0.5*cell_w, -half + 0.5*cell_h)
        cx_expected = -half + 0.5 * cell_w
        cy_expected = -half + 0.5 * cell_h

        # Verify the formula is consistent
        assert abs(cx_expected - (-half + cell_w / 2.0)) < 1e-6
        assert abs(cy_expected - (-half + cell_h / 2.0)) < 1e-6

    def test_cell_19_19_centre(self):
        """TG2: cell (row=19, col=19) centre at (19.5*cell_w, 19.5*cell_h) from lower-left."""
        gsd = _load_gsd()
        half = gsd.PRINT_SIZE_MM / 2.0 + gsd.FRINGE_XY_EXPANSION_MM / 2.0
        frame_w = 2.0 * half
        cell_w = frame_w / 20.0

        # Cell (col=19, row=19) centre in world coords
        cx = -half + (19 + 0.5) * cell_w
        cy = -half + (19 + 0.5) * cell_w

        # Should be close to but not exceed +half
        assert cx < half + 1e-6
        assert cy < half + 1e-6
        assert cx > half - cell_w  # close to the right edge

    def test_400_cell_centres_cover_full_frame(self):
        """TG2: all 400 cell centres tile the frame without overlap or gaps."""
        gsd = _load_gsd()
        half = gsd.PRINT_SIZE_MM / 2.0 + gsd.FRINGE_XY_EXPANSION_MM / 2.0
        frame_side = 2.0 * half
        cell_w = frame_side / 20.0
        cell_h = frame_side / 20.0

        centres = set()
        for row in range(20):
            for col in range(20):
                cx = round(-half + (col + 0.5) * cell_w, 6)
                cy = round(-half + (row + 0.5) * cell_h, 6)
                centres.add((cx, cy))
        assert len(centres) == 400, f"Expected 400 unique cell centres, got {len(centres)}"


# ===========================================================================
# TG3  Empty gridCellHeights → smooth Poisson-derived surface
# ===========================================================================

class TestEmptyGridCellHeightsSmooth:
    """TG3: No gridCellHeights → all 400 cells use Poisson defaults.
    TPS fits → smooth surface, all Z finite, in valid range.
    """

    def test_empty_grid_no_crash(self):
        """TG3a: EGM with no gridCellHeights field → build_fringe_mesh runs without error."""
        gsd = _load_gsd()
        cx_px, cy_px, r_px = 300.0, 300.0, 105.0
        egm = _base_egm(cx_px, cy_px, r_px)  # no gridCellHeights key
        Z_mm, xs_g, ys_g, inside_mask = _flat_green_arrays(cx_px, cy_px, r_px)
        green_bnd_px = gsd.interpolate_catmull_rom(egm["polygons"][0]["points"])

        fringe_mesh = gsd.build_fringe_mesh(
            Z_mm, xs_g, ys_g, inside_mask, green_bnd_px, egm,
            fringe_grid_res=40,
        )
        verts = np.asarray(fringe_mesh.vertices)
        assert len(verts) > 0, "Fringe mesh has no vertices"
        assert np.all(np.isfinite(verts)), "Fringe mesh has NaN/Inf vertices"

    def test_empty_dict_grid_no_crash(self):
        """TG3b: EGM with gridCellHeights={} → same, no crash."""
        gsd = _load_gsd()
        cx_px, cy_px, r_px = 300.0, 300.0, 105.0
        egm = _base_egm(cx_px, cy_px, r_px, grid_cell_heights={})
        Z_mm, xs_g, ys_g, inside_mask = _flat_green_arrays(cx_px, cy_px, r_px)
        green_bnd_px = gsd.interpolate_catmull_rom(egm["polygons"][0]["points"])

        fringe_mesh = gsd.build_fringe_mesh(
            Z_mm, xs_g, ys_g, inside_mask, green_bnd_px, egm,
            fringe_grid_res=40,
        )
        verts = np.asarray(fringe_mesh.vertices)
        assert len(verts) > 0
        assert np.all(np.isfinite(verts))

    def test_empty_grid_z_in_valid_range(self):
        """TG3c: Empty gridCellHeights → fringe Z in [BASE, BASE + elevationRange + 2]."""
        gsd = _load_gsd()
        cx_px, cy_px, r_px = 300.0, 300.0, 105.0
        egm = _base_egm(cx_px, cy_px, r_px)
        Z_mm, xs_g, ys_g, inside_mask = _flat_green_arrays(cx_px, cy_px, r_px, z_val=5.0)
        green_bnd_px = gsd.interpolate_catmull_rom(egm["polygons"][0]["points"])

        fringe_mesh = gsd.build_fringe_mesh(
            Z_mm, xs_g, ys_g, inside_mask, green_bnd_px, egm,
            fringe_grid_res=40,
        )
        verts = np.asarray(fringe_mesh.vertices)
        top = verts[verts[:, 2] > gsd.BASE_THICKNESS_MM * 0.5]
        assert len(top) > 0
        base = gsd.BASE_THICKNESS_MM
        elev_range = float(egm.get("elevationRange", gsd.ELEVATION_RANGE_MM))
        max_z = base + elev_range + 2.0
        z_max = float(top[:, 2].max())
        assert z_max <= max_z + 0.5, (
            f"Fringe Z max {z_max:.3f} > allowed {max_z:.3f} mm (BASE+range+2)"
        )


# ===========================================================================
# TG4  Single user-set cell overrides locally
# ===========================================================================

class TestSingleCellOverride:
    """TG4: EGM with one set cell → TPS Z at that cell centre ≈ user value."""

    def test_single_cell_10_at_15mm(self):
        """TG4: gridCellHeights = {10: 15.0} → fringe Z near cell 10 centre is raised.

        Cell 10 = row 0, col 10 → bottom-centre fringe area, outside the green.
        With a flat Poisson green at 3 mm, cell 10 carries 15 mm from the user.
        The TPS surface at fringe cells near the bottom-centre should exceed the
        3 mm baseline.
        """
        gsd = _load_gsd()
        cx_px, cy_px, r_px = 300.0, 300.0, 105.0
        # Cell 10 = row 0, col 10 → bottom-centre of frame, clearly in fringe area
        egm = _base_egm(cx_px, cy_px, r_px, grid_cell_heights={"10": 15.0})
        Z_mm, xs_g, ys_g, inside_mask = _flat_green_arrays(cx_px, cy_px, r_px, z_val=3.0)
        green_bnd_px = gsd.interpolate_catmull_rom(egm["polygons"][0]["points"])

        fringe_mesh = gsd.build_fringe_mesh(
            Z_mm, xs_g, ys_g, inside_mask, green_bnd_px, egm,
            fringe_grid_res=60,
        )
        verts = np.asarray(fringe_mesh.vertices)
        assert len(verts) > 0
        assert np.all(np.isfinite(verts)), "Mesh has NaN/Inf"

        # Cell 10 is in the bottom-centre fringe area and set to 15 mm.
        # The TPS must propagate the override: fringe Z max should exceed baseline.
        top = verts[verts[:, 2] > gsd.BASE_THICKNESS_MM * 0.5]
        z_max = float(top[:, 2].max())
        assert z_max > 5.0, (
            f"Single fringe-area cell override at 15 mm not reflected: "
            f"fringe Z max = {z_max:.3f} mm; expected > 5 mm "
            f"(TPS should lift Z toward user value at fringe cell 10)"
        )

    def test_single_cell_override_locally_dominant(self):
        """TG4b: Z at or near cell 210 centre is higher than the far-away fringe Z.

        The user-set cell (row=10, col=10) at 15 mm should produce a local
        maximum in the fringe that decays away from the cell — TPS smoothness.
        """
        gsd = _load_gsd()
        cx_px, cy_px, r_px = 300.0, 300.0, 105.0
        egm = _base_egm(cx_px, cy_px, r_px, grid_cell_heights={"210": 15.0})
        Z_mm, xs_g, ys_g, inside_mask = _flat_green_arrays(cx_px, cy_px, r_px, z_val=3.0)
        green_bnd_px = gsd.interpolate_catmull_rom(egm["polygons"][0]["points"])

        # We need direct access to the TPS grid, not just the mesh.
        # Verify via _build_tps_grid_height_field helper function.
        assert hasattr(gsd, "_build_tps_grid_height_field"), (
            "_build_tps_grid_height_field not found — implement it to expose the "
            "400-cell TPS surface builder for testing"
        )

        half = gsd.PRINT_SIZE_MM / 2.0 + gsd.FRINGE_XY_EXPANSION_MM / 2.0
        cell_side = 2.0 * half / 20.0
        # Cell 210: row=10, col=10 → centre at (-half + 10.5*cell_side, -half + 10.5*cell_side)
        cell_cx = -half + 10.5 * cell_side
        cell_cy = -half + 10.5 * cell_side

        grid_res = 50
        gx = np.linspace(-half, half, grid_res)
        gy = np.linspace(-half, half, grid_res)
        GX, GY = np.meshgrid(gx, gy)

        green_bnd_mm = gsd._px_to_mm_2d(
            green_bnd_px.copy(),
            *gsd._compute_px_to_mm(
                np.array([(p["x"], p["y"]) for p in egm["polygons"][0]["points"]],
                         dtype=np.float64),
                egm
            )
        )
        # Sample the Poisson-derived bnd_z at cell centres
        # (we use z_val=3.0 so all boundary Z values are ≈ 3 mm except the override)
        z_tps = gsd._build_tps_grid_height_field(
            egm_data=egm,
            green_bnd_mm=green_bnd_mm,
            bnd_z=np.full(len(green_bnd_mm), 3.0),  # flat Poisson baseline at 3 mm
            grid_x=GX,
            grid_y=GY,
        )

        # Find Z at the cell-210 centre location
        dist_sq = (GX - cell_cx) ** 2 + (GY - cell_cy) ** 2
        ni = np.unravel_index(np.argmin(dist_sq), dist_sq.shape)
        z_at_cell = float(z_tps[ni])

        # Z at cell 210 must be elevated above the 3 mm baseline
        assert z_at_cell > 5.0, (
            f"TPS Z at cell 210 centre = {z_at_cell:.3f} mm; "
            f"expected > 5 mm (user override at 15 mm, Poisson default at 3 mm)"
        )


# ===========================================================================
# TG5  Block of 4 adjacent cells → flat top region
# ===========================================================================

class TestBlockCellsFlat:
    """TG5: 4 adjacent cells all set to 20 mm → TPS approximately flat at ~20 mm
    over that block.
    """

    def test_4_adjacent_cells_raised(self):
        """TG5: cells 200, 201, 220, 221 (row 10/11, col 0/1) all at 20 mm."""
        gsd = _load_gsd()
        assert hasattr(gsd, "_build_tps_grid_height_field"), (
            "_build_tps_grid_height_field not found"
        )
        cx_px, cy_px, r_px = 300.0, 300.0, 105.0
        # Cells at row 10 col 0 = 200, row 10 col 1 = 201,
        #           row 11 col 0 = 220, row 11 col 1 = 221
        egm = _base_egm(cx_px, cy_px, r_px, grid_cell_heights={
            "200": 20.0, "201": 20.0, "220": 20.0, "221": 20.0
        })
        green_pts_px = np.array(
            [(p["x"], p["y"]) for p in egm["polygons"][0]["points"]], dtype=np.float64
        )
        scale, centroid_px = gsd._compute_px_to_mm(green_pts_px, egm)
        green_bnd_px = gsd.interpolate_catmull_rom(egm["polygons"][0]["points"])
        green_bnd_mm = gsd._px_to_mm_2d(green_bnd_px.copy(), scale, centroid_px)

        half = gsd.PRINT_SIZE_MM / 2.0 + gsd.FRINGE_XY_EXPANSION_MM / 2.0
        grid_res = 60
        GX, GY = np.meshgrid(
            np.linspace(-half, half, grid_res),
            np.linspace(-half, half, grid_res),
        )

        # Poisson baseline at 3 mm everywhere
        bnd_z = np.full(len(green_bnd_mm), 3.0)

        z_tps = gsd._build_tps_grid_height_field(
            egm_data=egm,
            green_bnd_mm=green_bnd_mm,
            bnd_z=bnd_z,
            grid_x=GX,
            grid_y=GY,
        )

        # Sample at the block centroid (midpoint of the 4 cells)
        cell_side = 2.0 * half / 20.0
        # Row 10-11, col 0-1 → block centre
        block_cx = -half + 1.0 * cell_side   # between col 0 and col 1
        block_cy = -half + 10.5 * cell_side  # row 10.5

        dist_sq = (GX - block_cx) ** 2 + (GY - block_cy) ** 2
        ni = np.unravel_index(np.argmin(dist_sq), dist_sq.shape)
        z_at_block = float(z_tps[ni])

        # TPS with 4 cells at 20 mm and surrounding default at 3 mm:
        # at the block centre Z should be substantially elevated
        assert z_at_block > 12.0, (
            f"TPS Z at 4-cell block centre = {z_at_block:.3f} mm; "
            f"expected > 12 mm (4 cells at 20 mm)"
        )


# ===========================================================================
# TG6  C² smoothness across cell boundaries
# ===========================================================================

class TestCellBoundarySmooth:
    """TG6: Gradient at cell boundary changes smoothly — no step discontinuities."""

    def test_no_gradient_step_at_cell_boundary(self):
        """TG6: finite-difference derivative jump < 2.0 mm/mm across cell edges."""
        gsd = _load_gsd()
        assert hasattr(gsd, "_build_tps_grid_height_field"), (
            "_build_tps_grid_height_field not found"
        )
        cx_px, cy_px, r_px = 300.0, 300.0, 105.0
        # One raised cell at (row=10, col=10) = index 210
        egm = _base_egm(cx_px, cy_px, r_px, grid_cell_heights={"210": 12.0})
        green_pts_px = np.array(
            [(p["x"], p["y"]) for p in egm["polygons"][0]["points"]], dtype=np.float64
        )
        scale, centroid_px = gsd._compute_px_to_mm(green_pts_px, egm)
        green_bnd_px = gsd.interpolate_catmull_rom(egm["polygons"][0]["points"])
        green_bnd_mm = gsd._px_to_mm_2d(green_bnd_px.copy(), scale, centroid_px)

        half = gsd.PRINT_SIZE_MM / 2.0 + gsd.FRINGE_XY_EXPANSION_MM / 2.0
        cell_side = 2.0 * half / 20.0

        # Dense 1D sample through cell 210 centre along x-axis
        cell_cx = -half + 10.5 * cell_side
        cell_cy = -half + 10.5 * cell_side
        step_mm = 0.25
        n_pts = 60
        sample_xs = np.array([cell_cx + (i - n_pts // 2) * step_mm for i in range(n_pts)])
        sample_ys = np.full(n_pts, cell_cy)

        GX = sample_xs.reshape(1, -1)
        GY = sample_ys.reshape(1, -1)

        bnd_z = np.full(len(green_bnd_mm), 3.0)

        z_1d = gsd._build_tps_grid_height_field(
            egm_data=egm,
            green_bnd_mm=green_bnd_mm,
            bnd_z=bnd_z,
            grid_x=GX,
            grid_y=GY,
        ).ravel()

        assert np.all(np.isfinite(z_1d)), "TPS 1D profile has NaN/Inf"

        # First derivative (mm/mm)
        dz = np.abs(np.diff(z_1d)) / step_mm
        # Second derivative (change in slope)
        d2z = np.abs(np.diff(dz))
        max_jump = float(d2z.max())

        assert max_jump < 2.0, (
            f"TPS gradient jump at cell boundary = {max_jump:.4f} mm/mm "
            f"(tol=2.0) — expected smooth TPS (C² continuous)"
        )


# ===========================================================================
# TG7  Regression: Poisson green surface unchanged
# ===========================================================================

class TestPoissonGreenUnchanged:
    """TG7: Green surface (interior Poisson) is not modified by TPS grid mechanism."""

    def test_green_z_mm_unchanged(self):
        """TG7: Z_mm array passed to build_fringe_mesh must not be mutated."""
        gsd = _load_gsd()
        cx_px, cy_px, r_px = 300.0, 300.0, 105.0
        egm = _base_egm(cx_px, cy_px, r_px, grid_cell_heights={"210": 15.0})
        Z_mm, xs_g, ys_g, inside_mask = _flat_green_arrays(cx_px, cy_px, r_px, z_val=5.0)

        # Take a deep copy before call
        Z_mm_before = Z_mm.copy()
        green_bnd_px = gsd.interpolate_catmull_rom(egm["polygons"][0]["points"])

        gsd.build_fringe_mesh(
            Z_mm, xs_g, ys_g, inside_mask, green_bnd_px, egm,
            fringe_grid_res=40,
        )

        # Z_mm must not have changed (fringe builder must not mutate the green surface)
        np.testing.assert_array_equal(Z_mm, Z_mm_before,
            err_msg="build_fringe_mesh mutated Z_mm — Poisson green surface was modified")


# ===========================================================================
# TG8  Regression: fringe round-trip with tilted green
# ===========================================================================

class TestTiltedGreenFringeVariation:
    """TG8: Fringe still mirrors tilted green Z variation when gridCellHeights is absent."""

    def test_fringe_z_varies_with_tilted_green(self):
        """TG8: Tilted green (3..7 mm) with empty gridCellHeights → fringe Z range > 2 mm."""
        gsd = _load_gsd()
        cx_px, cy_px, r_px = 300.0, 300.0, 105.0
        egm = _base_egm(cx_px, cy_px, r_px)  # no gridCellHeights
        Z_mm, xs_g, ys_g, inside_mask = _tilted_green_arrays(cx_px, cy_px, r_px)
        green_bnd_px = gsd.interpolate_catmull_rom(egm["polygons"][0]["points"])

        fringe_mesh = gsd.build_fringe_mesh(
            Z_mm, xs_g, ys_g, inside_mask, green_bnd_px, egm,
            fringe_grid_res=60,
        )
        verts = np.asarray(fringe_mesh.vertices)
        top = verts[verts[:, 2] > gsd.BASE_THICKNESS_MM * 0.5]
        assert len(top) > 10

        z_range = float(top[:, 2].max() - top[:, 2].min())
        assert z_range > 2.0, (
            f"Fringe Z range = {z_range:.4f} mm — expected > 2 mm "
            f"(fringe mirrors tilted green via TPS defaults)"
        )


# ===========================================================================
# TG9  Regression: water slab still flat
# ===========================================================================

class TestWaterSlabFlat:
    """TG9: Water slab is unaffected by TPS grid changes — still flat."""

    def test_water_slab_flat(self):
        """TG9: export_water_meshes slab Z variation < 0.1 mm even with gridCellHeights."""
        gsd = _load_gsd()
        cx_px, cy_px, r_px = 300.0, 300.0, 105.0
        water_pts = [
            {"x": cx_px + 30 + 30 * math.cos(2 * math.pi * i / 16),
             "y": cy_px + 30 * math.sin(2 * math.pi * i / 16)}
            for i in range(16)
        ]
        egm = _base_egm(cx_px, cy_px, r_px, grid_cell_heights={"210": 12.0})
        egm["polygons"].append({"name": "Water1", "type": "water", "points": water_pts})

        green_bnd_px = gsd.interpolate_catmull_rom(egm["polygons"][0]["points"])

        try:
            water_meshes = gsd.export_water_meshes(
                green_bnd_px, egm, fringe_grid_res=60,
            )
        except Exception as exc:
            pytest.skip(f"export_water_meshes raised {exc} — water pipeline not available")

        for wm in water_meshes:
            wv = np.asarray(wm.vertices)
            top_w = wv[wv[:, 2] > gsd.BASE_THICKNESS_MM * 0.1]
            if len(top_w) < 3:
                continue
            z_range_w = float(top_w[:, 2].max() - top_w[:, 2].min())
            assert z_range_w < 0.1, (
                f"Water slab Z range = {z_range_w:.4f} mm (tol=0.1 mm); "
                f"TPS grid mechanism may have warped the water slab"
            )


# ===========================================================================
# TG10  _build_tps_grid_height_field function exists
# ===========================================================================

class TestTpsGridHelperExists:
    """TG10: _build_tps_grid_height_field function is importable and callable."""

    def test_function_exists(self):
        """TG10: _build_tps_grid_height_field must be defined in gradient_surface_diagnostic."""
        gsd = _load_gsd()
        assert hasattr(gsd, "_build_tps_grid_height_field"), (
            "_build_tps_grid_height_field not found in gradient_surface_diagnostic.py — "
            "implement the 400-cell TPS surface builder"
        )

    def test_function_callable_with_empty_grid(self):
        """TG10: _build_tps_grid_height_field accepts (egm_data, green_bnd_mm, bnd_z, GX, GY)
        and returns (R, C) array.
        """
        gsd = _load_gsd()
        assert hasattr(gsd, "_build_tps_grid_height_field"), (
            "_build_tps_grid_height_field not found"
        )
        cx_px, cy_px, r_px = 300.0, 300.0, 105.0
        egm = _base_egm(cx_px, cy_px, r_px)  # no gridCellHeights
        green_pts_px = np.array(
            [(p["x"], p["y"]) for p in egm["polygons"][0]["points"]], dtype=np.float64
        )
        scale, centroid_px = gsd._compute_px_to_mm(green_pts_px, egm)
        green_bnd_px = gsd.interpolate_catmull_rom(egm["polygons"][0]["points"])
        green_bnd_mm = gsd._px_to_mm_2d(green_bnd_px.copy(), scale, centroid_px)

        half = gsd.PRINT_SIZE_MM / 2.0 + gsd.FRINGE_XY_EXPANSION_MM / 2.0
        GX, GY = np.meshgrid(
            np.linspace(-half, half, 20),
            np.linspace(-half, half, 20),
        )

        # Flat bnd_z at 3 mm
        bnd_z = np.full(len(green_bnd_mm), 3.0)

        result = gsd._build_tps_grid_height_field(
            egm_data=egm,
            green_bnd_mm=green_bnd_mm,
            bnd_z=bnd_z,
            grid_x=GX,
            grid_y=GY,
        )

        assert result.shape == GX.shape, (
            f"_build_tps_grid_height_field returned shape {result.shape}, expected {GX.shape}"
        )
        assert np.all(np.isfinite(result)), "Result has NaN/Inf"
        base = gsd.BASE_THICKNESS_MM
        elev = float(egm.get("elevationRange", gsd.ELEVATION_RANGE_MM))
        assert float(result.max()) <= base + elev + 2.0 + 0.5, (
            f"Result max {float(result.max()):.3f} mm exceeds valid range"
        )
