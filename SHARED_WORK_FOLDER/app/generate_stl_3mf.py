"""
generate_stl_3mf.py — Build a combined 3MF from EGM boundary data.

Each polygon in the EGM file is a set of Catmull-Rom control points (the same
spline the editor draws on screen).  We:

  1. Interpolate a dense smooth outline using closed Catmull-Rom with tension=0.5,
     16 segments per edge — exactly matching the editor's traceSplinePath().
  2. Extrude the outline into a flat slab (green = 3 mm, fringe = 2 mm, traps = 2 mm).
  3. Build a fringe frame: a full 178mm × 178mm rectangle with the green and all trap
     polygons subtracted as cutouts — a placement template / puzzle frame.
  4. Scale so the largest overall dimension fits in PRINT_SIZE_MM (178 mm = 7 in).
  5. Assemble all slabs into a trimesh Scene and export as a single .3mf file.

Dependencies (all already installed):
    numpy, trimesh, shapely, mapbox-earcut, lxml

------------------------------------------------------------------------------
DEPRECATION NOTICE — Topo, 2026-05-07 (per homeowner decision)
------------------------------------------------------------------------------
The arrow-detection / gradient-field / Poisson / no-arrows-fallback code paths
that previously lived in this file were superseded by `gradient_surface_diagnostic.py`
(its `run_pipeline()` is the live pipeline called by `app.py`).

Stripped sections (do NOT re-introduce here — edit `gradient_surface_diagnostic.py`):
  - `_grad_build_dark_mask`
  - `_grad_pca_orientation`
  - `_grad_resolve_direction`
  - `_grad_detect_arrows`
  - `_grad_build_gradient_field`
  - `_grad_solve_poisson`
  - `_grad_height_to_mm`
  - `_grad_build_heightmap_mesh`
  - `_build_gradient_green` (and its in-`generate_from_egm` callsite)
  - The local `FLAT_FALLBACK_Z_RAW` no-arrows fallback inside `_build_gradient_green`

Retained because they are still imported elsewhere (NOT duplicates of the
survivor pipeline):
  - `course_paths`, `EGM_BASE`, `OWNER_INBOX`, `PRINT_SIZE_MM`, `FRINGE_XY_EXPANSION_MM`
  - `interpolate_catmull_rom`, `_catmull_rom_point`
  - `_build_flat_slab`, `_build_slab_from_shapely`, `_build_stepped_green`, `_build_fringe`
  - `_compute_scale_and_offset`, `_to_mm`, `_interpolate_open_polyline`
  - `remove_arrows_from_green`, `extract_contour_polylines_from_mask`
  - `_slugify`, `_3mf_filename`, `generate_from_egm`, `generate_from_egm_file`
    (the gradient-surface block inside `generate_from_egm` was neutralized;
     the rest still builds flat slabs, fringe, traps, etc.)
"""

from __future__ import annotations

import json
import math
import os
import re
from typing import Any

import numpy as np
from shapely.geometry import Polygon as ShapelyPolygon
from shapely.ops import unary_union
import trimesh

# Optional heavy deps — imported lazily inside functions that need them
# cv2, scipy.sparse, scipy.sparse.linalg

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PRINT_SIZE_MM: float = 171.45       # max bounding-box dimension after scaling (6.75 in)
CATMULL_TENSION: float = 0.5        # editor uses 0.5
CATMULL_SEGMENTS: int = 16          # editor uses 16 segments per edge

THICKNESS_BY_TYPE: dict[str, float] = {
    "green":  15.0,
    "fringe": 12.0,
    "trap":   10.0,
}
DEFAULT_THICKNESS: float = 2.5
PRINT_TOLERANCE_MM: float = 0.25    # inset each piece by this much for easier fit

# Fringe frame: the frame is a full PRINT_SIZE_MM square centred at the origin
# with the green and trap polygons subtracted as shaped cutouts.
# Half of PRINT_SIZE_MM (89 mm) gives the rectangle corners at (±89, ±89).
#
# FRINGE_XY_EXPANSION_MM is a signed TOTAL offset per axis on the outer rectangle.
# Positive = grow, negative = shrink. Only the outer rectangle moves; the inner
# green/trap cutouts remain anchored at world origin so they still mate with the
# un-shrunk green and trap meshes.  Value matches gradient_surface_diagnostic.py
# (prior -0.2 mm inset + 0.5% shrink of PRINT_SIZE_MM = -1.057 mm).  v3.16.
FRINGE_XY_EXPANSION_MM: float = -1.057  # signed total XY offset per axis (negative = shrink)
FRINGE_HALF_MM: float = PRINT_SIZE_MM / 2.0 + FRINGE_XY_EXPANSION_MM / 2.0   # ~88.47 mm after shrink

OWNER_INBOX: str = os.path.join(
    os.path.dirname(__file__), "..", "owner_inbox"
)

# ---------------------------------------------------------------------------
# EGM folder structure helpers
# ---------------------------------------------------------------------------

EGM_BASE: str = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "EliteGolfMoments", "GolfCourses")
)


def course_paths(course: str) -> dict:
    """Return resolved paths for a course's subdirectories.

    Keys: 'images', 'egms', 'stls', '3mfs'
    """
    base = os.path.join(EGM_BASE, course)
    return {
        "images": os.path.join(base, "Images"),
        "egms":   os.path.join(base, "EGMs"),
        "stls":   os.path.join(base, "STLs"),
        "3mfs":   os.path.join(base, "3MFs"),
    }

# ---------------------------------------------------------------------------
# Catmull-Rom spline (closed, matching the editor's traceSplinePath)
# ---------------------------------------------------------------------------

