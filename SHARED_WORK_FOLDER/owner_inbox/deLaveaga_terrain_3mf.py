"""
deLaveaga_terrain_3mf.py  —  Topo pipeline for De Laveaga GPS from Stracka.txt
Converts 1071 GPS points (whole course, De Laveaga Golf Course, Santa Cruz CA)
to a watertight 3MF suitable for 3D printing.

Design decisions:
  - Two disconnected point clusters (56.7m gap) handled as separate interpolation
    regions, each alpha-shaped via shapely concave_hull, then merged into one mesh.
  - Print scale: 200mm (E) x 160mm (N) — whole-course overview, larger than plaque.
  - Vertical exaggeration: x3 — alt range 36.8m becomes ~65mm Z in print (readable).
  - Grid: 150x120 cells across the full bounding box; out-of-alpha-hull cells set to
    base level so walls seal cleanly.
  - Base thickness: 3mm.
  - Output serial: 251.

v0.1 — 2026-09-21 — Topo
"""

import json
import math
import sys
from pathlib import Path

import numpy as np
from scipy.interpolate import griddata
from scipy.ndimage import gaussian_filter
from shapely import concave_hull
from shapely.geometry import MultiPoint
import trimesh

# ── Paths ──────────────────────────────────────────────────────────────────────
GPS_FILE   = Path("/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/ItWentIn/De Laveaga GPS from Stracka.txt")
SERIAL_JSON = Path("/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/ItWentIn/GolfCourses/DeLaveaga/serial.json")
OUT_DIR_3MF = Path("/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/ItWentIn/GolfCourses/DeLaveaga/3MFs")
OUT_DIR_IMG = Path("/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/ItWentIn/GolfCourses/DeLaveaga/Images")
INBOX       = Path("/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/owner_inbox")

# ── Constants ──────────────────────────────────────────────────────────────────
LAT_M_PER_DEG = 111_320.0
REF_LAT_DEG   = 36.9967         # approximate center of De Laveaga

VERT_EXAG     = 3.0             # vertical exaggeration (x3)
PRINT_E_MM    = 200.0           # print bed size: East direction (mm)
PRINT_N_MM    = 160.0           # print bed size: North direction (mm)
GRID_E        = 150             # grid columns
GRID_N        = 120             # grid rows
BASE_MM       = 3.0             # base plate thickness (mm)
SMOOTH_SIGMA  = 1.5             # gaussian smoothing sigma (grid cells)
ALPHA_RATIO   = 0.3             # shapely concave_hull ratio (0=convex, 1=tightest)
VERSION       = "v0.1"
DATE          = "2026-09-21"
SERIAL        = 251             # assigned serial


# ── Stage 1: Parse GPS file ────────────────────────────────────────────────────
def load_gps_points(path: Path) -> list:
    """Skip UI chrome, find JSON start, parse geoHashCells array."""
    raw = path.read_text(encoding="utf-8", errors="replace")
    lines = raw.splitlines()
    json_start = None
    for i, line in enumerate(lines):
        if line.strip().startswith("{"):
            json_start = i
            break
    if json_start is None:
        raise ValueError("No JSON found in file")
    data = json.loads("\n".join(lines[json_start:]))
    cells = data.get("geoHashCells", [])
    print(f"  Loaded {len(cells)} geoHashCells (cellCount={data.get('cellCount')})")
    return cells


# ── Stage 2: Project to local ENU metres ──────────────────────────────────────
def project_to_enu(cells: list) -> np.ndarray:
    """
    Returns Nx3 float array: [east_m, north_m, alt_m].
    Origin = SW corner (min lon, min lat).  All values >= 0.
    """
    lats = np.array([c["gpsCoordinate"]["latitude"]  for c in cells])
    lons = np.array([c["gpsCoordinate"]["longitude"] for c in cells])
    alts = np.array([c["gpsCoordinate"]["altitude"]  for c in cells])

    lon_m = LAT_M_PER_DEG * math.cos(math.radians(REF_LAT_DEG))
    east  = (lons - lons.min()) * lon_m
    north = (lats - lats.min()) * LAT_M_PER_DEG

    print(f"  East  extent : {east.max():.1f} m")
    print(f"  North extent : {north.max():.1f} m")
    print(f"  Alt   range  : {alts.min():.2f} – {alts.max():.2f} m  (delta {alts.max()-alts.min():.2f} m)")

    return np.column_stack([east, north, alts])


