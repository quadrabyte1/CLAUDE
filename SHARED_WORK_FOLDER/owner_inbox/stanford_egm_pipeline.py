"""
stanford_egm_pipeline.py — Topo GPS-to-EGM pipeline for Stanford (8).gps
Derives a plaque-quality EGM from the GPS point cloud (no contour image).

Stages:
  1. Load + project GPS data to local ENU metres
  2. Isolate the green (easternmost ~50 m, altitude < 41 m)
  3. Build green polygon via alpha-shape / convex hull fallback
  4. Map green polygon to image space (945x1500) for EGM JSON
  5. Render: plaque-quality top-down preview PNG
  6. Render: tee-to-green context PNG (full-hole 3D)
  7. Write EGM JSON
  8. Emit summary statistics for handoff doc

v0.1 — 2026-09-18 — Topo
No emojis. Do not modify source .gps file.
"""

import json
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.colors as mcolors
import matplotlib.cm as cm
from matplotlib.patches import Polygon as MplPolygon
from matplotlib.collections import PatchCollection
import matplotlib.patheffects as pe
import numpy as np
from scipy.interpolate import griddata
from scipy.ndimage import gaussian_filter
from scipy.spatial import ConvexHull

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE = Path("/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER")
GPS_FILE  = BASE / "ItWentIn/GolfCourses/Stanford/GolfIntelligence/Stanford (8).gps"
COURSE_DIR = BASE / "ItWentIn/GolfCourses/Stanford"
EGM_OUT   = COURSE_DIR / "EGMs/Stanford (Hole 8).egm"
IMG_OUT_PLAQUE  = COURSE_DIR / "Images/Stanford (Hole 8) plaque preview.png"
IMG_OUT_CONTEXT = COURSE_DIR / "Images/Stanford (Hole 8) tee-to-green context.png"

# ── Constants ──────────────────────────────────────────────────────────────────
LAT_M_PER_DEG = 111_320.0
REF_LAT_DEG   = 37.42383242       # Stanford site latitude
LNG_M_PER_DEG = 111_320.0 * math.cos(math.radians(REF_LAT_DEG))   # ~88 470 m

# Green isolation criterion:
#   "The N easternmost points (east_m >= east_max - GREEN_EAST_WINDOW_M)
#    within altitude < GREEN_ALT_CEILING_M.
#    This captures the geohash cells that topographically occupy the
#    low flat area at the east end of the fairway corridor — the
#    canonical GPS signature of a par-4 green approach."
GREEN_EAST_WINDOW_M = 50.0    # how many metres back from the east edge to include
GREEN_ALT_CEILING_M = 41.0    # altitude ceiling to exclude fairway shoulder rise

# Image dimensions (must match the existing Stanford (Hole 8).png)
IMG_W = 945
IMG_H = 1500

VERSION = "v0.1"
DATE    = "2026-09-18"
BADGE   = f"Stanford Hole 8 EGM {VERSION} — {DATE} — Topo"

# EGM render rules (from project_golf_render_rules memory):
#   - green never capped
#   - fringe/traps: 9 mm cap only within ~1 mm of frame edge
#   - plaque 3-line shift applied
#   - this hole has no water, so water-hole rule not triggered
EGM_PARAMS = {
    "course":               "Stanford",
    "hole":                 "8",
    "image":                "Stanford (Hole 8).png",
    "imageCourse":          "Stanford",
    "imageSize":            {"width": IMG_W, "height": IMG_H},
    "contourStep":          0.5,
    "grassAmplitude":       0.5,
    "grassSpacing":         2.4,
    "greenStyle":           "terraced",
    "elevationRange":       16,
    "greenScale":           1.0,
    "fringeEdgeHeight":     9,      # 9 mm fringe cap per render rule
    "baseThicknessMm":      2.0,    # >= 2 mm per render rule (no water but safe default)
    "includeBoundaryRegion": False,
    "applyFringeFrameCap":  True,
    "flagOffsetXMm":        0,
    "flagOffsetYMm":        0,
}

# ── Stage 1: Parse GPS data ────────────────────────────────────────────────────
def load_gps_points(path: Path) -> list:
    raw = path.read_text(encoding="utf-8", errors="replace")
    lines = raw.splitlines()
    json_start = next(
        i for i, l in enumerate(lines) if l.strip().startswith("{")
    )
    data = json.loads("\n".join(lines[json_start:]))
    coord_list = next(
        v for v in data.values()
        if isinstance(v, list) and len(v) > 0 and "gpsCoordinate" in v[0]
    )
    print(f"  Loaded {len(coord_list)} GPS points")
    return coord_list


