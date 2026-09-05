"""
task_719 diagnostic — enumerate fringe/trap intrusions on DeLaveaga H11 [212].

For each trap:
  1. Load the trap slab mesh from the 3MF.
  2. Compute the trap polygon (from EGM, using same px→mm transform).
  3. Compute an aspect ratio to identify the "jelly bean" trap.
  4. Count fringe triangles whose XY footprint intersects the trap polygon interior.
  5. Count trap triangles whose XY footprint extends outside the trap polygon.

Also does the same for water (Los Lagos H16) once we regen.
"""
import os
import sys
import json
import numpy as np
import trimesh
from shapely.geometry import Polygon as ShapelyPolygon, LineString
from shapely.ops import unary_union

APP_DIR = "/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/app"
sys.path.insert(0, APP_DIR)

from gradient_surface_diagnostic import (
    _compute_px_to_mm,
    _px_to_mm_2d,
    _poly_to_dense_px,
    TRAP_FRINGE_GAP_MM,
    PRINT_TOLERANCE_MM,
    _remove_faces_whose_footprint_overlaps_polygon,
    load_egm,
    _clip_polygon_to_fringe_rect,
)


def load_3mf_scene(path: str):
    scene = trimesh.load(path, force="scene")
    print(f"[load] {os.path.basename(path)}")
    # Build node_name -> mesh mapping via scene.graph
    node_to_mesh = {}
    for n in scene.graph.nodes:
        try:
            _tf, geom_name = scene.graph[n]
        except Exception:
            continue
        if geom_name is None:
            continue
        if geom_name in scene.geometry:
            node_to_mesh[n] = scene.geometry[geom_name]
    print(f"  nodes: {list(node_to_mesh.keys())}")
    return scene, node_to_mesh


def load_trap_polys_mm(egm_path: str):
    """Use load_egm to get the SAME smoothed trap polys the pipeline uses."""
    egm, _image_path, green_boundary_px = load_egm(egm_path)
    scale, centroid_px = _compute_px_to_mm(green_boundary_px, egm)
    trap_polys = []
    for i, p in enumerate([q for q in egm["polygons"] if q.get("type") == "trap"], start=1):
        pts_px = _poly_to_dense_px(p)
        pts_mm = _px_to_mm_2d(pts_px, scale, centroid_px)
        sp = ShapelyPolygon(pts_mm)
        if not sp.is_valid:
            sp = sp.buffer(0)
        # Same clip the pipeline does
        sp_clipped = _clip_polygon_to_fringe_rect(sp, f"Trap {i}")
        if sp_clipped is None:
            sp_clipped = sp
        trap_polys.append((f"trap_{i}", sp_clipped))
    return trap_polys


def poly_metrics(sp: ShapelyPolygon):
    """Return (aspect_ratio_MABR, curvature_score) — higher curvature = more jelly-bean-y."""
    from shapely.affinity import rotate
    # oriented minimum bounding rectangle
    mabr = sp.minimum_rotated_rectangle
    coords = list(mabr.exterior.coords)
    # side lengths
    sides = []
    for i in range(4):
        (x1, y1), (x2, y2) = coords[i], coords[i + 1]
        sides.append(np.hypot(x2 - x1, y2 - y1))
    L = max(sides)
    W = min(sides)
    aspect = L / max(W, 1e-9)
    # curvature: ratio of perimeter to convex-hull perimeter (jelly beans deviate from convex)
    hull = sp.convex_hull
    curve = sp.length / max(hull.length, 1e-9)
    return aspect, curve, L, W


def count_intrusions(fringe_mesh: trimesh.Trimesh, trap_poly: ShapelyPolygon, label: str):
    """Count fringe triangles whose XY footprint intersects trap interior."""
    tri_v = fringe_mesh.triangles  # (N, 3, 3)
    ax, ay = tri_v[:, 0, 0], tri_v[:, 0, 1]
    bx, by = tri_v[:, 1, 0], tri_v[:, 1, 1]
    cx, cy = tri_v[:, 2, 0], tri_v[:, 2, 1]

    pxmin, pymin, pxmax, pymax = trap_poly.bounds
    fxmin = np.minimum(np.minimum(ax, bx), cx)
    fxmax = np.maximum(np.maximum(ax, bx), cx)
    fymin = np.minimum(np.minimum(ay, by), cy)
    fymax = np.maximum(np.maximum(ay, by), cy)
    bbox_hit = (fxmax >= pxmin) & (fxmin <= pxmax) & (fymax >= pymin) & (fymin <= pymax)
    cand = np.where(bbox_hit)[0]
    if cand.size == 0:
        return 0, []

    from shapely.vectorized import contains as _sh_contains
    va_in = _sh_contains(trap_poly, ax[cand], ay[cand])
    vb_in = _sh_contains(trap_poly, bx[cand], by[cand])
    vc_in = _sh_contains(trap_poly, cx[cand], cy[cand])
    vert_hit = va_in | vb_in | vc_in

    rep = trap_poly.representative_point()
    rx, ry = float(rep.x), float(rep.y)
    axs = ax[cand]; ays = ay[cand]
    bxs = bx[cand]; bys = by[cand]
    cxs = cx[cand]; cys = cy[cand]
    d1 = (rx - bxs) * (ays - bys) - (axs - bxs) * (ry - bys)
    d2 = (rx - cxs) * (bys - cys) - (bxs - cxs) * (ry - cys)
    d3 = (rx - axs) * (cys - ays) - (cxs - axs) * (ry - ays)
    has_neg = (d1 < 0) | (d2 < 0) | (d3 < 0)
    has_pos = (d1 > 0) | (d2 > 0) | (d3 > 0)
    pt_in_tri = ~(has_neg & has_pos)

    # edge crossing
    boundary = trap_poly.exterior if trap_poly.exterior is not None else trap_poly.boundary
    edge_hit = np.zeros(cand.size, dtype=bool)
    _remaining = np.where(~(vert_hit | pt_in_tri))[0]
    for k in _remaining:
        for (px, py, qx, qy) in [
            (axs[k], ays[k], bxs[k], bys[k]),
            (bxs[k], bys[k], cxs[k], cys[k]),
            (cxs[k], cys[k], axs[k], ays[k]),
        ]:
            if LineString([(px, py), (qx, qy)]).intersects(boundary):
                edge_hit[k] = True
                break

    hit_local = vert_hit | pt_in_tri | edge_hit
    n_hit = int(hit_local.sum())
    hit_face_indices = cand[hit_local].tolist()

    details = []
    if n_hit > 0 and n_hit <= 30:
        for k, is_hit in enumerate(hit_local):
            if not is_hit:
                continue
            fi = cand[k]
            v = tri_v[fi]
            zs = v[:, 2]
            details.append({
                "face_idx": int(fi),
                "z_range": (float(zs.min()), float(zs.max())),
                "verts": v.tolist(),
                "vertex_hit": bool(vert_hit[k]),
                "pt_in_tri": bool(pt_in_tri[k]),
                "edge_hit": bool(edge_hit[k]),
            })
    print(f"  [{label}] {n_hit}/{cand.size} candidate fringe triangles intrude on trap interior")
    return n_hit, details


