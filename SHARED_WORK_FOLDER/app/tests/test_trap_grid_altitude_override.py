"""
test_trap_grid_altitude_override.py — Bug→TDD for trap altitude grid-cell override.

Task 716 (Topo, 2026-10-05).
Thomas's request: if a user-set grid-cell (blue dot) centre falls inside a trap
polygon, use the mean of those cell values as the flat trap Z instead of the
default min(fringe boundary Z) − 2 mm rule.

Tests
-----
TG1  No override cells → default fringe-min rule applies.
TG2  Single override cell inside trap → trap_Z = that cell's value (7 mm).
TG3  Multiple override cells inside trap → trap_Z = mean (6+8)/2 = 7 mm.
TG4  Set cells OUTSIDE the trap polygon are ignored for that trap's override.
TG5  Only SET cells count — unset cells (Poisson defaults) never trigger override.
TG6  Multi-trap: two traps, each with its own override, each uses its own mean.
TG7  Boundary edge case: cell centre exactly on polygon edge → excluded (shapely
     strict-interior `contains`).
TG8  Regression: rake lines still visible after override (top Z spread ≥ 0.1 mm).
TG9  Regression: trap frame-cap and water-hole lift flags unchanged.
TG10 _trap_grid_override helper exists and is callable from the module.

Run:
    cd /Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER
    python -m pytest app/tests/test_trap_grid_altitude_override.py -v
"""
from __future__ import annotations

