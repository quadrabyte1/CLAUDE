"""
Regenerate Firefly Hole 14 3 times with grassSpacing=1.0 and grassAmplitude
in {0.5, 1.0, 2.0}. Report fringe top-band Z stddev for each.
"""
import os, sys, json, time, numpy as np, trimesh, copy
REPO = "/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER"
sys.path.insert(0, os.path.join(REPO, "app"))
os.chdir(os.path.join(REPO, "app"))

import gradient_surface_diagnostic as gsd

EGM = os.path.join(REPO, "ItWentIn/GolfCourses/Firefly/EGMs/Firefly (Hole 14).egm")
FIREFLY_DIR = os.path.join(REPO, "ItWentIn/GolfCourses/Firefly/3MFs")

# Read original EGM
with open(EGM) as f:
    egm_orig = json.load(f)

results = []
paths = []
for amplitude in (0.0, 0.5, 1.0, 2.0):
    # Rewrite EGM with new params (spacing=1.0, this amplitude)
    egm_new = copy.deepcopy(egm_orig)
    egm_new["grassSpacing"] = 1.0
    egm_new["grassAmplitude"] = amplitude
    with open(EGM, "w") as f:
        json.dump(egm_new, f, indent=2)
    print(f"\n{'='*60}\nRUN: spacing=1.0 amplitude={amplitude}\n{'='*60}")
    t0 = time.time()
    path = gsd.run_pipeline(EGM)
    dt = time.time() - t0
    paths.append((amplitude, path, dt))

    # Load and measure fringe top Z stddev
    scene = trimesh.load(path, process=False)
    fringe = max(scene.geometry.values(), key=lambda m: len(m.vertices))
    v = fringe.vertices
    top = v[:, 2] > gsd.BASE_THICKNESS_MM
    # Filter to interior (>3mm from seam) so we measure grass effect not terrain
    # variation. Load seam polylines from EGM for this measurement.
    egm_now = json.load(open(EGM))
    # Approximate: use bounding-box near a known interior area.
    # Simpler: use only verts with z close to the local median (rejects the ~5mm
    # cap-band verts and outliers), then stddev = grass contribution + smooth
    # terrain variation. Baseline (amp=0) captures terrain only.
    top_v = v[top]
    top_z = top_v[:, 2]
    # Also compute stddev in a small interior tile (avoid edges/cap band)
    # 30x30 mm window at (-40, +40)
    in_tile = (top_v[:, 0] > -50) & (top_v[:, 0] < -30) & (top_v[:, 1] > 30) & (top_v[:, 1] < 50)
    tile_z = top_v[in_tile, 2]
    tile_sd = tile_z.std() if len(tile_z) > 10 else -1
    print(f"  Fringe top Z: n={int(top.sum())} mean={top_z.mean():.3f} "
          f"stddev={top_z.std():.4f} min={top_z.min():.3f} max={top_z.max():.3f}")
    print(f"  Interior tile (-50,30)-(-30,50): n={len(tile_z)} stddev={tile_sd:.4f}")
    results.append((amplitude, top_z.std(), tile_sd, top_z.mean(), top_z.min(), top_z.max()))

# Restore EGM
with open(EGM, "w") as f:
    json.dump(egm_orig, f, indent=2)

print(f"\n{'='*60}\nSENSITIVITY TABLE (spacing=1.0, seam-freeze applied)\n{'='*60}")
print(f"{'amplitude':>10} {'full_stddev':>12} {'tile_stddev':>12} {'tile_delta_vs_amp=0':>20}  path")
tile_sd_baseline = results[0][2] if results and results[0][0] == 0.0 else 0.0
for r, path_info in zip(results, paths):
    amp, sd, tile_sd, mn, mnz, mxz = r
    delta = tile_sd - tile_sd_baseline
    print(f"{amp:>10} {sd:>12.4f} {tile_sd:>12.4f} {delta:>20.4f}  {os.path.basename(path_info[1])}")