def count_trap_extrusions(trap_mesh: trimesh.Trimesh, trap_poly: ShapelyPolygon, label: str):
    """Count trap triangles whose XY footprint EXTENDS OUTSIDE the trap polygon."""
    # Buffer polygon OUT by tiny epsilon; any face vertex outside this OR any edge crossing exterior = extrusion.
    # Since trap slab is built from -PRINT_TOLERANCE_MM inset, ALL its faces should sit inside the polygon.
    tri_v = trap_mesh.triangles
    ax, ay = tri_v[:, 0, 0], tri_v[:, 0, 1]
    bx, by = tri_v[:, 1, 0], tri_v[:, 1, 1]
    cx, cy = tri_v[:, 2, 0], tri_v[:, 2, 1]

    from shapely.vectorized import contains as _sh_contains
    # tolerant polygon: allow 0.01 mm slop for float noise
    tol_poly = trap_poly.buffer(0.01)
    va_in = _sh_contains(tol_poly, ax, ay)
    vb_in = _sh_contains(tol_poly, bx, by)
    vc_in = _sh_contains(tol_poly, cx, cy)
    any_outside = ~(va_in & vb_in & vc_in)
    n_ext = int(any_outside.sum())
    print(f"  [{label}] {n_ext}/{len(tri_v)} trap triangles have XY vertex OUTSIDE trap polygon (tol 0.01mm)")
    return n_ext


def main(path_3mf: str, egm_path: str):
    scene, node_to_mesh = load_3mf_scene(path_3mf)
    fringe_key = next((n for n in node_to_mesh if "fringe" in n.lower()), None)
    trap_keys = sorted([n for n in node_to_mesh if n.lower().startswith("trap_")])
    print(f"  fringe node: {fringe_key}, trap nodes: {trap_keys}")
    fringe = node_to_mesh[fringe_key]

    trap_polys = load_trap_polys_mm(egm_path)
    print(f"  loaded {len(trap_polys)} trap polygons from EGM")

    print("\n== JELLY-BEAN IDENTIFICATION (metrics) ==")
    for name, sp in trap_polys:
        aspect, curve, L, W = poly_metrics(sp)
        area = sp.area
        print(f"  {name}: area={area:.1f} mm^2  MABR L={L:.1f} W={W:.1f}  aspect={aspect:.2f}  perimeter/hull={curve:.3f}")

    print("\n== FRINGE→TRAP INTRUSIONS ==")
    all_intrusion_details = {}
    for name, sp in trap_polys:
        n, details = count_intrusions(fringe, sp, name)
        all_intrusion_details[name] = (n, details)
        if details:
            print(f"    details for {name}:")
            for d in details[:10]:
                print(f"      face {d['face_idx']}  z[{d['z_range'][0]:.2f},{d['z_range'][1]:.2f}]  "
                      f"vhit={d['vertex_hit']} pt={d['pt_in_tri']} edge={d['edge_hit']}")
                for v in d['verts']:
                    print(f"        v=({v[0]:7.2f},{v[1]:7.2f},{v[2]:6.2f})")

    print("\n== TRAP→FRINGE EXTRUSIONS ==")
    for name, sp in trap_polys:
        if name not in node_to_mesh:
            print(f"  {name}: no matching mesh in scene, skipping")
            continue
        trap_mesh = node_to_mesh[name]
        count_trap_extrusions(trap_mesh, sp, name)

    return all_intrusion_details


if __name__ == "__main__":
    egm_path = "/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/ItWentIn/GolfCourses/DeLaveaga/EGMs/DeLaveaga (Hole 11).egm"
    default_3mf = "/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/ItWentIn/GolfCourses/DeLaveaga/3MFs/DeLaveaga (Hole 11) [212].3mf"
    p = sys.argv[1] if len(sys.argv) > 1 else default_3mf
    main(p, egm_path)
