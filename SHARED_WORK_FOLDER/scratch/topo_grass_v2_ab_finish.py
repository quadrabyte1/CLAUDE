"""
Topo — finish grass v2 A/B on Firefly Hole 14.

Prior run (topo_grass_v2_ab.py) only completed RUN A_v1 (serial 144) before
being terminated. This script:
  * runs RUN B (v2 cone) and RUN C (v2 pyramid) with amp=0.5, spacing=1.0
  * loads all three (A=144, B=<new>, C=<new>), measures them
  * runs a one-shot Poisson center count sanity check on the H14 fringe
  * restores the EGM to its pre-A/B state
  * emits a compact report

Reuses the same instrumentation pattern as topo_grass_v2_ab.py so the
measurements are directly comparable.
"""
import os, sys, json, time, copy, shutil, glob
import numpy as np
import trimesh
from scipy.spatial import cKDTree

REPO = "/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER"
sys.path.insert(0, os.path.join(REPO, "app"))
os.chdir(os.path.join(REPO, "app"))

import gradient_surface_diagnostic as gsd

EGM     = os.path.join(REPO, "ItWentIn/GolfCourses/Firefly/EGMs/Firefly (Hole 14).egm")
DIR_3MF = os.path.join(REPO, "ItWentIn/GolfCourses/Firefly/3MFs")

# --- Snapshot EGM so we can restore. NOTE the prior aborted script LEFT
#     the EGM with grassAmplitude=0.5 and grassSpacing=1.0. We need to
#     restore it to Thomas's real defaults after we're done. Pull those
#     from a nearby hole (same course) so we can undo cleanly.
with open(EGM) as f:
    egm_current = json.load(f)

# Determine the "true" original values by inspecting other Firefly holes.
sibling_amps, sibling_spacings = [], []
for other in glob.glob(os.path.join(os.path.dirname(EGM), "Firefly (Hole *).egm")):
    if other == EGM: continue
    try:
        with open(other) as f:
            j = json.load(f)
        if "grassAmplitude" in j: sibling_amps.append(j["grassAmplitude"])
        if "grassSpacing"  in j: sibling_spacings.append(j["grassSpacing"])
    except Exception:
        pass

# most-common sibling value; fall back to hard defaults if none.
def _mode(xs, fallback):
    if not xs: return fallback
    from collections import Counter
    return Counter(xs).most_common(1)[0][0]

egm_original_amp     = _mode(sibling_amps,     0.5)
egm_original_spacing = _mode(sibling_spacings, 0.4)
print(f"[restore-target] amp={egm_original_amp}  spacing={egm_original_spacing}  "
      f"(from {len(sibling_amps)} sibling Firefly EGMs)")

# Force amp=0.5, spacing=1.0 for the A/B (it's already there, but be explicit).
egm_ab = copy.deepcopy(egm_current)
egm_ab["grassAmplitude"] = 0.5
egm_ab["grassSpacing"]   = 1.0
with open(EGM, "w") as f:
    json.dump(egm_ab, f, indent=2)


# --- Instrument v2 to record center count & elapsed --------------------------
_v2_stats = {}
_orig_v2 = gsd.apply_grass_texture_v2

def _spy_v2(mesh, **kw):
    profile = kw.get("profile", "cone")
    t0 = time.time()
    # We need the RAW Poisson count (pre-on-mesh-filter, pre-seam-filter). Rerun
    # Bridson with the same seed advancement the real fn does.
    verts = mesh.vertices
    top_mask = verts[:, 2] > gsd.BASE_THICKNESS_MM
    top_xy = verts[top_mask, :2].copy()
    rng_seed = kw.get("rng_seed", 42)
    rng_probe = np.random.default_rng(rng_seed)
    xy_shear = kw.get("xy_shear_mm", 0.15)
    if xy_shear > 0:
        _ = np.sqrt(rng_probe.random(len(top_xy))) * xy_shear
        _ = 2*np.pi*rng_probe.random(len(top_xy))
    x_min, x_max = float(top_xy[:,0].min()), float(top_xy[:,0].max())
    y_min, y_max = float(top_xy[:,1].min()), float(top_xy[:,1].max())
    centers_raw = gsd._bridson_poisson_disk_2d(
        x_min, y_min, x_max, y_max,
        radius=kw["bump_spacing"], k=kw.get("poisson_k", 30), rng=rng_probe)
    n_centers_raw = len(centers_raw)

    result = _orig_v2(mesh, **kw)
    dt = time.time() - t0
    _v2_stats[profile] = {"centers_raw": n_centers_raw, "elapsed_s": dt}
    return result

# Wrap so we can override profile per-run via a mutable holder
_run_profile = {"value": "cone"}
def _dispatch_v2(mesh, **kw):
    kw["profile"] = _run_profile["value"]
    return _spy_v2(mesh, **kw)
gsd.apply_grass_texture_v2 = _dispatch_v2


# --- Run configs (skip A — already done as serial 144) -----------------------
runs = [
    {"label": "B_v2_cone",    "algo": "v2", "profile": "cone"},
    {"label": "C_v2_pyramid", "algo": "v2", "profile": "pyramid"},
]

fresh_results = []
for r in runs:
    gsd.GRASS_ALGORITHM = r["algo"]
    _run_profile["value"] = r["profile"]

    print("\n" + "="*70)
    print(f"RUN {r['label']}  (algo={r['algo']}, profile={r['profile']})")
    print("="*70, flush=True)

    t0 = time.time()
    path = gsd.run_pipeline(EGM)
    dt_total = time.time() - t0

    fresh_results.append({
        "label": r["label"],
        "algo":  r["algo"],
        "profile": r["profile"],
        "path":  path,
        "total_s": dt_total,
        "grass_call_s": _v2_stats.get(r["profile"], {}).get("elapsed_s"),
        "poisson_centers_raw": _v2_stats.get(r["profile"], {}).get("centers_raw"),
    })

