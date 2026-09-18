"""
stanford_gps_3d_pipeline.py — Topo pipeline for Stanford (8).gps
Converts 351 GPS points (Hole 8, Stanford University Golf Course) to:
  1. Static PNG (matplotlib Axes3D)
  2. Interactive HTML (plotly)
No image processing stage — we already have the point cloud.
v0.1 — 2026-09-18 — Topo
"""

import json
import math
import sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401
import matplotlib.colors as mcolors
from scipy.interpolate import griddata
import plotly.graph_objects as go
import plotly.io as pio

# ── Paths ─────────────────────────────────────────────────────────────────────
GPS_FILE = Path("/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/ItWentIn/GolfCourses/Stanford/GolfIntelligence/Stanford (8).gps")
INBOX = Path("/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/owner_inbox")
OUT_PNG = INBOX / "stanford_gps_3d.png"
OUT_HTML = INBOX / "stanford_gps_3d.html"
OUT_STL = INBOX / "stanford_gps_3d.stl"

# ── Constants ─────────────────────────────────────────────────────────────────
# At Stanford's latitude (~37.42 N):
#   1 degree latitude  ≈ 111,320 m
#   1 degree longitude ≈ 111,320 * cos(lat_rad) ≈ 88,500 m
LAT_M_PER_DEG = 111_320.0
REF_LAT_DEG = 37.42383242  # approximate center / origin
LNG_M_PER_DEG = 111_320.0 * math.cos(math.radians(REF_LAT_DEG))  # ≈ 88,470 m

VERT_EXAG = 10.0          # vertical exaggeration factor
GRID_RES = 100            # interpolation grid: 100×100
VERSION = "v0.1"
DATE = "2026-09-18"

# ── Stage 1: Parse GPS file ───────────────────────────────────────────────────
def load_gps_points(path: Path) -> list[dict]:
    """Skip UI cruft (first 36 lines), find JSON start, parse robustly."""
    raw_text = path.read_text(encoding="utf-8", errors="replace")
    lines = raw_text.splitlines()
    # Find first line that starts with '{'
    json_start = None
    for i, line in enumerate(lines):
        if line.strip().startswith("{"):
            json_start = i
            break
    if json_start is None:
        raise ValueError("No JSON object found in file")
    json_text = "\n".join(lines[json_start:])
    data = json.loads(json_text)
    print(f"  Parsed JSON with top-level keys: {list(data.keys())}")

    # Find the first list-of-dicts whose entries contain 'gpsCoordinate'
    coord_list = None
    for key, val in data.items():
        if isinstance(val, list) and len(val) > 0 and isinstance(val[0], dict) and "gpsCoordinate" in val[0]:
            coord_list = val
            print(f"  Found coordinate array under key '{key}' with {len(val)} entries")
            break
    if coord_list is None:
        raise ValueError("Could not locate gpsCoordinate list in JSON")
    return coord_list


# ── Stage 2: Extract + project to local ENU (meters) ─────────────────────────
def extract_and_project(coord_list: list[dict]) -> np.ndarray:
    """
    Returns Nx3 array: [east_m, north_m, alt_m].
    Origin = (min_lat, min_lng) — so all values are non-negative.
    """
    lats  = np.array([e["gpsCoordinate"]["latitude"]  for e in coord_list])
    lngs  = np.array([e["gpsCoordinate"]["longitude"] for e in coord_list])
    alts  = np.array([e["gpsCoordinate"]["altitude"]  for e in coord_list])

    origin_lat = lats.min()
    origin_lng = lngs.min()

    north_m = (lats - origin_lat) * LAT_M_PER_DEG
    east_m  = (lngs - origin_lng) * LNG_M_PER_DEG

    print(f"  Altitude range : {alts.min():.2f} – {alts.max():.2f} m  (spread {alts.max()-alts.min():.2f} m)")
    print(f"  East  range    : {east_m.min():.1f} – {east_m.max():.1f} m")
    print(f"  North range    : {north_m.min():.1f} – {north_m.max():.1f} m")

    return np.column_stack([east_m, north_m, alts])


# ── Stage 3: Interpolate surface ──────────────────────────────────────────────
def interpolate_surface(pts: np.ndarray, grid_res: int = GRID_RES):
    """
    Returns (grid_e, grid_n, grid_z) — arrays for imshow / plot_surface.
    Tries cubic first; falls back to linear on failure/NaN-overflow.
    """
    east  = pts[:, 0]
    north = pts[:, 1]
    alt   = pts[:, 2]

    ei = np.linspace(east.min(),  east.max(),  grid_res)
    ni = np.linspace(north.min(), north.max(), grid_res)
    GE, GN = np.meshgrid(ei, ni)

    try:
        GZ = griddata((east, north), alt, (GE, GN), method="cubic")
        nan_frac = np.isnan(GZ).mean()
        if nan_frac > 0.5:
            raise RuntimeError(f"Cubic interpolation produced {nan_frac*100:.0f}% NaN; falling back to linear")
        print(f"  Surface interpolation: cubic, NaN fraction = {nan_frac*100:.1f}%")
    except Exception as exc:
        print(f"  WARNING: {exc}")
        GZ = griddata((east, north), alt, (GE, GN), method="linear")
        nan_frac = np.isnan(GZ).mean()
        print(f"  Surface interpolation: linear, NaN fraction = {nan_frac*100:.1f}%")

    # Fill remaining NaN at edges with nearest-neighbor
    if np.isnan(GZ).any():
        GZ_fill = griddata((east, north), alt, (GE, GN), method="nearest")
        mask = np.isnan(GZ)
        GZ[mask] = GZ_fill[mask]
        print(f"  Edge NaNs filled with nearest-neighbor ({mask.sum()} cells)")

    return GE, GN, GZ


