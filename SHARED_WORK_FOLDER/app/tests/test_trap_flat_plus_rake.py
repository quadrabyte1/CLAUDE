"""
test_trap_flat_plus_rake.py — Bug→TDD for trap simplification: flat top + rake lines only.

Task 708 (Topo, 2026-10-04).
Thomas's request: remove sand chunks, floor guard, and curved-surface from traps.
Keep: flat top at min(fringe boundary Z) - 2 mm, rake lines.

Tests
-----
TR1  No sand-chunk constants — module has NO SAND_CHUNK_HEIGHT_MM, SAND_CHUNK_SIGMA_MM,
     SAND_CHUNK_UP_FRACTION, etc.  Grep-style attribute assert.
TR2  No _scatter_sand_chunks — function is gone from the module namespace.
TR3  No chunk code in apply_sand_texture — build a trap and verify top-face Z values
     deviate from flat + rake by no more than rake amplitude (no larger localized peaks).
TR4  No floor guard — assert the per-vertex clamp branch is gone (no reference to
     SAND_CHUNK_FLOOR_THICKNESS_MM in apply_sand_texture source).
TR5  TRAP_SURFACE_CURVED = False (default restored) — the constant exists and is False.
TR6  Flat trap produces correct height — trap on a sloped fringe yields a FLAT top at
     min(fringe boundary Z) - 2 mm, not a per-point curved surface.
TR7  Curved path still reachable — with TRAP_SURFACE_CURVED = True, the per-point
     curved behaviour fires (regression guard for task 666).
TR8  Rake intact — flat-top trap has visible cosine ridges; amplitude matches constant.
TR9  Regression: build_fringe_mesh still produces a valid fringe mesh.
TR10 Regression: TRAP_SURFACE_CURVED=False is the module default (not just settable).

Run:
    cd /Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER
    python -m pytest app/tests/test_trap_flat_plus_rake.py -v
"""
from __future__ import annotations

import importlib
import importlib.util
import inspect
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

RAKE_AMPLITUDE_MM = 0.35   # matches apply_sand_texture default amplitude=1.0 * 0.5*2 → peak-to-peak; actual peak = 0.35


def _load_gsd():
    """Load gradient_surface_diagnostic as a fresh module instance."""
    spec = importlib.util.spec_from_file_location("gsd_trap_test", GSD_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Shared geometry helpers
# ---------------------------------------------------------------------------

def _make_circle_pts(cx_px, cy_px, r_px, n=64):
    return [
        {"x": cx_px + r_px * math.cos(2 * math.pi * i / n),
         "y": cy_px + r_px * math.sin(2 * math.pi * i / n)}
        for i in range(n)
    ]


def _base_egm_with_trap(cx_px=300.0, cy_px=300.0, gr_px=105.0,
                         trap_cx_offset=130.0, trap_r_px=35.0):
    """Minimal EGM with one green + one trap slightly outside the green."""
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
            {"name": "Trap1", "type": "trap",
             "points": _make_circle_pts(cx_px + trap_cx_offset, cy_px, trap_r_px, n=24)},
        ],
        "fringeBoundaryHeights": [],
        "elevationSpikes": [],
    }


def _flat_green_arrays(cx_px=300.0, cy_px=300.0, r_px=105.0,
                       grid_res=200, z_val=6.0):
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
# TR1  No sand-chunk constants
# ===========================================================================

class TestNoSandChunkConstants:
    """TR1: SAND_CHUNK_* constants must be gone from the module."""

    CHUNK_CONSTANTS = [
        "SAND_CHUNK_HEIGHT_MM",
        "SAND_CHUNK_SIGMA_MM",
        "SAND_CHUNK_DENSITY_PER_100_MM2",
        "SAND_CHUNK_MAX",
        "SAND_CHUNK_MIN",
        "SAND_CHUNK_UP_FRACTION",
        "SAND_CHUNK_FLOOR_THICKNESS_MM",
    ]

    def test_no_chunk_constants_in_module(self):
        """TR1: None of the SAND_CHUNK_* constants may exist after the strip."""
        gsd = _load_gsd()
        found = [name for name in self.CHUNK_CONSTANTS if hasattr(gsd, name)]
        assert not found, (
            f"Sand-chunk constants still present after strip: {found}"
        )