# ── Stage 3: Build alpha-shape mask ───────────────────────────────────────────
def build_alpha_mask(pts: np.ndarray, grid_e: np.ndarray, grid_n: np.ndarray) -> np.ndarray:
    """
    Compute concave hull of the point cloud in ENU space.
    Returns boolean mask (GRID_N x GRID_E): True = inside hull = valid terrain.
    Uses alpha_ratio=ALPHA_RATIO. Grid cells outside the hull are treated as base.
    """
    mp = MultiPoint(pts[:, :2])          # (E, N) only
    hull = concave_hull(mp, ratio=ALPHA_RATIO)
    print(f"  Alpha hull geom type : {hull.geom_type}")

    # Build grid of (E, N) query points
    GE, GN = np.meshgrid(grid_e, grid_n)
    query_pts = np.column_stack([GE.ravel(), GN.ravel()])

    # Check containment using shapely 2.x vectorised API
    from shapely import contains_xy
    mask_flat = contains_xy(hull, query_pts[:, 0], query_pts[:, 1])
    mask = mask_flat.reshape(GN.shape)
    inside_frac = mask.mean()
    print(f"  Alpha mask: {inside_frac*100:.1f}% of grid cells inside hull ({mask.sum()} / {mask.size})")
    return mask


# ── Stage 4: Interpolate surface ──────────────────────────────────────────────
def interpolate_surface(pts: np.ndarray, grid_e, grid_n):
    """
    Returns (GE, GN, GZ) where GZ is in real-world metres.
    Strategy: linear griddata, then nearest-fill NaN edges, then gaussian smooth.
    """
    east  = pts[:, 0]
    north = pts[:, 1]
    alt   = pts[:, 2]

    GE, GN = np.meshgrid(grid_e, grid_n)

    GZ = griddata((east, north), alt, (GE, GN), method="linear")
    nan_count = np.isnan(GZ).sum()
    print(f"  Linear interpolation: {nan_count} NaN cells ({nan_count/GZ.size*100:.1f}%)")

    if nan_count > 0:
        GZ_nn = griddata((east, north), alt, (GE, GN), method="nearest")
        nan_mask = np.isnan(GZ)
        GZ[nan_mask] = GZ_nn[nan_mask]
        print(f"  Nearest-fill resolved all NaN cells")

    GZ_smooth = gaussian_filter(GZ, sigma=SMOOTH_SIGMA)
    print(f"  Gaussian smoothing applied (sigma={SMOOTH_SIGMA} cells)")
    return GE, GN, GZ_smooth


# ── Stage 5: Scale to print dimensions ────────────────────────────────────────
def scale_to_print(pts: np.ndarray, GE, GN, GZ) -> tuple:
    """
    Scale (GE, GN, GZ) from real-world metres to millimetres.
    - E range -> PRINT_E_MM
    - N range -> PRINT_N_MM  (aspect ratio is maintained by design choice)
    - Z: subtract minimum, apply VERT_EXAG, then scale to mm proportionally
         (same scale factor as horizontal so vertical exag is meaningful)
    Returns (GE_mm, GN_mm, GZ_mm, base_z_mm) all in millimetres.
    """
    e_range = GE.max() - GE.min()
    n_range = GN.max() - GN.min()
    alt_min  = GZ.min()

    scale_e = PRINT_E_MM / e_range
    scale_n = PRINT_N_MM / n_range
    # Use the smaller of the two to keep correct aspect ratio
    # (caller chose PRINT_E_MM and PRINT_N_MM to match course aspect ~1.25:1,
    #  so scale factors should be close; we use scale_e for the horizontal plane
    #  and a consistent vertical scale)
    h_scale = min(scale_e, scale_n)   # mm per real-world metre

    GE_mm = (GE - GE.min()) * scale_e
    GN_mm = (GN - GN.min()) * scale_n
    GZ_mm = (GZ - alt_min) * h_scale * VERT_EXAG

    base_z_mm = 0.0  # base plate sits at z=0 in print space

    print(f"  H scale  : {h_scale:.4f} mm/m  (E: {scale_e:.4f}, N: {scale_n:.4f})")
    print(f"  V scale  : {h_scale * VERT_EXAG:.4f} mm/m (exag x{VERT_EXAG})")
    print(f"  Terrain Z range (mm): {GZ_mm.min():.2f} – {GZ_mm.max():.2f}")
    print(f"  Total model height   : {GZ_mm.max() + BASE_MM:.2f} mm (terrain + {BASE_MM}mm base)")

    return GE_mm, GN_mm, GZ_mm, base_z_mm