def project_to_enu(coord_list: list) -> np.ndarray:
    """Return Nx3 array [east_m, north_m, alt_m] in local ENU frame."""
    lats = np.array([e["gpsCoordinate"]["latitude"]  for e in coord_list])
    lngs = np.array([e["gpsCoordinate"]["longitude"] for e in coord_list])
    alts = np.array([e["gpsCoordinate"]["altitude"]  for e in coord_list])

    origin_lat = lats.min()
    origin_lng = lngs.min()

    north_m = (lats - origin_lat) * LAT_M_PER_DEG
    east_m  = (lngs - origin_lng) * LNG_M_PER_DEG

    print(f"  Alt range   : {alts.min():.2f} - {alts.max():.2f} m")
    print(f"  East extent : {east_m.max() - east_m.min():.1f} m")
    print(f"  North extent: {north_m.max() - north_m.min():.1f} m")

    return np.column_stack([east_m, north_m, alts])


# ── Stage 2: Isolate green ─────────────────────────────────────────────────────
def isolate_green(pts: np.ndarray) -> np.ndarray:
    """
    Green isolation criterion:
      All GPS points in the easternmost GREEN_EAST_WINDOW_M metres of
      the corridor whose altitude is below GREEN_ALT_CEILING_M.

    Rationale: the par-4 green at Stanford Hole 8 is the lowest and
    easternmost feature of the fairway corridor.  The 50-m east window
    captures the geohash-grid cells that straddle the green surface.
    The 41 m altitude ceiling excludes shoulder/bunker rise on the
    western edges of that region.

    Thomas can override by changing GREEN_EAST_WINDOW_M / GREEN_ALT_CEILING_M
    at the top of this file.
    """
    east_max = pts[:, 0].max()
    mask = (pts[:, 0] >= east_max - GREEN_EAST_WINDOW_M) & (pts[:, 2] < GREEN_ALT_CEILING_M)
    green_pts = pts[mask]
    print(f"\n  Green isolation: {mask.sum()} points (east>={east_max - GREEN_EAST_WINDOW_M:.1f} m, alt<{GREEN_ALT_CEILING_M} m)")
    print(f"    East range : {green_pts[:,0].min():.1f} - {green_pts[:,0].max():.1f} m ({green_pts[:,0].max()-green_pts[:,0].min():.1f} m wide)")
    print(f"    North range: {green_pts[:,1].min():.1f} - {green_pts[:,1].max():.1f} m ({green_pts[:,1].max()-green_pts[:,1].min():.1f} m deep)")
    print(f"    Alt range  : {green_pts[:,2].min():.2f} - {green_pts[:,2].max():.2f} m (spread {green_pts[:,2].max()-green_pts[:,2].min():.2f} m)")
    return green_pts


# ── Stage 3: Build green polygon ───────────────────────────────────────────────
def build_green_polygon(green_pts: np.ndarray) -> np.ndarray:
    """
    Compute the convex hull of the green point cloud (east, north only).
    Returns Nx2 array of [east_m, north_m] polygon vertices in CCW order.

    We use convex hull as a conservative first approximation — it encloses
    all sampled cells.  The geohash grid is ~5 m resolution; the real green
    boundary lies roughly at the convex hull perimeter.  A more precise
    concave (alpha-shape) boundary requires labeled ground-truth.
    """
    xy = green_pts[:, :2]   # east, north
    hull = ConvexHull(xy)
    hull_pts = xy[hull.vertices]
    print(f"\n  Green convex hull: {len(hull_pts)} vertices")
    return hull_pts