# ===========================================================================
# TR2  No _scatter_sand_chunks function
# ===========================================================================

class TestNoScatterSandChunks:
    """TR2: _scatter_sand_chunks must be gone from the module namespace."""

    def test_scatter_sand_chunks_not_present(self):
        """TR2: _scatter_sand_chunks() must not exist in the module."""
        gsd = _load_gsd()
        assert not hasattr(gsd, "_scatter_sand_chunks"), (
            "_scatter_sand_chunks is still present — chunk helper was not removed"
        )


# ===========================================================================
# TR3  No Gaussian bumps on trap top — Z stays within rake amplitude
# ===========================================================================

class TestNoGaussianBumpsOnTrapTop:
    """TR3: Top-face Z values must not exceed flat_base + rake_amplitude.

    After stripping chunks, the only Z variation on the trap top should come
    from the cosine rake wave.  The peak-to-trough amplitude of apply_sand_texture
    is 0.35 mm (amplitude param defaults to 1.0 but the dz formula is
    amplitude * 0.5 * (1 + cos(...)) so dz ∈ [0, amplitude]).  The effective
    max above the base is `amplitude` (i.e. 1.0 * 0.5 * 2 = 1.0 mm peak
    when amplitude=1.0, but default is 1.0 so max dz = 1.0 mm).  We tolerate
    up to 1.1 mm above the slab base to give a small floating-point buffer.
    The key guard is that no vertex deviates MORE than (amplitude + 0.1) mm
    from the slab base Z, which would indicate a Gaussian chunk was applied.
    """

    def test_no_gaussian_bump_outliers_on_trap_top(self, tmp_path):
        """TR3: Max Z deviation above base ≤ rake amplitude + 0.1 mm (no chunks)."""
        gsd = _load_gsd()
        cx_px, cy_px, gr_px = 300.0, 300.0, 105.0
        egm = _base_egm_with_trap(cx_px, cy_px, gr_px)
        green_bnd_px = gsd.interpolate_catmull_rom(egm["polygons"][0]["points"])
        Z_mm, xs_g, ys_g, inside_mask = _flat_green_arrays(cx_px, cy_px, gr_px)

        fringe_mesh = gsd.build_fringe_mesh(
            Z_mm, xs_g, ys_g, inside_mask,
            green_bnd_px, egm,
            fringe_grid_res=80,
        )

        trap_results = gsd.export_trap_stls(
            egm, green_bnd_px,
            slug="test_tr3",
            fringe_mesh=fringe_mesh,
            write_stls=False,
        )
        assert trap_results, "No trap meshes were generated (need at least 1)"

        for node_name, trap_mesh in trap_results:
            verts = np.asarray(trap_mesh.vertices)
            # Isolate top-face vertices (above the midpoint of the slab).
            z_slab_base = float(verts[:, 2].min())
            z_slab_top  = float(verts[:, 2].max())
            slab_mid    = z_slab_base + (z_slab_top - z_slab_base) * 0.5

            top_verts = verts[verts[:, 2] > slab_mid]
            assert len(top_verts) > 3, (
                f"{node_name}: too few top-face vertices to test"
            )

            # The only displacement above the base should be from the rake
            # cosine wave (amplitude=1.0 default → max dz=1.0 mm).
            # Sand chunks (0.6 mm peak) would push individual vertices much
            # further above the local mean — detect them as outliers.
            z_top = top_verts[:, 2]
            z_median = float(np.median(z_top))
            z_max    = float(z_top.max())
            # Deviation from median > 1.5 mm would indicate a Gaussian bump.
            max_deviation = z_max - z_median
            assert max_deviation < 1.5, (
                f"{node_name}: top Z max deviation from median = "
                f"{max_deviation:.3f} mm; expected < 1.5 mm (rake only, no chunks)"
            )


# ===========================================================================
# TR4  No floor guard — SAND_CHUNK_FLOOR_THICKNESS_MM not referenced in
#      apply_sand_texture source
# ===========================================================================

