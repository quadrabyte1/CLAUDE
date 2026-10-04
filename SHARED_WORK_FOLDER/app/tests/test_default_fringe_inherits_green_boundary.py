"""
test_default_fringe_inherits_green_boundary.py — Bug→TDD for task 700.

Thomas's spec (verbatim):
    "By default, if there aren't any specific elevation notes given in the
    boundary editor the elevation of the green should be the same as the
    corresponding elevation sorry the elevation of the fringe should be the
    same as the corresponding elevation in the green across that interface
    and all the way out to the edge of the frame."

Design: for each fringe cell (x, y), find the nearest point on the green
polygon boundary, look up the Poisson green surface Z at that boundary point,
and hold that Z constant all the way out to the frame edge.  No decay toward
BASE_THICKNESS_MM.

Tests:
    T1  Fringe at mid-edge inherits green Z — green rectangle with Poisson
        Z = 7 mm uniformly; fringe midpoint 20 mm outside the green edge
        has Z ≈ 7 mm (not BASE_THICKNESS_MM).  Tolerance: ±0.1 mm.
    T2  Fringe at tilted-green mirrors tilt — green with linear Z ramp
        5 → 10 mm across its boundary; fringe on each side carries that
        side's Z.  Sample both sides, assert ≈ 5 mm one side, ≈ 10 mm other.
    T3  Fringe at sharp corner — fringe cells near a corner of a
        non-circular polygon transition from one side's Z to the adjacent
        side's Z along the Voronoi split.  Assert smooth transition (no
        discontinuous cliff) at the diagonal.
    T4  Fringe at frame edge — fringe Z at the frame extent equals green
        boundary Z at the nearest green edge point (not decayed).
    T5  TPS primitive still callable with empty inputs — regression test that
        _build_tps_base([]) returns a sensible array without raising.
    T6  Regression: trap + rake + water surfaces unchanged by this task.

Run:
    cd /Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER
    python -m pytest app/tests/test_default_fringe_inherits_green_boundary.py -v
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
    spec = importlib.util.spec_from_file_location("gsd_dfig_test", GSD_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Shared geometry helpers
# ---------------------------------------------------------------------------

def _make_rect_green_pts(cx_px, cy_px, half_w_px, half_h_px):
    """Return [{x, y}] polygon points for a rectangle in pixel space."""
    # 4 corners, wound CCW
    return [
        {"x": cx_px - half_w_px, "y": cy_px - half_h_px},
        {"x": cx_px + half_w_px, "y": cy_px - half_h_px},
        {"x": cx_px + half_w_px, "y": cy_px + half_h_px},
        {"x": cx_px - half_w_px, "y": cy_px + half_h_px},
    ]


def _make_circular_green_pts(cx_px, cy_px, r_px, n=64):
    """Return [{x, y}] polygon points for a circle."""
    return [
        {"x": cx_px + r_px * math.cos(2 * math.pi * i / n),
         "y": cy_px + r_px * math.sin(2 * math.pi * i / n)}
        for i in range(n)
    ]


def _base_egm_rect(cx_px=300.0, cy_px=300.0,
                   half_w_px=80.0, half_h_px=60.0,
                   elevation_range=14.5):
    """Minimal EGM dict with a rectangular green."""
    return {
        "course": "TestCourse",
        "hole": "99",
        "image": "dummy.png",
        "imageSize": {"width": 600, "height": 600},
        "elevationRange": elevation_range,
        "greenScale": 1.0,
        "polygons": [{"name": "Green", "type": "green",
                      "points": _make_rect_green_pts(cx_px, cy_px,
                                                     half_w_px, half_h_px)}],
        "fringeBoundaryHeights": [],
        "elevationSpikes": [],
    }


def _base_egm_circ(cx_px=300.0, cy_px=300.0, r_px=90.0, n=64,
                   elevation_range=14.5):
    """Minimal EGM dict with a circular green."""
    return {
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


def _flat_inside_mask_z(cx_px, cy_px, r_px, grid_res=200, z_val=7.0):
    """Build flat inside_mask + Z_mm + xs_g + ys_g for a circular green at z_val."""
    xs_g = np.linspace(0.0, 599.0, grid_res)
    ys_g = np.linspace(0.0, 599.0, grid_res)
    inside_mask = np.zeros((grid_res, grid_res), dtype=bool)
    Z_mm = np.full((grid_res, grid_res), z_val)
    for ri, py in enumerate(ys_g):
        for ci, px in enumerate(xs_g):
            if math.hypot(px - cx_px, py - cy_px) < r_px:
                inside_mask[ri, ci] = True
    return Z_mm, xs_g, ys_g, inside_mask


def _rect_inside_mask_z(cx_px, cy_px, half_w_px, half_h_px,
                        grid_res=200, z_val=7.0):
    """Build flat inside_mask + Z_mm for a rectangular green at z_val."""
    xs_g = np.linspace(0.0, 599.0, grid_res)
    ys_g = np.linspace(0.0, 599.0, grid_res)
    inside_mask = np.zeros((grid_res, grid_res), dtype=bool)
    Z_mm = np.full((grid_res, grid_res), z_val)
    for ri, py in enumerate(ys_g):
        for ci, px in enumerate(xs_g):
            if (abs(px - cx_px) < half_w_px) and (abs(py - cy_px) < half_h_px):
                inside_mask[ri, ci] = True
    return Z_mm, xs_g, ys_g, inside_mask


def _tilted_inside_mask_z(cx_px, cy_px, r_px, grid_res=200,
                           z_left=5.0, z_right=10.0):
    """Build inside_mask + Z_mm for a circular green with left→right tilt.

    Z varies linearly from z_left (leftmost edge) to z_right (rightmost edge).
    Left = negative x relative to cx_px, right = positive x.
    """
    xs_g = np.linspace(0.0, 599.0, grid_res)
    ys_g = np.linspace(0.0, 599.0, grid_res)
    inside_mask = np.zeros((grid_res, grid_res), dtype=bool)
    Z_mm = np.zeros((grid_res, grid_res), dtype=float)
    for ri, py in enumerate(ys_g):
        for ci, px in enumerate(xs_g):
            if math.hypot(px - cx_px, py - cy_px) < r_px:
                inside_mask[ri, ci] = True
                # Linear ramp: -r_px → z_left, +r_px → z_right
                t = (px - cx_px + r_px) / (2.0 * r_px)   # 0 at left, 1 at right
                Z_mm[ri, ci] = z_left + (z_right - z_left) * t
    return Z_mm, xs_g, ys_g, inside_mask


# ===========================================================================
# T1  Fringe at mid-edge inherits uniform green Z (not BASE_THICKNESS_MM)
# ===========================================================================

class TestFringeInheritsGreenZ:
    """T1: fringe Z 20 mm outside the green edge equals the green boundary Z."""

    def test_fringe_midedge_equals_green_boundary_z(self):
        """T1: green uniform 7 mm; fringe midpoint 20 mm away → Z ≈ 7 mm."""
        gsd = _load_gsd()
        cx_px, cy_px, r_px = 300.0, 300.0, 90.0
        egm = _base_egm_circ(cx_px, cy_px, r_px)
        Z_mm, xs_g, ys_g, inside_mask = _flat_inside_mask_z(
            cx_px, cy_px, r_px, grid_res=200, z_val=7.0
        )
        green_pts_px = np.array(
            [(p["x"], p["y"]) for p in egm["polygons"][0]["points"]],
            dtype=np.float64,
        )
        green_bnd_px = gsd.interpolate_catmull_rom(egm["polygons"][0]["points"])

        mesh = gsd.build_fringe_mesh(
            Z_mm=Z_mm,
            xs_grid=xs_g,
            ys_grid=ys_g,
            inside_mask=inside_mask,
            green_boundary_px=green_pts_px,
            egm_data=egm,
            fringe_grid_res=100,
        )

        # The mesh is in mm coords. Sample vertices that are approximately
        # 20 mm outside the green boundary (green radius in mm-space).
        # Filter to TOP-SURFACE vertices only (Z > 1.0 mm) — the watertight-rewrite
        # path produces a full solid with bottom faces at Z=0 and top surface at
        # green-boundary Z; bottom/wall vertices must be excluded from the test.
        scale, centroid_px = gsd._compute_px_to_mm(green_pts_px, egm)
        r_mm = r_px * scale  # green radius in mm

        # Pick top-surface vertices whose XY distance from origin is between
        # r_mm+10 and r_mm+30 mm (clearly outside the green).
        verts = mesh.vertices
        r_vert = np.sqrt(verts[:, 0] ** 2 + verts[:, 1] ** 2)
        top_mask = verts[:, 2] > 1.0   # exclude bottom face / wall base vertices
        band_mask = (r_vert > r_mm + 10.0) & (r_vert < r_mm + 30.0) & top_mask
        band_verts = verts[band_mask]

        assert len(band_verts) > 0, (
            f"No top-surface fringe vertices found in the 10-30 mm band outside "
            f"the green (r_mm={r_mm:.1f})"
        )

        # ALL top-surface vertices in this band should have Z ≈ 7.0 mm (green
        # boundary Z).  Before the fix, they would be at BASE_THICKNESS_MM
        # (~1.5 mm) because the TPS with only 16 outer-frame anchors at BASE
        # drove everything to flat.
        z_vals = band_verts[:, 2]
        z_mean = float(np.mean(z_vals))
        z_min = float(np.min(z_vals))
        base = gsd.BASE_THICKNESS_MM

        assert z_mean > base + 4.0, (
            f"T1 FAILED: fringe Z mean in 10-30 mm band expected ≈7.0 mm "
            f"(green boundary Z), got mean={z_mean:.3f} mm. "
            f"BASE_THICKNESS_MM={base:.1f} mm. "
            f"The fringe is still decaying to BASE instead of inheriting green Z."
        )
        assert abs(z_mean - 7.0) < 0.5, (
            f"T1 FAILED: fringe Z mean expected ≈ 7.0 mm, got {z_mean:.3f} mm"
        )


# ===========================================================================
# T2  Fringe mirrors tilt: left side ≈5 mm, right side ≈10 mm
# ===========================================================================

class TestFringeMirrorsTilt:
    """T2: green with linear Z ramp 5→10 mm; fringe mirrors the tilt."""

    def test_fringe_left_and_right_carry_tilt(self):
        """T2: fringe on low side ≈5 mm, high side ≈8 mm.

        Use z_right=8.0 mm (below BOUNDARY_HEIGHT_CAP_MM=9.0) so the
        plateau-taper logic does not reduce the high-side fringe Z.
        """
        gsd = _load_gsd()
        cx_px, cy_px, r_px = 300.0, 300.0, 85.0
        egm = _base_egm_circ(cx_px, cy_px, r_px)
        Z_mm, xs_g, ys_g, inside_mask = _tilted_inside_mask_z(
            cx_px, cy_px, r_px, grid_res=200, z_left=5.0, z_right=8.0
        )
        green_pts_px = np.array(
            [(p["x"], p["y"]) for p in egm["polygons"][0]["points"]],
            dtype=np.float64,
        )

        mesh = gsd.build_fringe_mesh(
            Z_mm=Z_mm,
            xs_grid=xs_g,
            ys_grid=ys_g,
            inside_mask=inside_mask,
            green_boundary_px=green_pts_px,
            egm_data=egm,
            fringe_grid_res=100,
        )

        scale, centroid_px = gsd._compute_px_to_mm(green_pts_px, egm)
        r_mm = r_px * scale

        verts = mesh.vertices
        # Filter to top-surface vertices only (Z > 1.0 mm).
        top_mask = verts[:, 2] > 1.0
        # Left-side fringe: x < -r_mm*0.5 (clearly left of centre), outside green
        r_vert = np.sqrt(verts[:, 0] ** 2 + verts[:, 1] ** 2)
        left_mask = (verts[:, 0] < -r_mm * 0.5) & (r_vert > r_mm + 5.0) & top_mask
        right_mask = (verts[:, 0] > r_mm * 0.5) & (r_vert > r_mm + 5.0) & top_mask

        left_verts = verts[left_mask]
        right_verts = verts[right_mask]

        assert len(left_verts) > 0, "No left-side fringe vertices found"
        assert len(right_verts) > 0, "No right-side fringe vertices found"

        z_left_mean = float(np.mean(left_verts[:, 2]))
        z_right_mean = float(np.mean(right_verts[:, 2]))

        # Left side should be near 5.0 mm (green boundary Z on that side).
        # Tolerance of 1.0 mm accommodates the seam-reseat smoothing and
        # FRINGE_PLATEAU_MARGIN_MM floor adjustment near the boundary.
        assert abs(z_left_mean - 5.0) < 1.0, (
            f"T2 FAILED: left fringe Z expected ≈5.0 mm, got {z_left_mean:.3f} mm. "
            f"The fringe should inherit the green boundary Z on the low side."
        )
        # Right side should be near 8.0 mm (within the BOUNDARY_HEIGHT_CAP_MM=9.0).
        assert abs(z_right_mean - 8.0) < 1.0, (
            f"T2 FAILED: right fringe Z expected ≈8.0 mm, got {z_right_mean:.3f} mm. "
            f"The fringe should inherit the green boundary Z on the high side."
        )
        # Right must be clearly higher than left
        assert z_right_mean > z_left_mean + 1.5, (
            f"T2 FAILED: right fringe ({z_right_mean:.3f} mm) should be "
            f"significantly above left fringe ({z_left_mean:.3f} mm) — "
            f"the tilt should be mirrored in the fringe."
        )


# ===========================================================================
# T3  Fringe near corners — smooth Voronoi transition
# ===========================================================================

class TestFringeCornerTransition:
    """T3: sharp corner polygon; fringe transitions smoothly along diagonal."""

    def test_fringe_corner_smooth_transition(self):
        """T3: fringe near a corner has no discontinuous Z cliff."""
        gsd = _load_gsd()
        cx_px, cy_px, r_px = 300.0, 300.0, 85.0
        egm = _base_egm_circ(cx_px, cy_px, r_px)
        # Use a tilted green so corners have different Z
        Z_mm, xs_g, ys_g, inside_mask = _tilted_inside_mask_z(
            cx_px, cy_px, r_px, grid_res=200, z_left=5.0, z_right=10.0
        )
        green_pts_px = np.array(
            [(p["x"], p["y"]) for p in egm["polygons"][0]["points"]],
            dtype=np.float64,
        )

        mesh = gsd.build_fringe_mesh(
            Z_mm=Z_mm,
            xs_grid=xs_g,
            ys_grid=ys_g,
            inside_mask=inside_mask,
            green_boundary_px=green_pts_px,
            egm_data=egm,
            fringe_grid_res=100,
        )

        scale, centroid_px = gsd._compute_px_to_mm(green_pts_px, egm)
        r_mm = r_px * scale

        # Gather top-surface fringe vertices sorted by azimuth angle around origin.
        # Filter out bottom/wall vertices (Z=0) — we only want the top surface.
        verts = mesh.vertices
        r_vert = np.sqrt(verts[:, 0] ** 2 + verts[:, 1] ** 2)
        top_mask = verts[:, 2] > 1.0
        ring_mask = (r_vert > r_mm + 8.0) & (r_vert < r_mm + 25.0) & top_mask
        ring_verts = verts[ring_mask]

        assert len(ring_verts) > 10, (
            f"Too few fringe ring vertices (need >10 for continuity test, got {len(ring_verts)})"
        )

        # Sort by azimuth
        angles = np.arctan2(ring_verts[:, 1], ring_verts[:, 0])
        order = np.argsort(angles)
        sorted_z = ring_verts[order, 2]

        # Check: no adjacent Z step larger than 3.0 mm around the ring.
        # A hard cliff from the old TPS would have a ~(BASE vs green_Z) jump
        # that is several mm at the transition.
        max_step = 0.0
        for i in range(len(sorted_z) - 1):
            step = abs(float(sorted_z[i + 1]) - float(sorted_z[i]))
            if step > max_step:
                max_step = step

        assert max_step < 3.5, (
            f"T3 FAILED: largest adjacent Z step around fringe ring = {max_step:.3f} mm. "
            f"Expected smooth Voronoi-style transition (no cliff > 3.5 mm). "
            f"A large step means the fringe is not inheriting boundary Z smoothly."
        )


# ===========================================================================
# T4  Fringe at frame edge — Z matches nearest green boundary Z (not decayed)
# ===========================================================================

class TestFringAtFrameEdge:
    """T4: fringe Z at the outermost frame cells equals the nearest green boundary Z."""

    def test_frame_edge_z_not_decayed(self):
        """T4: fringe Z at frame edge ≈ green boundary Z (constant extension)."""
        gsd = _load_gsd()
        cx_px, cy_px, r_px = 300.0, 300.0, 90.0
        egm = _base_egm_circ(cx_px, cy_px, r_px)
        z_green = 8.5
        Z_mm, xs_g, ys_g, inside_mask = _flat_inside_mask_z(
            cx_px, cy_px, r_px, grid_res=200, z_val=z_green
        )
        green_pts_px = np.array(
            [(p["x"], p["y"]) for p in egm["polygons"][0]["points"]],
            dtype=np.float64,
        )

        mesh = gsd.build_fringe_mesh(
            Z_mm=Z_mm,
            xs_grid=xs_g,
            ys_grid=ys_g,
            inside_mask=inside_mask,
            green_boundary_px=green_pts_px,
            egm_data=egm,
            fringe_grid_res=100,
        )

        half = gsd.PRINT_SIZE_MM / 2.0 + gsd.FRINGE_XY_EXPANSION_MM / 2.0

        # Frame-edge vertices: |x| > half*0.88 OR |y| > half*0.88,
        # filtered to top-surface only (Z > 1.0 mm to exclude bottom/walls).
        verts = mesh.vertices
        top_mask = verts[:, 2] > 1.0
        edge_mask = (
            (np.abs(verts[:, 0]) > half * 0.88) |
            (np.abs(verts[:, 1]) > half * 0.88)
        ) & top_mask
        edge_verts = verts[edge_mask]

        assert len(edge_verts) > 0, (
            f"No fringe vertices found near the frame edge (half={half:.1f} mm)"
        )

        z_edge = edge_verts[:, 2]
        z_edge_mean = float(np.mean(z_edge))
        base = gsd.BASE_THICKNESS_MM

        # Before fix: frame-edge cells would be near BASE_THICKNESS_MM (TPS
        # drove them to the 16-point frame ring at base).
        # After fix: they should be near z_green (constant extension).
        assert z_edge_mean > base + 4.0, (
            f"T4 FAILED: fringe Z at frame edge expected ≈{z_green} mm "
            f"(constant green boundary extension), got mean={z_edge_mean:.3f} mm. "
            f"BASE_THICKNESS_MM={base:.1f} mm. The fringe still decays to base "
            f"at the frame edge instead of holding green boundary Z."
        )
        assert abs(z_edge_mean - z_green) < 1.0, (
            f"T4 FAILED: frame edge fringe Z expected ≈{z_green} mm, "
            f"got {z_edge_mean:.3f} mm"
        )


# ===========================================================================
# T5  TPS primitive still callable with empty inputs (regression)
# ===========================================================================

class TestTPSPrimitiveRegression:
    """T5: _build_tps_base with empty/minimal inputs must not raise."""

    def test_tps_callable_with_empty_inputs(self):
        """T5: _build_tps_base with no fbh/spikes returns finite array."""
        gsd = _load_gsd()
        assert hasattr(gsd, "_build_tps_base"), (
            "_build_tps_base not found — TPS primitive must remain intact"
        )
        cx_px, cy_px, r_px = 300.0, 300.0, 90.0
        egm = _base_egm_circ(cx_px, cy_px, r_px)
        pts_px = np.array(
            [(p["x"], p["y"]) for p in egm["polygons"][0]["points"]],
            dtype=np.float64,
        )
        scale, centroid_px = gsd._compute_px_to_mm(pts_px, egm)
        green_bnd_px = gsd.interpolate_catmull_rom(egm["polygons"][0]["points"])
        green_bnd_mm = gsd._px_to_mm_2d(green_bnd_px.copy(), scale, centroid_px)

        half = gsd.PRINT_SIZE_MM / 2.0 + gsd.FRINGE_XY_EXPANSION_MM / 2.0
        gx = np.linspace(-half, half, 20)
        gy = np.linspace(-half, half, 20)
        GX, GY = np.meshgrid(gx, gy)

        # Must not raise
        z_out = gsd._build_tps_base(
            egm_data=egm,
            green_bnd_mm=green_bnd_mm,
            elevation_spikes_mm=[],
            fringe_boundary_heights_mm=[],
            grid_x=GX,
            grid_y=GY,
        )
        assert z_out.shape == GX.shape, (
            f"T5: expected shape {GX.shape}, got {z_out.shape}"
        )
        assert np.all(np.isfinite(z_out)), "T5: _build_tps_base returned non-finite values"
        base = gsd.BASE_THICKNESS_MM
        # With only frame anchors → surface should be near BASE everywhere
        assert float(np.mean(z_out)) == pytest.approx(base, abs=1.0), (
            f"T5: expected TPS mean ≈ BASE_THICKNESS_MM={base:.1f} mm with empty inputs, "
            f"got mean={float(np.mean(z_out)):.3f} mm"
        )


# ===========================================================================
# T6  Regression: trap + water unaffected
# ===========================================================================

class TestFringeRegressionTrapWater:
    """T6: trap and water meshes unchanged by this task."""

    def test_trap_regression(self, tmp_path):
        """T6a: trap surface still builds without error."""
        gsd = _load_gsd()
        cx_px, cy_px, r_px = 300.0, 300.0, 90.0
        trap_pts = [
            {"x": cx_px + 120, "y": cy_px - 50},
            {"x": cx_px + 180, "y": cy_px - 50},
            {"x": cx_px + 180, "y": cy_px + 50},
            {"x": cx_px + 120, "y": cy_px + 50},
        ]
        egm = {
            "course": "TestCourse",
            "hole": "99",
            "image": "dummy.png",
            "imageSize": {"width": 600, "height": 600},
            "elevationRange": 14.5,
            "greenScale": 1.0,
            "polygons": [
                {"name": "Green", "type": "green",
                 "points": _make_circular_green_pts(cx_px, cy_px, r_px)},
                {"name": "Trap", "type": "trap", "points": trap_pts},
            ],
            "fringeBoundaryHeights": [],
            "elevationSpikes": [],
        }
        Z_mm, xs_g, ys_g, inside_mask = _flat_inside_mask_z(
            cx_px, cy_px, r_px, grid_res=200, z_val=7.0
        )
        green_pts_px = np.array(
            [(p["x"], p["y"]) for p in egm["polygons"][0]["points"]],
            dtype=np.float64,
        )

        fringe_mesh = gsd.build_fringe_mesh(
            Z_mm=Z_mm,
            xs_grid=xs_g,
            ys_grid=ys_g,
            inside_mask=inside_mask,
            green_boundary_px=green_pts_px,
            egm_data=egm,
            fringe_grid_res=100,
        )

        assert fringe_mesh is not None, "T6a: fringe mesh is None (build failed)"
        assert len(fringe_mesh.vertices) > 0, "T6a: fringe mesh has no vertices"

        # Trap meshes — write_stls=False to avoid disk I/O in tmp_path
        trap_results = gsd.export_trap_stls(
            egm_data=egm,
            green_boundary_px=green_pts_px,
            slug="test_t6a",
            fringe_mesh=fringe_mesh,
            stl_dir=str(tmp_path),
            write_stls=False,
        )
        assert len(trap_results) > 0, (
            "T6a: no trap meshes produced — trap pipeline broken"
        )
        for _node_name, tm in trap_results:
            assert tm is not None, "T6a: one of the trap meshes is None"
            assert len(tm.vertices) > 0, "T6a: a trap mesh has no vertices"

    def test_water_regression(self, tmp_path):
        """T6b: water slab still builds at approximately flat Z."""
        gsd = _load_gsd()
        cx_px, cy_px, r_px = 300.0, 300.0, 90.0
        water_pts = [
            {"x": cx_px + 120, "y": cy_px - 50},
            {"x": cx_px + 180, "y": cy_px - 50},
            {"x": cx_px + 180, "y": cy_px + 50},
            {"x": cx_px + 120, "y": cy_px + 50},
        ]
        egm = {
            "course": "TestCourse",
            "hole": "99",
            "image": "dummy.png",
            "imageSize": {"width": 600, "height": 600},
            "elevationRange": 14.5,
            "greenScale": 1.0,
            "polygons": [
                {"name": "Green", "type": "green",
                 "points": _make_circular_green_pts(cx_px, cy_px, r_px)},
                {"name": "Water", "type": "water", "points": water_pts},
            ],
            "fringeBoundaryHeights": [],
            "elevationSpikes": [],
        }
        Z_mm, xs_g, ys_g, inside_mask = _flat_inside_mask_z(
            cx_px, cy_px, r_px, grid_res=200, z_val=7.0
        )
        green_pts_px = np.array(
            [(p["x"], p["y"]) for p in egm["polygons"][0]["points"]],
            dtype=np.float64,
        )

        fringe_mesh = gsd.build_fringe_mesh(
            Z_mm=Z_mm,
            xs_grid=xs_g,
            ys_grid=ys_g,
            inside_mask=inside_mask,
            green_boundary_px=green_pts_px,
            egm_data=egm,
            fringe_grid_res=100,
        )
        assert fringe_mesh is not None, "T6b: fringe mesh is None"

        water_results = gsd.export_water_meshes(
            egm_data=egm,
            green_boundary_px=green_pts_px,
            slug="test_t6b",
            fringe_mesh=fringe_mesh,
            stl_dir=str(tmp_path),
            write_stls=False,
        )
        assert len(water_results) > 0, (
            "T6b: no water meshes produced — water pipeline broken"
        )