# ── Stage 4: Map GPS polygon to image coordinates ─────────────────────────────
def gps_to_image_coords(
    green_hull_m: np.ndarray,
    all_pts: np.ndarray,
    img_w: int = IMG_W,
    img_h: int = IMG_H,
    margin: float = 60.0,
) -> list:
    """
    Project GPS east/north polygon to image pixel coordinates.

    The existing Stanford (Hole 8).png is a top-down approach view with
    the green at the top and the tee at the bottom (y=0 = north end of
    the green, y=img_h = south edge of the image).

    EGM pixel convention: origin top-left, x=east, y=south (image-down).
    We scale the green polygon to fill the central portion of the image
    with 'margin' pixels of padding on each side.
    """
    # Use the green cluster bounding box as the reference extent for the image
    e_min = green_hull_m[:, 0].min()
    e_max = green_hull_m[:, 0].max()
    n_min = green_hull_m[:, 1].min()
    n_max = green_hull_m[:, 1].max()

    # Add a generous margin so the polygon doesn't kiss the image edges
    e_pad = (e_max - e_min) * 0.4
    n_pad = (n_max - n_min) * 0.4

    e_lo = e_min - e_pad
    e_hi = e_max + e_pad
    n_lo = n_min - n_pad
    n_hi = n_max + n_pad

    def to_px(east, north):
        # east -> x (left to right), north -> y (top = high north)
        x = margin + (east - e_lo) / (e_hi - e_lo) * (img_w - 2 * margin)
        y = margin + (n_hi - north) / (n_hi - n_lo) * (img_h - 2 * margin)
        return {"x": round(float(x), 1), "y": round(float(y), 1)}

    polygon_px = [to_px(e, n) for e, n in green_hull_m]
    print(f"\n  Image polygon ({len(polygon_px)} pts):")
    for p in polygon_px:
        print(f"    ({p['x']:.0f}, {p['y']:.0f})")
    return polygon_px


# ── Stage 5: Build green heightmap for plaque view ────────────────────────────
def build_green_heightmap(green_pts: np.ndarray, grid_res: int = 60):
    """
    Interpolate a fine heightmap over the isolated green cluster.
    Returns (GE, GN, GZ) on a grid_res x grid_res grid.
    """
    east  = green_pts[:, 0]
    north = green_pts[:, 1]
    alt   = green_pts[:, 2]

    ei = np.linspace(east.min(), east.max(), grid_res)
    ni = np.linspace(north.min(), north.max(), grid_res)
    GE, GN = np.meshgrid(ei, ni)

    try:
        GZ = griddata((east, north), alt, (GE, GN), method="cubic")
        if np.isnan(GZ).mean() > 0.5:
            raise RuntimeError("Cubic > 50% NaN, fall back to linear")
    except Exception as exc:
        print(f"  WARNING: {exc}")
        GZ = griddata((east, north), alt, (GE, GN), method="linear")

    # Fill remaining NaN edges with nearest-neighbor
    if np.isnan(GZ).any():
        GZ_fill = griddata((east, north), alt, (GE, GN), method="nearest")
        mask = np.isnan(GZ)
        GZ[mask] = GZ_fill[mask]

    # Smooth lightly after interpolation
    GZ = gaussian_filter(GZ, sigma=1.0)
    return GE, GN, GZ