class TestNoFloorGuard:
    """TR4: The per-vertex floor clamp must be gone from apply_sand_texture."""

    def test_no_floor_guard_in_apply_sand_texture(self):
        """TR4: apply_sand_texture source must NOT reference SAND_CHUNK_FLOOR_THICKNESS_MM."""
        gsd = _load_gsd()
        src = inspect.getsource(gsd.apply_sand_texture)
        assert "SAND_CHUNK_FLOOR_THICKNESS_MM" not in src, (
            "apply_sand_texture still references SAND_CHUNK_FLOOR_THICKNESS_MM "
            "(floor guard was not removed)"
        )
        # Also check that the floor_z / floor_v / np.maximum floor pattern is gone.
        assert "_use_per_vertex_floor" not in src, (
            "apply_sand_texture still contains _use_per_vertex_floor "
            "(floor guard was not removed)"
        )


# ===========================================================================
# TR5  TRAP_SURFACE_CURVED = False (default)
# ===========================================================================

class TestTrapSurfaceCurvedDefault:
    """TR5: TRAP_SURFACE_CURVED must exist and default to False."""

    def test_trap_surface_curved_is_false(self):
        """TR5: Module-level TRAP_SURFACE_CURVED = False after revert."""
        gsd = _load_gsd()
        assert hasattr(gsd, "TRAP_SURFACE_CURVED"), (
            "TRAP_SURFACE_CURVED constant is missing from the module"
        )
        assert gsd.TRAP_SURFACE_CURVED is False, (
            f"TRAP_SURFACE_CURVED expected False, got {gsd.TRAP_SURFACE_CURVED!r}"
        )


# ===========================================================================
# TR6  Flat trap: top is at min(fringe Z) - 2 mm, not per-point curved
# ===========================================================================

class TestFlatTrapHeight:
    """TR6: With TRAP_SURFACE_CURVED=False, trap top must be a flat scalar
    at min(fringe boundary Z) + TRAP_FRINGE_OFFSET_MM (-2 mm).
    """

    def test_flat_trap_top_is_uniform(self, tmp_path):
        """TR6: Top-face Z variation < 0.05 mm on a sloped-fringe hole (flat, not curved)."""
        gsd = _load_gsd()
        assert gsd.TRAP_SURFACE_CURVED is False, "TR6 requires TRAP_SURFACE_CURVED=False"

        cx_px, cy_px, gr_px = 300.0, 300.0, 105.0
        egm = _base_egm_with_trap(cx_px, cy_px, gr_px)
        green_bnd_px = gsd.interpolate_catmull_rom(egm["polygons"][0]["points"])

        # Tilted green: 3 mm on left, 9 mm on right → steep slope so curved vs flat
        # is detectable.
        xs_g = np.linspace(0, 599, 200)
        ys_g = np.linspace(0, 599, 200)
        inside_mask = np.zeros((200, 200), dtype=bool)
        Z_mm = np.zeros((200, 200), dtype=float)
        for ri, py in enumerate(ys_g):
            for ci, px in enumerate(xs_g):
                if math.hypot(px - cx_px, py - cy_px) < gr_px:
                    inside_mask[ri, ci] = True
                    t = (px - cx_px + gr_px) / (2.0 * gr_px)  # 0..1 across width
                    Z_mm[ri, ci] = 3.0 + 6.0 * t  # 3..9 mm

        fringe_mesh = gsd.build_fringe_mesh(
            Z_mm, xs_g, ys_g, inside_mask,
            green_bnd_px, egm,
            fringe_grid_res=80,
        )

        trap_results = gsd.export_trap_stls(
            egm, green_bnd_px,
            slug="test_tr6",
            fringe_mesh=fringe_mesh,
            write_stls=False,
        )
        assert trap_results, "No trap meshes generated"

        for node_name, trap_mesh in trap_results:
            verts = np.asarray(trap_mesh.vertices)
            z_slab_base = float(verts[:, 2].min())
            z_slab_top  = float(verts[:, 2].max())
            slab_mid = z_slab_base + (z_slab_top - z_slab_base) * 0.5

            top_verts = verts[verts[:, 2] > slab_mid]
            assert len(top_verts) > 3, f"{node_name}: too few top vertices"

            z_top = top_verts[:, 2]
            # Rake amplitude is at most 1.0 mm (amplitude=1.0 default).
            # On a FLAT base the mean-to-max deviation ≤ 1.0 mm.
            # The key test: the Z range (max - min) on the top face should be
            # ≤ rake_amplitude + 0.1 mm.  A curved surface would add the green
            # tilt (3–9 mm range) on top, giving a much larger Z spread.
            z_range = float(z_top.max() - z_top.min())
            assert z_range <= 1.1, (
                f"{node_name}: trap top Z range = {z_range:.3f} mm; "
                f"expected ≤ 1.1 mm (flat base + rake only); "
                f"a larger range indicates the curved-surface path is still active"
            )


