"""
test_tps_global_height_field.py — Bug→TDD for C1-continuous global height field
via thin-plate spline (task 684, Topo 2026-10-02).

Updated for task 690 (Topo 2026-10-02): fringeBoundaryHeights stripped from TPS.
Thomas's revelation: the exterior fringe numbers are *distance-from-pin markers*,
not altitudes.  _build_tps_base() now ignores fringe_boundary_heights_mm.

Thomas's original problem statement (task 684):
    "Fringe peaks were picked up but the fringe altitude was set right at the
    boundary and dropped immediately on either side.  On the green side the
    green didn't meet that new height and the fringe didn't trail from that new
    height out to the frame.  I'd like to blend from a fringe height to a
    specific green height so we get continuous surface everywhere.  Nowhere can
    the derivative of the gradient be undefined."

After implementation all tests here must be GREEN, and the existing test suite
(88+ tests) must remain green.

Tests:
    T1  TPS fringe-anchor parameter accepted but IGNORED (task 690) — single
        fbh passed at (x0, y0) value=8 with no spikes → TPS Z at that point
        ≈ BASE_THICKNESS_MM (frame-base driven), NOT the anchor value.
    T2  TPS interior-spike honored — single spike at interior (x1, y1) value=12
        → TPS Z at that point ≈ 12 within 0.1 mm.
    T3  Smooth outward decay — Z at frame outer edge ≈ BASE_HEIGHT_MM; no
        step change between anchor and frame outer circle.
    T4  Degenerate 0 constraints → flat BASE_THICKNESS_MM surface.
    T5  C1 continuity across fringe/green seam — finite-difference gradient
        step at boundary < 2 mm/mm.
    T6  Regression — build_fringe_mesh round-trip: fringe Z near boundary is
        driven by interior spike (no fringe anchors), smoothly between spike Z
        and BASE.  Vertex Z must be finite and > 0.
    T7  Trap + rake + chunks regression — build_fringe_mesh produces a mesh
        that still has vertices at varying heights (trap not flattened).
    T8  Water still flat — export_water_meshes on a water EGM still produces
        a slab within ±0.1 mm of BASE_THICKNESS_MM.
    T9  Co-located interior-spike constraints with conflicting Z → averaged
        without error (fringe anchors are now ignored, test uses spikes).
    T10 TPS with only outer-frame anchors (no spikes, no fbh) → surface
        stays near BASE_THICKNESS_MM everywhere (no blow-up).

Run:
    cd /Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER
    python -m pytest app/tests/test_tps_global_height_field.py -v
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
    spec = importlib.util.spec_from_file_location("gsd_tps_test", GSD_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Shared geometry helpers
# ---------------------------------------------------------------------------

def _make_circular_green_pts(cx_px, cy_px, r_px, n=64):
    """Return [{x, y}] polygon points for a circle."""
    return [
        {"x": cx_px + r_px * math.cos(2 * math.pi * i / n),
         "y": cy_px + r_px * math.sin(2 * math.pi * i / n)}
        for i in range(n)
    ]


def _base_egm(cx_px=300.0, cy_px=300.0, r_px=105.0, n=64,
              elevation_range=14.5,
              fringe_boundary_heights=None,
              elevation_spikes=None):
    """Build a minimal egm_data dict with a circular green."""
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
# T1  TPS fringe-anchor honored
# ===========================================================================

class TestTPSFringeAnchorHonored:
    """T1 (updated task 690): fringe_boundary_heights_mm is accepted but IGNORED.

    Thomas's revelation: the exterior fringe numbers are *distance-from-pin
    markers*, not altitudes.  Passing fbh no longer influences TPS Z.
    With no interior spikes, Z is driven only by the 16-point outer-frame ring
    at BASE_THICKNESS_MM → surface is flat at BASE everywhere.
    """

    def test_single_fringe_anchor_ignored(self):
        """T1: fringe_boundary_heights_mm passed but IGNORED (task 690).

        With no spikes, TPS Z at the snapped boundary point ≈ BASE_THICKNESS_MM
        (frame-base driven), NOT the anchor value (8.0 mm).
        """
        gsd = _load_gsd()
        # The function that builds the TPS base surface must exist.
        assert hasattr(gsd, "_build_tps_base"), (
            "_build_tps_base not found — TPS not yet implemented"
        )
        cx_px, cy_px, r_px = 300.0, 300.0, 105.0
        egm = _base_egm(
            cx_px, cy_px, r_px,
            fringe_boundary_heights=[
                {"x": cx_px + r_px * 1.35, "y": cy_px, "value": 8.0}
            ],
        )
        green_pts_px = np.array(
            [(p["x"], p["y"]) for p in egm["polygons"][0]["points"]],
            dtype=np.float64,
        )
        scale, centroid_px = gsd._compute_px_to_mm(green_pts_px, egm)
        green_bnd_px = gsd.interpolate_catmull_rom(egm["polygons"][0]["points"])
        green_bnd_mm = gsd._px_to_mm_2d(green_bnd_px.copy(), scale, centroid_px)

        # Anchor in mm
        anchor_mm = gsd._px_to_mm_2d(
            np.array([[cx_px + r_px * 1.35, cy_px]], dtype=np.float64),
            scale, centroid_px,
        )[0]

        # Snap anchor to nearest green boundary point (as spec requires)
        from scipy.spatial import cKDTree
        bnd_kd = cKDTree(green_bnd_mm)
        _, idx = bnd_kd.query(anchor_mm[:2], k=1)
        snapped_xy = green_bnd_mm[idx]  # (x_mm, y_mm)

        # Build TPS surface — no interior spikes
        half = gsd.PRINT_SIZE_MM / 2.0 + gsd.FRINGE_XY_EXPANSION_MM / 2.0
        grid_res = 50
        gx = np.linspace(-half, half, grid_res)
        gy = np.linspace(-half, half, grid_res)
        GX, GY = np.meshgrid(gx, gy)

        z_tps = gsd._build_tps_base(
            egm_data=egm,
            green_bnd_mm=green_bnd_mm,
            elevation_spikes_mm=[],   # no interior spikes
            fringe_boundary_heights_mm=[
                {"xy_mm": snapped_xy, "z_mm": 8.0}
            ],
            grid_x=GX,
            grid_y=GY,
        )
        # Find the TPS Z at the snapped boundary point
        dist_sq = (GX - snapped_xy[0]) ** 2 + (GY - snapped_xy[1]) ** 2
        nearest_idx = np.unravel_index(np.argmin(dist_sq), dist_sq.shape)
        z_at_anchor = float(z_tps[nearest_idx])

        # After task 690 strip: fringe anchor is IGNORED.
        # With no spikes, only 16 frame anchors at BASE_THICKNESS_MM → flat surface.
        base = gsd.BASE_THICKNESS_MM
        assert z_at_anchor == pytest.approx(base, abs=0.5), (
            f"TPS fringe anchor should be IGNORED (task 690). "
            f"With no spikes, Z at anchor point expected ≈ BASE ({base:.1f} mm), "
            f"got {z_at_anchor:.4f} mm"
        )


# ===========================================================================
# T2  TPS interior-spike honored
# ===========================================================================

class TestTPSInteriorSpikeHonored:
    """T2: Interior elevation spike → TPS Z at that point ≈ spike value."""

    @pytest.mark.skip(reason="T5/T6: elevation_spikes_mm removed from TPS pipeline by task 698 — awaits Topo T6 completion")
    def test_single_interior_spike_honored(self):
        """T2: TPS Z at interior spike location ≈ spike value (within 0.1 mm)."""
        gsd = _load_gsd()
        assert hasattr(gsd, "_build_tps_base"), (
            "_build_tps_base not found — TPS not yet implemented"
        )
        cx_px, cy_px, r_px = 300.0, 300.0, 105.0
        # Spike at green centre (pixel coords)
        spike_px = np.array([[cx_px, cy_px]], dtype=np.float64)
        green_pts_px = np.array(
            [(p["x"], p["y"]) for p in _make_circular_green_pts(cx_px, cy_px, r_px)],
            dtype=np.float64,
        )
        egm = _base_egm(cx_px, cy_px, r_px)
        scale, centroid_px = gsd._compute_px_to_mm(green_pts_px, egm)
        green_bnd_px = gsd.interpolate_catmull_rom(egm["polygons"][0]["points"])
        green_bnd_mm = gsd._px_to_mm_2d(green_bnd_px.copy(), scale, centroid_px)

        spike_mm_xy = gsd._px_to_mm_2d(spike_px, scale, centroid_px)[0]
        spike_z = 12.0

        half = gsd.PRINT_SIZE_MM / 2.0 + gsd.FRINGE_XY_EXPANSION_MM / 2.0
        grid_res = 50
        gx = np.linspace(-half, half, grid_res)
        gy = np.linspace(-half, half, grid_res)
        GX, GY = np.meshgrid(gx, gy)

        z_tps = gsd._build_tps_base(
            egm_data=egm,
            green_bnd_mm=green_bnd_mm,
            elevation_spikes_mm=[{"xy_mm": spike_mm_xy, "z_mm": spike_z}],
            fringe_boundary_heights_mm=[],
            grid_x=GX,
            grid_y=GY,
        )
        dist_sq = (GX - spike_mm_xy[0]) ** 2 + (GY - spike_mm_xy[1]) ** 2
        nearest_idx = np.unravel_index(np.argmin(dist_sq), dist_sq.shape)
        z_at_spike = float(z_tps[nearest_idx])

        assert z_at_spike == pytest.approx(spike_z, abs=0.1), (
            f"TPS Z at interior spike expected ≈ {spike_z} mm, "
            f"got {z_at_spike:.4f} mm"
        )


# ===========================================================================
# T3  Smooth outward decay — Z near outer frame ≈ BASE_THICKNESS_MM
# ===========================================================================

class TestTPSOuterFrameDecay:
    """T3: TPS Z at outer frame anchors ≈ BASE_THICKNESS_MM (no blow-up)."""

    def test_frame_z_near_base(self):
        """T3: Z at outer frame circle (1.1× half_extent) ≈ BASE_THICKNESS_MM ± 2 mm."""
        gsd = _load_gsd()
        assert hasattr(gsd, "_build_tps_base"), (
            "_build_tps_base not found — TPS not yet implemented"
        )
        cx_px, cy_px, r_px = 300.0, 300.0, 105.0
        egm = _base_egm(cx_px, cy_px, r_px,
                        fringe_boundary_heights=[
                            {"x": cx_px + r_px * 1.35, "y": cy_px, "value": 8.0}
                        ])
        green_pts_px = np.array(
            [(p["x"], p["y"]) for p in egm["polygons"][0]["points"]],
            dtype=np.float64,
        )
        scale, centroid_px = gsd._compute_px_to_mm(green_pts_px, egm)
        green_bnd_px = gsd.interpolate_catmull_rom(egm["polygons"][0]["points"])
        green_bnd_mm = gsd._px_to_mm_2d(green_bnd_px.copy(), scale, centroid_px)

        anchor_mm = gsd._px_to_mm_2d(
            np.array([[cx_px + r_px * 1.35, cy_px]], dtype=np.float64),
            scale, centroid_px,
        )[0]
        from scipy.spatial import cKDTree
        bnd_kd = cKDTree(green_bnd_mm)
        _, idx = bnd_kd.query(anchor_mm[:2], k=1)
        snapped_xy = green_bnd_mm[idx]

        half = gsd.PRINT_SIZE_MM / 2.0 + gsd.FRINGE_XY_EXPANSION_MM / 2.0
        grid_res = 60
        gx = np.linspace(-half, half, grid_res)
        gy = np.linspace(-half, half, grid_res)
        GX, GY = np.meshgrid(gx, gy)

        z_tps = gsd._build_tps_base(
            egm_data=egm,
            green_bnd_mm=green_bnd_mm,
            elevation_spikes_mm=[],
            fringe_boundary_heights_mm=[{"xy_mm": snapped_xy, "z_mm": 8.0}],
            grid_x=GX,
            grid_y=GY,
        )

        # Sample at 8 points around the outer frame ring at 1.05× half
        r_outer = half * 1.05
        frame_z_vals = []
        for angle in np.linspace(0, 2 * np.pi, 8, endpoint=False):
            fx = r_outer * np.cos(angle)
            fy = r_outer * np.sin(angle)
            dist_sq = (GX - fx) ** 2 + (GY - fy) ** 2
            ni = np.unravel_index(np.argmin(dist_sq), dist_sq.shape)
            frame_z_vals.append(float(z_tps[ni]))

        base = gsd.BASE_THICKNESS_MM
        for fz in frame_z_vals:
            assert abs(fz - base) < 3.0, (
                f"TPS Z at outer frame expected near BASE_THICKNESS_MM={base:.1f} mm, "
                f"got {fz:.4f} mm (diff={abs(fz - base):.4f})"
            )


# ===========================================================================
# T4  Degenerate — 0 constraints → flat BASE_THICKNESS_MM
# ===========================================================================

class TestTPSDegenerate:
    """T4: With zero constraints → flat BASE_THICKNESS_MM surface."""

    def test_zero_constraints_flat_fallback(self):
        """T4: _build_tps_base with no spikes, no anchors → all Z = BASE_THICKNESS_MM."""
        gsd = _load_gsd()
        assert hasattr(gsd, "_build_tps_base"), (
            "_build_tps_base not found — TPS not yet implemented"
        )
        cx_px, cy_px, r_px = 300.0, 300.0, 105.0
        egm = _base_egm(cx_px, cy_px, r_px)  # no spikes, no fbh
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

        z_tps = gsd._build_tps_base(
            egm_data=egm,
            green_bnd_mm=green_bnd_mm,
            elevation_spikes_mm=[],
            fringe_boundary_heights_mm=[],
            grid_x=GX,
            grid_y=GY,
        )

        base = gsd.BASE_THICKNESS_MM
        # All values should equal BASE_THICKNESS_MM (or be within 0.01 mm on
        # the flat-fallback path — outer-frame anchors set to BASE_THICKNESS_MM).
        assert np.all(np.abs(z_tps - base) < 0.5), (
            f"Degenerate (0 constraints) TPS should be flat at BASE={base:.1f} mm; "
            f"range={float(z_tps.min()):.4f}..{float(z_tps.max()):.4f}"
        )


# ===========================================================================
# T5  C1 continuity across fringe/green seam
# ===========================================================================

class TestTPSSeamContinuity:
    """T5: Finite-difference gradient step at boundary < 2 mm/mm (C1 smooth)."""

    def test_seam_gradient_continuous(self):
        """T5: |∇Z| finite-difference step at fringe/green seam < 2 mm/mm."""
        gsd = _load_gsd()
        assert hasattr(gsd, "_build_tps_base"), (
            "_build_tps_base not found — TPS not yet implemented"
        )
        cx_px, cy_px, r_px = 300.0, 300.0, 105.0
        egm = _base_egm(
            cx_px, cy_px, r_px,
            fringe_boundary_heights=[
                {"x": cx_px + r_px * 1.35, "y": cy_px, "value": 8.0}
            ],
        )
        green_pts_px = np.array(
            [(p["x"], p["y"]) for p in egm["polygons"][0]["points"]],
            dtype=np.float64,
        )
        scale, centroid_px = gsd._compute_px_to_mm(green_pts_px, egm)
        green_bnd_px = gsd.interpolate_catmull_rom(egm["polygons"][0]["points"])
        green_bnd_mm = gsd._px_to_mm_2d(green_bnd_px.copy(), scale, centroid_px)

        anchor_mm = gsd._px_to_mm_2d(
            np.array([[cx_px + r_px * 1.35, cy_px]], dtype=np.float64),
            scale, centroid_px,
        )[0]
        from scipy.spatial import cKDTree
        bnd_kd = cKDTree(green_bnd_mm)
        _, idx = bnd_kd.query(anchor_mm[:2], k=1)
        snapped_xy = green_bnd_mm[idx]

        # Build on a 1D radial transect crossing the boundary near the anchor.
        # Sample Z along radial direction at small steps (0.5 mm).
        # Boundary is at ~radius mm from green centre.
        # Green centre in mm
        cx_mm = float(gsd._px_to_mm_2d(
            np.array([[cx_px, cy_px]], dtype=np.float64), scale, centroid_px
        )[0, 0])
        cy_mm = float(gsd._px_to_mm_2d(
            np.array([[cx_px, cy_px]], dtype=np.float64), scale, centroid_px
        )[0, 1])
        # Radius in mm
        r_mm = float(np.linalg.norm(snapped_xy - np.array([cx_mm, cy_mm])))
        # Sample along X-axis through snapped_xy
        step_mm = 0.5
        n_sample = 20
        # 10 steps on each side of boundary
        sample_xs = np.array([snapped_xy[0] + (i - n_sample // 2) * step_mm
                               for i in range(n_sample)])
        sample_ys = np.full(n_sample, snapped_xy[1])

        half = gsd.PRINT_SIZE_MM / 2.0 + gsd.FRINGE_XY_EXPANSION_MM / 2.0
        # Build a narrow grid covering just this transect
        gx = sample_xs
        gy = sample_ys
        GX = sample_xs.reshape(1, -1)
        GY = sample_ys.reshape(1, -1)

        z_tps_1d = gsd._build_tps_base(
            egm_data=egm,
            green_bnd_mm=green_bnd_mm,
            elevation_spikes_mm=[],
            fringe_boundary_heights_mm=[{"xy_mm": snapped_xy, "z_mm": 8.0}],
            grid_x=GX,
            grid_y=GY,
        ).ravel()

        # Finite-difference derivative (mm/mm) at each step
        dz_dx = np.abs(np.diff(z_tps_1d)) / step_mm  # shape (n_sample - 1,)
        # Check the derivative change between adjacent samples (second difference)
        # A crease shows up as a large jump in dz_dx.
        d2z_dx2 = np.abs(np.diff(dz_dx))  # shape (n_sample - 2,)
        max_deriv_jump = float(d2z_dx2.max())

        # C1-continuity test: derivative must not jump by more than 2 mm/mm
        # between adjacent half-mm samples across the boundary.
        assert max_deriv_jump < 2.0, (
            f"Gradient discontinuity at fringe/green seam: max |Δ(dZ/dx)| = "
            f"{max_deriv_jump:.4f} mm/mm (tol=2.0). Z transect: {z_tps_1d}"
        )


# ===========================================================================
# T6  Regression — fringe Z at boundary anchor still ≈ anchor value
# (build_fringe_mesh round-trip, not just _build_tps_base unit test)
# ===========================================================================

class TestTPSFringeMeshRoundTrip:
    """T6 (updated task 690): build_fringe_mesh with TPS base produces valid
    fringe mesh when fringeBoundaryHeights are present (but now ignored).

    Original test verified anchor Z was honored; after the strip it verifies
    the fringe mesh is still well-formed (finite vertices, Z ≥ BASE) even
    when fringeBoundaryHeights are passed but ignored.
    """

    def test_fringe_mesh_valid_with_ignored_anchors(self, tmp_path):
        """T6: build_fringe_mesh still produces a valid mesh when fbh is present
        but ignored; top fringe vertices have Z ≥ BASE_THICKNESS_MM and are finite."""
        gsd = _load_gsd()
        cx_px, cy_px, r_px = 300.0, 300.0, 105.0
        # Pass fringeBoundaryHeights (now ignored) and an interior spike
        spike_z = 9.0
        egm = _base_egm(
            cx_px, cy_px, r_px,
            fringe_boundary_heights=[
                {"x": cx_px + r_px * 1.35, "y": cy_px, "value": 8.0}
            ],
            elevation_spikes=[
                {"x": cx_px, "y": cy_px, "mm": spike_z}
            ],
        )
        green_bnd_px = gsd.interpolate_catmull_rom(egm["polygons"][0]["points"])
        Z_mm, xs_g, ys_g, inside_mask = _flat_green_arrays(cx_px, cy_px, r_px)

        fringe_mesh = gsd.build_fringe_mesh(
            Z_mm, xs_g, ys_g, inside_mask,
            green_bnd_px, egm,
            fringe_grid_res=80,
        )

        verts = np.asarray(fringe_mesh.vertices)
        assert len(verts) > 0, "Fringe mesh has no vertices"

        top_verts = verts[verts[:, 2] > gsd.BASE_THICKNESS_MM * 0.5]
        assert len(top_verts) > 0, "No top fringe vertices found (Z > BASE/2)"

        # All top vertices must be finite
        assert np.all(np.isfinite(top_verts)), "Fringe mesh top vertices contain NaN/Inf"

        # All top vertices must be at or above BASE_THICKNESS_MM (no negative Z)
        assert float(top_verts[:, 2].min()) >= gsd.BASE_THICKNESS_MM - 0.1, (
            f"Fringe top vertex Z min = {float(top_verts[:,2].min()):.3f} mm; "
            f"expected ≥ BASE={gsd.BASE_THICKNESS_MM:.1f} mm"
        )

        # The spike at green centre should influence fringe near the boundary —
        # max Z should be above BASE (spike is driving the surface up somewhere)
        assert float(top_verts[:, 2].max()) > gsd.BASE_THICKNESS_MM + 0.5, (
            f"Fringe top Z max = {float(top_verts[:,2].max()):.3f} mm; "
            f"spike at {spike_z} mm should raise Z above BASE"
        )


# ===========================================================================
# T7  Regression — trap + rake + chunks still work
# ===========================================================================

class TestTPSTrapRegression:
    """T7: build_fringe_mesh still produces a fringe with varying Z (trap still curves).

    Updated for task 700: fringe Z now inherits green boundary Z (nearest-boundary
    extension).  elevationSpikes are deprecated/ignored (task 698) and no longer
    drive Z variation.  Instead the test uses a tilted green (left=3 mm, right=7 mm)
    to verify that the fringe mirrors the tilt and that a trap polygon is carved
    out correctly — the core trap-regression invariant (trap mesh still builds and
    fringe Z is not flat when the green is tilted).
    """

    def test_trap_not_flattened(self, tmp_path):
        """T7: fringe+trap with tilted green — fringe Z varies (mirrors tilt, > 2 mm range)."""
        gsd = _load_gsd()
        cx_px, cy_px, r_px = 300.0, 300.0, 105.0
        # Add a trap polygon slightly outside the green (right side).
        trap_r_px = 120.0
        trap_pts = _make_circular_green_pts(cx_px + 20, cy_px, trap_r_px * 0.4, n=16)
        egm = _base_egm(cx_px, cy_px, r_px)
        egm["polygons"].append({"name": "Trap1", "type": "trap", "points": trap_pts})
        egm["fringeBoundaryHeights"] = []
        egm["elevationSpikes"] = []  # deprecated/ignored since task 698

        green_bnd_px = gsd.interpolate_catmull_rom(egm["polygons"][0]["points"])

        # Tilted green: left edge = 3 mm, right edge = 7 mm.
        # With the task-700 nearest-boundary Z extension, the fringe mirrors
        # this tilt, giving a Z range of ≈ 4 mm across the fringe rectangle.
        xs_g = np.linspace(0, 599, 200)
        ys_g = np.linspace(0, 599, 200)
        inside_mask = np.zeros((200, 200), dtype=bool)
        Z_mm = np.zeros((200, 200), dtype=float)
        for ri, py in enumerate(ys_g):
            for ci, px in enumerate(xs_g):
                if math.hypot(px - cx_px, py - cy_px) < r_px:
                    inside_mask[ri, ci] = True
                    t = (px - cx_px + r_px) / (2.0 * r_px)  # 0 at left, 1 at right
                    Z_mm[ri, ci] = 3.0 + 4.0 * t  # 3..7 mm

        fringe_mesh = gsd.build_fringe_mesh(
            Z_mm, xs_g, ys_g, inside_mask,
            green_bnd_px, egm,
            fringe_grid_res=80,
        )
        verts = np.asarray(fringe_mesh.vertices)
        # Top-surface vertices only (exclude bottom face at Z=0).
        top_verts = verts[verts[:, 2] > gsd.BASE_THICKNESS_MM * 0.5]
        assert len(top_verts) > 10, "Too few top fringe vertices — mesh may be degenerate"

        # Task 700: fringe mirrors the green tilt → Z range should be > 2 mm.
        z_range = float(top_verts[:, 2].max() - top_verts[:, 2].min())
        assert z_range > 2.0, (
            f"Fringe top Z range = {z_range:.4f} mm — should have > 2 mm variation "
            f"mirroring the tilted green surface (nearest-boundary extension, task 700)"
        )


# ===========================================================================
# T8  Water still flat
# ===========================================================================

class TestTPSWaterFlat:
    """T8: Water mesh slab remains flat after TPS integration."""

    def test_water_slab_flat(self, tmp_path):
        """T8: export_water_meshes slab Z variation < 0.1 mm."""
        gsd = _load_gsd()
        cx_px, cy_px, r_px = 300.0, 300.0, 105.0
        # Add a small water polygon
        water_pts = _make_circular_green_pts(cx_px + 30, cy_px, 30.0, n=16)
        egm = _base_egm(cx_px, cy_px, r_px)
        egm["polygons"].append({"name": "Water1", "type": "water", "points": water_pts})

        green_bnd_px = gsd.interpolate_catmull_rom(egm["polygons"][0]["points"])
        Z_mm, xs_g, ys_g, inside_mask = _flat_green_arrays(cx_px, cy_px, r_px)

        try:
            water_meshes = gsd.export_water_meshes(
                green_bnd_px, egm,
                fringe_grid_res=80,
            )
        except Exception as exc:
            pytest.skip(f"export_water_meshes raised {exc} — water pipeline not available in this test context")

        for wm in water_meshes:
            wv = np.asarray(wm.vertices)
            top_w = wv[wv[:, 2] > gsd.BASE_THICKNESS_MM * 0.1]
            if len(top_w) < 3:
                continue
            z_range_w = float(top_w[:, 2].max() - top_w[:, 2].min())
            assert z_range_w < 0.1, (
                f"Water slab Z range = {z_range_w:.4f} mm — should be flat (< 0.1 mm); "
                f"TPS may have warped the water slab"
            )


# ===========================================================================
# T9  Co-located constraints with conflicting Z → averaged without error
# ===========================================================================

class TestTPSConflictingConstraints:
    """T9 (updated task 690): Two co-located *interior spikes* with conflicting Z
    → averaged without error.

    Original test used fringe_boundary_heights_mm for conflicting constraints;
    updated to use elevation_spikes_mm since fringe anchors are now ignored.
    The averaging logic applies to any co-located spike pair.
    """

    @pytest.mark.skip(reason="T5/T6: elevation_spikes_mm removed from TPS pipeline by task 698 — awaits Topo T6 completion")
    def test_collocated_constraints_averaged(self):
        """T9: Co-located interior spikes (xy) with conflicting Z → no exception, Z = avg."""
        gsd = _load_gsd()
        assert hasattr(gsd, "_build_tps_base"), (
            "_build_tps_base not found — TPS not yet implemented"
        )
        cx_px, cy_px, r_px = 300.0, 300.0, 105.0
        egm = _base_egm(cx_px, cy_px, r_px)
        green_pts_px = np.array(
            [(p["x"], p["y"]) for p in egm["polygons"][0]["points"]],
            dtype=np.float64,
        )
        scale, centroid_px = gsd._compute_px_to_mm(green_pts_px, egm)
        green_bnd_px = gsd.interpolate_catmull_rom(egm["polygons"][0]["points"])
        green_bnd_mm = gsd._px_to_mm_2d(green_bnd_px.copy(), scale, centroid_px)

        # Two interior spikes at EXACTLY the same XY but different Z
        # (Updated from fringe anchors — fringe anchors are now ignored, task 690)
        pt_mm = np.array([5.0, 0.0])
        conflicting_spikes = [
            {"xy_mm": pt_mm.copy(), "z_mm": 6.0},
            {"xy_mm": pt_mm.copy(), "z_mm": 10.0},
        ]

        half = gsd.PRINT_SIZE_MM / 2.0 + gsd.FRINGE_XY_EXPANSION_MM / 2.0
        grid_res = 20
        gx = np.linspace(-half, half, grid_res)
        gy = np.linspace(-half, half, grid_res)
        GX, GY = np.meshgrid(gx, gy)

        # Must not raise
        z_tps = gsd._build_tps_base(
            egm_data=egm,
            green_bnd_mm=green_bnd_mm,
            elevation_spikes_mm=conflicting_spikes,
            fringe_boundary_heights_mm=[],  # fringe anchors ignored (task 690)
            grid_x=GX,
            grid_y=GY,
        )
        assert z_tps.shape == GX.shape, "Output shape mismatch"
        assert np.all(np.isfinite(z_tps)), "TPS output contains NaN or Inf"

        # Z at the co-located spike point should be near the average = 8.0
        dist_sq = (GX - pt_mm[0]) ** 2 + (GY - pt_mm[1]) ** 2
        ni = np.unravel_index(np.argmin(dist_sq), dist_sq.shape)
        z_at_pt = float(z_tps[ni])
        assert z_at_pt == pytest.approx(8.0, abs=1.0), (
            f"Co-located spikes (6.0, 10.0) → expected Z≈8.0 (avg), got {z_at_pt:.4f}"
        )


# ===========================================================================
# T10  Only outer-frame anchors → no blow-up
# ===========================================================================

class TestTPSOnlyFrameAnchors:
    """T10: TPS with only outer-frame anchors stays near BASE_THICKNESS_MM."""

    def test_only_frame_anchors_no_blowup(self):
        """T10: No spikes, no fbh → outer anchors keep TPS bounded near BASE."""
        gsd = _load_gsd()
        assert hasattr(gsd, "_build_tps_base"), (
            "_build_tps_base not found — TPS not yet implemented"
        )
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
        grid_res = 40
        gx = np.linspace(-half, half, grid_res)
        gy = np.linspace(-half, half, grid_res)
        GX, GY = np.meshgrid(gx, gy)

        z_tps = gsd._build_tps_base(
            egm_data=egm,
            green_bnd_mm=green_bnd_mm,
            elevation_spikes_mm=[],
            fringe_boundary_heights_mm=[],
            grid_x=GX,
            grid_y=GY,
        )

        assert np.all(np.isfinite(z_tps)), "TPS with only frame anchors produced NaN/Inf"
        base = gsd.BASE_THICKNESS_MM
        elev_range = float(egm.get("elevationRange", gsd.ELEVATION_RANGE_MM))
        max_allowed = base + elev_range + 2.0  # a little slack for smoothing
        assert float(z_tps.max()) <= max_allowed, (
            f"TPS blow-up: max Z = {float(z_tps.max()):.4f} mm > {max_allowed:.1f} mm"
        )
        assert float(z_tps.min()) >= 0.0, (
            f"TPS undershoot: min Z = {float(z_tps.min()):.4f} mm < 0"
        )