# ── Stage 6: Render plaque preview PNG ────────────────────────────────────────
def render_plaque_preview(
    green_pts: np.ndarray,
    green_hull_m: np.ndarray,
    GE, GN, GZ,
    out_path: Path,
):
    """
    Top-down EGM-style plaque preview: contour-filled heightmap of the
    isolated green, green polygon boundary overlaid, GPS points shown.
    Matches the 'plaque preview' style used for EGM renders.
    """
    fig, ax = plt.subplots(figsize=(7, 10), dpi=150)
    fig.patch.set_facecolor("#1a2a1a")
    ax.set_facecolor("#1a2a1a")

    # Filled contours of the green heightmap
    levels = np.linspace(GZ.min(), GZ.max(), 28)
    cf = ax.contourf(GE, GN, GZ, levels=levels, cmap="YlGn", alpha=0.92, zorder=1)

    # Contour lines (iso-elevation)
    cs = ax.contour(GE, GN, GZ, levels=levels[::3], colors="white", linewidths=0.4,
                    alpha=0.55, zorder=2)

    # Green polygon boundary
    hull_closed = np.vstack([green_hull_m, green_hull_m[0]])
    ax.plot(hull_closed[:, 0], hull_closed[:, 1], color="#ffffff", linewidth=1.8,
            linestyle="--", zorder=4, alpha=0.85, label="Green boundary (convex hull)")

    # GPS points coloured by altitude
    sc = ax.scatter(
        green_pts[:, 0], green_pts[:, 1], c=green_pts[:, 2],
        cmap="YlGn", s=22, zorder=5, edgecolors="#333333", linewidths=0.3,
        vmin=GZ.min(), vmax=GZ.max()
    )

    # Colorbar
    cbar = fig.colorbar(sc, ax=ax, shrink=0.45, pad=0.02)
    cbar.set_label("Altitude (m ASL)", color="white", fontsize=9)
    cbar.ax.yaxis.set_tick_params(color="white")
    plt.setp(cbar.ax.yaxis.get_ticklabels(), color="white")

    # Annotations
    ax.set_xlabel("East (m)", color="white", fontsize=9)
    ax.set_ylabel("North (m)", color="white", fontsize=9)
    ax.tick_params(colors="white")
    for spine in ax.spines.values():
        spine.set_edgecolor("#444444")

    ax.set_title(
        "Stanford Golf — Hole 8\nGreen Region — Plaque Preview\n"
        f"GPS-derived green polygon | {len(green_pts)} pts | {GREEN_EAST_WINDOW_M:.0f} m east window",
        color="white", fontsize=10, pad=10,
    )
    ax.legend(loc="lower right", fontsize=7, facecolor="#2a3a2a",
              edgecolor="#555555", labelcolor="white")

    # Arrow indicating N (north up)
    ax.annotate("", xy=(GE.min() + 3, GN.max() - 2), xytext=(GE.min() + 3, GN.max() - 8),
                arrowprops=dict(arrowstyle="->", color="white", lw=1.5))
    ax.text(GE.min() + 3, GN.max() - 0.5, "N", color="white", fontsize=8, ha="center")

    # Version badge upper-left (house rule)
    fig.text(
        0.01, 0.99, BADGE,
        fontsize=7, va="top", ha="left", color="white",
        bbox=dict(facecolor="#222222", alpha=0.85, pad=3, edgecolor="none"),
        transform=fig.transFigure,
    )

    fig.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"  Plaque preview saved: {out_path}")