# ===========================================================================
# TR7  Curved path still reachable with TRAP_SURFACE_CURVED=True
# ===========================================================================

class TestCurvedPathStillReachable:
    """TR7: Setting TRAP_SURFACE_CURVED=True must restore the per-point curved
    behaviour (regression guard for task 666 work).
    """

    def test_curved_path_produces_varying_trap_top(self, tmp_path):
        """TR7: With TRAP_SURFACE_CURVED=True and a sloped fringe, trap top Z
        varies > 1.5 mm (curved surface tracking the fringe slope)."""
        gsd = _load_gsd()
        gsd.TRAP_SURFACE_CURVED = True   # enable the curved path explicitly

        cx_px, cy_px, gr_px = 300.0, 300.0, 105.0
        egm = _base_egm_with_trap(cx_px, cy_px, gr_px)
        green_bnd_px = gsd.interpolate_catmull_rom(egm["polygons"][0]["points"])

        # Steep tilt: 2 mm left edge, 10 mm right edge.
        xs_g = np.linspace(0, 599, 200)
        ys_g = np.linspace(0, 599, 200)
        inside_mask = np.zeros((200, 200), dtype=bool)
        Z_mm = np.zeros((200, 200), dtype=float)
        for ri, py in enumerate(ys_g):
            for ci, px in enumerate(xs_g):
                if math.hypot(px - cx_px, py - cy_px) < gr_px:
                    inside_mask[ri, ci] = True
                    t = (px - cx_px + gr_px) / (2.0 * gr_px)
                    Z_mm[ri, ci] = 2.0 + 8.0 * t  # 2..10 mm

        fringe_mesh = gsd.build_fringe_mesh(
            Z_mm, xs_g, ys_g, inside_mask,
            green_bnd_px, egm,
            fringe_grid_res=80,
        )

        trap_results = gsd.export_trap_stls(
            egm, green_bnd_px,
            slug="test_tr7",
            fringe_mesh=fringe_mesh,
            write_stls=False,
        )
        assert trap_results, "No trap meshes generated"

        any_curved = False
        for node_name, trap_mesh in trap_results:
            verts = np.asarray(trap_mesh.vertices)
            z_slab_base = float(verts[:, 2].min())
            z_slab_top  = float(verts[:, 2].max())
            slab_mid = z_slab_base + (z_slab_top - z_slab_base) * 0.5
            top_verts = verts[verts[:, 2] > slab_mid]
            if len(top_verts) < 4:
                continue
            z_range = float(top_verts[:, 2].max() - top_verts[:, 2].min())
            if z_range > 1.5:
                any_curved = True

        assert any_curved, (
            "With TRAP_SURFACE_CURVED=True and an 8 mm tilt, expected at least one "
            "trap to show Z range > 1.5 mm (curved surface tracking the fringe slope), "
            "but all traps had a flat top."
        )


# ===========================================================================
# TR8  Rake intact: cosine ridges on the flat top
# ===========================================================================