def _catmull_rom_point(
    p0: np.ndarray,
    p1: np.ndarray,
    p2: np.ndarray,
    p3: np.ndarray,
    t: float,
    tension: float = 0.5,
) -> np.ndarray:
    """Evaluate one point on a Catmull-Rom segment from p1→p2 at parameter t∈[0,1]."""
    t2 = t * t
    t3 = t2 * t
    # Standard Catmull-Rom matrix with given tension (alpha = tension / 2)
    alpha = tension
    return (
        (-alpha * t3 + 2 * alpha * t2 - alpha * t) * p0
        + ((2 - alpha) * t3 + (alpha - 3) * t2 + 1) * p1
        + ((alpha - 2) * t3 + (3 - 2 * alpha) * t2 + alpha * t) * p2
        + (alpha * t3 - alpha * t2) * p3
    )


def interpolate_catmull_rom(
    control_points: list[dict],
    segments: int = CATMULL_SEGMENTS,
    tension: float = CATMULL_TENSION,
) -> np.ndarray:
    """
    Return a dense closed 2D polyline that matches the editor's traceSplinePath().

    Parameters
    ----------
    control_points : list of {"x": float, "y": float} dicts
    segments       : number of interpolated points per control-point edge
    tension        : Catmull-Rom tension (0.5 matches the editor default)

    Returns
    -------
    np.ndarray of shape (N, 2), dtype float64 — the spline vertices in image pixels
    """
    n = len(control_points)
    if n < 3:
        # Fall back to straight edges for degenerate polygons
        return np.array([[p["x"], p["y"]] for p in control_points], dtype=np.float64)

    pts = np.array([[p["x"], p["y"]] for p in control_points], dtype=np.float64)

    result: list[np.ndarray] = []
    for i in range(n):
        p0 = pts[(i - 1) % n]
        p1 = pts[i % n]
        p2 = pts[(i + 1) % n]
        p3 = pts[(i + 2) % n]
        for s in range(segments):
            t = s / segments
            result.append(_catmull_rom_point(p0, p1, p2, p3, t, tension))

    return np.array(result, dtype=np.float64)


# ---------------------------------------------------------------------------
# Coordinate helpers
# ---------------------------------------------------------------------------

def _compute_scale_and_offset(
    all_polygons_splines: list[np.ndarray],
    image_size: dict,
    print_size_mm: float = PRINT_SIZE_MM,
) -> tuple[float, np.ndarray]:
    """
    Compute a uniform scale factor (pixels → mm) and a 2D translation so that
    the entire layout of all polygons fits inside print_size_mm × print_size_mm,
    centred at the origin.

    Returns (scale, offset_xy) where:
        mm_coords = (pixel_coords - offset_xy) * scale
    """
    # Use the image bounding box as the canonical space so that spatial
    # relationships between pieces are preserved.
    img_w = float(image_size.get("width", 1))
    img_h = float(image_size.get("height", 1))

    max_dim = max(img_w, img_h)
    scale = print_size_mm / max_dim

    # Centre the image coordinate space at the origin
    offset_xy = np.array([img_w / 2.0, img_h / 2.0])

    return scale, offset_xy


def _to_mm(spline_px: np.ndarray, scale: float, offset: np.ndarray) -> np.ndarray:
    """Convert pixel spline coordinates to millimetres (Y axis flipped for 3D)."""
    xy = (spline_px - offset) * scale
    # Flip Y so that "up" on screen is "up" in 3D print space
    xy[:, 1] = -xy[:, 1]
    return xy


# ---------------------------------------------------------------------------
# Mesh construction
# ---------------------------------------------------------------------------

def _build_flat_slab(outline_mm: np.ndarray, thickness_mm: float) -> trimesh.Trimesh:
    """
    Extrude a 2D closed outline (Nx2 array, in mm) to a flat slab of given thickness.

    Uses Shapely for the polygon → trimesh extrude_polygon.

    Returns a watertight trimesh.Trimesh.
    """
    # Ensure the polygon is wound counter-clockwise (Shapely convention)
    poly = ShapelyPolygon(outline_mm)

    if not poly.is_valid:
        poly = poly.buffer(0)  # attempt to repair self-intersections

    if poly.is_empty or not poly.is_valid:
        raise ValueError("Polygon is invalid even after buffer(0) repair.")

    # trimesh.creation.extrude_polygon puts the "bottom" at z=0 and top at z=height
    mesh = trimesh.creation.extrude_polygon(poly, height=thickness_mm)

    if not mesh.is_watertight:
        trimesh.repair.fix_normals(mesh)
        trimesh.repair.fill_holes(mesh)

    return mesh


def _build_slab_from_shapely(poly: ShapelyPolygon, thickness_mm: float) -> trimesh.Trimesh:
    """
    Extrude an already-constructed Shapely polygon to a flat slab.
    Handles MultiPolygon results by taking the largest sub-polygon.
    """
    from shapely.geometry import MultiPolygon

    if not poly.is_valid:
        poly = poly.buffer(0)

    if poly.is_empty or not poly.is_valid:
        raise ValueError("Shapely polygon is empty or invalid after repair.")

    # If the result is a MultiPolygon (e.g. fringe minus traps), pick the largest piece
    # and build separate meshes for each.
    if isinstance(poly, MultiPolygon):
        geoms = list(poly.geoms)
    else:
        geoms = [poly]

    meshes = []
    for g in geoms:
        if g.is_empty:
            continue
        try:
            m = trimesh.creation.extrude_polygon(g, height=thickness_mm)
            if not m.is_watertight:
                trimesh.repair.fix_normals(m)
                trimesh.repair.fill_holes(m)
            meshes.append(m)
        except Exception as exc:
            print(f"[generate_stl_3mf] WARNING: sub-polygon extrusion failed: {exc}")

    if not meshes:
        raise ValueError("No valid sub-polygons produced a mesh.")

    if len(meshes) == 1:
        return meshes[0]

    return trimesh.util.concatenate(meshes)