# --- Restore EGM -------------------------------------------------------------
egm_current["grassAmplitude"] = egm_original_amp
egm_current["grassSpacing"]   = egm_original_spacing
with open(EGM, "w") as f:
    json.dump(egm_current, f, indent=2)
print(f"\n[cleanup] EGM restored: grassAmplitude={egm_original_amp} "
      f"grassSpacing={egm_original_spacing}")


# --- Measure all three (A=144, plus the two fresh runs) ----------------------
A_PATH = os.path.join(DIR_3MF, "Firefly (Hole 14) [144].3mf")
targets = [
    ("A_v1",           "v1",      None,      A_PATH),
    (fresh_results[0]["label"], fresh_results[0]["algo"], fresh_results[0]["profile"], fresh_results[0]["path"]),
    (fresh_results[1]["label"], fresh_results[1]["algo"], fresh_results[1]["profile"], fresh_results[1]["path"]),
]

def _measure(path):
    scene = trimesh.load(path, process=False)
    meshes = dict(scene.geometry)
    green = meshes.get("green_surface")
    fringe = None; mv = 0
    for n, m in meshes.items():
        if n == "green_surface": continue
        if len(m.vertices) > mv:
            mv = len(m.vertices); fringe = m
    v = fringe.vertices
    top_mask = v[:, 2] > gsd.BASE_THICKNESS_MM
    top_v = v[top_mask]
    # Interior 20x20 mm tile at (-50,-30) x (30,50) — same tile as task 500
    in_tile = ((top_v[:,0] > -50) & (top_v[:,0] < -30) &
               (top_v[:,1] >  30) & (top_v[:,1] <  50))
    tile_z = top_v[in_tile, 2]
    tile_sd = float(tile_z.std()) if len(tile_z) > 10 else float("nan")
    tile_pp = float(tile_z.ptp())  if len(tile_z) > 10 else float("nan")
    green_zmax = float(green.vertices[:, 2].max()) if green is not None else float("nan")

    # Displaced-fraction proxy: fraction of top verts whose Z sits > 0.05 mm
    # above the interior-tile median (a stand-in "baseline plane" — good enough
    # for A/B relative comparison; not an absolute baseline).
    if len(tile_z) > 10:
        z_base = float(np.median(tile_z))
    else:
        z_base = float(np.median(top_v[:, 2]))
    disp_frac = float(((top_v[:, 2] - z_base) > 0.05).mean())

    return {
        "top_verts":  int(top_mask.sum()),
        "tile_sd":    tile_sd,
        "tile_pp":    tile_pp,
        "disp_frac":  disp_frac,
        "green_zmax": green_zmax,
    }

measurements = []
for label, algo, profile, path in targets:
    m = _measure(path)
    m["label"]   = label
    m["algo"]    = algo
    m["profile"] = profile
    m["path"]    = path
    m["serial"]  = int(os.path.basename(path).split("[")[1].split("]")[0])
    measurements.append(m)

# --- One-shot Poisson center count on a scratch fringe -----------------------
# Build a synthetic top-surface disc that matches Firefly H14 fringe extent
# (~170x170 mm, ~160k top verts), then call _bridson_poisson_disk_2d directly.
# This is the sanity-check Thomas asked for.
print("\n" + "="*70)
print("ONE-SHOT POISSON CENTER COUNT (H14 fringe extent, spacing=1.0)")
print("="*70)
t_pois = time.time()
rng = np.random.default_rng(42)
centers_oneshot = gsd._bridson_poisson_disk_2d(
    -85.2, -85.2, 85.2, 85.2, radius=1.0, k=30, rng=rng)
poisson_dt = time.time() - t_pois
print(f"  Bridson centers (spacing=1.0 mm, 170x170 mm bbox): "
      f"{len(centers_oneshot)}   ({poisson_dt*1000:.1f} ms)")


# --- Report ------------------------------------------------------------------
print("\n" + "="*70)
print("GRASS v2 A/B REPORT — Firefly Hole 14, amp=0.5, spacing=1.0")
print("="*70)
hdr = f"{'label':<14} {'serial':>6} {'algo':<12} {'top_verts':>10} " \
      f"{'disp_frac':>10} {'tile_SD':>9} {'tile_pp':>9} {'greenZmax':>10}"
print(hdr)
print("-" * len(hdr))
for m in measurements:
    algo_str = m["algo"] if not m["profile"] else f"{m['algo']}-{m['profile']}"
    print(f"{m['label']:<14} {m['serial']:>6d} {algo_str:<12} "
          f"{m['top_verts']:>10d} {m['disp_frac']:>10.4f} "
          f"{m['tile_sd']:>9.4f} {m['tile_pp']:>9.4f} {m['green_zmax']:>10.4f}")

print("\nFresh runs (v2 only) — Poisson counts & timing:")
for r in fresh_results:
    print(f"  {r['label']:<14} centers(raw)={r['poisson_centers_raw']:>6d}  "
          f"grass_fn={r['grass_call_s']:.2f}s   total_pipeline={r['total_s']:.2f}s")
print(f"\nOne-shot Poisson (H14 bbox, spacing=1.0): {len(centers_oneshot)} centers "
      f"in {poisson_dt*1000:.1f} ms")