# ── Stage 4: Static PNG ───────────────────────────────────────────────────────
def make_png(pts: np.ndarray, GE, GN, GZ, out_path: Path):
    """Matplotlib Axes3D scatter + surface, colored by altitude."""
    alt   = pts[:, 2]
    alt_exag = alt - alt.min()

    GZ_exag = (GZ - GZ.min()) * VERT_EXAG

    fig = plt.figure(figsize=(14, 10))
    ax = fig.add_subplot(111, projection="3d")

    # Surface
    cmap_surf = plt.get_cmap("terrain")
    norm_surf = mcolors.Normalize(vmin=GZ.min(), vmax=GZ.max())
    surf = ax.plot_surface(
        GE, GN, GZ_exag,
        facecolors=cmap_surf(norm_surf(GZ)),
        alpha=0.65,
        linewidth=0,
        antialiased=True,
    )

    # Scatter points
    scatter_z = alt_exag * VERT_EXAG
    sc = ax.scatter(
        pts[:, 0], pts[:, 1], scatter_z,
        c=alt, cmap="terrain", s=18, zorder=5, edgecolors="none"
    )

    # Colorbar
    sm = plt.cm.ScalarMappable(cmap="terrain", norm=norm_surf)
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, shrink=0.5, pad=0.1)
    cbar.set_label("Altitude (m, real scale)")

    # Labels
    ax.set_xlabel("East (m)")
    ax.set_ylabel("North (m)")
    ax.set_zlabel(f"Altitude × {VERT_EXAG:.0f} (m exag.)")
    ax.set_title(
        f"Stanford Golf Course — Hole 8\n"
        f"351 GPS points | Vert. exag. ×{VERT_EXAG:.0f} | Alt. {alt.min():.1f}–{alt.max():.1f} m"
    )

    # Version badge upper-left
    fig.text(
        0.01, 0.97,
        f"{VERSION} · {DATE} · Topo",
        fontsize=8, va="top", ha="left",
        color="white",
        bbox=dict(facecolor="#333333", alpha=0.7, pad=3, edgecolor="none"),
    )

    fig.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  PNG saved: {out_path}")


# ── Stage 5: Interactive HTML ─────────────────────────────────────────────────
def make_html(pts: np.ndarray, GE, GN, GZ, out_path: Path):
    """Plotly Scatter3d scatter + Surface, user can rotate/zoom."""
    alt = pts[:, 2]
    GZ_exag = (GZ - GZ.min()) * VERT_EXAG
    alt_exag = (alt - alt.min()) * VERT_EXAG

    # Surface trace
    surface_trace = go.Surface(
        x=GE,
        y=GN,
        z=GZ_exag,
        surfacecolor=GZ,   # color by real altitude
        colorscale="Earth",
        opacity=0.7,
        name="Interpolated surface",
        colorbar=dict(title="Altitude (m)", x=1.02),
        showscale=True,
    )

    # Scatter trace
    scatter_trace = go.Scatter3d(
        x=pts[:, 0],
        y=pts[:, 1],
        z=alt_exag,
        mode="markers",
        marker=dict(
            size=3,
            color=alt,
            colorscale="Earth",
            showscale=False,
        ),
        name="GPS points",
        text=[f"Alt: {a:.2f} m" for a in alt],
        hoverinfo="text+x+y",
    )

    layout = go.Layout(
        title=dict(
            text=(
                f"Stanford Golf — Hole 8 | 351 GPS Points | "
                f"Vert. exag. ×{VERT_EXAG:.0f} | {VERSION} · {DATE} · Topo"
            ),
            x=0.02,
            xanchor="left",
            font=dict(size=13),
        ),
        scene=dict(
            xaxis_title="East (m)",
            yaxis_title="North (m)",
            zaxis_title=f"Alt ×{VERT_EXAG:.0f} (m exag.)",
            aspectmode="data",
        ),
        margin=dict(l=0, r=0, b=0, t=50),
    )

    fig = go.Figure(data=[surface_trace, scatter_trace], layout=layout)
    pio.write_html(fig, file=str(out_path), include_plotlyjs="cdn", full_html=True)
    print(f"  HTML saved: {out_path}")