def _interpolate_open_polyline(
    control_points: list[dict],
) -> np.ndarray:
    """
    Return a simple 2-D open polyline from a list of {"x", "y"} dicts.
    Contour lines are stored as straight-segment open polylines (not splines),
    so we just return the points as-is.
    """
    return np.array([[p["x"], p["y"]] for p in control_points], dtype=np.float64)


def _build_stepped_green(
    green_outline_mm: np.ndarray,
    contour_lines_mm: list[np.ndarray],
    contour_directions: list[str],
    base_thickness_mm: float,
    step_mm: float,
    image_path: str | None = None,
    scale: float = 1.0,
    offset: np.ndarray | None = None,
) -> trimesh.Trimesh:
    """
    Build a stepped-surface green mesh by reading the source image's color bands
    directly.  Each color band (blue, green, yellow, orange, red) becomes a
    separate elevation level.

    Algorithm:
    1. Read the source image pixel colors inside the green perimeter.
    2. Classify pixels into elevation bands (0-4) by HSV hue.
    3. For each band, build a Shapely polygon from the band's mask, intersected
       with the green perimeter.
    4. Extrude each band region at base_thickness + band_level * step_mm.

    The contour_lines_mm / contour_directions args are kept for API compat but
    the image-based approach is preferred when image_path is available.
    """
    from shapely.geometry import MultiPolygon

    from shapely.geometry import LineString, MultiPolygon
    from shapely.ops import split

    green_poly = ShapelyPolygon(green_outline_mm)
    if not green_poly.is_valid:
        green_poly = green_poly.buffer(0)

    if not contour_lines_mm:
        return _build_flat_slab(green_outline_mm, base_thickness_mm)

    # ── Split the green polygon along each manually-drawn contour line ──
    bb = green_poly.bounds
    diag = np.hypot(bb[2] - bb[0], bb[3] - bb[1])
    extend = diag * 0.2  # extend lines well past the green edge

    def _extend_line(pts: np.ndarray, extra: float) -> np.ndarray:
        if len(pts) < 2:
            return pts
        d0 = pts[0] - pts[1]
        d0_len = np.linalg.norm(d0)
        if d0_len > 0:
            d0 = d0 / d0_len * extra
        d1 = pts[-1] - pts[-2]
        d1_len = np.linalg.norm(d1)
        if d1_len > 0:
            d1 = d1 / d1_len * extra
        return np.vstack([pts[0:1] + d0, pts, pts[-1:] + d1])

    regions: list[ShapelyPolygon] = [green_poly]

    for cline_mm in contour_lines_mm:
        if len(cline_mm) < 2:
            continue
        extended = _extend_line(cline_mm, extend)
        # Densify: add intermediate points so the line closely follows
        # the drawn path and intersects the polygon boundary cleanly
        splitter = LineString(extended)
        new_regions = []
        for region in regions:
            try:
                result = split(region, splitter)
                geoms = list(result.geoms) if hasattr(result, "geoms") else [result]
                for g in geoms:
                    if g.is_empty:
                        continue
                    if isinstance(g, MultiPolygon):
                        new_regions.extend(g.geoms)
                    elif hasattr(g, "exterior"):
                        new_regions.append(g)
            except Exception as exc:
                print(f"[generate_stl_3mf] Contour split warning: {exc}")
                new_regions.append(region)
        regions = new_regions if new_regions else regions

    print(f"[generate_stl_3mf] Split green into {len(regions)} region(s) "
          f"with {len(contour_lines_mm)} contour line(s)")

    # ── Score regions by counting "up" crossings ──
    centroids = [np.array(r.centroid.coords[0]) for r in regions]

    def _side_of_line(pt, p0, p1):
        d = p1 - p0
        perp = np.array([-d[1], d[0]])
        return float(np.dot(pt - p0, perp))

    scores = [0] * len(regions)
    for cline_mm, direction in zip(contour_lines_mm, contour_directions):
        if len(cline_mm) < 2:
            continue
        p0 = cline_mm[0]
        p1 = cline_mm[-1]
        for ri, c in enumerate(centroids):
            side = _side_of_line(c, p0, p1)
            if direction == "left" and side > 0:
                scores[ri] += 1
            elif direction == "right" and side < 0:
                scores[ri] += 1

    min_score = min(scores) if scores else 0
    max_score = max(scores) if scores else 0

    # ── Save debug image showing regions + scores ──
    try:
        import cv2 as _cv2
        debug_h, debug_w = 800, 800
        debug_img = np.zeros((debug_h, debug_w, 3), dtype=np.uint8)
        # Map mm coords to debug image
        all_pts = green_outline_mm
        mm_min = all_pts.min(axis=0)
        mm_max = all_pts.max(axis=0)
        mm_range = mm_max - mm_min
        margin = 40
        draw_w = debug_w - 2 * margin
        draw_h = debug_h - 2 * margin
        sc = min(draw_w / max(mm_range[0], 1), draw_h / max(mm_range[1], 1))

        def mm_to_px(pt):
            x = int(margin + (pt[0] - mm_min[0]) * sc)
            y = int(margin + (mm_max[1] - pt[1]) * sc)  # flip Y
            return (x, y)

        # Color palette for elevation levels
        n_levels = max_score - min_score + 1
        colors = [
            (180, 60, 60),    # dark blue (low)
            (180, 120, 40),   # teal
            (60, 180, 60),    # green
            (40, 200, 200),   # yellow
            (30, 140, 220),   # orange
            (50, 80, 220),    # red-orange
            (40, 40, 200),    # red (high)
            (200, 100, 200),  # magenta
        ]

        for ri, (region, score) in enumerate(zip(regions, scores)):
            level = score - min_score
            color = colors[level % len(colors)]
            # Draw filled polygon
            ext = np.array(region.exterior.coords)
            pts_px = np.array([mm_to_px(p) for p in ext], dtype=np.int32)
            _cv2.fillPoly(debug_img, [pts_px], color)
            # Label with score
            cx, cy = mm_to_px(centroids[ri])
            _cv2.putText(debug_img, str(level), (cx - 8, cy + 5),
                         _cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)

        # Draw contour lines in white
        for cline_mm in contour_lines_mm:
            for i in range(len(cline_mm) - 1):
                p1 = mm_to_px(cline_mm[i])
                p2 = mm_to_px(cline_mm[i + 1])
                _cv2.line(debug_img, p1, p2, (255, 255, 255), 2)

        # Draw green outline
        outline_px = np.array([mm_to_px(p) for p in green_outline_mm], dtype=np.int32)
        _cv2.polylines(debug_img, [outline_px], True, (0, 255, 0), 1)

        debug_path = os.path.join(OWNER_INBOX, "debug_stepped_green.png")
        _cv2.imwrite(debug_path, debug_img)
        print(f"[generate_stl_3mf] Debug image saved: {debug_path}")
    except Exception as exc:
        print(f"[generate_stl_3mf] Debug image failed: {exc}")

    # ── Extrude each region at its elevation ──
    meshes: list[trimesh.Trimesh] = []
    for region, score in zip(regions, scores):
        level = score - min_score
        z_top = base_thickness_mm + level * step_mm
        try:
            slab = _build_slab_from_shapely(region, z_top)
            meshes.append(slab)
        except Exception as exc:
            print(f"[generate_stl_3mf] WARNING: stepped slab failed (level={level}): {exc}")

    if not meshes:
        print("[generate_stl_3mf] WARNING: all stepped slabs failed — flat slab fallback")
        return _build_flat_slab(green_outline_mm, base_thickness_mm)

    result = trimesh.util.concatenate(meshes) if len(meshes) > 1 else meshes[0]
    print(f"[generate_stl_3mf] Stepped green: {len(regions)} region(s), "
          f"{n_levels} level(s), step={step_mm}mm, "
          f"height={base_thickness_mm}–{base_thickness_mm + (max_score - min_score) * step_mm:.1f}mm")
    return result