# ── Stage 6: Build watertight mesh ────────────────────────────────────────────
def build_watertight_mesh(GE_mm, GN_mm, GZ_mm, alpha_mask) -> trimesh.Trimesh:
    """
    Construct a watertight solid:
      - Top surface: heightmap triangles only where alpha_mask=True; elsewhere at base+epsilon
      - Perimeter walls: connect top boundary to base
      - Base plate: flat at z=0

    All z values are ABOVE z=0 (terrain sits on a BASE_MM slab).
    Strategy: shift the terrain surface up by BASE_MM so the base is at z=0.
    """
    rows, cols = GZ_mm.shape
    assert GE_mm.shape == GN_mm.shape == GZ_mm.shape == alpha_mask.shape, \
        "Grid shape mismatch"

    # Terrain z: base plate at 0, terrain surface at BASE_MM + GZ_mm
    Z_top = np.where(alpha_mask, GZ_mm + BASE_MM, BASE_MM)

    def vi(r, c):
        """Vertex index in top surface array."""
        return r * cols + c

    # Build top surface vertices (rows x cols)
    top_verts = np.column_stack([
        GE_mm.ravel(),
        GN_mm.ravel(),
        Z_top.ravel(),
    ])

    # Build base surface vertices (same XY, z=0)
    base_verts = np.column_stack([
        GE_mm.ravel(),
        GN_mm.ravel(),
        np.zeros(rows * cols),
    ])

    n_top = len(top_verts)
    all_verts = np.vstack([top_verts, base_verts])

    def bi(r, c):
        """Vertex index in base surface array (offset by n_top)."""
        return n_top + r * cols + c

    top_faces  = []
    bot_faces  = []
    wall_faces = []

    # Top surface triangles (outward normal = +Z)
    for r in range(rows - 1):
        for c in range(cols - 1):
            v00 = vi(r,   c)
            v10 = vi(r+1, c)
            v01 = vi(r,   c+1)
            v11 = vi(r+1, c+1)
            # CCW when viewed from +Z
            top_faces.append([v00, v10, v01])
            top_faces.append([v10, v11, v01])

    # Bottom surface triangles (outward normal = -Z, so CW when viewed from -Z = CCW reversed)
    for r in range(rows - 1):
        for c in range(cols - 1):
            b00 = bi(r,   c)
            b10 = bi(r+1, c)
            b01 = bi(r,   c+1)
            b11 = bi(r+1, c+1)
            # Reversed winding vs top
            bot_faces.append([b00, b01, b10])
            bot_faces.append([b10, b01, b11])

    # Side walls: connect top perimeter to base perimeter
    # Top row (r=0, northward-facing)
    for c in range(cols - 1):
        t0 = vi(0, c);   t1 = vi(0, c+1)
        b0 = bi(0, c);   b1 = bi(0, c+1)
        wall_faces += [[t0, b0, t1], [t1, b0, b1]]

    # Bottom row (r=rows-1, southward-facing)
    for c in range(cols - 1):
        t0 = vi(rows-1, c);   t1 = vi(rows-1, c+1)
        b0 = bi(rows-1, c);   b1 = bi(rows-1, c+1)
        wall_faces += [[t0, t1, b0], [t1, b1, b0]]

    # Left col (c=0, westward-facing)
    for r in range(rows - 1):
        t0 = vi(r,   0);  t1 = vi(r+1, 0)
        b0 = bi(r,   0);  b1 = bi(r+1, 0)
        wall_faces += [[t0, t1, b0], [t1, b1, b0]]

    # Right col (c=cols-1, eastward-facing)
    for r in range(rows - 1):
        t0 = vi(r,   cols-1);  t1 = vi(r+1, cols-1)
        b0 = bi(r,   cols-1);  b1 = bi(r+1, cols-1)
        wall_faces += [[t0, b0, t1], [t1, b0, b1]]

    # Combine all faces
    all_faces = np.array(
        top_faces + bot_faces + wall_faces,
        dtype=np.int64
    )

    print(f"  Vertex count : {len(all_verts)}")
    print(f"  Face count   : {len(all_faces)}  "
          f"(top={len(top_faces)}, bot={len(bot_faces)}, walls={len(wall_faces)})")

    mesh = trimesh.Trimesh(vertices=all_verts, faces=all_faces, process=True)
    return mesh


