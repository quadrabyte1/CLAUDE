"""
Topo — grass v2 A/B on Firefly Hole 14.

Approach: monkey-patch apply_grass_texture and apply_grass_texture_v2 to
override amplitude/bump_spacing at call time (bypasses the on-disk EGM
so the web server's autosave can't stomp our params). Also patches the
GRASS_ALGORITHM switch.

Runs the fringe build 3x at grassAmplitude=0.5, grassSpacing=1.0:
  A: GRASS_ALGORITHM='v1'      — current paraboloid grid (baseline)
  B: GRASS_ALGORITHM='v2', profile='cone'
  C: GRASS_ALGORITHM='v2', profile='pyramid'

Metrics: Poisson center count, grass-call seconds, total pipeline seconds,
interior 20x20 mm tile Z stddev, fraction top-verts displaced, green Zmax.
"""
import os, sys, json, time, copy, shutil
import numpy as np
import trimesh

REPO = "/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER"
sys.path.insert(0, os.path.join(REPO, "app"))
os.chdir(os.path.join(REPO, "app"))

import gradient_surface_diagnostic as gsd

EGM = os.path.join(REPO, "ItWentIn/GolfCourses/Firefly/EGMs/Firefly (Hole 14).egm")
DIR_3MF = os.path.join(REPO, "ItWentIn/GolfCourses/Firefly/3MFs")

# Target grass params for the A/B (bypass EGM values entirely).
TARGET_AMPLITUDE = 0.5
TARGET_SPACING   = 1.0

# --- Instrument: swap grass functions ----------------------------------------
_stats = {}

_orig_v1 = gsd.apply_grass_texture
_orig_v2 = gsd.apply_grass_texture_v2

_current_label   = {"value": None}
_current_profile = {"value": "cone"}

def _patched_v1(mesh, **kw):
    kw["amplitude"]    = TARGET_AMPLITUDE
    kw["bump_spacing"] = TARGET_SPACING
    top_before = int((mesh.vertices[:, 2] > gsd.BASE_THICKNESS_MM).sum())
    z_before = mesh.vertices[mesh.vertices[:, 2] > gsd.BASE_THICKNESS_MM, 2].copy()
    t0 = time.time()
    result = _orig_v1(mesh, **kw)
    dt = time.time() - t0
    z_after = mesh.vertices[mesh.vertices[:, 2] > gsd.BASE_THICKNESS_MM, 2]
    displaced = int((np.abs(z_after - z_before) > 1e-9).sum()) if len(z_after)==len(z_before) else -1
    _stats[_current_label["value"]] = {
        "grass_s":   dt,
        "centers":   None,
        "displaced": displaced,
        "top_verts": top_before,
        "profile":   None,
        "algo":      "v1",
    }
    return result

def _patched_v2(mesh, **kw):
    kw["amplitude"]    = TARGET_AMPLITUDE
    kw["bump_spacing"] = TARGET_SPACING
    kw["profile"]      = _current_profile["value"]
    top_before = int((mesh.vertices[:, 2] > gsd.BASE_THICKNESS_MM).sum())
    z_before = mesh.vertices[mesh.vertices[:, 2] > gsd.BASE_THICKNESS_MM, 2].copy()

    # Deterministic Poisson-count preview: replicate RNG stream up to the
    # Poisson call inside apply_grass_texture_v2. Cheap (~50 ms).
    verts = mesh.vertices
    top_mask = verts[:, 2] > gsd.BASE_THICKNESS_MM
    top_xy = verts[top_mask, :2].copy()
    rng = np.random.default_rng(kw.get("rng_seed", 42))
    # Inside the function: first consumes rng for the protect-mask pass
    # (none — that path uses cKDTree, no rng draws), then shear if
    # xy_shear_mm>0 draws 2N floats.
    xy_shear = kw.get("xy_shear_mm", 0.15)
    if xy_shear > 0:
        _ = np.sqrt(rng.random(len(top_xy))) * xy_shear
        _ = 2*np.pi*rng.random(len(top_xy))
    x_min, x_max = float(top_xy[:,0].min()), float(top_xy[:,0].max())
    y_min, y_max = float(top_xy[:,1].min()), float(top_xy[:,1].max())
    centers = gsd._bridson_poisson_disk_2d(x_min, y_min, x_max, y_max,
                                            radius=TARGET_SPACING,
                                            k=kw.get("poisson_k", 30),
                                            rng=rng)
    n_centers_bbox = len(centers)

    t0 = time.time()
    result = _orig_v2(mesh, **kw)
    dt = time.time() - t0

    z_after = mesh.vertices[mesh.vertices[:, 2] > gsd.BASE_THICKNESS_MM, 2]
    displaced = int((np.abs(z_after - z_before) > 1e-9).sum()) if len(z_after)==len(z_before) else -1
    _stats[_current_label["value"]] = {
        "grass_s":       dt,
        "centers_bbox":  n_centers_bbox,
        "displaced":     displaced,
        "top_verts":     top_before,
        "profile":       _current_profile["value"],
        "algo":          "v2",
    }
    return result