# ── Stage 7: Render tee-to-green context PNG ──────────────────────────────────
def render_tee_to_green_context(
    all_pts: np.ndarray,
    green_pts: np.ndarray,
    out_path: Path,
):
    """
    Wide-view 3D render of the full hole: interpolated surface coloured by
    altitude, GPS points overlaid, tee cluster and green cluster highlighted
    with distinct markers and labels.
    """
    from mpl_toolkits.mplot3d import Axes3D  # noqa: F401

    VERT_EXAG = 6.0
    GRID_RES  = 100

    east  = all_pts[:, 0]
    north = all_pts[:, 1]
    alt   = all_pts[:, 2]

    # Build full-hole surface — use linear interpolation (more stable for sparse
    # geohash grid) with post-smoothing to eliminate staircase artifacts.
    ei = np.linspace(east.min(), east.max(), GRID_RES)
    ni = np.linspace(north.min(), north.max(), GRID_RES)
    GE, GN = np.meshgrid(ei, ni)

    GZ = griddata((east, north), alt, (GE, GN), method="linear")

    if np.isnan(GZ).any():
        GZ_fill = griddata((east, north), alt, (GE, GN), method="nearest")
        mask_nan = np.isnan(GZ)
        GZ[mask_nan] = GZ_fill[mask_nan]

    # Smooth after interpolation to reduce the geohash staircase effect
    GZ = gaussian_filter(GZ, sigma=1.5)

    GZ_exag = (GZ - GZ.min()) * VERT_EXAG

    # Classify tee vs green vs fairway
    east_max  = east.max()
    east_min  = east.min()
    tee_mask   = alt >= 55.0                                           # elevated tee cluster
    green_mask = (east >= east_max - GREEN_EAST_WINDOW_M) & (alt < GREEN_ALT_CEILING_M)
    fair_mask  = ~tee_mask & ~green_mask

    fig = plt.figure(figsize=(16, 9), dpi=150)
    ax  = fig.add_subplot(111, projection="3d")

    # Surface
    norm_surf = mcolors.Normalize(vmin=GZ.min(), vmax=GZ.max())
    surf = ax.plot_surface(
        GE, GN, GZ_exag,
        facecolors=cm.terrain(norm_surf(GZ)),
        alpha=0.60,
        linewidth=0,
        antialiased=True,
    )

    # Fairway points
    alt_exag_fair = (alt[fair_mask] - alt.min()) * VERT_EXAG
    ax.scatter(east[fair_mask], north[fair_mask], alt_exag_fair,
               c=alt[fair_mask], cmap="terrain", vmin=alt.min(), vmax=alt.max(),
               s=14, alpha=0.5, edgecolors="none", zorder=3)

    # Green points (highlighted)
    alt_exag_green = (alt[green_mask] - alt.min()) * VERT_EXAG
    ax.scatter(east[green_mask], north[green_mask], alt_exag_green,
               c="#22cc66", s=38, zorder=6, edgecolors="white", linewidths=0.6,
               label=f"Green region ({green_mask.sum()} pts, ~{alt[green_mask].mean():.1f} m)")

    # Tee points (highlighted)
    alt_exag_tee = (alt[tee_mask] - alt.min()) * VERT_EXAG
    ax.scatter(east[tee_mask], north[tee_mask], alt_exag_tee,
               c="#ff8800", s=55, marker="^", zorder=6, edgecolors="white", linewidths=0.6,
               label=f"Tee cluster ({tee_mask.sum()} pts, ~{alt[tee_mask].mean():.1f} m)")

    # Elevation annotations
    tee_center_e  = east[tee_mask].mean()
    tee_center_n  = north[tee_mask].mean()
    tee_center_z  = (alt[tee_mask].mean() - alt.min()) * VERT_EXAG
    grn_center_e  = east[green_mask].mean()
    grn_center_n  = north[green_mask].mean()
    grn_center_z  = (alt[green_mask].mean() - alt.min()) * VERT_EXAG

    ax.text(tee_center_e, tee_center_n, tee_center_z + 30,
            f"TEE\n~{alt[tee_mask].mean():.0f} m ASL",
            color="#ff8800", fontsize=9, ha="center", fontweight="bold",
            path_effects=[pe.withStroke(linewidth=2, foreground="black")])

    ax.text(grn_center_e, grn_center_n, grn_center_z + 30,
            f"GREEN\n~{alt[green_mask].mean():.0f} m ASL",
            color="#22cc66", fontsize=9, ha="center", fontweight="bold",
            path_effects=[pe.withStroke(linewidth=2, foreground="black")])

    # Elevation drop callout
    elev_diff = alt[tee_mask].mean() - alt[green_mask].mean()
    dist_m = math.sqrt(
        (east[tee_mask].mean() - east[green_mask].mean()) ** 2 +
        (north[tee_mask].mean() - north[green_mask].mean()) ** 2
    )
    fig.text(
        0.65, 0.88,
        f"Tee-to-green drop: ~{elev_diff:.0f} m over ~{dist_m:.0f} m horizontal",
        fontsize=10, color="white",
        bbox=dict(facecolor="#333333", alpha=0.75, pad=5, edgecolor="#888888"),
        transform=fig.transFigure,
    )

    # Colorbar
    sm = plt.cm.ScalarMappable(cmap="terrain", norm=norm_surf)
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, shrink=0.45, pad=0.08)
    cbar.set_label("Altitude (m, real scale)", fontsize=9)

    ax.set_xlabel("East (m)", fontsize=9, labelpad=6)
    ax.set_ylabel("North (m)", fontsize=9, labelpad=6)
    ax.set_zlabel(f"Alt x{VERT_EXAG:.0f} (exag.)", fontsize=9)
    ax.set_title(
        f"Stanford Golf — Hole 8 — Tee-to-Green Context\n"
        f"351 GPS pts | Vert. exag. x{VERT_EXAG:.0f} | "
        f"Tee {alt[tee_mask].max():.0f} m -> Green {alt[green_mask].min():.0f} m ASL",
        fontsize=11, pad=12,
    )
    ax.legend(loc="upper right", fontsize=8)

    # View angle: looking from S toward N — tee cluster (NW) on left-rear,
    # green (east) on right-front.  elev=28 flattens the terrain just enough
    # to make the fairway descent from tee to green read clearly.
    ax.view_init(elev=28, azim=-70)

    # Version badge upper-left
    fig.text(
        0.01, 0.99, BADGE,
        fontsize=7, va="top", ha="left", color="white",
        bbox=dict(facecolor="#222222", alpha=0.85, pad=3, edgecolor="none"),
        transform=fig.transFigure,
    )

    fig.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Tee-to-green context saved: {out_path}")


