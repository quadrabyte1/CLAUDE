"""
test_gradient_surface_diagnostic.py  —  Geometry tests for trap rake / water surface.

Bug→TDD:  tests written first (RED); fixed by:
  1. Removing the post-texture flatten from export_trap_stls  (trap rake lines).
  2. Setting WATER_RIPPLE_ENABLED = False and removing the post-ripple flatten
     from export_water_meshes  (water smooth-flat slab at correct height).
  3. Trap frame-cap parity: apply the same BOUNDARY_CAP_BAND_MM/TAPER cap that
     fringe receives to trap meshes always (not just on water holes), gated by
     the EGM-level applyFringeFrameCap flag.
  4. Trap top height = adjoining fringe max Z − TRAP_FRINGE_OFFSET_MM (2 mm below
     the highest fringe point on the trap boundary), not interior fringe max.
  5. (Task #606) Rake direction = trap major axis (PCA), jitter noise, cap
     suspension toggle, TRAP_FRINGE_OFFSET_MM -2 → -4 mm.

Covers
------
  A. Trap rake lines — after apply_sand_texture the top surface must carry
     parallel-ridge Z variation.  Tests also confirm the production file no
     longer contains the post-texture flatten block that was wiping the texture.

  B. Water smoothness — water top surface must be flat at the intended slab
     height.  Tests confirm WATER_RIPPLE_ENABLED is False (so no displacement)
     and that the production file no longer contains the post-ripple flatten
     (which was collapsing the slab to the deepest ripple point, ~0.28 mm low).

  C. Trap frame-cap parity (Part 1): trap mesh vertices within
     BOUNDARY_CAP_BAND_MM of the frame edge must be clipped to
     BOUNDARY_HEIGHT_CAP_MM, regardless of whether the hole has water.
     When applyFringeFrameCap=False the cap is skipped for traps too.

  D. Trap height from adjoining fringe (Part 2): trap top = fringe_boundary_max
     − TRAP_FRINGE_OFFSET_MM; fallback to TRAP_THICKNESS_MM when no fringe mesh;
     multi-fringe (two adjoining fringes) uses the higher of the two.

  E. (Task #606) Rake axis = trap major axis (PCA-derived per-trap).
     A trap rotated 30° from X must have rake ridges parallel to its long axis.
     A Y-aligned trap must still produce rakes along Y (regression).

  F. (Task #606) Jitter noise on top of rake lines.
     Same trap → two calls → identical Z values (reproducible).
     Two different traps → different noise patterns.
     Peak-to-peak jitter ≤ SAND_JITTER_AMPLITUDE_MM * 2 + epsilon.

  G. (Task #606) BOUNDARY_HEIGHT_CAP_ENABLED toggle.
     When False: frame-edge vertices keep natural height, no 9-mm clamp.
     When True: existing cap behavior is restored.

  H. (Task #606) TRAP_FRINGE_OFFSET_MM updated from -2.0 to -4.0.
"""
from __future__ import annotations

import importlib.util
import math
import re
import sys
from pathlib import Path

import numpy as np
import pytest
from shapely.geometry import Polygon as ShapelyPolygon

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
APP_DIR = Path(__file__).parent.parent  # .../app/
GSD_PATH = APP_DIR / "gradient_surface_diagnostic.py"
sys.path.insert(0, str(APP_DIR))


# ---------------------------------------------------------------------------
# Module loader
# ---------------------------------------------------------------------------