gsd.apply_grass_texture     = _patched_v1
gsd.apply_grass_texture_v2  = _patched_v2

assert TARGET_SPACING >= gsd.FRINGE_GRASS_MIN_SPACING_MM, "target spacing would trigger the floor clamp"

runs = [
    {"label": "A_v1",         "algo": "v1", "profile": None},
    {"label": "B_v2_cone",    "algo": "v2", "profile": "cone"},
    {"label": "C_v2_pyramid", "algo": "v2", "profile": "pyramid"},
]

results = []
for r in runs:
    gsd.GRASS_ALGORITHM = r["algo"]
    _current_label["value"] = r["label"]
    if r["profile"]:
        _current_profile["value"] = r["profile"]

    print("\n" + "="*70)
    print(f"RUN {r['label']}  (algo={r['algo']}, profile={r['profile']})")
    print("="*70)

    t0 = time.time()
    path = gsd.run_pipeline(EGM)
    dt_total = time.time() - t0

    stem, ext = os.path.splitext(os.path.basename(path))
    renamed = os.path.join(os.path.dirname(path), f"{stem}_{r['label']}{ext}")
    shutil.copy2(path, renamed)

    scene = trimesh.load(path, process=False)
    geoms = list(scene.geometry.items())
    green = geoms[0][1]
    fringe = geoms[1][1]
    v = fringe.vertices
    top_mask = v[:, 2] > gsd.BASE_THICKNESS_MM
    top_v = v[top_mask]
    in_tile = ((top_v[:,0] > -50) & (top_v[:,0] < -30) &
               (top_v[:,1] >  30) & (top_v[:,1] <  50))
    tile_z = top_v[in_tile, 2]
    tile_sd = float(tile_z.std()) if len(tile_z) > 10 else float("nan")

    st = _stats.get(r["label"], {})
    results.append({
        "label":            r["label"],
        "algo":             r["algo"],
        "profile":          r["profile"],
        "path":             path,
        "renamed":          renamed,
        "total_s":          dt_total,
        "grass_s":          st.get("grass_s"),
        "centers":          st.get("centers_bbox"),
        "displaced_top":    st.get("displaced"),
        "top_verts":        st.get("top_verts"),
        "displaced_frac":   (st.get("displaced")/st.get("top_verts")) if st.get("top_verts") else None,
        "tile_sd":          tile_sd,
        "tile_n":           int(len(tile_z)),
        "green_zmax":       float(green.vertices[:, 2].max()),
    })

print("\n" + "="*80)
print(f"GRASS v2 A/B — Firefly H14 amp={TARGET_AMPLITUDE} spacing={TARGET_SPACING}")
print("="*80)
print(f"{'label':<15} {'grass_s':>8} {'total_s':>8} {'centers':>9} "
      f"{'displaced':>11} {'frac':>7} {'tile_SD':>9} {'greenZmax':>10}")
for r in results:
    print(f"{r['label']:<15} "
          f"{(r.get('grass_s') or float('nan')):>8.3f} "
          f"{r['total_s']:>8.2f} "
          f"{str(r.get('centers','—')):>9} "
          f"{str(r.get('displaced_top','—')):>11} "
          f"{(r.get('displaced_frac') or 0):>7.3f} "
          f"{r['tile_sd']:>9.4f} "
          f"{r['green_zmax']:>10.4f}")

print("\nRaw dict:")
for r in results:
    print(" ", {k: v for k, v in r.items() if k not in ("path","renamed")})
print("\n3MFs written:")
for r in results:
    print(" ", r["renamed"])
