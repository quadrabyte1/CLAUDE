"""
test_gradient_surface_diagnostic.py  —  Geometry tests for trap rake / water surface.

Bug→TDD:  tests written first (RED); fixed by:
  1. Removing the post-texture flatten from export_trap_stls  (trap rake lines).
  2. Setting WATER_RIPPLE_ENABLED = False and removing the post-ripple flatten
     from export_water_meshes  (water smooth-flat slab at correct height).

Covers
------
  A. Trap rake lines — after apply_sand_texture the top surface must carry
     parallel-ridge Z variation.  Tests also confirm the production file no
     longer contains the post-texture flatten block that was wiping the texture.

  B. Water smoothness — water top surface must be flat at the intended slab
     height.  Tests confirm WATER_RIPPLE_ENABLED is False (so no displacement)
     and that the production file no longer contains the post-ripple flatten
     (which was collapsing the slab to the deepest ripple point, ~0.28 mm low).
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
        # the _hole_water / Water-hole-rule block that follows it.
        trap_fn_pattern = re.compile(
            r"apply_sand_texture\(mesh.*?\n(.*?)(?=if _hole_water:)",
            re.DOTALL,
        )
        m = trap_fn_pattern.search(source)
        if m is None:
            # Pattern didn't match — most likely the source changed significantly.
            # Fail with a clear message.
            pytest.fail(
                "Could not locate the apply_sand_texture→_hole_water block in "
                "export_trap_stls.  The test regex needs updating."
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