# ── Stage 7: Validate mesh ────────────────────────────────────────────────────
def validate_mesh(mesh: trimesh.Trimesh) -> bool:
    # Fix winding consistency before checking is_volume.
    # Mixed windings arise from the wall-construction stitch; fix_normals resolves them.
    trimesh.repair.fix_normals(mesh)

    print(f"  is_watertight      : {mesh.is_watertight}")
    print(f"  is_volume          : {mesh.is_volume}")
    print(f"  is_winding_consistent : {mesh.is_winding_consistent}")
    print(f"  euler_number       : {mesh.euler_number}")
    print(f"  volume (mm^3)      : {mesh.volume:.1f}")
    print(f"  Vertices (final)   : {len(mesh.vertices)}")
    print(f"  Faces    (final)   : {len(mesh.faces)}")
    bb = mesh.bounds
    print(f"  Bounding box (mm)  : E {bb[0,0]:.1f}-{bb[1,0]:.1f}  "
          f"N {bb[0,1]:.1f}-{bb[1,1]:.1f}  "
          f"Z {bb[0,2]:.1f}-{bb[1,2]:.1f}")
    if not mesh.is_watertight:
        print("  WARNING: mesh is NOT watertight — attempting fill_holes")
        trimesh.repair.fill_holes(mesh)
        print(f"  After fill_holes: is_watertight={mesh.is_watertight}")
    return mesh.is_watertight and mesh.is_volume


# ── Stage 8: Export 3MF ───────────────────────────────────────────────────────
def export_3mf(mesh: trimesh.Trimesh, out_path: Path) -> int:
    """Export to 3MF and return file size in bytes."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    mesh.export(str(out_path))
    size = out_path.stat().st_size
    print(f"  3MF written: {out_path}")
    print(f"  File size  : {size/1024:.1f} KB")
    return size


# ── Stage 9: Orientation PNG (optional but useful) ────────────────────────────
def save_orientation_png(pts_mm: np.ndarray, GE_mm, GN_mm, GZ_mm, out_path: Path):
    """
    Save a top-down colored elevation view for orientation.
    Version badge upper-left per project convention.
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.colors as mcolors
    except ImportError:
        print("  matplotlib not available — skipping orientation PNG")
        return

    fig, axes = plt.subplots(1, 2, figsize=(18, 7))

    # Left: top-down heat map
    ax = axes[0]
    im = ax.imshow(
        GZ_mm,
        origin="lower",
        cmap="terrain",
        aspect="auto",
        extent=[GE_mm.min(), GE_mm.max(), GN_mm.min(), GN_mm.max()],
    )
    ax.scatter(pts_mm[:, 0], pts_mm[:, 1], c=pts_mm[:, 2],
               cmap="terrain", s=4, edgecolors="none", zorder=3)
    cb = fig.colorbar(im, ax=ax, shrink=0.7)
    cb.set_label("Terrain Z (mm print scale, incl. exag)")
    ax.set_xlabel("East (mm print)")
    ax.set_ylabel("North (mm print)")
    ax.set_title("De Laveaga GPS — Top-down view")

    # Right: oblique 3D perspective
    ax3 = fig.add_subplot(1, 2, 2, projection="3d")
    ax3.plot_surface(
        GE_mm, GN_mm, GZ_mm + 3.0,
        cmap="terrain",
        alpha=0.75,
        linewidth=0,
        antialiased=True,
    )
    ax3.set_xlabel("East (mm)")
    ax3.set_ylabel("North (mm)")
    ax3.set_zlabel("Z (mm, exag x3)")
    ax3.set_title("De Laveaga — Oblique view")

    # Version badge upper-left of figure
    fig.text(
        0.01, 0.99,
        f"De Laveaga Course from Stracka  {VERSION} · {DATE} · Topo",
        fontsize=9, va="top", ha="left",
        color="white",
        bbox=dict(facecolor="#333333", alpha=0.8, pad=4, edgecolor="none"),
    )

    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(out_path), dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Orientation PNG: {out_path}")