# ── Stage 6: Optional STL (watertight heightmap mesh) ────────────────────────
def make_stl(GE, GN, GZ, pts, out_path: Path):
    """
    Build a watertight STL from the interpolated surface.
    Requires numpy-stl (stl.mesh). Skips gracefully if not available.
    """
    try:
        from stl import mesh as stl_mesh
    except ImportError:
        print("  numpy-stl not available — skipping STL export")
        return False

    rows, cols = GZ.shape
    # Build vertex grid: top surface
    verts = np.stack([GE.ravel(), GN.ravel(), GZ.ravel()], axis=1)

    # Build triangles for the top surface
    triangles = []
    def idx(r, c): return r * cols + c

    for r in range(rows - 1):
        for c in range(cols - 1):
            # Two triangles per grid cell
            triangles.append([idx(r,   c),   idx(r+1, c),   idx(r,   c+1)])
            triangles.append([idx(r+1, c),   idx(r+1, c+1), idx(r,   c+1)])

    triangles = np.array(triangles, dtype=np.int32)

    # Add bottom face and walls for watertight mesh
    base_z = GZ.min() - 2.0   # 2 m below minimum
    n_top_verts = len(verts)

    # Bottom vertices (same XY, flat Z)
    bottom_verts = verts.copy()
    bottom_verts[:, 2] = base_z
    all_verts = np.vstack([verts, bottom_verts])

    # Top face triangles (already built)
    # Bottom face triangles (reversed winding for outward normals)
    bottom_tris = triangles + n_top_verts
    bottom_tris[:, [1, 2]] = bottom_tris[:, [2, 1]]  # flip

    # Side walls: perimeter edges
    wall_tris = []
    # Top row (r=0)
    for c in range(cols - 1):
        t = idx(0, c);       tn = idx(0, c+1)
        b = t + n_top_verts; bn = tn + n_top_verts
        wall_tris += [[t, b, tn], [tn, b, bn]]
    # Bottom row (r=rows-1)
    for c in range(cols - 1):
        t = idx(rows-1, c);  tn = idx(rows-1, c+1)
        b = t + n_top_verts; bn = tn + n_top_verts
        wall_tris += [[t, tn, b], [tn, bn, b]]
    # Left col (c=0)
    for r in range(rows - 1):
        t = idx(r, 0);       tn = idx(r+1, 0)
        b = t + n_top_verts; bn = tn + n_top_verts
        wall_tris += [[t, tn, b], [tn, bn, b]]
    # Right col (c=cols-1)
    for r in range(rows - 1):
        t = idx(r, cols-1);  tn = idx(r+1, cols-1)
        b = t + n_top_verts; bn = tn + n_top_verts
        wall_tris += [[t, b, tn], [tn, b, bn]]

    all_tris = np.vstack([triangles, bottom_tris, np.array(wall_tris, dtype=np.int32)])

    # Build numpy-stl mesh
    mesh = stl_mesh.Mesh(np.zeros(len(all_tris), dtype=stl_mesh.Mesh.dtype))
    for i, tri in enumerate(all_tris):
        for j in range(3):
            mesh.vectors[i][j] = all_verts[tri[j]]

    mesh.save(str(out_path))
    print(f"  STL saved: {out_path}  ({len(all_tris)} triangles)")
    return True


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print(f"\n=== Stanford GPS 3D Pipeline {VERSION} ===\n")

    print("Stage 1: Loading GPS data...")
    coord_list = load_gps_points(GPS_FILE)

    print("\nStage 2: Projecting to ENU metres...")
    pts = extract_and_project(coord_list)

    print("\nStage 3: Interpolating surface...")
    GE, GN, GZ = interpolate_surface(pts)

    print("\nStage 4: Rendering static PNG...")
    make_png(pts, GE, GN, GZ, OUT_PNG)

    print("\nStage 5: Rendering interactive HTML...")
    make_html(pts, GE, GN, GZ, OUT_HTML)

    print("\nStage 6: Building STL (optional)...")
    stl_ok = make_stl(GE, GN, GZ, pts, OUT_STL)

    # Print summary stats for readme
    alt = pts[:, 2]
    east = pts[:, 0]
    north = pts[:, 1]
    print(f"\n=== Summary ===")
    print(f"  Points       : {len(pts)}")
    print(f"  Alt range    : {alt.min():.2f} – {alt.max():.2f} m  (spread {alt.max()-alt.min():.2f} m)")
    print(f"  East extent  : {east.max()-east.min():.1f} m")
    print(f"  North extent : {north.max()-north.min():.1f} m")
    print(f"  STL produced : {stl_ok}")

    # Flag any outlier altitudes (>3 std devs from mean)
    alt_mean = alt.mean()
    alt_std  = alt.std()
    outliers = np.where(np.abs(alt - alt_mean) > 3 * alt_std)[0]
    if len(outliers):
        print(f"\n  Outlier altitude points (>3σ from mean={alt_mean:.2f} m, σ={alt_std:.2f} m):")
        for idx in outliers:
            coord = coord_list[idx]["gpsCoordinate"]
            print(f"    idx={idx}  alt={coord['altitude']:.2f}  lat={coord['latitude']}  lng={coord['longitude']}")
    else:
        print(f"  No altitude outliers detected (mean={alt_mean:.2f} m, σ={alt_std:.2f} m)")

    print("\nDone.")


if __name__ == "__main__":
    main()
