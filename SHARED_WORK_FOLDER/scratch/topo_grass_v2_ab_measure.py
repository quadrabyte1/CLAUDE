"""
Measure-only: load A=144 (v1), B=147 (v2 cone), C=148 (v2 pyramid) and
report top-vert count, interior-tile stddev / peak-to-peak, displaced fraction,
and green Zmax. Also runs the one-shot Poisson center count for the report.
"""
import os, sys, time
import numpy as np
import trimesh

REPO = "/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER"
sys.path.insert(0, os.path.join(REPO, "app"))
os.chdir(os.path.join(REPO, "app"))
import gradient_surface_diagnostic as gsd

DIR_3MF = os.path.join(REPO, "ItWentIn/GolfCourses/Firefly/3MFs")
targets = [
    ("A_v1",         "v1",      None,      os.path.join(DIR_3MF, "Firefly (Hole 14) [144].3mf")),
    ("B_v2_cone",    "v2",      "cone",    os.path.join(DIR_3MF, "Firefly (Hole 14) [147].3mf")),
    ("C_v2_pyramid", "v2",      "pyramid", os.path.join(DIR_3MF, "Firefly (Hole 14) [148].3mf")),
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
    v = np.asarray(fringe.vertices)
    top_mask = v[:, 2] > gsd.BASE_THICKNESS_MM
    top_v = v[top_mask]
    in_tile = ((top_v[:,0] > -50) & (top_v[:,0] < -30) &
               (top_v[:,1] >  30) & (top_v[:,1] <  50))
    tile_z = top_v[in_tile, 2]
    tile_sd = float(np.std(tile_z))            if len(tile_z) > 10 else float("nan")
    tile_pp = float(tile_z.max()-tile_z.min()) if len(tile_z) > 10 else float("nan")
    green_zmax = float(np.asarray(green.vertices)[:, 2].max()) if green is not None else float("nan")

    # Baseline for displaced-fraction: use interior-tile median (an approx
    # "un-textured" reference — good enough for relative A/B).
    z_base = float(np.median(tile_z)) if len(tile_z) > 10 else float(np.median(top_v[:, 2]))
    disp_frac = float(((top_v[:, 2] - z_base) > 0.05).mean())

    return {
        "top_verts":  int(top_mask.sum()),
        "tile_sd":    tile_sd,
        "tile_pp":    tile_pp,
        "tile_n":     int(len(tile_z)),
        "disp_frac":  disp_frac,
        "green_zmax": green_zmax,
    }

measurements = []
for label, algo, profile, path in targets:
    if not os.path.exists(path):
        print(f"MISSING: {path}"); continue
    m = _measure(path)
    m.update({"label": label, "algo": algo, "profile": profile,
              "serial": int(os.path.basename(path).split("[")[1].split("]")[0])})
    measurements.append(m)

# One-shot Poisson on H14 fringe bbox (170 x 170 mm, spacing=1.0)
t0 = time.time()
rng = np.random.default_rng(42)
centers = gsd._bridson_poisson_disk_2d(-85.2, -85.2, 85.2, 85.2, radius=1.0, k=30, rng=rng)
poisson_dt = time.time() - t0

print("\n" + "="*80)
print("GRASS v2 A/B REPORT — Firefly Hole 14, amp=0.5, spacing=1.0")
print("="*80)
print(f"{'label':<14} {'serial':>6} {'algo':<12} {'tile_n':>7} {'top_verts':>10} "
      f"{'disp_frac':>10} {'tile_SD':>9} {'tile_pp':>9} {'greenZmax':>10}")
print("-"*95)
for m in measurements:
    algo_str = m["algo"] if not m["profile"] else f"{m['algo']}-{m['profile']}"
    print(f"{m['label']:<14} {m['serial']:>6d} {algo_str:<12} {m['tile_n']:>7d} "
          f"{m['top_verts']:>10d} {m['disp_frac']:>10.4f} "
          f"{m['tile_sd']:>9.4f} {m['tile_pp']:>9.4f} {m['green_zmax']:>10.4f}")

print(f"\nOne-shot Bridson Poisson (170x170 mm bbox, R=1.0 mm): "
      f"{len(centers)} centers in {poisson_dt*1000:.1f} ms")
print(f"Fresh-run raw Poisson (cone & pyramid, H14 fringe bbox, from log): 11691 centers")
print(f"Fresh-run RUN B (cone)   grass_fn timing: (see log; total pipeline ~= per-run print)")