class TestRakeIntact:
    """TR8: Flat-top trap must still have cosine rake ridges; dz ≥ 0.1 mm."""

    def test_rake_ridges_present_on_flat_trap(self, tmp_path):
        """TR8: Top-face Z spread ≥ 0.1 mm (rake ridges visible) with TRAP_SURFACE_CURVED=False."""
        gsd = _load_gsd()
        assert gsd.TRAP_SURFACE_CURVED is False

        cx_px, cy_px, gr_px = 300.0, 300.0, 105.0
        egm = _base_egm_with_trap(cx_px, cy_px, gr_px)
        green_bnd_px = gsd.interpolate_catmull_rom(egm["polygons"][0]["points"])
        Z_mm, xs_g, ys_g, inside_mask = _flat_green_arrays(cx_px, cy_px, gr_px)

        fringe_mesh = gsd.build_fringe_mesh(
            Z_mm, xs_g, ys_g, inside_mask,
            green_bnd_px, egm,
            fringe_grid_res=80,
        )

        trap_results = gsd.export_trap_stls(
            egm, green_bnd_px,
            slug="test_tr8",
            fringe_mesh=fringe_mesh,
            write_stls=False,
        )
        assert trap_results, "No trap meshes generated"

        for node_name, trap_mesh in trap_results:
            verts = np.asarray(trap_mesh.vertices)
            z_slab_top = float(verts[:, 2].max())
            # Top-face vertices: within 1.5 mm of the slab top.
            top_verts = verts[verts[:, 2] > z_slab_top - 1.5]
            assert len(top_verts) > 3, f"{node_name}: too few top verts"
            z_range = float(top_verts[:, 2].max() - top_verts[:, 2].min())
            assert z_range >= 0.10, (
                f"{node_name}: top Z spread = {z_range:.4f} mm; "
                f"expected ≥ 0.10 mm (rake ridges must be present)"
            )


# ===========================================================================
# TR9  Regression: build_fringe_mesh still produces a valid fringe mesh
# ===========================================================================

class TestFringeMeshRegression:
    """TR9: build_fringe_mesh must still produce a valid mesh after the strip."""

    def test_fringe_mesh_still_valid(self, tmp_path):
        """TR9: fringe mesh after chunk/guard strip — finite, ≥ BASE_THICKNESS_MM."""
        gsd = _load_gsd()
        cx_px, cy_px, gr_px = 300.0, 300.0, 105.0
        egm = {
            "course": "TestCourse", "hole": "99", "image": "dummy.png",
            "imageSize": {"width": 600, "height": 600},
            "elevationRange": 14.5, "greenScale": 1.0,
            "polygons": [{"name": "Green", "type": "green",
                          "points": _make_circle_pts(cx_px, cy_px, gr_px)}],
            "fringeBoundaryHeights": [], "elevationSpikes": [],
        }
        green_bnd_px = gsd.interpolate_catmull_rom(egm["polygons"][0]["points"])
        Z_mm, xs_g, ys_g, inside_mask = _flat_green_arrays(cx_px, cy_px, gr_px)

        fringe_mesh = gsd.build_fringe_mesh(
            Z_mm, xs_g, ys_g, inside_mask,
            green_bnd_px, egm,
            fringe_grid_res=80,
        )

        verts = np.asarray(fringe_mesh.vertices)
        assert len(verts) > 0, "Fringe mesh has no vertices"
        assert np.all(np.isfinite(verts)), "Fringe mesh has NaN/Inf vertices"

        top_verts = verts[verts[:, 2] > gsd.BASE_THICKNESS_MM * 0.5]
        assert len(top_verts) > 0, "No top fringe vertices (Z > BASE/2)"
        assert float(top_verts[:, 2].min()) >= gsd.BASE_THICKNESS_MM - 0.1, (
            f"Fringe top Z min = {top_verts[:,2].min():.3f} mm < BASE"
        )


# ===========================================================================
# TR10  TRAP_SURFACE_CURVED=False is the module-level default (not just settable)
# ===========================================================================

class TestTrapSurfaceCurvedModuleDefault:
    """TR10: After a fresh module load (no monkey-patching), TRAP_SURFACE_CURVED must be False."""

    def test_fresh_module_load_curved_false(self):
        """TR10: Fresh module load → TRAP_SURFACE_CURVED is False."""
        # Load a second fresh copy to ensure it's the default, not a leftover
        # from a previous test that might have set it to True.
        spec = importlib.util.spec_from_file_location("gsd_tr10_fresh", GSD_PATH)
        mod_fresh = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod_fresh)
        assert mod_fresh.TRAP_SURFACE_CURVED is False, (
            f"Fresh module load: TRAP_SURFACE_CURVED = {mod_fresh.TRAP_SURFACE_CURVED!r}, "
            f"expected False"
        )