def _build_fringe(
    green_poly: ShapelyPolygon,
    trap_polys: list[ShapelyPolygon],
    thickness_mm: float,
) -> trimesh.Trimesh | None:
    """
    Build the fringe frame mesh — a 178 mm × 178 mm placement template:
      - Start with a full PRINT_SIZE_MM square centred at the origin.
      - Subtract the green polygon (creates the green's shaped cutout).
      - Subtract all trap polygons (creates each trap's shaped cutout).
      - Extrude the resulting frame to thickness_mm.

    The printed frame acts as a puzzle base: drop the green and trap pieces
    into their matching cutouts to verify fit and arrangement.

    Returns None if the frame polygon is empty after subtraction.
    """
    from shapely.geometry import box as shapely_box

    h = FRINGE_HALF_MM  # 89.0 mm
    frame = shapely_box(-h, -h, h, h)
    print(f"[generate_stl_3mf] Fringe frame: {PRINT_SIZE_MM:.0f} x {PRINT_SIZE_MM:.0f} mm "
          f"rectangle centred at origin")

    # Subtract green cutout
    frame = frame.difference(green_poly)

    # Subtract each trap cutout
    if trap_polys:
        all_traps = unary_union(trap_polys)
        frame = frame.difference(all_traps)

    if frame.is_empty:
        print("[generate_stl_3mf] WARNING: fringe frame is empty after subtraction.")
        return None

    try:
        return _build_slab_from_shapely(frame, thickness_mm)
    except Exception as exc:
        print(f"[generate_stl_3mf] WARNING: fringe frame mesh build failed: {exc}")
        return None


# ---------------------------------------------------------------------------
# Gradient surface (DEPRECATED 2026-05-07)
#
# The arrow-detection + Poisson reconstruction pipeline that previously lived
# here has been removed per the homeowner's deprecation decision. The live
# pipeline is now `gradient_surface_diagnostic.run_pipeline()`. See the file
# header for the full list of stripped symbols.
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# Arrow removal (pre-processing for contour detection)
# ---------------------------------------------------------------------------