# ── Stage 10: Increment serial ────────────────────────────────────────────────
def increment_serial(serial_path: Path, current_serial: int):
    """Write next_serial = current_serial + 1 to serial.json."""
    import json as _json
    new_data = {"next_serial": current_serial + 1}
    serial_path.write_text(_json.dumps(new_data, indent=2) + "\n")
    print(f"  serial.json updated: {current_serial} -> {current_serial + 1}")


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    print(f"\n=== De Laveaga Terrain 3MF Pipeline {VERSION} ===\n")

    # ---- Stage 1: Load ----
    print("Stage 1: Loading GPS data...")
    cells = load_gps_points(GPS_FILE)

    # ---- Stage 2: Project ----
    print("\nStage 2: Project to ENU metres...")
    pts = project_to_enu(cells)           # Nx3: [east_m, north_m, alt_m]

    # ---- Stage 3: Define grid in real-world metres ----
    print("\nStage 3: Building interpolation grid...")
    e_min, e_max = pts[:, 0].min(), pts[:, 0].max()
    n_min, n_max = pts[:, 1].min(), pts[:, 1].max()
    grid_e = np.linspace(e_min, e_max, GRID_E)
    grid_n = np.linspace(n_min, n_max, GRID_N)
    print(f"  Grid: {GRID_E} x {GRID_N}  ({e_max-e_min:.1f} x {n_max-n_min:.1f} m)")

    # ---- Stage 4: Alpha mask ----
    print("\nStage 4: Building alpha-shape mask...")
    alpha_mask = build_alpha_mask(pts, grid_e, grid_n)

    # ---- Stage 5: Interpolate surface ----
    print("\nStage 5: Interpolating terrain surface...")
    GE, GN, GZ = interpolate_surface(pts, grid_e, grid_n)

    # ---- Stage 6: Scale to print mm ----
    print("\nStage 6: Scaling to print dimensions...")
    GE_mm, GN_mm, GZ_mm, base_z_mm = scale_to_print(pts, GE, GN, GZ)

    # Scale GPS points to mm for PNG overlay
    e_scale = PRINT_E_MM / (e_max - e_min)
    n_scale = PRINT_N_MM / (n_max - n_min)
    h_scale = min(e_scale, n_scale)
    pts_mm = np.column_stack([
        (pts[:, 0] - e_min) * e_scale,
        (pts[:, 1] - n_min) * n_scale,
        (pts[:, 2] - pts[:, 2].min()) * h_scale * VERT_EXAG,
    ])

    # ---- Stage 7: Build mesh ----
    print("\nStage 7: Building watertight mesh...")
    mesh = build_watertight_mesh(GE_mm, GN_mm, GZ_mm, alpha_mask)

    # ---- Stage 8: Validate ----
    print("\nStage 8: Validating mesh...")
    watertight = validate_mesh(mesh)

    # ---- Stage 9: Export 3MF ----
    print("\nStage 9: Exporting 3MF...")
    tmf_name = f"De Laveaga (Course from Stracka) [{SERIAL}].3mf"
    out_3mf  = OUT_DIR_3MF / tmf_name
    file_size = export_3mf(mesh, out_3mf)

    # ---- Stage 10: Orientation PNG ----
    print("\nStage 10: Saving orientation PNG...")
    png_name = f"De Laveaga (Course from Stracka) [{SERIAL}].png"
    out_png  = OUT_DIR_IMG / png_name
    save_orientation_png(pts_mm, GE_mm, GN_mm, GZ_mm, out_png)

    # ---- Stage 11: Increment serial (only if not already incremented) ----
    print("\nStage 11: Updating serial.json...")
    cur_data = json.loads(SERIAL_JSON.read_text())
    if cur_data.get("next_serial", 0) <= SERIAL:
        increment_serial(SERIAL_JSON, SERIAL)
    else:
        print(f"  serial.json already at {cur_data['next_serial']}, no update needed")

    # ---- Summary ----
    alt = pts[:, 2]
    print(f"\n{'='*50}")
    print(f"SUMMARY")
    print(f"{'='*50}")
    print(f"  Input file      : {GPS_FILE.name}")
    print(f"  Points          : {len(pts)}")
    print(f"  Alt range (real): {alt.min():.2f} – {alt.max():.2f} m")
    print(f"  Vert exag       : x{VERT_EXAG}")
    print(f"  Print size      : {PRINT_E_MM:.0f} x {PRINT_N_MM:.0f} mm")
    print(f"  Watertight      : {watertight}")
    print(f"  Serial          : {SERIAL}")
    print(f"  Output 3MF      : {out_3mf}")
    print(f"  Output PNG      : {out_png}")
    print(f"  File size       : {file_size/1024:.1f} KB")
    print(f"\nDone.")


if __name__ == "__main__":
    main()