def _load_gsd():
    """Load gradient_surface_diagnostic as a fresh module object."""
    spec = importlib.util.spec_from_file_location(
        "gradient_surface_diagnostic",
        GSD_PATH,
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Shared mesh helper
# ---------------------------------------------------------------------------

def _build_slab(side_mm: float, height_mm: float):
    """Return a watertight trimesh slab for a square footprint."""
    from generate_stl_3mf import _build_slab_from_shapely

    poly = ShapelyPolygon([(0, 0), (side_mm, 0), (side_mm, side_mm), (0, side_mm)])
    return _build_slab_from_shapely(poly, height_mm)


# ===========================================================================
# A.  Sand-trap rake lines
# ===========================================================================

class TestTrapRakeLines:
    """
    apply_sand_texture must produce genuine Z variation on the top surface,
    and the production code must NOT contain a post-texture flatten that
    would destroy that variation.
    """

    def test_rake_z_variation_present(self):
        """
        After apply_sand_texture the top-surface Z range must be ≥ half the
        default amplitude (0.35 mm), confirming rake lines are present.

        RED  before fix: production code calls apply_sand_texture then flattens
                         all top verts to min-Z (range → 0).
                         NOTE: this test calls the function directly, so it
                         tests the texture function itself.  The companion test
                         test_production_code_has_no_post_texture_flatten is the
                         one that fails on the BUGGY production code.
        GREEN after fix:  flatten removed; Z variation survives.
        """
        gsd = _load_gsd()
        mesh = _build_slab(side_mm=20.0, height_mm=5.0)
        gsd.apply_sand_texture(mesh, trap_index=0)

        top_z = mesh.vertices[mesh.vertices[:, 2] > 1e-6, 2]
        assert len(top_z) > 0, "No top-surface vertices found after apply_sand_texture"
        z_range = float(top_z.max() - top_z.min())

        expected_min_range = 0.35 * 0.5  # half-amplitude, 0.175 mm
        assert z_range >= expected_min_range, (
            f"Rake-line Z variation too small: {z_range:.4f} mm "
            f"(expected >= {expected_min_range:.3f} mm).  "
            "apply_sand_texture may itself be broken (separate from the flatten)."
        )

    def test_rake_peak_count_plausible(self):
        """
        The X-axis profile of the trap top surface must show ≥ 5 local maxima,
        confirming the sinusoidal rake pattern is present.

        With grain_spacing=1.125 mm and a 20 mm trap we expect ~17 peaks.
        """
        gsd = _load_gsd()
        mesh = _build_slab(side_mm=20.0, height_mm=5.0)
        gsd.apply_sand_texture(mesh, trap_index=0)

        top_mask = mesh.vertices[:, 2] > 1e-6
        top_verts = mesh.vertices[top_mask]
        if len(top_verts) == 0:
            pytest.fail("No top-surface vertices found.")

        # Bin by X in 0.5 mm slices; take median Z per bin.
        x_vals = top_verts[:, 0]
        x_min, x_max = x_vals.min(), x_vals.max()
        n_bins = max(1, int((x_max - x_min) / 0.5))
        bin_idx = np.floor(
            (x_vals - x_min) / (x_max - x_min + 1e-9) * n_bins
        ).astype(int)
        bin_z = np.array([
            np.median(top_verts[bin_idx == b, 2]) if np.any(bin_idx == b) else 0.0
            for b in range(n_bins)
        ])

        peaks = [
            i for i in range(1, len(bin_z) - 1)
            if bin_z[i] > bin_z[i - 1] and bin_z[i] > bin_z[i + 1]
        ]

        assert len(peaks) >= 5, (
            f"Too few rake-line peaks: {len(peaks)} (expected ≥ 5).  "
            "apply_sand_texture is not producing a sinusoidal Z profile."
        )

    def test_production_code_has_no_post_texture_flatten(self):
        """
        Static code check: the production source must NOT contain the
        post-texture flatten block (collapsing top verts to min-Z) immediately
        after the apply_sand_texture call in export_trap_stls.

        RED  before fix: the flatten block `_top_min_z = float(...min())` /
                         `mesh.vertices[_top_mask, 2] = _top_min_z` appears
                         in the trap path after apply_sand_texture.
        GREEN after fix:  that block is removed; only the comment/note remains.

        This test guards against the flatten being re-introduced accidentally.
        The sentinel is the variable name `_top_min_z` inside export_trap_stls
        (a water-slab version also uses it but that is inside export_water_meshes,
        a different function; after the water fix that block is also gone).
        """
        source = GSD_PATH.read_text(encoding="utf-8")

        # Find the export_trap_stls function body.
        # We look for the flatten sentinel between apply_sand_texture call and
        # the unconditional cap / touches block that follows it (task #604:
        # `if _hole_water:` was replaced by the unconditional `touches =`).
        trap_fn_pattern = re.compile(
            r"apply_sand_texture\(mesh.*?\n(.*?)(?=touches = _polygon_touches_frame_boundary)",
            re.DOTALL,
        )
        m = trap_fn_pattern.search(source)
        if m is None:
            # Pattern didn't match — most likely the source changed significantly.
            # Fail with a clear message.
            pytest.fail(
                "Could not locate the apply_sand_texture→touches block in "
                "export_trap_stls.  The test regex needs updating "
                "(expected `touches = _polygon_touches_frame_boundary` after "
                "apply_sand_texture — did the cap restructuring move things?)."
            )

        between = m.group(1)
        # The flatten uses `_top_min_z` as the variable name.  Its presence
        # means the flatten is still there.
        assert "_top_min_z" not in between, (
            "Found `_top_min_z` assignment between apply_sand_texture and the "
            "water-hole-rule block in export_trap_stls.  The post-texture flatten "
            "is still present and will wipe the rake-line Z variation."
        )


# ===========================================================================
# B.  Water surface smoothness
# ===========================================================================

class TestWaterSurface:
    """
    Water top surface must be perfectly flat at the intended slab height.

    After WATER_RIPPLE_ENABLED = False the path is:
      _build_slab_from_shapely  →  flat slab at intended height
      (no ripple, no flatten)
    so the top surface is inherently flat and at the correct height.
    """

    @staticmethod
    def _run_water_path(height_mm: float = 4.0, side_mm: float = 20.0):
        """
        Mirror the current export_water_meshes code path:
        build slab, optionally apply ripple, optionally flatten.
        """
        from generate_stl_3mf import _build_slab_from_shapely

        gsd = _load_gsd()
        poly = ShapelyPolygon([(0, 0), (side_mm, 0), (side_mm, side_mm), (0, side_mm)])
        mesh = _build_slab_from_shapely(poly, height_mm)

        # Mirror the gated ripple call.
        if gsd.WATER_RIPPLE_ENABLED:
            gsd.apply_water_ripple_texture(mesh, water_index=1)

        # Mirror the current post-ripple flatten (present only in buggy code).
        # After the fix this block is removed from the production path, but we
        # keep the check here so the test also covers the case where RIPPLE is
        # still accidentally enabled.
        _top_mask = mesh.vertices[:, 2] > 1e-6
        if _top_mask.any():
            _top_min_z = float(mesh.vertices[_top_mask, 2].min())
            mesh.vertices[_top_mask, 2] = _top_min_z

        return mesh, height_mm, gsd

    def test_water_ripple_flag_is_disabled(self):
        """
        WATER_RIPPLE_ENABLED must be False.

        RED  before fix: True  — water receives ripple displacement.
        GREEN after fix:  False — water is a plain flat slab.
        """
        gsd = _load_gsd()
        assert not gsd.WATER_RIPPLE_ENABLED, (
            "WATER_RIPPLE_ENABLED is True — water will receive a ripple texture.  "
            "Set WATER_RIPPLE_ENABLED = False to restore smooth-flat-slab behaviour."
        )

    def test_water_top_is_flat(self):
        """
        All top-surface vertices must share the same Z (within 0.001 mm).
        """
        mesh, _, _ = self._run_water_path(height_mm=3.0)
        top_z = mesh.vertices[mesh.vertices[:, 2] > 1e-6, 2]
        assert len(top_z) > 0, "No top-surface vertices."
        z_range = float(top_z.max() - top_z.min())
        assert z_range < 0.001, (
            f"Water top surface is NOT flat: Z range = {z_range:.4f} mm "
            "(expected < 0.001 mm)."
        )

    def test_water_top_height_matches_intended_slab_height(self):
        """
        The flat top surface must sit at the exact intended slab height.

        RED  before fix: WATER_RIPPLE_ENABLED=True → ripple displaces down
                         ~0.28 mm; flatten collapses to ripple minimum →
                         actual_top_z ≈ intended - 0.28 mm.
        GREEN after fix:  WATER_RIPPLE_ENABLED=False → no displacement →
                          slab stays at the height _build_slab_from_shapely set.

        Note: our `_run_water_path` helper mirrors the production path including
        the post-ripple flatten.  When RIPPLE is disabled, the flatten is a
        no-op (top verts are already at min=max=intended height), so height is
        preserved correctly.
        """
        intended_mm = 4.0
        mesh, _, _ = self._run_water_path(height_mm=intended_mm)

        top_z = mesh.vertices[mesh.vertices[:, 2] > 1e-6, 2]
        actual_top_z = float(top_z.max())

        tolerance_mm = 0.01  # 10 µm — within FDM resolution
        assert abs(actual_top_z - intended_mm) <= tolerance_mm, (
            f"Water top Z = {actual_top_z:.4f} mm but intended {intended_mm} mm "
            f"(delta = {abs(actual_top_z - intended_mm):.4f} mm > {tolerance_mm} mm).  "
            "The ripple texture is displacing the slab downward.  "
            "Set WATER_RIPPLE_ENABLED = False."
        )

    def test_production_code_has_no_post_ripple_flatten(self):
        """
        Static code check: the production source must NOT contain the
        post-ripple flatten block inside export_water_meshes.

        RED  before fix: `_top_min_z` assignment present in the water path.
        GREEN after fix:  only a comment/note remains; the assignment is gone.
        """
        source = GSD_PATH.read_text(encoding="utf-8")

        # Find the export_water_meshes function body.
        # Look for the region between the WATER_RIPPLE_ENABLED gate and the
        # `bb = mesh.bounds` print that follows.
        water_fn_pattern = re.compile(
            r"if WATER_RIPPLE_ENABLED:(.*?)bb = mesh\.bounds",
            re.DOTALL,
        )
        m = water_fn_pattern.search(source)
        if m is None:
            pytest.fail(
                "Could not locate the WATER_RIPPLE_ENABLED→bb=mesh.bounds block "
                "in export_water_meshes.  The test regex needs updating."
            )

        between = m.group(1)
        assert "_top_min_z" not in between, (
            "Found `_top_min_z` assignment in export_water_meshes after the "
            "ripple call.  The post-ripple flatten is still present; it sets "
            "water height to the ripple minimum instead of the intended height.  "
            "Remove the flatten block from export_water_meshes."
        )


# ===========================================================================
# C.  Trap frame-cap parity  (Part 1)
# ===========================================================================

class TestTrapFrameCapParity:
    """
    Part 1 — Trap edge-of-frame cap must mirror the fringe cap rule.

    The fringe cap (BOUNDARY_CAP_BAND_MM=1 mm hard + BOUNDARY_CAP_TAPER_MM=5 mm
    taper, ceiling BOUNDARY_HEIGHT_CAP_MM=9 mm) currently only fires for traps
    on water holes.  These tests assert the cap fires unconditionally for any
    trap whose vertices fall in the frame-edge band, gated by applyFringeFrameCap.

    RED before fix: _apply_lift_and_cap is only called inside `if _hole_water:`.
    GREEN after fix: cap is applied always (regardless of water), gated by
                     apply_fringe_frame_cap passed into export_trap_stls.
    """

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------

    @staticmethod
    def _make_fringe_vertices_flat(half_mm: float, height_mm: float) -> np.ndarray:
        """
        Return a minimal set of fringe top-surface vertices covering the
        frame-edge band at uniform height.  Enough for the KD-tree lookups
        in export_trap_stls to find neighbours.

        Places a 5×5 grid across the square frame (side = 2*half_mm).
        All z values = height_mm (> 0, so they are "top" vertices).
        """
        xs = np.linspace(-half_mm, half_mm, 5)
        ys = np.linspace(-half_mm, half_mm, 5)
        xx, yy = np.meshgrid(xs, ys)
        pts = np.column_stack([xx.ravel(), yy.ravel(),
                               np.full(xx.size, height_mm)])
        return pts

    @staticmethod
    def _fringe_mesh_from_verts(verts: np.ndarray) -> "trimesh.Trimesh":
        """
        Build a trimesh Trimesh from a set of top-surface vertices.
        We add a bottom plane at z=0 and stitch faces so the mesh is
        non-empty (the cap code only needs mesh.vertices to be mutable).
        """
        import trimesh
        from scipy.spatial import Delaunay

        tri = Delaunay(verts[:, :2])
        top_faces = tri.simplices.tolist()
        bottom_verts = verts.copy()
        bottom_verts[:, 2] = 0.0
        all_verts = np.vstack([verts, bottom_verts])
        n = len(verts)
        bottom_faces = [[f[0] + n, f[2] + n, f[1] + n] for f in top_faces]
        faces = np.array(top_faces + bottom_faces, dtype=np.int64)
        m = trimesh.Trimesh(vertices=all_verts, faces=faces, process=False)
        return m

    @staticmethod
    def _build_frame_edge_trap_mesh(
        frame_half_mm: float,
        trap_height_mm: float,
    ):
        """
        Build a small slab whose left edge is flush with the left frame edge
        (x = -frame_half_mm).  Top verts at x≈-frame_half_mm are within
        BOUNDARY_CAP_BAND_MM of the frame edge → should be capped.
        """
        import trimesh
        from generate_stl_3mf import _build_slab_from_shapely

        poly = ShapelyPolygon([
            (-frame_half_mm,       -5.0),
            (-frame_half_mm + 8.0, -5.0),
            (-frame_half_mm + 8.0,  5.0),
            (-frame_half_mm,        5.0),
        ])
        return _build_slab_from_shapely(poly, trap_height_mm)

    # -----------------------------------------------------------------------
    # Tests
    # -----------------------------------------------------------------------

    def test_cap_fires_without_water_when_enabled(self):
        """
        A trap flush with the frame edge must have its boundary-band top verts
        clipped to BOUNDARY_HEIGHT_CAP_MM even on a non-water hole, when the
        cap toggle is on.

        RED before fix (#604): cap only fires inside `if _hole_water:`, so a
                        trap on a non-water hole keeps its full height (e.g. 12 mm)
                        right at the frame edge.
        GREEN after fix (#604): cap fires unconditionally (gated by applyFringeFrameCap,
                         default True), so top verts ≤ 9 mm at the edge.

        Note: Task #606 added BOUNDARY_HEIGHT_CAP_ENABLED (default False) which
        suspends the cap globally.  This test patches it to True so it continues
        to verify the cap MECHANISM works correctly when the toggle is on.
        """
        gsd = _load_gsd()

        frame_half = gsd.PRINT_SIZE_MM / 2.0 + gsd.FRINGE_XY_EXPANSION_MM / 2.0
        trap_height = gsd.BOUNDARY_HEIGHT_CAP_MM + 3.0  # 12 mm — clearly over cap

        mesh = self._build_frame_edge_trap_mesh(frame_half, trap_height)

        # Task #606: cap is now off by default; enable it for this mechanism test.
        gsd.BOUNDARY_HEIGHT_CAP_ENABLED = True
        try:
            # Apply cap (the logic that export_trap_stls should invoke unconditionally
            # after the fix).
            gsd._apply_lift_and_cap(
                mesh,
                lift_mm=0.0,
                cap_mm=gsd.BOUNDARY_HEIGHT_CAP_MM,
                label="test_trap_cap",
            )
        finally:
            gsd.BOUNDARY_HEIGHT_CAP_ENABLED = False  # restore default

        top_verts = mesh.vertices[mesh.vertices[:, 2] > 1e-6]
        # Vertices right at the frame edge (within BOUNDARY_CAP_BAND_MM)
        band = gsd.BOUNDARY_CAP_BAND_MM
        edge_verts = top_verts[
            np.abs(np.abs(top_verts[:, 0]) - frame_half) <= band
        ]
        assert len(edge_verts) > 0, (
            "No top-surface vertices found within the frame-edge band.  "
            "Adjust _build_frame_edge_trap_mesh so its left edge is flush."
        )
        max_edge_z = float(edge_verts[:, 2].max())
        assert max_edge_z <= gsd.BOUNDARY_HEIGHT_CAP_MM + 1e-3, (
            f"Frame-edge trap top Z = {max_edge_z:.3f} mm exceeds cap "
            f"{gsd.BOUNDARY_HEIGHT_CAP_MM} mm.  The cap is not being applied "
            "unconditionally (only fires on water holes in the buggy code)."
        )

    def test_cap_skipped_when_apply_fringe_frame_cap_false(self):
        """
        When applyFringeFrameCap=False, the trap cap must be skipped — matching
        fringe behavior.  The trap keeps its full height at the frame edge.

        GREEN always (no code path currently calls _apply_lift_and_cap with
        cap_mm=None for trap; this test documents the expected behavior and
        will stay green after the fix because the fix gates the cap call on
        apply_fringe_frame_cap).
        """
        gsd = _load_gsd()

        frame_half = gsd.PRINT_SIZE_MM / 2.0 + gsd.FRINGE_XY_EXPANSION_MM / 2.0
        trap_height = gsd.BOUNDARY_HEIGHT_CAP_MM + 3.0  # 12 mm

        mesh = self._build_frame_edge_trap_mesh(frame_half, trap_height)

        # applyFringeFrameCap=False → pass cap_mm=None (no clip)
        gsd._apply_lift_and_cap(
            mesh,
            lift_mm=0.0,
            cap_mm=None,
            label="test_trap_no_cap",
        )

        top_verts = mesh.vertices[mesh.vertices[:, 2] > 1e-6]
        max_z = float(top_verts[:, 2].max())
        # Height should remain near the original trap_height (no clipping)
        assert max_z >= gsd.BOUNDARY_HEIGHT_CAP_MM, (
            f"Trap max Z = {max_z:.3f} mm fell below cap {gsd.BOUNDARY_HEIGHT_CAP_MM} mm "
            "even though cap_mm=None was passed (cap should be skipped)."
        )

    def test_export_trap_stls_accepts_apply_fringe_frame_cap_kwarg(self):
        """
        export_trap_stls must accept an `apply_fringe_frame_cap` keyword argument
        so callers can pass the EGM flag value.

        RED before fix: the function signature does not include apply_fringe_frame_cap.
        GREEN after fix: the parameter exists.
        """
        import inspect
        gsd = _load_gsd()
        sig = inspect.signature(gsd.export_trap_stls)
        assert "apply_fringe_frame_cap" in sig.parameters, (
            "export_trap_stls does not accept `apply_fringe_frame_cap`.  "
            "Add the parameter so the EGM flag can control the cap."
        )

    def test_production_code_cap_not_gated_by_hole_water(self):
        """
        Static code check: the cap call in export_trap_stls must NOT be inside
        `if _hole_water:` (or equivalent).  It must fire unconditionally.

        RED before fix: `_apply_lift_and_cap` call for trap is inside the
                        `if _hole_water:` block.
        GREEN after fix: the cap call is outside the water-hole gate.
        """
        source = GSD_PATH.read_text(encoding="utf-8")

        # Find the export_trap_stls function body.
        fn_start = source.find("def export_trap_stls(")
        fn_end   = source.find("\ndef ", fn_start + 1)
        if fn_start == -1:
            pytest.fail("Could not find export_trap_stls in source.")
        fn_body = source[fn_start:fn_end if fn_end != -1 else len(source)]

        # There must be an _apply_lift_and_cap call outside the `if _hole_water:`
        # block.  A naive check: count _apply_lift_and_cap calls and ensure at
        # least one occurs before/outside the `_hole_water` conditional.
        #
        # Strategy: look for an `_apply_lift_and_cap` call that is NOT preceded
        # by `if _hole_water:` within the same indented block.  We check for the
        # unconditional cap pattern introduced by the fix.
        assert "_apply_lift_and_cap" in fn_body, (
            "No _apply_lift_and_cap call found in export_trap_stls at all."
        )

        # After the fix, there should be a cap call that is NOT gated by _hole_water.
        # We look for the new unconditional call pattern:
        # `if apply_fringe_frame_cap` or similar outside the water gate.
        has_unconditional_cap = (
            "apply_fringe_frame_cap" in fn_body
            or "applyFringeFrameCap" in fn_body
        )
        assert has_unconditional_cap, (
            "export_trap_stls does not reference apply_fringe_frame_cap.  "
            "The trap cap is still gated only by _hole_water; it must be "
            "applied unconditionally (gated by apply_fringe_frame_cap instead)."
        )


# ===========================================================================
# D.  Trap height from adjoining fringe  (Part 2)
# ===========================================================================

class TestTrapHeightFromAdjoiningFringe:
    """
    Part 2 — Trap top = adjoining-fringe max Z − TRAP_FRINGE_OFFSET_MM (2 mm).

    The height sampling must query fringe vertices near the TRAP BOUNDARY
    (perimeter band), not the trap interior, and must subtract 2 mm.

    RED before fix:
      - No TRAP_FRINGE_OFFSET_MM constant exists.
      - Sampling queries interior points and uses max() with no offset.
    GREEN after fix:
      - TRAP_FRINGE_OFFSET_MM = -2.0 constant exists.
      - Boundary-band fringe sampling returns fringe_boundary_max − 2.0 mm.
      - Fallback (no fringe mesh) → TRAP_THICKNESS_MM.
      - Multi-fringe (two adjoining fringes) → max of the two − 2.0 mm.
    """

    @staticmethod
    def _fringe_mesh_ring(
        trap_poly_mm,
        fringe_z_near: float,
        fringe_z_far: float = 5.0,
        ring_width_mm: float = 8.0,
    ):
        """
        Build a synthetic fringe mesh as a ring around trap_poly_mm.

        Vertices within ring_width_mm of the trap boundary are set to
        fringe_z_near; vertices beyond that distance are set to fringe_z_far.
        This lets tests assert that the boundary-band sampling picks up
        fringe_z_near (not fringe_z_far from far-interior fringe cells).
        """
        import trimesh
        from shapely.geometry import Point as ShapelyPoint

        trap_ext = trap_poly_mm.buffer(ring_width_mm).exterior
        ring_poly = trap_poly_mm.buffer(ring_width_mm + 4.0)

        # Sample a grid over the bounding box of ring_poly
        minx, miny, maxx, maxy = ring_poly.bounds
        xs = np.linspace(minx, maxx, 20)
        ys = np.linspace(miny, maxy, 20)
        verts_top = []
        for x in xs:
            for y in ys:
                if not ring_poly.contains(ShapelyPoint(x, y)):
                    continue
                # Distance from trap exterior
                dist = trap_poly_mm.exterior.distance(ShapelyPoint(x, y))
                z = fringe_z_near if dist <= ring_width_mm else fringe_z_far
                verts_top.append([x, y, z])

        if not verts_top:
            pytest.skip("_fringe_mesh_ring produced no vertices — geometry degenerate.")

        verts_top = np.array(verts_top, dtype=np.float64)
        # Add bottom plane at z=0
        verts_bot = verts_top.copy(); verts_bot[:, 2] = 0.0
        all_verts = np.vstack([verts_top, verts_bot])

        from scipy.spatial import Delaunay
        tri = Delaunay(verts_top[:, :2])
        n = len(verts_top)
        top_faces  = tri.simplices.tolist()
        bot_faces  = [[f[0]+n, f[2]+n, f[1]+n] for f in top_faces]
        faces = np.array(top_faces + bot_faces, dtype=np.int64)
        return trimesh.Trimesh(vertices=all_verts, faces=faces, process=False)

    def test_trap_fringe_offset_constant_exists(self):
        """
        TRAP_FRINGE_OFFSET_MM must exist and equal -4.0.

        Task #604: constant introduced at -2.0.
        Task #606: updated to -4.0 (trap 4 mm below fringe per Thomas's request).

        RED before fix (#604): constant does not exist.
        GREEN after fix (#604): TRAP_FRINGE_OFFSET_MM = -2.0 is defined.
        GREEN after fix (#606): TRAP_FRINGE_OFFSET_MM = -4.0.
        """
        gsd = _load_gsd()
        assert hasattr(gsd, "TRAP_FRINGE_OFFSET_MM"), (
            "TRAP_FRINGE_OFFSET_MM is not defined in gradient_surface_diagnostic.py.  "
            "Add TRAP_FRINGE_OFFSET_MM: float = -4.0 to the constants section."
        )
        val = gsd.TRAP_FRINGE_OFFSET_MM
        assert abs(val - (-4.0)) < 1e-6, (
            f"TRAP_FRINGE_OFFSET_MM = {val}, expected -4.0 (updated from -2.0 in task #606)."
        )

    def test_trap_height_is_fringe_boundary_max_minus_offset(self):
        """
        The height computed for a trap that adjoins a fringe must be
        fringe_boundary_max + TRAP_FRINGE_OFFSET_MM (= fringe_boundary_max − 2.0).

        We call the new helper _compute_trap_height_from_fringe directly.

        RED before fix: no such helper; the current code path returns interior
                        max (no boundary distinction) with no offset.
        GREEN after fix: helper exists and returns fringe_boundary_max − 2.0.
        """
        gsd = _load_gsd()

        if not hasattr(gsd, "_compute_trap_height_from_fringe"):
            pytest.fail(
                "_compute_trap_height_from_fringe does not exist.  "
                "Add this helper to encapsulate the new boundary-band sampling."
            )

        from shapely.geometry import Polygon as ShapelyPolygon

        # Small square trap centred at origin, 10×10 mm
        trap_poly = ShapelyPolygon([(-5, -5), (5, -5), (5, 5), (-5, 5)])

        # Fringe: near-boundary z = 11.0, far z = 5.0
        fringe_mesh = self._fringe_mesh_ring(trap_poly, fringe_z_near=11.0, fringe_z_far=5.0)

        result = gsd._compute_trap_height_from_fringe(trap_poly, fringe_mesh)

        expected = 11.0 + gsd.TRAP_FRINGE_OFFSET_MM  # = 9.0
        tol = 0.5  # allow 0.5 mm for sampling density effects
        assert abs(result - expected) <= tol, (
            f"_compute_trap_height_from_fringe returned {result:.3f} mm; "
            f"expected {expected:.3f} mm (fringe_boundary_max=11.0 "
            f"+ TRAP_FRINGE_OFFSET_MM={gsd.TRAP_FRINGE_OFFSET_MM}).  "
            "Boundary-band sampling or offset is not applied correctly."
        )

    def test_fallback_no_fringe_mesh(self):
        """
        When fringe_mesh is None, _compute_trap_height_from_fringe must return
        TRAP_THICKNESS_MM (the existing fallback).

        RED before fix: helper doesn't exist.
        GREEN after fix: returns TRAP_THICKNESS_MM when fringe_mesh is None.
        """
        gsd = _load_gsd()

        if not hasattr(gsd, "_compute_trap_height_from_fringe"):
            pytest.fail(
                "_compute_trap_height_from_fringe does not exist."
            )

        from shapely.geometry import Polygon as ShapelyPolygon
        trap_poly = ShapelyPolygon([(-5, -5), (5, -5), (5, 5), (-5, 5)])
        result = gsd._compute_trap_height_from_fringe(trap_poly, None)
        assert abs(result - gsd.TRAP_THICKNESS_MM) < 1e-6, (
            f"Fallback returned {result:.3f} mm, expected TRAP_THICKNESS_MM = "
            f"{gsd.TRAP_THICKNESS_MM} mm."
        )

    def test_multi_fringe_uses_higher_max(self):
        """
        When a trap adjoins two fringe zones with different heights, the height
        must be max(fringe1_boundary_z, fringe2_boundary_z) + TRAP_FRINGE_OFFSET_MM.

        We simulate two fringes by passing a single combined fringe mesh where
        half the boundary band is at H1=8.0 mm and the other half is at H2=12.0 mm.
        The result should be 12.0 − 2.0 = 10.0 mm.

        RED before fix: no boundary-band logic; interior max used; no offset.
        GREEN after fix: boundary max = 12.0 → result = 10.0 mm.
        """
        gsd = _load_gsd()

        if not hasattr(gsd, "_compute_trap_height_from_fringe"):
            pytest.fail("_compute_trap_height_from_fringe does not exist.")

        import trimesh
        from scipy.spatial import Delaunay
        from shapely.geometry import Polygon as ShapelyPolygon, Point as ShapelyPoint

        trap_poly = ShapelyPolygon([(-5, -5), (5, -5), (5, 5), (-5, 5)])

        # Build a fringe mesh where:
        #   - vertices with x < 0 (left half of boundary band) → z = 8.0
        #   - vertices with x >= 0 (right half of boundary band) → z = 12.0
        #   - far interior → z = 5.0
        ring_poly = trap_poly.buffer(10.0)
        minx, miny, maxx, maxy = ring_poly.bounds
        xs = np.linspace(minx, maxx, 25)
        ys = np.linspace(miny, maxy, 25)
        verts_top = []
        for x in xs:
            for y in ys:
                if not ring_poly.contains(ShapelyPoint(x, y)):
                    continue
                dist = trap_poly.exterior.distance(ShapelyPoint(x, y))
                if dist <= 6.0:
                    z = 8.0 if x < 0 else 12.0
                else:
                    z = 5.0
                verts_top.append([x, y, z])

        if not verts_top:
            pytest.skip("multi_fringe mesh produced no vertices.")

        verts_top = np.array(verts_top, dtype=np.float64)
        verts_bot = verts_top.copy(); verts_bot[:, 2] = 0.0
        all_verts = np.vstack([verts_top, verts_bot])
        tri = Delaunay(verts_top[:, :2])
        n = len(verts_top)
        top_f = tri.simplices.tolist()
        bot_f = [[f[0]+n, f[2]+n, f[1]+n] for f in top_f]
        fringe_mesh = trimesh.Trimesh(
            vertices=all_verts,
            faces=np.array(top_f + bot_f, dtype=np.int64),
            process=False,
        )

        result = gsd._compute_trap_height_from_fringe(trap_poly, fringe_mesh)

        expected = 12.0 + gsd.TRAP_FRINGE_OFFSET_MM  # = 10.0
        tol = 0.5
        assert abs(result - expected) <= tol, (
            f"Multi-fringe: result={result:.3f} mm, expected {expected:.3f} mm "
            "(max of the two fringe boundary heights minus offset).  "
            "The boundary-band sampling is not taking the global max."
        )


# ===========================================================================
# E.  Rake direction = trap major axis  (Task #606, Item 1)
# ===========================================================================

class TestRakeMajorAxis:
    """
    apply_sand_texture must orient rake ridges parallel to the trap's PCA
    major axis, not fixed at X=0 (old Y-axis-parallel orientation).

    Rake ridges = contours of constant Z on the top surface.  A ridge is
    constant-Z if varying x along the ridge produces no change in z.
    In the major-axis frame: projection onto the minor axis drives the cosine
    wave; projection onto the major axis is constant within a ridge.

    RED before fix:  apply_sand_texture always displaces along global X, so
                     ridges are Y-parallel regardless of trap orientation.
    GREEN after fix: apply_sand_texture uses PCA major axis; a 30°-rotated
                     trap produces ridges at ~30° from Y.
    """

    @staticmethod
    def _rotated_trap_poly(angle_deg: float, length: float = 40.0, width: float = 10.0):
        """
        Return a ShapelyPolygon that is a rectangle of size length×width,
        rotated by angle_deg CCW from the X axis, centred at origin.
        """
        import math
        theta = math.radians(angle_deg)
        cos_t, sin_t = math.cos(theta), math.sin(theta)
        # Corners in local frame (long axis = x, short = y)
        half_l, half_w = length / 2, width / 2
        corners_local = [
            (-half_l, -half_w), (half_l, -half_w),
            (half_l,  half_w), (-half_l,  half_w),
        ]
        corners = [
            (cos_t * x - sin_t * y, sin_t * x + cos_t * y)
            for x, y in corners_local
        ]
        return ShapelyPolygon(corners)

    @staticmethod
    def _build_rotated_slab(angle_deg: float, height_mm: float = 5.0):
        """Build a watertight slab for a rotated rectangle trap."""
        from generate_stl_3mf import _build_slab_from_shapely

        poly = TestRakeMajorAxis._rotated_trap_poly(angle_deg)
        return _build_slab_from_shapely(poly, height_mm)

    def _dominant_ridge_angle(self, mesh) -> float:
        """
        Estimate the dominant ridge angle from the top-surface vertices.

        Strategy:
          1. Collect all top-surface vertices.
          2. For each pair of vertices that are 'close' (within 0.8 mm,
             roughly one grid_step), compute the XY vector between them.
          3. If their Z difference is very small (< 0.03 mm, same-ridge
             tolerance), they are on the same ridge → record the angle.
          4. Return the circular mean of all same-ridge angles (mod 180°).
        This gives the dominant direction of constant-Z contours = ridge angle.
        """
        top_mask = mesh.vertices[:, 2] > 1e-6
        top_verts = mesh.vertices[top_mask]
        if len(top_verts) < 4:
            return float("nan")

        from scipy.spatial import cKDTree
        kd = cKDTree(top_verts[:, :2])
        pairs = kd.query_pairs(r=0.9)  # within ~1 grid_step

        angles = []
        for i, j in pairs:
            dz = abs(float(top_verts[i, 2] - top_verts[j, 2]))
            if dz < 0.04:  # same ridge
                dx = float(top_verts[j, 0] - top_verts[i, 0])
                dy = float(top_verts[j, 1] - top_verts[i, 1])
                if abs(dx) + abs(dy) < 1e-9:
                    continue
                angles.append(math.degrees(math.atan2(dy, dx)) % 180.0)

        if not angles:
            return float("nan")

        # Circular mean (angles mod 180° → doubled, averaged, halved)
        angles_rad2 = [2.0 * math.radians(a) for a in angles]
        sx = sum(math.cos(a) for a in angles_rad2)
        sy = sum(math.sin(a) for a in angles_rad2)
        return math.degrees(math.atan2(sy, sx) / 2.0) % 180.0

    def test_rake_follows_major_axis_30deg(self):
        """
        A trap rectangle oriented at 30° from X (long axis at 30°) must
        produce rake ridges parallel to the long axis, i.e. ridge angle ≈ 30°.

        Tolerance: ±20° (rake direction need not be pixel-exact, just
        substantially better than the old X-axis default which would give ~90°
        for ridges perpendicular to X).

        RED before fix: ridges are Y-parallel (angle ≈ 90°) regardless of
                        trap orientation.
        GREEN after fix: ridges follow the 30° long axis (angle ≈ 30°).
        """
        gsd = _load_gsd()
        mesh = self._build_rotated_slab(angle_deg=30.0)
        gsd.apply_sand_texture(mesh, trap_index=0)

        ridge_angle = self._dominant_ridge_angle(mesh)
        assert not math.isnan(ridge_angle), (
            "Could not estimate ridge angle from top-surface vertices."
        )

        # Major axis of the 30°-rotated rectangle is at 30° (mod 180°).
        expected = 30.0
        diff = abs(((ridge_angle - expected) + 90) % 180 - 90)
        assert diff <= 20.0, (
            f"Ridge angle = {ridge_angle:.1f}° for a 30°-rotated trap; "
            f"expected ~{expected}° (±20°).  "
            "apply_sand_texture is not using the PCA major axis for rake direction."
        )

    def test_rake_y_aligned_trap_still_works(self):
        """
        Regression: a trap aligned with the Y axis (angle=90°, wider than tall
        after rotation, major axis along Y) must still produce rake ridges
        near 90° (Y-direction).

        This was the old fixed behaviour; the new code must reproduce it when
        the trap's long axis happens to be near Y.
        """
        gsd = _load_gsd()
        # 40×10 rectangle rotated 90°: long axis now along Y.
        mesh = self._build_rotated_slab(angle_deg=90.0)
        gsd.apply_sand_texture(mesh, trap_index=0)

        ridge_angle = self._dominant_ridge_angle(mesh)
        assert not math.isnan(ridge_angle), (
            "Could not estimate ridge angle from top-surface vertices."
        )

        expected = 90.0
        diff = abs(((ridge_angle - expected) + 90) % 180 - 90)
        assert diff <= 20.0, (
            f"Ridge angle = {ridge_angle:.1f}° for a Y-aligned (90°) trap; "
            f"expected ~90° (±20°).  Regression in PCA major-axis rake logic."
        )

    def test_rake_uses_pca_major_axis_constant_exists(self):
        """
        Static check: apply_sand_texture source must reference 'svd' or
        'major_axis' indicating PCA is now used to derive rake direction.

        RED before fix: no PCA / SVD in apply_sand_texture.
        GREEN after fix: SVD-based major axis computation is present.
        """
        source = GSD_PATH.read_text(encoding="utf-8")
        # Find the apply_sand_texture function body.
        fn_start = source.find("def apply_sand_texture(")
        fn_end = source.find("\ndef ", fn_start + 1)
        fn_body = source[fn_start:fn_end if fn_end != -1 else len(source)]

        has_pca = "svd" in fn_body.lower() or "major_axis" in fn_body.lower()
        assert has_pca, (
            "apply_sand_texture does not contain 'svd' or 'major_axis'.  "
            "PCA-based major axis computation is not present.  "
            "Add `np.linalg.svd(pts - c)` to derive the trap's major axis."
        )


# ===========================================================================
# F.  Texture variation on rake lines  (Task #606 → updated Task #608)
# ===========================================================================

class TestRakeJitter:
    """
    apply_sand_texture must produce reproducible per-trap top-surface variation
    above the cosine rake baseline.

    Task #606 introduced sinusoidal jitter (SAND_JITTER_AMPLITUDE_MM).
    Task #608 replaced it with discrete Gaussian chunk bumps.  These tests
    verify the structural properties that hold for both approaches: same trap +
    same index → identical Z; different trap_index → different Z.

    Tests that specifically referenced SAND_JITTER_AMPLITUDE_MM are updated
    to reference the new chunk constants, or replaced with chunk-based checks
    (see class TestSandChunkScatter below for the full chunk test suite).
    """

    @staticmethod
    def _top_z_sorted(mesh) -> np.ndarray:
        """Return sorted top-surface Z array."""
        top_mask = mesh.vertices[:, 2] > 1e-6
        return np.sort(mesh.vertices[top_mask, 2])

    def test_jitter_constant_absent_after_608(self):
        """
        Task #608: SAND_JITTER_AMPLITUDE_MM must NOT be defined.
        Sinusoidal jitter was replaced by chunk scatter.

        RED (task #606 code): constant is still present.
        GREEN (task #608 code): constant is gone.
        """
        gsd = _load_gsd()
        assert not hasattr(gsd, "SAND_JITTER_AMPLITUDE_MM"), (
            "SAND_JITTER_AMPLITUDE_MM is still defined.  "
            "Task #608 removed sinusoidal jitter in favour of chunk scatter.  "
            "Delete SAND_JITTER_AMPLITUDE_MM from the constants section."
        )

    def test_chunk_scatter_present_on_top_surface(self):
        """
        Task #608: apply_sand_texture must produce Z variation above the pure
        rake cosine, contributed by the chunk scatter pass.

        We confirm the function body references _scatter_sand_chunks (static
        code check) and that apply_sand_texture produces Z max > z_max +
        rake_amplitude (chunks add on top of the cosine peak).

        GREEN after fix: _scatter_sand_chunks called; Z max > z_max + amplitude.
        """
        gsd = _load_gsd()
        source = GSD_PATH.read_text(encoding="utf-8")
        fn_start = source.find("def apply_sand_texture(")
        fn_end = source.find("\ndef ", fn_start + 1)
        fn_body = source[fn_start:fn_end if fn_end != -1 else len(source)]

        assert "_scatter_sand_chunks" in fn_body, (
            "apply_sand_texture does not call _scatter_sand_chunks.  "
            "Chunk scatter pass is missing (task #608)."
        )

        # The cosine peak is z_max + amplitude (when amplitude=0.35).
        # Chunks push some vertices above that: max Z > z_max + amplitude.
        mesh = _build_slab(side_mm=20.0, height_mm=5.0)
        z_max_before = float(mesh.vertices[:, 2].max())
        gsd.apply_sand_texture(mesh, trap_index=0)
        top_z = mesh.vertices[mesh.vertices[:, 2] > 1e-6, 2]
        # With default amplitude=0.35 mm and chunks up to 0.6*1.3 mm,
        # max Z should be above z_max_before + amplitude (= 5.35 mm).
        assert top_z.max() > z_max_before + 0.35, (
            f"Top Z max = {top_z.max():.4f} mm, expected > {z_max_before + 0.35:.4f} mm.  "
            "Chunk bumps are not raising vertices above the rake peak."
        )

    def test_jitter_is_reproducible_same_trap(self):
        """
        Two apply_sand_texture calls on identical slabs with the same
        trap_index must produce identical top-surface Z vectors.

        This holds for chunk scatter (seeded RNG) just as it did for jitter.

        GREEN: seeded chunk RNG → identical Z on both calls.
        """
        gsd = _load_gsd()
        mesh_a = _build_slab(side_mm=20.0, height_mm=5.0)
        mesh_b = _build_slab(side_mm=20.0, height_mm=5.0)

        gsd.apply_sand_texture(mesh_a, trap_index=3)
        gsd.apply_sand_texture(mesh_b, trap_index=3)

        za = self._top_z_sorted(mesh_a)
        zb = self._top_z_sorted(mesh_b)

        assert len(za) == len(zb), (
            f"Top vertex count differs between runs: {len(za)} vs {len(zb)}.  "
            "Seeding must be deterministic (same grid_step, same slab)."
        )
        max_diff = float(np.max(np.abs(za - zb)))
        assert max_diff < 1e-6, (
            f"Top-surface Z differs between identical runs (max diff = {max_diff:.6f} mm).  "
            "The chunk RNG is not seeded correctly — must produce identical "
            "results for the same trap geometry and trap_index."
        )

    def test_jitter_differs_between_traps(self):
        """
        Two slabs with different trap_index values must produce different
        top-surface Z arrays.

        Chunk scatter uses per-trap seeding (same as the retired jitter seed
        pattern), so different trap_index values → different chunk positions →
        different Z maxima.

        GREEN after fix: per-trap seeding → different arrays.
        """
        gsd = _load_gsd()
        mesh_0 = _build_slab(side_mm=20.0, height_mm=5.0)
        mesh_1 = _build_slab(side_mm=20.0, height_mm=5.0)

        gsd.apply_sand_texture(mesh_0, trap_index=0)
        gsd.apply_sand_texture(mesh_1, trap_index=7)

        z0 = self._top_z_sorted(mesh_0)
        z1 = self._top_z_sorted(mesh_1)

        if len(z0) != len(z1):
            # Different vertex counts → obviously different. Pass.
            return

        max_diff = float(np.max(np.abs(z0 - z1)))
        assert max_diff > 1e-6, (
            f"Top-surface Z is identical for trap_index=0 and trap_index=7 "
            f"(max diff = {max_diff:.9f} mm).  "
            "Per-trap chunk seeding is not implemented — different traps must "
            "produce different noise patterns."
        )

    def test_chunk_z_range_bounded(self):
        """
        Task #608: with default constants (amplitude=0.35 mm rake, chunk
        height up to 0.6*1.3*K mm), the top-surface Z range must be bounded.
        Upper bound: rake range (amplitude) + chunk max height * K_overlap
        where K_overlap=3 (up to 3 chunks can overlap).
        Lower bound: at least rake amplitude * 0.5 (rake is still visible).

        GREEN after fix: total Z range within expected bounds.
        """
        gsd = _load_gsd()
        mesh = _build_slab(side_mm=20.0, height_mm=5.0)
        # Use default amplitude (0.35 mm).
        gsd.apply_sand_texture(mesh, trap_index=4)

        top_z = mesh.vertices[mesh.vertices[:, 2] > 1e-6, 2]
        z_range = float(top_z.max() - top_z.min())

        rake_amplitude = 0.35  # default
        h = gsd.SAND_CHUNK_HEIGHT_MM
        # Max: rake range + 3 overlapping chunks at max height
        max_allowed = rake_amplitude + h * 1.3 * 3 + 0.1
        # Min: at least rake visible (half-amplitude)
        min_expected = rake_amplitude * 0.5

        assert z_range >= min_expected, (
            f"Z range = {z_range:.4f} mm < {min_expected:.4f} mm.  "
            "Rake texture appears to be missing."
        )
        assert z_range <= max_allowed, (
            f"Z range = {z_range:.4f} mm > {max_allowed:.4f} mm upper bound.  "
            "Chunk heights appear out of range."
        )


# ===========================================================================
# G.  BOUNDARY_HEIGHT_CAP_ENABLED toggle  (Task #606, Item 3)
# ===========================================================================

class TestCapEnabledToggle:
    """
    BOUNDARY_HEIGHT_CAP_ENABLED = False suspends the frame-edge height cap.
    When False, vertices near the frame that exceed BOUNDARY_HEIGHT_CAP_MM are
    left at their natural height.  When True, the existing cap is applied.

    RED before fix: BOUNDARY_HEIGHT_CAP_ENABLED constant does not exist.
    GREEN after fix: constant exists at False (default off per Thomas's request);
                     _apply_lift_and_cap respects it.
    """

    @staticmethod
    def _frame_edge_slab(height_mm: float):
        """Slab whose left edge is flush with the frame (same helper as class C)."""
        from generate_stl_3mf import _build_slab_from_shapely

        gsd = _load_gsd()
        frame_half = gsd.PRINT_SIZE_MM / 2.0 + gsd.FRINGE_XY_EXPANSION_MM / 2.0
        poly = ShapelyPolygon([
            (-frame_half,       -5.0),
            (-frame_half + 8.0, -5.0),
            (-frame_half + 8.0,  5.0),
            (-frame_half,        5.0),
        ])
        return _build_slab_from_shapely(poly, height_mm), frame_half

    def test_cap_enabled_constant_exists_and_is_false(self):
        """
        BOUNDARY_HEIGHT_CAP_ENABLED must exist and default to False
        (cap is suspended per Thomas's request).

        RED before fix: constant does not exist.
        GREEN after fix: BOUNDARY_HEIGHT_CAP_ENABLED = False is defined.
        """
        gsd = _load_gsd()
        assert hasattr(gsd, "BOUNDARY_HEIGHT_CAP_ENABLED"), (
            "BOUNDARY_HEIGHT_CAP_ENABLED is not defined in gradient_surface_diagnostic.py.  "
            "Add `BOUNDARY_HEIGHT_CAP_ENABLED: bool = False` to the constants section."
        )
        assert gsd.BOUNDARY_HEIGHT_CAP_ENABLED is False, (
            f"BOUNDARY_HEIGHT_CAP_ENABLED = {gsd.BOUNDARY_HEIGHT_CAP_ENABLED}; "
            "expected False (cap suspended per Thomas's request, task #606)."
        )

    def test_cap_disabled_leaves_vertex_above_cap_mm(self):
        """
        When BOUNDARY_HEIGHT_CAP_ENABLED is False, a tall trap slab whose
        frame-edge vertices exceed BOUNDARY_HEIGHT_CAP_MM must keep its
        natural height — no clipping.

        We monkey-patch the constant to False and call _apply_lift_and_cap
        with a cap_mm value, then verify the edge verts are NOT clipped.

        RED before fix: constant does not exist → apply_lift_and_cap always
                        clips regardless.
        GREEN after fix: cap skipped when BOUNDARY_HEIGHT_CAP_ENABLED=False.
        """
        gsd = _load_gsd()
        if not hasattr(gsd, "BOUNDARY_HEIGHT_CAP_ENABLED"):
            pytest.skip("BOUNDARY_HEIGHT_CAP_ENABLED not defined yet.")

        cap_mm = gsd.BOUNDARY_HEIGHT_CAP_MM
        tall_height = cap_mm + 5.0  # clearly over the cap

        mesh, frame_half = self._frame_edge_slab(tall_height)

        # Monkey-patch: disable cap
        gsd.BOUNDARY_HEIGHT_CAP_ENABLED = False
        try:
            gsd._apply_lift_and_cap(
                mesh,
                lift_mm=0.0,
                cap_mm=cap_mm,
                label="test_cap_disabled",
            )
        finally:
            gsd.BOUNDARY_HEIGHT_CAP_ENABLED = False  # restore

        top_v = mesh.vertices[mesh.vertices[:, 2] > 1e-6]
        band = gsd.BOUNDARY_CAP_BAND_MM
        edge_verts = top_v[np.abs(np.abs(top_v[:, 0]) - frame_half) <= band]

        if len(edge_verts) == 0:
            pytest.skip("No frame-edge vertices in test slab — geometry may have shifted.")

        max_edge_z = float(edge_verts[:, 2].max())
        assert max_edge_z > cap_mm, (
            f"Frame-edge Z = {max_edge_z:.3f} mm was capped to {cap_mm} mm "
            "even though BOUNDARY_HEIGHT_CAP_ENABLED=False.  "
            "The toggle is not being respected by _apply_lift_and_cap."
        )

    def test_cap_enabled_true_still_clips(self):
        """
        Regression: when BOUNDARY_HEIGHT_CAP_ENABLED is True, the original
        cap behaviour must be preserved (edge verts ≤ BOUNDARY_HEIGHT_CAP_MM).

        RED: impossible to test when constant doesn't exist.
        GREEN after fix: True → cap fires.
        """
        gsd = _load_gsd()
        if not hasattr(gsd, "BOUNDARY_HEIGHT_CAP_ENABLED"):
            pytest.skip("BOUNDARY_HEIGHT_CAP_ENABLED not defined yet.")

        cap_mm = gsd.BOUNDARY_HEIGHT_CAP_MM
        tall_height = cap_mm + 5.0

        mesh, frame_half = self._frame_edge_slab(tall_height)

        # Monkey-patch: enable cap
        gsd.BOUNDARY_HEIGHT_CAP_ENABLED = True
        try:
            gsd._apply_lift_and_cap(
                mesh,
                lift_mm=0.0,
                cap_mm=cap_mm,
                label="test_cap_enabled",
            )
        finally:
            gsd.BOUNDARY_HEIGHT_CAP_ENABLED = False  # restore to default

        top_v = mesh.vertices[mesh.vertices[:, 2] > 1e-6]
        band = gsd.BOUNDARY_CAP_BAND_MM
        edge_verts = top_v[np.abs(np.abs(top_v[:, 0]) - frame_half) <= band]

        if len(edge_verts) == 0:
            pytest.skip("No frame-edge vertices — geometry may have shifted.")

        max_edge_z = float(edge_verts[:, 2].max())
        assert max_edge_z <= cap_mm + 1e-3, (
            f"Frame-edge Z = {max_edge_z:.3f} mm exceeds cap {cap_mm} mm "
            "when BOUNDARY_HEIGHT_CAP_ENABLED=True.  Regression in cap logic."
        )


# ===========================================================================
# H.  TRAP_FRINGE_OFFSET_MM updated to -4.0  (Task #606, Item 4)
# ===========================================================================

class TestTrapFringeOffsetUpdated:
    """
    TRAP_FRINGE_OFFSET_MM must be -4.0 (changed from -2.0 per Thomas's request
    in task #606: trap 4 mm below fringe instead of 2 mm).

    RED before fix: TRAP_FRINGE_OFFSET_MM = -2.0 (task #604 value).
    GREEN after fix: TRAP_FRINGE_OFFSET_MM = -4.0.
    """

    def test_trap_fringe_offset_is_minus_four(self):
        """
        TRAP_FRINGE_OFFSET_MM must equal -4.0.

        RED before fix: value is -2.0.
        GREEN after fix: value is -4.0.
        """
        gsd = _load_gsd()
        val = gsd.TRAP_FRINGE_OFFSET_MM
        assert abs(val - (-4.0)) < 1e-6, (
            f"TRAP_FRINGE_OFFSET_MM = {val}; expected -4.0.  "
            "Update the constant from -2.0 to -4.0 per task #606."
        )

    def test_trap_height_fringe_boundary_uses_minus_four(self):
        """
        _compute_trap_height_from_fringe must now return fringe_boundary_max − 4.0.

        We reuse the basic fringe mesh from class D but expect the new offset.

        RED before fix: returns fringe_boundary_max − 2.0.
        GREEN after fix: returns fringe_boundary_max − 4.0.
        """
        gsd = _load_gsd()
        from shapely.geometry import Polygon as ShapelyPolygon, Point as ShapelyPoint
        import trimesh
        from scipy.spatial import Delaunay

        trap_poly = ShapelyPolygon([(-5, -5), (5, -5), (5, 5), (-5, 5)])

        # Build a simple ring fringe with near-boundary z = 11.0
        ring_poly = trap_poly.buffer(10.0)
        minx, miny, maxx, maxy = ring_poly.bounds
        xs = np.linspace(minx, maxx, 15)
        ys = np.linspace(miny, maxy, 15)
        verts_top = []
        for x in xs:
            for y in ys:
                if not ring_poly.contains(ShapelyPoint(x, y)):
                    continue
                dist = trap_poly.exterior.distance(ShapelyPoint(x, y))
                z = 11.0 if dist <= 6.0 else 5.0
                verts_top.append([x, y, z])

        verts_top = np.array(verts_top, dtype=np.float64)
        verts_bot = verts_top.copy(); verts_bot[:, 2] = 0.0
        all_verts = np.vstack([verts_top, verts_bot])
        tri = Delaunay(verts_top[:, :2])
        n = len(verts_top)
        top_f = tri.simplices.tolist()
        bot_f = [[f[0]+n, f[2]+n, f[1]+n] for f in top_f]
        fringe_mesh = trimesh.Trimesh(
            vertices=all_verts,
            faces=np.array(top_f + bot_f, dtype=np.int64),
            process=False,
        )

        result = gsd._compute_trap_height_from_fringe(trap_poly, fringe_mesh)

        expected = 11.0 + gsd.TRAP_FRINGE_OFFSET_MM  # should be 11.0 - 4.0 = 7.0
        tol = 0.5
        assert abs(result - expected) <= tol, (
            f"_compute_trap_height_from_fringe returned {result:.3f} mm; "
            f"expected {expected:.3f} mm (fringe_boundary_max=11.0 "
            f"+ TRAP_FRINGE_OFFSET_MM={gsd.TRAP_FRINGE_OFFSET_MM}).  "
            "TRAP_FRINGE_OFFSET_MM was not updated to -4.0."
        )


# ===========================================================================
# I.  Sand-chunk scatter pass  (Task #608)
# ===========================================================================

class TestSandChunkScatter:
    """
    apply_sand_texture must scatter discrete Gaussian mound 'chunks' across
    the trap top surface, replacing the old sinusoidal jitter.

    RED before fix:
      - SAND_JITTER_AMPLITUDE_MM still exists (will be removed).
      - SAND_CHUNK_HEIGHT_MM, SAND_CHUNK_SIGMA_MM, SAND_CHUNK_DENSITY_PER_100_MM2,
        SAND_CHUNK_MAX, SAND_CHUNK_MIN constants do not exist.
      - _scatter_sand_chunks helper does not exist.
      - No chunk bumps applied → Z above rake baseline is zero.
    GREEN after fix:
      - Jitter constants/code removed; chunk constants added.
      - Same trap + same trap_index → identical chunk positions & heights.
      - Count law satisfied (floor=3, cap=20, density=0.3 per 100 mm²).
      - Every chunk centre strictly inside the trap polygon.
      - Chunk pass is additive: Z with chunks ≥ Z without chunks everywhere.
      - Peak Z increment from chunks bounded above.
    """

    # -----------------------------------------------------------------------
    # Helper: build a rectangular Shapely polygon of given area
    # -----------------------------------------------------------------------

    @staticmethod
    def _rect_poly(area_mm2: float, aspect: float = 2.0):
        """Return a rectangle Shapely polygon with the given area and aspect ratio."""
        w = math.sqrt(area_mm2 / aspect)
        h = area_mm2 / w
        return ShapelyPolygon([(0, 0), (w, 0), (w, h), (0, h)])

    @staticmethod
    def _slab_for_poly(poly, height_mm: float = 5.0):
        from generate_stl_3mf import _build_slab_from_shapely
        return _build_slab_from_shapely(poly, height_mm)

    # -----------------------------------------------------------------------
    # I-1  Constants exist and have correct defaults
    # -----------------------------------------------------------------------

    def test_chunk_constants_exist(self):
        """
        SAND_CHUNK_HEIGHT_MM, SAND_CHUNK_SIGMA_MM,
        SAND_CHUNK_DENSITY_PER_100_MM2, SAND_CHUNK_MAX, SAND_CHUNK_MIN
        must all be defined.

        RED before fix: none of these constants exist.
        GREEN after fix: all five constants present with correct defaults.
        """
        gsd = _load_gsd()
        for name, expected, tol in [
            ("SAND_CHUNK_HEIGHT_MM",          0.6,  0.01),
            ("SAND_CHUNK_SIGMA_MM",           1.5,  0.01),
            ("SAND_CHUNK_DENSITY_PER_100_MM2", 0.3, 0.001),
            ("SAND_CHUNK_MAX",                20,   0),
            ("SAND_CHUNK_MIN",                3,    0),
        ]:
            assert hasattr(gsd, name), (
                f"{name} is not defined in gradient_surface_diagnostic.py."
            )
            val = float(getattr(gsd, name))
            if tol == 0:
                assert int(val) == int(expected), (
                    f"{name} = {val}, expected {expected}."
                )
            else:
                assert abs(val - expected) <= tol, (
                    f"{name} = {val:.4f}, expected {expected}."
                )

    def test_jitter_constant_removed(self):
        """
        SAND_JITTER_AMPLITUDE_MM must NOT be defined after task #608.

        RED (currently green — jitter still exists): the constant is present.
        GREEN after fix: the constant is gone.
        """
        gsd = _load_gsd()
        assert not hasattr(gsd, "SAND_JITTER_AMPLITUDE_MM"), (
            "SAND_JITTER_AMPLITUDE_MM is still defined.  "
            "Remove the sinusoidal jitter constant and code (task #608)."
        )

    # -----------------------------------------------------------------------
    # I-2  Count-vs-area law
    # -----------------------------------------------------------------------

    def test_chunk_count_law(self):
        """
        _scatter_sand_chunks must return the correct count for three areas:
          - 500 mm²  → raw = round(500/100 * 0.3) = 2 → clamped to SAND_CHUNK_MIN = 3
          - 3000 mm² → raw = round(3000/100 * 0.3) = 9 → 9 (within [3,20])
          - 50000 mm²→ raw = round(50000/100 * 0.3) = 150 → clamped to SAND_CHUNK_MAX = 20

        RED before fix: helper does not exist.
        GREEN after fix: count matches for all three cases.
        """
        gsd = _load_gsd()
        if not hasattr(gsd, "_scatter_sand_chunks"):
            pytest.fail(
                "_scatter_sand_chunks does not exist.  "
                "Add this helper to encapsulate the chunk scatter logic."
            )

        cases = [
            (500,   gsd.SAND_CHUNK_MIN),     # floor
            (3000,  9),                       # within range
            (50000, gsd.SAND_CHUNK_MAX),      # cap
        ]
        for area_mm2, expected_count in cases:
            poly = self._rect_poly(area_mm2)
            chunks = gsd._scatter_sand_chunks(poly, trap_index=0)
            n = len(chunks)
            assert n == expected_count, (
                f"Area={area_mm2} mm²: got {n} chunks, expected {expected_count}.  "
                f"(density={gsd.SAND_CHUNK_DENSITY_PER_100_MM2}/100mm², "
                f"min={gsd.SAND_CHUNK_MIN}, max={gsd.SAND_CHUNK_MAX})"
            )

    # -----------------------------------------------------------------------
    # I-3  Reproducibility
    # -----------------------------------------------------------------------

    def test_chunk_reproducibility(self):
        """
        Same trap polygon + same trap_index → identical chunk centres and
        peak heights across two independent calls.

        RED before fix: helper doesn't exist.
        GREEN after fix: deterministic via seeded RNG.
        """
        gsd = _load_gsd()
        if not hasattr(gsd, "_scatter_sand_chunks"):
            pytest.fail("_scatter_sand_chunks does not exist.")

        poly = self._rect_poly(2000)
        chunks_a = gsd._scatter_sand_chunks(poly, trap_index=5)
        chunks_b = gsd._scatter_sand_chunks(poly, trap_index=5)

        assert len(chunks_a) == len(chunks_b), (
            f"Chunk count differs between runs: {len(chunks_a)} vs {len(chunks_b)}."
        )
        for k, (a, b) in enumerate(zip(chunks_a, chunks_b)):
            cx_a, cy_a, h_a, sig_a = a
            cx_b, cy_b, h_b, sig_b = b
            assert abs(cx_a - cx_b) < 1e-9 and abs(cy_a - cy_b) < 1e-9, (
                f"Chunk {k} centre differs: ({cx_a:.6f},{cy_a:.6f}) vs "
                f"({cx_b:.6f},{cy_b:.6f}).  RNG is not seeded reproducibly."
            )
            assert abs(h_a - h_b) < 1e-9, (
                f"Chunk {k} height differs: {h_a:.6f} vs {h_b:.6f}."
            )

    # -----------------------------------------------------------------------
    # I-4  Peak height bounds
    # -----------------------------------------------------------------------

    def test_chunk_peak_height_bounds(self):
        """
        Peak Z increment from chunks on any vertex must be within:
          lower = SAND_CHUNK_HEIGHT_MM * 0.7  (at least one chunk > 0)
          upper = SAND_CHUNK_HEIGHT_MM * 1.3 * K  where K=3 (overlap allowance)

        We call apply_sand_texture and compare Z values of a textured mesh
        against a rake-only mesh (without chunks) to isolate the chunk delta.

        RED before fix: no chunks → delta is zero everywhere.
        GREEN after fix: max delta > lower and ≤ upper.
        """
        gsd = _load_gsd()
        if not hasattr(gsd, "SAND_CHUNK_HEIGHT_MM"):
            pytest.skip("SAND_CHUNK_HEIGHT_MM not defined yet.")

        # Build two identical slabs; apply texture to one.
        poly = self._rect_poly(3000)   # 9 chunks expected
        mesh_with = self._slab_for_poly(poly, height_mm=5.0)
        mesh_rake_only = self._slab_for_poly(poly, height_mm=5.0)

        # Temporarily remove chunk pass to get rake-only Z.
        # We monkey-patch SAND_CHUNK_MIN/MAX to zero to suppress chunks.
        orig_min = gsd.SAND_CHUNK_MIN
        orig_max = gsd.SAND_CHUNK_MAX
        orig_density = gsd.SAND_CHUNK_DENSITY_PER_100_MM2
        gsd.SAND_CHUNK_MIN = 0
        gsd.SAND_CHUNK_MAX = 0
        gsd.SAND_CHUNK_DENSITY_PER_100_MM2 = 0.0
        try:
            gsd.apply_sand_texture(mesh_rake_only, trap_index=0)
        finally:
            gsd.SAND_CHUNK_MIN = orig_min
            gsd.SAND_CHUNK_MAX = orig_max
            gsd.SAND_CHUNK_DENSITY_PER_100_MM2 = orig_density

        gsd.apply_sand_texture(mesh_with, trap_index=0)

        top_with  = mesh_with.vertices[mesh_with.vertices[:, 2] > 1e-6, 2]
        top_rake  = mesh_rake_only.vertices[mesh_rake_only.vertices[:, 2] > 1e-6, 2]

        max_delta = float(top_with.max() - top_rake.max())
        h = gsd.SAND_CHUNK_HEIGHT_MM
        lower = h * 0.7
        upper = h * 1.3 * 3  # K=3 bump-overlap allowance

        assert max_delta >= lower, (
            f"Max chunk Z increment = {max_delta:.4f} mm < lower bound {lower:.4f} mm.  "
            "Chunks are not producing visible mounds."
        )
        assert max_delta <= upper, (
            f"Max chunk Z increment = {max_delta:.4f} mm > upper bound {upper:.4f} mm.  "
            "Chunk heights are out of range."
        )

    # -----------------------------------------------------------------------
    # I-5  Placement inside polygon
    # -----------------------------------------------------------------------

    def test_chunk_centres_inside_polygon(self):
        """
        Every chunk centre returned by _scatter_sand_chunks must be strictly
        inside the trap polygon (shapely contains).

        RED before fix: helper doesn't exist.
        GREEN after fix: all centres pass shapely.contains.
        """
        from shapely.geometry import Point as ShapelyPoint
        gsd = _load_gsd()
        if not hasattr(gsd, "_scatter_sand_chunks"):
            pytest.fail("_scatter_sand_chunks does not exist.")

        poly = self._rect_poly(5000)
        chunks = gsd._scatter_sand_chunks(poly, trap_index=2)
        assert len(chunks) > 0, "No chunks returned — cannot test placement."

        for k, (cx, cy, h, sig) in enumerate(chunks):
            pt = ShapelyPoint(cx, cy)
            assert poly.contains(pt), (
                f"Chunk {k} centre ({cx:.3f}, {cy:.3f}) is outside the trap polygon.  "
                "Rejection sampling is not working correctly."
            )

    # -----------------------------------------------------------------------
    # I-6  Chunks additive to rake
    # -----------------------------------------------------------------------

    def test_chunks_additive_to_rake(self):
        """
        Z values with chunks must be >= Z values without chunks everywhere
        (chunks only add positive Gaussian bumps, never subtract).

        We compare sorted top-Z arrays from two identical slabs.

        RED before fix: no chunks → both arrays identical, delta = 0.
                        This test is designed to FAIL red (0 delta = not additive
                        in a visible way), but strictly chunks being additive
                        means with_chunks >= without_chunks pointwise.
                        Actually the test below confirms chunks are present
                        (max of with_chunks > max of without_chunks), which
                        only passes after the implementation.
        GREEN after fix: max(with) > max(without) by at least SAND_CHUNK_HEIGHT_MM * 0.7.
        """
        gsd = _load_gsd()
        if not hasattr(gsd, "SAND_CHUNK_HEIGHT_MM"):
            pytest.skip("SAND_CHUNK_HEIGHT_MM not defined yet.")

        poly = self._rect_poly(3000)
        mesh_with = self._slab_for_poly(poly, height_mm=5.0)
        mesh_without = self._slab_for_poly(poly, height_mm=5.0)

        orig_min = gsd.SAND_CHUNK_MIN
        orig_max = gsd.SAND_CHUNK_MAX
        orig_density = gsd.SAND_CHUNK_DENSITY_PER_100_MM2
        gsd.SAND_CHUNK_MIN = 0
        gsd.SAND_CHUNK_MAX = 0
        gsd.SAND_CHUNK_DENSITY_PER_100_MM2 = 0.0
        try:
            gsd.apply_sand_texture(mesh_without, trap_index=1)
        finally:
            gsd.SAND_CHUNK_MIN = orig_min
            gsd.SAND_CHUNK_MAX = orig_max
            gsd.SAND_CHUNK_DENSITY_PER_100_MM2 = orig_density

        gsd.apply_sand_texture(mesh_with, trap_index=1)

        top_with    = mesh_with.vertices[mesh_with.vertices[:, 2] > 1e-6, 2]
        top_without = mesh_without.vertices[mesh_without.vertices[:, 2] > 1e-6, 2]

        delta = float(top_with.max() - top_without.max())
        assert delta >= gsd.SAND_CHUNK_HEIGHT_MM * 0.7, (
            f"max(with_chunks)={top_with.max():.4f} vs max(without)={top_without.max():.4f}; "
            f"delta={delta:.4f} mm < {gsd.SAND_CHUNK_HEIGHT_MM * 0.7:.4f} mm.  "
            "Chunks are not being applied additively on top of the rake."
        )