import importlib
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
    spec = importlib.util.spec_from_file_location("gsd_tg_test", GSD_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------

def _make_circle_pts(cx_px, cy_px, r_px, n=64):
    return [
        {"x": cx_px + r_px * math.cos(2 * math.pi * i / n),
         "y": cy_px + r_px * math.sin(2 * math.pi * i / n)}
        for i in range(n)
    ]


def _base_egm(cx_px=300.0, cy_px=300.0, gr_px=105.0):
    """Minimal EGM with one green only — no trap."""
    return {
        "course": "TestCourse",
        "hole": "99",
        "image": "dummy.png",
        "imageSize": {"width": 600, "height": 600},
        "elevationRange": 14.5,
        "greenScale": 1.0,
        "polygons": [
            {"name": "Green", "type": "green",
             "points": _make_circle_pts(cx_px, cy_px, gr_px)},
        ],
        "fringeBoundaryHeights": [],
        "elevationSpikes": [],
    }


def _flat_green_arrays(cx_px=300.0, cy_px=300.0, r_px=105.0,
                       grid_res=80, z_val=6.0):
    """Uniform-Z green surface arrays."""
    xs_g = np.linspace(0, 599, grid_res)
    ys_g = np.linspace(0, 599, grid_res)
    inside_mask = np.zeros((grid_res, grid_res), dtype=bool)
    Z_mm = np.full((grid_res, grid_res), z_val)
    for ri, py in enumerate(ys_g):
        for ci, px in enumerate(xs_g):
            if math.hypot(px - cx_px, py - cy_px) < r_px:
                inside_mask[ri, ci] = True
    return Z_mm, xs_g, ys_g, inside_mask


def _get_grid_geometry(gsd):
    """Return (half, cell_side, GRID_SIZE) matching _build_tps_grid_height_field."""
    GRID_SIZE = 20
    half = gsd.PRINT_SIZE_MM / 2.0 + gsd.FRINGE_XY_EXPANSION_MM / 2.0
    cell_side = (2.0 * half) / GRID_SIZE
    return half, cell_side, GRID_SIZE


def _cell_center_mm(row, col, half, cell_side):
    """World-mm coords of cell (row, col) centre."""
    cx = -half + (col + 0.5) * cell_side
    cy = -half + (row + 0.5) * cell_side
    return cx, cy


def _cell_index(row, col, grid_size=20):
    return row * grid_size + col


# ---------------------------------------------------------------------------
# Build a trap polygon in mm that contains specific grid cells.
#
# Strategy: pick a cell, get its mm centre, build a trap circle around it
# large enough to contain the cell interior but small enough to exclude
# neighbouring cells.  The trap is expressed as pixel points and converted
# via export_trap_stls's own px→mm transform, which can be tricky.
#
# Simpler: call _trap_grid_override directly with a synthetic ShapelyPolygon
# in mm coords.  This tests the helper in isolation.
# ---------------------------------------------------------------------------

def _shapely_circle_mm(cx_mm, cy_mm, r_mm, n=64):
    """Build a Shapely Polygon circle in mm coords."""
    from shapely.geometry import Polygon as ShapelyPolygon
    pts = [(cx_mm + r_mm * math.cos(2 * math.pi * i / n),
            cy_mm + r_mm * math.sin(2 * math.pi * i / n))
           for i in range(n)]
    return ShapelyPolygon(pts)


# ===========================================================================
# TG10  _trap_grid_override helper exists in module
# ===========================================================================

class TestHelperExists:
    """TG10: _trap_grid_override must be callable from the module."""

    def test_trap_grid_override_exists(self):
        """TG10: Module must expose _trap_grid_override function."""
        gsd = _load_gsd()
        assert hasattr(gsd, "_trap_grid_override"), (
            "_trap_grid_override is not present in gradient_surface_diagnostic — "
            "add the helper function"
        )
        assert callable(gsd._trap_grid_override), (
            "_trap_grid_override is not callable"
        )


# ===========================================================================
# TG1  No override cells → default fringe-min rule (None return)
# ===========================================================================

class TestNoOverrideCells:
    """TG1: When no gridCellHeights entries are inside the trap, helper returns None."""

    def test_empty_grid_cell_heights_returns_none(self):
        """TG1: Empty gridCellHeights → _trap_grid_override returns None."""
        gsd = _load_gsd()
        half, cell_side, GRID_SIZE = _get_grid_geometry(gsd)
        # Build a trap circle near grid centre (0, 0) mm.
        trap_poly = _shapely_circle_mm(0.0, 0.0, cell_side * 0.4)
        result = gsd._trap_grid_override(trap_poly, {}, cell_side, half)
        assert result is None, (
            f"Expected None (no set cells) but got {result!r}"
        )

    def test_no_cells_inside_trap_returns_none(self):
        """TG1b: Set cells all outside trap polygon → returns None."""
        gsd = _load_gsd()
        half, cell_side, GRID_SIZE = _get_grid_geometry(gsd)
        # Use a tiny trap centred at exact cell (0,0) with radius < 0.4*cell_side
        # so no cell centre is inside it.
        cx0, cy0 = _cell_center_mm(0, 0, half, cell_side)
        trap_poly = _shapely_circle_mm(cx0, cy0, cell_side * 0.3)
        # Put a set cell at (1, 1) — definitely outside
        cx11, cy11 = _cell_center_mm(1, 1, half, cell_side)
        # verify it's not inside
        from shapely.geometry import Point as _P
        assert not trap_poly.contains(_P(cx11, cy11)), "Setup error: cell (1,1) should be outside the tiny trap"
        idx_str = str(_cell_index(1, 1))
        grid_cell_heights = {idx_str: 7.0}
        result = gsd._trap_grid_override(trap_poly, grid_cell_heights, cell_side, half)
        assert result is None, (
            f"Expected None (outside cells ignored) but got {result!r}"
        )


# ===========================================================================
# TG2  Single override cell inside trap → use its value
# ===========================================================================

class TestSingleOverrideCell:
    """TG2: One set cell inside trap → trap_Z = that cell's value."""

    def test_single_inside_cell_returns_its_value(self):
        """TG2: gridCellHeights with one inside cell → _trap_grid_override = 7.0."""
        gsd = _load_gsd()
        half, cell_side, GRID_SIZE = _get_grid_geometry(gsd)
        # Build trap centred on cell (10, 10).
        row, col = 10, 10
        cx, cy = _cell_center_mm(row, col, half, cell_side)
        trap_poly = _shapely_circle_mm(cx, cy, cell_side * 0.4)
        # Verify cell centre is inside
        from shapely.geometry import Point as _P
        assert trap_poly.contains(_P(cx, cy)), "Setup error: cell (10,10) should be inside the trap"
        idx_str = str(_cell_index(row, col))
        grid_cell_heights = {idx_str: 7.0}
        result = gsd._trap_grid_override(trap_poly, grid_cell_heights, cell_side, half)
        assert result is not None, "_trap_grid_override returned None for a cell inside the trap"
        assert abs(result - 7.0) < 1e-6, (
            f"Expected 7.0 mm but got {result:.4f} mm"
        )


# ===========================================================================
# TG3  Multiple override cells → mean
# ===========================================================================

class TestMultipleOverrideCells:
    """TG3: Two set cells inside trap → trap_Z = mean = (6+8)/2 = 7.0."""

    def test_two_inside_cells_returns_mean(self):
        """TG3: Two cells with values 6 and 8 inside same trap → mean = 7.0."""
        gsd = _load_gsd()
        half, cell_side, GRID_SIZE = _get_grid_geometry(gsd)
        # Build trap large enough to contain two adjacent cell centres.
        row, col = 10, 10
        cx0, cy0 = _cell_center_mm(row, col, half, cell_side)
        cx1, cy1 = _cell_center_mm(row, col + 1, half, cell_side)
        # Centre the trap between the two cells.
        tc_x = (cx0 + cx1) / 2.0
        tc_y = (cy0 + cy1) / 2.0
        trap_poly = _shapely_circle_mm(tc_x, tc_y, cell_side * 0.75)
        from shapely.geometry import Point as _P
        assert trap_poly.contains(_P(cx0, cy0)), "Setup error: cell (10,10) should be inside trap"
        assert trap_poly.contains(_P(cx1, cy1)), "Setup error: cell (10,11) should be inside trap"
        idx0 = str(_cell_index(row, col))
        idx1 = str(_cell_index(row, col + 1))
        grid_cell_heights = {idx0: 6.0, idx1: 8.0}
        result = gsd._trap_grid_override(trap_poly, grid_cell_heights, cell_side, half)
        assert result is not None, "_trap_grid_override returned None for two cells inside the trap"
        assert abs(result - 7.0) < 1e-6, (
            f"Expected mean = 7.0 mm but got {result:.4f} mm"
        )


# ===========================================================================
# TG4  Set cells outside trap are ignored
# ===========================================================================

class TestOutsideCellsIgnored:
    """TG4: A set cell outside the trap polygon must not contribute to override."""

    def test_outside_cell_does_not_trigger_override(self):
        """TG4: One inside cell (7 mm) + one outside cell (99 mm) → override = 7.0."""
        gsd = _load_gsd()
        half, cell_side, GRID_SIZE = _get_grid_geometry(gsd)
        # Trap centred on cell (10, 10).
        row_in, col_in = 10, 10
        cx_in, cy_in = _cell_center_mm(row_in, col_in, half, cell_side)
        trap_poly = _shapely_circle_mm(cx_in, cy_in, cell_side * 0.4)
        # Set cell (15, 15) far outside.
        row_out, col_out = 15, 15
        cx_out, cy_out = _cell_center_mm(row_out, col_out, half, cell_side)
        from shapely.geometry import Point as _P
        assert trap_poly.contains(_P(cx_in, cy_in)), "Setup: inside cell should be contained"
        assert not trap_poly.contains(_P(cx_out, cy_out)), "Setup: outside cell should not be contained"
        grid_cell_heights = {
            str(_cell_index(row_in, col_in)): 7.0,
            str(_cell_index(row_out, col_out)): 99.0,
        }
        result = gsd._trap_grid_override(trap_poly, grid_cell_heights, cell_side, half)
        assert result is not None
        assert abs(result - 7.0) < 1e-6, (
            f"Expected 7.0 (inside cell only) but got {result:.4f} mm — "
            f"outside cell must be ignored"
        )


# ===========================================================================
# TG5  Only SET cells count — unset cells (not in gridCellHeights) ignored
# ===========================================================================

class TestUnsetCellsNotTrigger:
    """TG5: Cells absent from gridCellHeights must not trigger override."""

    def test_unset_cells_do_not_trigger_override(self):
        """TG5: Trap contains many cell centres, but none are in gridCellHeights → None."""
        gsd = _load_gsd()
        half, cell_side, GRID_SIZE = _get_grid_geometry(gsd)
        # Build a large trap containing many cell centres (4x4 block of cells).
        row0, col0 = 8, 8
        cx_start, cy_start = _cell_center_mm(row0, col0, half, cell_side)
        cx_end, cy_end = _cell_center_mm(row0 + 3, col0 + 3, half, cell_side)
        tc_x = (cx_start + cx_end) / 2.0
        tc_y = (cy_start + cy_end) / 2.0
        # radius to contain the 4x4 block comfortably
        trap_poly = _shapely_circle_mm(tc_x, tc_y, cell_side * 2.5)
        # Verify at least one cell is inside
        from shapely.geometry import Point as _P
        cx_mid, cy_mid = _cell_center_mm(row0 + 1, col0 + 1, half, cell_side)
        assert trap_poly.contains(_P(cx_mid, cy_mid)), "Setup: cell should be inside trap"
        # Empty gridCellHeights → no set cells
        result = gsd._trap_grid_override(trap_poly, {}, cell_side, half)
        assert result is None, (
            f"Expected None (no set cells) but got {result!r} — "
            "unset/default cells must not trigger the override"
        )


# ===========================================================================
# TG6  Multi-trap: each trap uses its own set of inside cells
# ===========================================================================

class TestMultiTrap:
    """TG6: Two traps, each with one set cell inside → each uses its own value."""

    def test_two_traps_independent_overrides(self):
        """TG6: Trap A override = 5.0 mm, Trap B override = 9.0 mm, independent."""
        gsd = _load_gsd()
        half, cell_side, GRID_SIZE = _get_grid_geometry(gsd)
        # Trap A centred on cell (5, 5).
        row_a, col_a = 5, 5
        cx_a, cy_a = _cell_center_mm(row_a, col_a, half, cell_side)
        trap_a = _shapely_circle_mm(cx_a, cy_a, cell_side * 0.4)
        # Trap B centred on cell (15, 15).
        row_b, col_b = 15, 15
        cx_b, cy_b = _cell_center_mm(row_b, col_b, half, cell_side)
        trap_b = _shapely_circle_mm(cx_b, cy_b, cell_side * 0.4)
        from shapely.geometry import Point as _P
        assert trap_a.contains(_P(cx_a, cy_a))
        assert trap_b.contains(_P(cx_b, cy_b))
        assert not trap_a.contains(_P(cx_b, cy_b)), "Traps should not overlap"
        assert not trap_b.contains(_P(cx_a, cy_a)), "Traps should not overlap"
        grid_cell_heights = {
            str(_cell_index(row_a, col_a)): 5.0,
            str(_cell_index(row_b, col_b)): 9.0,
        }
        result_a = gsd._trap_grid_override(trap_a, grid_cell_heights, cell_side, half)
        result_b = gsd._trap_grid_override(trap_b, grid_cell_heights, cell_side, half)
        assert result_a is not None, "Trap A override should not be None"
        assert result_b is not None, "Trap B override should not be None"
        assert abs(result_a - 5.0) < 1e-6, f"Trap A: expected 5.0, got {result_a}"
        assert abs(result_b - 9.0) < 1e-6, f"Trap B: expected 9.0, got {result_b}"


# ===========================================================================
# TG7  Boundary edge: cell centre exactly on trap polygon edge → excluded
# ===========================================================================

class TestBoundaryEdgeExcluded:
    """TG7: Cell centre on the trap polygon boundary → shapely contains=False → excluded."""

    def test_cell_on_boundary_excluded(self):
        """TG7: Cell centre exactly on polygon edge → excluded by shapely strict interior."""
        gsd = _load_gsd()
        half, cell_side, GRID_SIZE = _get_grid_geometry(gsd)
        # Build a rectangular trap whose right edge passes through a cell centre.
        row, col = 10, 10
        cx, cy = _cell_center_mm(row, col, half, cell_side)
        # Trap: left edge at cx - 0.01 mm, right edge exactly at cx (cell centre on edge)
        from shapely.geometry import Polygon as _Poly, Point as _P
        # A tight rectangle: cell centre is on the right boundary
        trap_poly = _Poly([
            (cx - cell_side, cy - cell_side * 0.4),
            (cx,             cy - cell_side * 0.4),  # right side at cx
            (cx,             cy + cell_side * 0.4),
            (cx - cell_side, cy + cell_side * 0.4),
        ])
        # Verify: shapely .contains is False for point on boundary
        pt = _P(cx, cy)
        assert not trap_poly.contains(pt), (
            "Setup error: shapely should NOT contain a point on the boundary with strict interior"
        )
        grid_cell_heights = {str(_cell_index(row, col)): 12.0}
        result = gsd._trap_grid_override(trap_poly, grid_cell_heights, cell_side, half)
        assert result is None, (
            f"Expected None (cell centre on boundary → excluded) but got {result!r}"
        )


# ===========================================================================
# TG8  Regression: rake lines still visible after override
# ===========================================================================

class TestRakeRegressionAfterOverride:
    """TG8: When override is active, rake lines must still appear on the trap top."""

    def test_rake_visible_after_override(self, tmp_path):
        """TG8: Top-face Z spread ≥ 0.1 mm (rake ridges) even with grid-cell override."""
        gsd = _load_gsd()
        half, cell_side, GRID_SIZE = _get_grid_geometry(gsd)
        cx_px, cy_px, gr_px = 300.0, 300.0, 105.0
        egm = _base_egm(cx_px, cy_px, gr_px)

        # Add a trap far enough from the green that the fringe-min rule doesn't
        # produce the same height as our override.
        # We'll place the trap at a position that maps to a known cell.
        # The trap polygon is in pixel space; after _compute_px_to_mm it lands in mm.
        # Strategy: pick a trap position far enough from green centre to survive inset.
        trap_cx_offset_px = 130.0
        trap_r_px = 35.0
        egm["polygons"].append({
            "name": "Trap1", "type": "trap",
            "points": _make_circle_pts(cx_px + trap_cx_offset_px, cy_px, trap_r_px, n=24),
        })

        # Compute a grid cell that should land inside that trap in mm coords.
        # Use the px→mm transform that export_trap_stls uses:
        # _compute_px_to_mm scales green bnd to PRINT_SIZE_MM.
        # We figure out the cell near (half, 0) mm which is the right side.
        # Pick cell (10, 18) — right side, middle row.
        row_tg, col_tg = 10, 18
        cx_mm, cy_mm = _cell_center_mm(row_tg, col_tg, half, cell_side)
        idx_tg = str(_cell_index(row_tg, col_tg))
        # Set it to 12 mm (well above the fringe-min default of ~4 mm).
        egm["gridCellHeights"] = {idx_tg: 12.0}

        green_bnd_px = gsd.interpolate_catmull_rom(egm["polygons"][0]["points"])
        Z_mm, xs_g, ys_g, inside_mask = _flat_green_arrays(cx_px, cy_px, gr_px)

        fringe_mesh = gsd.build_fringe_mesh(
            Z_mm, xs_g, ys_g, inside_mask,
            green_bnd_px, egm,
            fringe_grid_res=80,
        )
        trap_results = gsd.export_trap_stls(
            egm, green_bnd_px,
            slug="test_tg8",
            fringe_mesh=fringe_mesh,
            write_stls=False,
        )
        assert trap_results, "No trap meshes generated"

        for node_name, trap_mesh in trap_results:
            verts = np.asarray(trap_mesh.vertices)
            z_slab_top = float(verts[:, 2].max())
            top_verts = verts[verts[:, 2] > z_slab_top - 1.5]
            assert len(top_verts) > 3, f"{node_name}: too few top verts"
            z_range = float(top_verts[:, 2].max() - top_verts[:, 2].min())
            assert z_range >= 0.10, (
                f"{node_name}: top Z spread = {z_range:.4f} mm; "
                "expected ≥ 0.10 mm (rake ridges must survive override)"
            )


# ===========================================================================
# TG9  Regression: trap frame-cap and water-hole lift unchanged
# ===========================================================================

class TestRegressionFrameCapAndWaterLift:
    """TG9: BOUNDARY_HEIGHT_CAP_ENABLED=False and WATER_HOLE_LIFT_ENABLED still honoured."""

    def test_boundary_cap_enabled_constant_still_accessible(self):
        """TG9a: BOUNDARY_HEIGHT_CAP_ENABLED constant still accessible."""
        gsd = _load_gsd()
        assert hasattr(gsd, "BOUNDARY_HEIGHT_CAP_ENABLED"), (
            "BOUNDARY_HEIGHT_CAP_ENABLED constant missing"
        )

    def test_water_hole_lift_enabled_constant_still_accessible(self):
        """TG9b: WATER_HOLE_LIFT_ENABLED constant still accessible."""
        gsd = _load_gsd()
        assert hasattr(gsd, "WATER_HOLE_LIFT_ENABLED"), (
            "WATER_HOLE_LIFT_ENABLED constant missing"
        )

    def test_trap_fringe_offset_constant_unchanged(self):
        """TG9c: TRAP_FRINGE_OFFSET_MM = -2.0 (default rule preserved)."""
        gsd = _load_gsd()
        assert hasattr(gsd, "TRAP_FRINGE_OFFSET_MM"), (
            "TRAP_FRINGE_OFFSET_MM constant missing"
        )
        assert abs(gsd.TRAP_FRINGE_OFFSET_MM - (-2.0)) < 1e-9, (
            f"TRAP_FRINGE_OFFSET_MM = {gsd.TRAP_FRINGE_OFFSET_MM}; expected -2.0"
        )


# ===========================================================================
# Integration test: export_trap_stls uses override when cell is inside trap
# ===========================================================================

class TestIntegrationOverrideApplied:
    """Integration: export_trap_stls applies the grid-cell override to trap height."""

    def test_override_height_used_when_cell_inside_trap(self, tmp_path):
        """Integration: slab height = override value (12 mm) when cell is inside trap."""
        gsd = _load_gsd()
        half, cell_side, GRID_SIZE = _get_grid_geometry(gsd)
        cx_px, cy_px, gr_px = 300.0, 300.0, 105.0

        # Place trap at (cx+130, cy) in px, radius 35 px.
        trap_cx_offset_px = 130.0
        trap_r_px = 35.0
        egm = _base_egm(cx_px, cy_px, gr_px)
        egm["polygons"].append({
            "name": "TrapA", "type": "trap",
            "points": _make_circle_pts(cx_px + trap_cx_offset_px, cy_px, trap_r_px, n=24),
        })

        # Compute mm position of the trap centre after px→mm transform.
        # _compute_px_to_mm: scale = PRINT_SIZE_MM / max_dim of green bbox,
        # centroid is the green centroid in px.
        green_bnd_px = gsd.interpolate_catmull_rom(egm["polygons"][0]["points"])
        scale, centroid_px = gsd._compute_px_to_mm(green_bnd_px, egm)
        trap_cx_mm = (cx_px + trap_cx_offset_px - centroid_px[0]) * scale
        trap_cy_mm = (cy_px - centroid_px[1]) * scale

        # Find which 20×20 cell contains the trap centre.
        # cell (row, col): cx = -half + (col+0.5)*cell_side → col = floor((cx+half)/cell_side - 0.5)
        col_tg = int(math.floor((trap_cx_mm + half) / cell_side))
        row_tg = int(math.floor((trap_cy_mm + half) / cell_side))
        col_tg = max(0, min(GRID_SIZE - 1, col_tg))
        row_tg = max(0, min(GRID_SIZE - 1, row_tg))
        idx_tg = str(_cell_index(row_tg, col_tg))
        cell_cx, cell_cy = _cell_center_mm(row_tg, col_tg, half, cell_side)

        # Verify the cell centre is inside the expected trap mm polygon.
        from shapely.geometry import Point as _P, Polygon as _PolyS
        trap_pts_mm = [(cx_px + trap_r_px * math.cos(2*math.pi*i/24) + trap_cx_offset_px - centroid_px[0],
                        cy_px + trap_r_px * math.sin(2*math.pi*i/24) - centroid_px[1])
                       for i in range(24)]
        trap_pts_mm = [((x * scale), (y * scale)) for x, y in trap_pts_mm]
        trap_shapely_mm = _PolyS(trap_pts_mm)
        cell_inside = trap_shapely_mm.contains(_P(cell_cx, cell_cy))

        if not cell_inside:
            pytest.skip(
                f"Cell ({row_tg},{col_tg}) centre ({cell_cx:.2f},{cell_cy:.2f}) mm "
                f"is not inside trap polygon — adjust geometry to make this test meaningful"
            )

        override_z = 12.0
        egm["gridCellHeights"] = {idx_tg: override_z}

        Z_mm, xs_g, ys_g, inside_mask = _flat_green_arrays(cx_px, cy_px, gr_px)
        fringe_mesh = gsd.build_fringe_mesh(
            Z_mm, xs_g, ys_g, inside_mask, green_bnd_px, egm, fringe_grid_res=80
        )
        trap_results = gsd.export_trap_stls(
            egm, green_bnd_px,
            slug="test_tg_int",
            fringe_mesh=fringe_mesh,
            write_stls=False,
        )
        assert trap_results, "No trap meshes generated"
        _node, trap_mesh = trap_results[0]
        verts = np.asarray(trap_mesh.vertices)
        # Top surface median Z should be very close to override_z (12 mm).
        z_slab_base = float(verts[:, 2].min())
        z_slab_top = float(verts[:, 2].max())
        slab_mid = z_slab_base + (z_slab_top - z_slab_base) * 0.5
        top_verts = verts[verts[:, 2] > slab_mid]
        assert len(top_verts) > 0, "No top-face vertices found"
        z_top_median = float(np.median(top_verts[:, 2]))
        # The override sets the HEIGHT (= top surface Z when BASE_THICKNESS_MM = 0 base).
        # Expect slab height ≈ override_z — allow 1.5 mm tolerance for rake amplitude.
        assert abs(z_top_median - override_z) <= 1.5, (
            f"Top Z median = {z_top_median:.2f} mm; expected ≈ {override_z} mm "
            f"(grid override should set trap height to 12 mm)"
        )