def remove_arrows_from_green(
    image_path: str,
    green_boundary_px: np.ndarray,
    dark_threshold: int = 50,
    max_arrow_area: int = 600,
    min_contour_area: int = 800,
    debug_out: str | None = None,
) -> np.ndarray:
    """
    Remove slope-direction arrows from inside the green boundary, leaving the
    actual contour lines intact.

    The GolfLogix images contain two categories of dark marks inside the green:
      • Arrows — small, isolated, roughly uniform chevron-shaped marks arranged
        in a regular grid.  Each arrow is a compact blob of ~50–600 px².
      • Contour lines — long, thin, continuous curves spanning a significant
        portion of the green.  Each connected dark component is very large
        (hundreds to thousands of pixels).

    Algorithm
    ---------
    1. Restrict analysis to the green interior (polygon mask).
    2. Threshold to isolate dark pixels (value < dark_threshold in HSV space).
    3. Run connected-component analysis on the dark mask.
    4. Label components with area ≤ max_arrow_area as arrows; those with
       area ≥ min_contour_area as contour lines.
    5. Build an inpaint mask from the arrow pixels and run cv2.inpaint()
       so each arrow region is filled with plausible surrounding color.
    6. Optionally save a debug image to debug_out (or owner_inbox/ by default).

    Parameters
    ----------
    image_path          : Absolute path to the source PNG/JPG.
    green_boundary_px   : Nx2 float array of (x, y) polygon vertices in image
                          pixel coordinates (from interpolate_catmull_rom).
    dark_threshold      : HSV-Value cutoff — pixels with V < this value are
                          treated as "dark" candidates.  Default 80 (~31% brightness).
    max_arrow_area      : Connected dark components ≤ this area (px²) are
                          considered arrows and removed.  Default 600.
    min_contour_area    : Connected dark components ≥ this area (px²) are
                          kept as contour lines.  Components in between are
                          ambiguous and also removed (conservative).
    debug_out           : Path to save the debug PNG.  Defaults to
                          owner_inbox/debug_arrows_removed.png.

    Returns
    -------
    tuple[np.ndarray, np.ndarray]
        (cleaned_image, contour_keep_mask) where cleaned_image is a BGR image
        (same size as input) with arrows inpainted away, and contour_keep_mask
        is a uint8 binary mask (255 = contour blob pixel, 0 = background).
    """
    import cv2

    # ── Load image ──────────────────────────────────────────────────────────
    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(f"Cannot read image: {image_path}")

    h, w = img.shape[:2]

    # ── Build green interior mask ────────────────────────────────────────────
    # Draw the polygon filled white on a black background
    boundary_i = green_boundary_px.astype(np.int32)
    green_mask = np.zeros((h, w), dtype=np.uint8)
    cv2.fillPoly(green_mask, [boundary_i], 255)

    # ── Isolate dark pixels inside green ────────────────────────────────────
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    value_channel = hsv[:, :, 2]  # V in HSV

    # Dark = low value, AND inside the green boundary
    dark_mask = np.zeros((h, w), dtype=np.uint8)
    dark_mask[(value_channel < dark_threshold) & (green_mask == 255)] = 255

    # ── Connected-component analysis ────────────────────────────────────────
    n_labels, labels, stats, _ = cv2.connectedComponentsWithStats(
        dark_mask, connectivity=8
    )

    # stats columns: LEFT, TOP, WIDTH, HEIGHT, AREA
    arrow_paint_mask = np.zeros((h, w), dtype=np.uint8)
    contour_keep_mask = np.zeros((h, w), dtype=np.uint8)

    n_arrows = 0
    n_contours = 0
    n_ambiguous = 0

    for lbl in range(1, n_labels):  # skip background (label 0)
        area = int(stats[lbl, cv2.CC_STAT_AREA])
        component_mask = (labels == lbl).astype(np.uint8) * 255

        if area <= max_arrow_area:
            # Small blob → arrow → mark for inpainting
            arrow_paint_mask |= component_mask
            n_arrows += 1
        elif area >= min_contour_area:
            # Large blob → contour line → keep
            contour_keep_mask |= component_mask
            n_contours += 1
        else:
            # Ambiguous size — treat as arrow (conservative: remove)
            arrow_paint_mask |= component_mask
            n_ambiguous += 1

    print(
        f"[remove_arrows] Components: {n_arrows} arrows removed, "
        f"{n_contours} contour blobs kept, {n_ambiguous} ambiguous removed"
    )

    # ── Inpaint arrow pixels ─────────────────────────────────────────────────
    # Dilate the arrow mask slightly so the inpainter has full context at edges
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    inpaint_mask = cv2.dilate(arrow_paint_mask, kernel, iterations=1)

    cleaned = cv2.inpaint(img, inpaint_mask, inpaintRadius=5, flags=cv2.INPAINT_TELEA)

    # ── Save debug image ─────────────────────────────────────────────────────
    if debug_out is None:
        debug_out = os.path.join(OWNER_INBOX, "debug_arrows_removed.png")

    os.makedirs(os.path.dirname(debug_out), exist_ok=True)

    # Side-by-side: original (cropped to green bbox) | cleaned
    # Find bounding box of the green polygon for a tight crop
    x_min = max(0, int(boundary_i[:, 0].min()) - 10)
    y_min = max(0, int(boundary_i[:, 1].min()) - 10)
    x_max = min(w, int(boundary_i[:, 0].max()) + 10)
    y_max = min(h, int(boundary_i[:, 1].max()) + 10)

    orig_crop = img[y_min:y_max, x_min:x_max].copy()
    clean_crop = cleaned[y_min:y_max, x_min:x_max].copy()

    # Draw green boundary on both crops
    shifted_pts = boundary_i.copy()
    shifted_pts[:, 0] -= x_min
    shifted_pts[:, 1] -= y_min

    cv2.polylines(orig_crop, [shifted_pts], isClosed=True, color=(0, 255, 0), thickness=2)
    cv2.polylines(clean_crop, [shifted_pts], isClosed=True, color=(0, 255, 0), thickness=2)

    # Label panels
    label_h = 30
    panel_h = orig_crop.shape[0] + label_h
    panel_w = orig_crop.shape[1]
    panel_orig = np.zeros((panel_h, panel_w, 3), dtype=np.uint8)
    panel_clean = np.zeros((panel_h, panel_w, 3), dtype=np.uint8)
    panel_orig[label_h:, :] = orig_crop
    panel_clean[label_h:, :] = clean_crop
    cv2.putText(panel_orig, "Original", (5, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
    cv2.putText(panel_clean,
                f"Arrows removed ({n_arrows}+{n_ambiguous} blobs)",
                (5, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 128), 1)

    # Overlay: contour-kept blobs highlighted in cyan on the cleaned image
    overlay_crop = clean_crop.copy()
    contour_crop = contour_keep_mask[y_min:y_max, x_min:x_max]
    overlay_crop[contour_crop == 255] = (255, 200, 0)  # cyan highlight

    panel_overlay = np.zeros((panel_h, panel_w, 3), dtype=np.uint8)
    panel_overlay[label_h:, :] = overlay_crop
    cv2.putText(panel_overlay,
                f"Kept contour blobs ({n_contours})",
                (5, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 200, 0), 1)

    debug_img = np.hstack([panel_orig, panel_clean, panel_overlay])
    cv2.imwrite(debug_out, debug_img)
    print(f"[remove_arrows] Debug image saved: {debug_out}")

    return cleaned, contour_keep_mask


# ---------------------------------------------------------------------------
# Auto-contour extraction from blob mask
# ---------------------------------------------------------------------------

def extract_contour_polylines_from_mask(
    contour_keep_mask: np.ndarray,
    green_boundary_px: np.ndarray,
    dp_epsilon: float = 2.0,
    debug_out: str | None = None,
    source_image: np.ndarray | None = None,
) -> list[np.ndarray]:
    """
    Extract ordered polylines from the contour blob mask using row-midpoint
    centerlines.

    Algorithm
    ---------
    1. Run connected-component analysis on contour_keep_mask; keep blobs with
       area >= 800 px².
    2. For each blob, iterate over every row (y) that intersects it.  Find the
       leftmost and rightmost set pixel in that row and compute the midpoint x.
    3. Collect all (mid_x, y) midpoints into an ordered array (top → bottom).
    4. Smooth the x-coordinates with a moving average (window = 15).
    5. Simplify with Douglas-Peucker (epsilon = 6.0) for a clean polyline.
    6. Skip blobs that produce fewer than 10 midpoints.
    7. Save a debug image showing the extracted polylines on source_image.

    Parameters
    ----------
    contour_keep_mask   : uint8 binary mask of contour blobs (from arrow removal).
    green_boundary_px   : Nx2 float array of green polygon vertices in pixel
                          coords (used for debug overlay only).
    dp_epsilon          : Douglas-Peucker epsilon in pixels (default overridden
                          to 6.0 internally for clean results).
    debug_out           : Path to save debug PNG.  Defaults to
                          owner_inbox/debug_auto_contours.png.
    source_image        : BGR image used for the debug overlay.  If None, a
                          blank canvas is used.

    Returns
    -------
    list[np.ndarray]  Each element is an Nx2 float64 array of (x, y) pixel
                      coordinates forming one ordered contour polyline.
    """
    import cv2

    MIN_BLOB_AREA   = 800   # px² — ignore noise specks
    MIN_MIDPOINTS   = 10    # rows — skip blobs too thin to trace
    MA_WINDOW       = 15    # moving-average smoothing window (x only)
    DP_EPSILON      = 6.0   # Douglas-Peucker simplification

    h, w = contour_keep_mask.shape[:2]

    # ── 1. Connected-component analysis on the blob mask ─────────────────────
    n_labels, labels, stats, _ = cv2.connectedComponentsWithStats(
        contour_keep_mask, connectivity=8
    )

    polylines: list[np.ndarray] = []

    for lbl in range(1, n_labels):
        area = stats[lbl, cv2.CC_STAT_AREA]
        if area < MIN_BLOB_AREA:
            continue

        # ── 2. Row-midpoint centerline ────────────────────────────────────────
        blob_pixels = np.argwhere(labels == lbl)  # [[row, col], ...]

        row_min = blob_pixels[:, 0].min()
        row_max = blob_pixels[:, 0].max()

        midpoints: list[tuple[float, int]] = []

        for y in range(row_min, row_max + 1):
            cols_in_row = blob_pixels[blob_pixels[:, 0] == y, 1]
            if cols_in_row.size == 0:
                continue
            mid_x = (cols_in_row.min() + cols_in_row.max()) / 2.0
            midpoints.append((mid_x, y))

        # ── 3. Skip blobs with too few midpoints ──────────────────────────────
        if len(midpoints) < MIN_MIDPOINTS:
            continue

        pts = np.array(midpoints, dtype=np.float64)  # shape (N, 2): (x, y)

        # ── 4. Moving-average smoothing on x only ─────────────────────────────
        half = MA_WINDOW // 2
        xs = pts[:, 0]
        xs_padded = np.pad(xs, (half, half), mode='edge')
        xs_smooth = np.convolve(xs_padded, np.ones(MA_WINDOW) / MA_WINDOW, mode='valid')
        # convolve with 'valid' on padded input keeps the original length
        xs_smooth = xs_smooth[:len(xs)]
        pts[:, 0] = xs_smooth

        # ── 5. Douglas-Peucker simplification ─────────────────────────────────
        pts_i32 = pts.astype(np.int32).reshape(-1, 1, 2)
        simplified = cv2.approxPolyDP(pts_i32, epsilon=DP_EPSILON, closed=False)
        pts_simplified = simplified.reshape(-1, 2).astype(np.float64)

        if len(pts_simplified) < 2:
            continue

        polylines.append(pts_simplified)

    print(f"[extract_contours] row-midpoint: {len(polylines)} contour polyline(s) "
          f"from {n_labels - 1} blob(s) (area>={MIN_BLOB_AREA}px kept)")

    # ── Debug image ───────────────────────────────────────────────────────────
    if debug_out is None:
        debug_out = os.path.join(OWNER_INBOX, "debug_auto_contours.png")

    try:
        if source_image is not None:
            debug_base = source_image.copy()
        else:
            debug_base = np.zeros((h, w, 3), dtype=np.uint8)

        # Draw green boundary
        boundary_i = green_boundary_px.astype(np.int32)
        cv2.polylines(debug_base, [boundary_i], isClosed=True,
                      color=(0, 255, 0), thickness=2)

        # Draw each extracted polyline in a distinct color
        palette = [
            (0, 100, 255),    # orange
            (255, 50, 50),    # blue
            (50, 255, 50),    # green
            (0, 255, 255),    # yellow
            (255, 0, 255),    # magenta
            (255, 255, 0),    # cyan
            (200, 100, 50),   # steel blue
            (50, 200, 200),   # olive
        ]

        for i, poly_line in enumerate(polylines):
            color = palette[i % len(palette)]
            pts_i = poly_line.astype(np.int32).reshape(-1, 1, 2)
            cv2.polylines(debug_base, [pts_i], isClosed=False, color=color, thickness=2)
            # Mark endpoints
            p0 = tuple(poly_line[0].astype(int))
            p1 = tuple(poly_line[-1].astype(int))
            cv2.circle(debug_base, p0, 5, color, -1)
            cv2.circle(debug_base, p1, 5, color, -1)
            cv2.putText(debug_base, str(i), (p0[0] + 6, p0[1] - 6),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

        os.makedirs(os.path.dirname(debug_out), exist_ok=True)
        cv2.imwrite(debug_out, debug_base)
        print(f"[extract_contours] Debug image saved: {debug_out}")
    except Exception as exc:
        print(f"[extract_contours] Debug image failed: {exc}")

    return polylines


# ---------------------------------------------------------------------------
# File naming helpers
# ---------------------------------------------------------------------------

def _slugify(text: str) -> str:
    """Return a filesystem-safe lowercase slug."""
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = text.strip("_")
    return text


def _3mf_filename(course: str, hole: str, serial: int | None = None) -> str:
    """e.g. "Moffett Field (Hole 9) [105].3mf" (or without brackets if no serial)."""
    base = f"{course} (Hole {hole})"
    if serial is not None:
        return f"{base} [{serial}].3mf"
    return f"{base}.3mf"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_from_egm(
    egm_data: dict[str, Any],
    output_dir: str | None = None,
    print_size_mm: float = PRINT_SIZE_MM,
    thickness_override: dict[str, float] | None = None,
) -> list[dict[str, str]]:
    """
    Generate one combined 3MF from EGM boundary data, containing the green,
    fringe ring, and all trap/obstacle polygons.

    Parameters
    ----------
    egm_data         : Parsed EGM JSON (same dict that the editor POSTs).
    output_dir       : Directory for output files.  Defaults to owner_inbox/.
    print_size_mm    : Largest printed dimension in mm (default 178 = 7 inches).
    thickness_override: Map of polygon type → thickness in mm (overrides defaults).

    Returns
    -------
    List of {"name": filename, "path": absolute_path, "type": "3mf"} dicts.
    """
    thickness_map = {**THICKNESS_BY_TYPE, **(thickness_override or {})}

    course = egm_data.get("course", "Unknown Course")
    hole = egm_data.get("hole", "0")

    # Resolve output directories: course-specific 3MFs/ and STLs/ folders.
    # If output_dir is explicitly passed, use it for both (backwards compat).
    _cpaths = course_paths(course)
    if output_dir is None:
        output_dir_3mf = _cpaths["3mfs"]
        output_dir_stl = _cpaths["stls"]
    else:
        output_dir_3mf = output_dir
        output_dir_stl = output_dir
    os.makedirs(output_dir_3mf, exist_ok=True)
    os.makedirs(output_dir_stl, exist_ok=True)

    image_size = egm_data.get("imageSize", {"width": 600, "height": 600})
    polygons = egm_data.get("polygons", [])
    contour_step_mm: float = float(egm_data.get("contourStep", 10.0))

    if not polygons:
        return []

    # Separate regular polygons from contour lines
    regular_polys = [p for p in polygons if p.get("type", "").lower() != "contour"]
    contour_polys = [p for p in polygons if p.get("type", "").lower() == "contour"]

    # --- 1. Interpolate all splines (regular polygons only) ---
    splines_px: list[np.ndarray] = []
    for poly in regular_polys:
        pts = poly.get("points", [])
        if len(pts) < 3:
            arr = np.array([[p["x"], p["y"]] for p in pts], dtype=np.float64)
        else:
            arr = interpolate_catmull_rom(pts)
        splines_px.append(arr)

    # Resolve source image path (for color-band scoring in stepped green)
    image_name = egm_data.get("image", "")
    image_path: str | None = None
    if image_name:
        # Check course Images/ folder first, then team_inbox as fallback
        paths = course_paths(course)
        for candidate_dir in (paths["images"],
                              os.path.join(os.path.dirname(__file__), "..", "team_inbox")):
            candidate = os.path.join(candidate_dir, image_name)
            if os.path.isfile(candidate):
                image_path = candidate
                break

    # --- 1b. Contour detection disabled — arrow-gradient Poisson surface is now
    #         the surface reconstruction method (see gradient_surface_diagnostic.py).
    #         Leaving old code commented out for reference. ---

    # --- 2. Compute scale/offset from image bounding box ---
    scale, offset = _compute_scale_and_offset(splines_px, image_size, print_size_mm)

    # --- 3. Convert regular polygon splines to mm ---
    splines_mm: list[np.ndarray] = [_to_mm(sp, scale, offset) for sp in splines_px]

    # --- 3b. Contour polylines disabled — using gradient surface instead ---
    contour_lines_mm: list[np.ndarray] = []
    contour_directions: list[str] = []

    # --- 4. Build Shapely polygons for all pieces (needed for fringe subtraction) ---
    shapely_polys: list[ShapelyPolygon | None] = []
    for outline_mm in splines_mm:
        p = ShapelyPolygon(outline_mm)
        if not p.is_valid:
            p = p.buffer(0)
        shapely_polys.append(p if (p.is_valid and not p.is_empty) else None)

    # --- 5. Identify green and trap Shapely polygons ---
    green_shapely: ShapelyPolygon | None = None
    green_outline_mm: np.ndarray | None = None
    trap_shapely_list: list[ShapelyPolygon] = []

    for poly, sp, outline_mm in zip(regular_polys, shapely_polys, splines_mm):
        if sp is None:
            continue
        ptype = poly.get("type", "").lower()
        if ptype == "green" and green_shapely is None:
            green_shapely = sp
            green_outline_mm = outline_mm
        elif ptype == "trap":
            trap_shapely_list.append(sp)

    # --- 6. Build meshes and assemble scene ---
    generated: list[dict[str, str]] = []
    scene = trimesh.scene.scene.Scene()
    name_counts: dict[str, int] = {}

    def _add_to_scene(mesh: trimesh.Trimesh, label: str) -> None:
        obj_label = label
        if obj_label in name_counts:
            name_counts[obj_label] += 1
            obj_label = f"{label} ({name_counts[obj_label]})"
        else:
            name_counts[obj_label] = 0
        scene.add_geometry(mesh, node_name=obj_label, geom_name=obj_label)
        wt = "watertight" if mesh.is_watertight else "NOT watertight"
        bb = mesh.bounding_box.extents
        print(f"[generate_stl_3mf]   Added '{obj_label}': "
              f"{bb[0]:.1f} x {bb[1]:.1f} x {bb[2]:.1f} mm, {wt}")

    # Gradient surface (DEPRECATED 2026-05-07): the arrow-detection + Poisson
    # build that previously ran here has been removed; the live pipeline is
    # now `gradient_surface_diagnostic.run_pipeline()`. The state vars are
    # kept set to None so the downstream conditionals naturally fall through
    # to the flat-slab / stepped-contour code paths.
    _gradient_smooth_mesh: trimesh.Trimesh | None = None
    _gradient_stepped_mesh: trimesh.Trimesh | None = None

    # Build and add each polygon mesh
    for poly, sp_px, outline_mm in zip(regular_polys, splines_px, splines_mm):
        poly_name = poly.get("name", "Region")
        poly_type = poly.get("type", "").lower()
        thickness = thickness_map.get(poly_type, DEFAULT_THICKNESS)

        # Inset outline by PRINT_TOLERANCE_MM for easier fit between pieces
        inset_poly = ShapelyPolygon(outline_mm).buffer(-PRINT_TOLERANCE_MM)
        if inset_poly.is_empty or not hasattr(inset_poly, 'exterior'):
            print(f"[generate_stl_3mf] WARNING: inset eliminated '{poly_name}' — skipping.")
            continue
        outline_mm_inset = np.array(inset_poly.exterior.coords, dtype=np.float64)

        try:
            # NOTE: gradient (Poisson) green surface branch removed 2026-05-07.
            # Green-surface generation is now handled by
            # `gradient_surface_diagnostic.run_pipeline()`.
            if poly_type == "green" and contour_lines_mm:
                # Legacy: stepped surface from drawn contour lines
                print(f"[generate_stl_3mf] Building stepped green with "
                      f"{len(contour_lines_mm)} contour line(s), step={contour_step_mm}mm")
                mesh_tm = _build_stepped_green(
                    outline_mm_inset,
                    contour_lines_mm,
                    contour_directions,
                    thickness,
                    contour_step_mm,
                    image_path=image_path,
                    scale=scale,
                    offset=offset,
                )
            else:
                mesh_tm = _build_flat_slab(outline_mm_inset, thickness)
        except Exception as exc:
            print(f"[generate_stl_3mf] WARNING: skipping polygon '{poly_name}': {exc}")
            continue

        _add_to_scene(mesh_tm, poly_name)

    # --- 7. Build and add fringe ring ---
    if green_shapely is not None:
        fringe_thickness = thickness_map.get("fringe", THICKNESS_BY_TYPE["fringe"])
        fringe_mesh = _build_fringe(green_shapely, trap_shapely_list, fringe_thickness)
        if fringe_mesh is not None:
            _add_to_scene(fringe_mesh, "Fringe")
    else:
        print("[generate_stl_3mf] WARNING: no green polygon found — skipping fringe.")

    # --- 8. Export combined 3MF and individual STLs ---
    base_slug = _slugify(f"{course}_hole_{hole}")
    if len(scene.geometry) > 0:
        try:
            from serial_engraver import peek_next_serial as _peek_serial
            _serial = _peek_serial(course)
        except Exception:
            _serial = None
        fname_3mf = _3mf_filename(course, hole, serial=_serial)
        path_3mf = os.path.join(output_dir_3mf, fname_3mf)
        scene.export(path_3mf)
        generated.append({"name": fname_3mf, "path": path_3mf, "type": "3mf"})
        print(f"[generate_stl_3mf] Written 3MF: {path_3mf}")

        # Export each scene object as an individual STL
        # (the green in the scene is the smooth gradient mesh)
        for geom_name, mesh in scene.geometry.items():
            stl_name = f"{base_slug}_{_slugify(geom_name)}.stl"
            stl_path = os.path.join(output_dir_stl, stl_name)
            mesh.export(stl_path)
            generated.append({"name": stl_name, "path": stl_path, "type": "stl"})
            print(f"[generate_stl_3mf]   STL: {stl_name}")

        print(f"[generate_stl_3mf] Scene contains {len(scene.geometry)} object(s): "
              f"{', '.join(scene.geometry.keys())}")

    # --- 8b. Gradient-surface STL exports (DEPRECATED 2026-05-07) ---
    # The smooth/stepped green STL exports that previously lived here required
    # `_build_gradient_green`, which was stripped. Green-surface generation is
    # now owned by `gradient_surface_diagnostic.run_pipeline()`. The branch is
    # left as a no-op so the rest of the function (flat slabs, fringe, traps,
    # 3MF assembly) continues to work for any non-pipeline callers.
    _ = (_gradient_smooth_mesh, _gradient_stepped_mesh)  # silence unused-var

    return generated


def generate_from_egm_file(
    egm_path: str,
    output_dir: str | None = None,
    **kwargs,
) -> list[dict[str, str]]:
    """Convenience wrapper: load an .egm file and call generate_from_egm()."""
    with open(egm_path) as f:
        data = json.load(f)
    return generate_from_egm(data, output_dir=output_dir, **kwargs)


# ---------------------------------------------------------------------------
# CLI helper
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python generate_stl_3mf.py <path/to/file.egm> [output_dir]")
        sys.exit(1)

    egm_path = sys.argv[1]
    out_dir = sys.argv[2] if len(sys.argv) > 2 else None
    results = generate_from_egm_file(egm_path, output_dir=out_dir)
    print("\nGenerated files:")
    for r in results:
        print(f"  [{r['type'].upper():3s}] {r['path']}")