# ── Stage 8: Write EGM JSON ────────────────────────────────────────────────────
def write_egm(polygon_px: list, out_path: Path):
    """
    Writes the EGM JSON file matching the Firefly/Stanford EGM format.
    Polygon vertices are derived from the GPS point cloud convex hull.
    No trap polygon in this GPS-derived version (GPS cells do not
    resolve individual bunker shapes; trap positions would need a
    hand-edited overlay or a separate labeled dataset).
    """
    egm = dict(EGM_PARAMS)
    egm["polygons"] = [
        {
            "name": "Green",
            "type": "green",
            "closed": True,
            "points": polygon_px,
        }
        # Note: trap/fringe polygons omitted — GPS cell resolution (~5 m)
        # is insufficient to reliably discriminate bunker from rough.
        # Thomas can add trap polygons manually in the EGM editor.
    ]
    egm["elevationSpikes"] = []
    egm["tee_hole"] = {"x_mm": 0, "y_mm": 0}   # default; override after plaque print

    out_path.write_text(json.dumps(egm, indent=2) + "\n", encoding="utf-8")
    print(f"\n  EGM written: {out_path}")


# ── Stage 9: Print summary ─────────────────────────────────────────────────────
def print_summary(all_pts: np.ndarray, green_pts: np.ndarray, green_hull_m: np.ndarray):
    east  = all_pts[:, 0]
    north = all_pts[:, 1]
    alt   = all_pts[:, 2]

    tee_mask   = alt >= 55.0
    tee_alt    = alt[tee_mask]
    green_alt  = green_pts[:, 2]

    elev_diff = tee_alt.mean() - green_alt.mean()
    dist_m = math.sqrt(
        (east[tee_mask].mean() - green_pts[:, 0].mean()) ** 2 +
        (north[tee_mask].mean() - green_pts[:, 1].mean()) ** 2
    )

    print("\n=== Summary ===")
    print(f"  Total GPS points  : {len(all_pts)}")
    print(f"  Green pts         : {len(green_pts)}")
    print(f"  Green isolation   : east>={all_pts[:,0].max() - GREEN_EAST_WINDOW_M:.0f} m, alt<{GREEN_ALT_CEILING_M} m")
    print(f"  Green extent      : {green_pts[:,0].max()-green_pts[:,0].min():.1f} m E-W x "
          f"{green_pts[:,1].max()-green_pts[:,1].min():.1f} m N-S")
    print(f"  Green alt range   : {green_alt.min():.2f} - {green_alt.max():.2f} m "
          f"(spread {green_alt.max()-green_alt.min():.2f} m)")
    print(f"  Tee alt range     : {tee_alt.min():.2f} - {tee_alt.max():.2f} m")
    print(f"  Tee-to-green drop : ~{elev_diff:.0f} m over ~{dist_m:.0f} m horizontal")
    print(f"  Green hull verts  : {len(green_hull_m)}")
    print(f"  EGM render rules  : no-cap green, 9mm fringe cap (applyFringeFrameCap=true)")


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    print(f"\n=== Stanford EGM Pipeline {VERSION} ===\n")

    print("Stage 1: Loading + projecting GPS data...")
    coord_list = load_gps_points(GPS_FILE)
    all_pts = project_to_enu(coord_list)

    print("\nStage 2: Isolating green region...")
    green_pts = isolate_green(all_pts)

    print("\nStage 3: Building green polygon (convex hull)...")
    green_hull_m = build_green_polygon(green_pts)

    print("\nStage 4: Mapping to image coordinates...")
    polygon_px = gps_to_image_coords(green_hull_m, all_pts)

    print("\nStage 5: Building green heightmap...")
    GE, GN, GZ = build_green_heightmap(green_pts)

    print("\nStage 6: Rendering plaque preview PNG...")
    render_plaque_preview(green_pts, green_hull_m, GE, GN, GZ, IMG_OUT_PLAQUE)

    print("\nStage 7: Rendering tee-to-green context PNG...")
    render_tee_to_green_context(all_pts, green_pts, IMG_OUT_CONTEXT)

    print("\nStage 8: Writing EGM JSON...")
    write_egm(polygon_px, EGM_OUT)

    print_summary(all_pts, green_pts, green_hull_m)
    print("\nDone.")


if __name__ == "__main__":
    main()
