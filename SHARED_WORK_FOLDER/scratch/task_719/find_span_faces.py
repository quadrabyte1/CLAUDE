"""Find fringe faces whose XY footprint spans across trap_1 interior."""
import sys
import numpy as np
import trimesh
from shapely.geometry import Polygon, Point

sys.path.insert(0, "/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/app")
from gradient_surface_diagnostic import (
    load_egm, _compute_px_to_mm, _px_to_mm_2d, _poly_to_dense_px, _clip_polygon_to_fringe_rect
)

def main():
    scene = trimesh.load(
        "/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/ItWentIn/GolfCourses/DeLaveaga/3MFs/DeLaveaga (Hole 11) [212].3mf",
        force="scene",
    )
    fringe = scene.geometry["geometry_1"]
    egm, _, gpx = load_egm(
        "/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/ItWentIn/GolfCourses/DeLaveaga/EGMs/DeLaveaga (Hole 11).egm"
    )
    scale, cpx = _compute_px_to_mm(gpx, egm)
    for tidx, tp_raw in enumerate([p for p in egm["polygons"] if p.get("type") == "trap"], start=1):
        tp_mm = _px_to_mm_2d(_poly_to_dense_px(tp_raw), scale, cpx)
        tp = Polygon(tp_mm)
        if not tp.is_valid: tp = tp.buffer(0)
        tp = _clip_polygon_to_fringe_rect(tp, f"Trap {tidx}") or tp
        rep = tp.representative_point()
        rx, ry = float(rep.x), float(rep.y)
        print(f"\ntrap_{tidx}: bounds={tp.bounds}, area={tp.area:.1f}, rep=({rx:.2f},{ry:.2f})")

        # Full point-in-triangle test across ALL fringe faces
        tri = fringe.triangles
        ax = tri[:,0,0]; ay = tri[:,0,1]
        bx = tri[:,1,0]; by = tri[:,1,1]
        cx = tri[:,2,0]; cy = tri[:,2,1]
        d1 = (rx-bx)*(ay-by) - (ax-bx)*(ry-by)
        d2 = (rx-cx)*(by-cy) - (bx-cx)*(ry-cy)
        d3 = (rx-ax)*(cy-ay) - (cx-ax)*(ry-ay)
        has_neg = (d1<0)|(d2<0)|(d3<0)
        has_pos = (d1>0)|(d2>0)|(d3>0)
        covers = ~(has_neg & has_pos)
        covers_idx = np.where(covers)[0]
        print(f"  fringe faces covering trap_{tidx} rep point: {len(covers_idx)}")
        for fi in covers_idx[:5]:
            v = tri[fi]
            print(f"    face {fi}: v0=({v[0,0]:.1f},{v[0,1]:.1f},{v[0,2]:.2f}) "
                  f"v1=({v[1,0]:.1f},{v[1,1]:.1f},{v[1,2]:.2f}) "
                  f"v2=({v[2,0]:.1f},{v[2,1]:.1f},{v[2,2]:.2f})")

        # Also: try many rep points spread across trap interior
        minx, miny, maxx, maxy = tp.bounds
        n_hits_by_face = {}
        for xt in np.linspace(minx+0.5, maxx-0.5, 8):
            for yt in np.linspace(miny+0.5, maxy-0.5, 8):
                pt = Point(xt, yt)
                if not tp.contains(pt): continue
                d1 = (xt-bx)*(ay-by) - (ax-bx)*(yt-by)
                d2 = (xt-cx)*(by-cy) - (bx-cx)*(yt-cy)
                d3 = (xt-ax)*(cy-ay) - (cx-ax)*(yt-ay)
                has_neg = (d1<0)|(d2<0)|(d3<0)
                has_pos = (d1>0)|(d2>0)|(d3>0)
                covers = ~(has_neg & has_pos)
                for fi in np.where(covers)[0]:
                    n_hits_by_face[fi] = n_hits_by_face.get(fi, 0) + 1
        print(f"  distinct fringe faces covering ANY of 64 grid points inside trap_{tidx}: {len(n_hits_by_face)}")
        for fi, n in sorted(n_hits_by_face.items(), key=lambda x: -x[1])[:5]:
            v = tri[fi]
            zmin, zmax = v[:,2].min(), v[:,2].max()
            print(f"    face {fi} covers {n}/64 pts  Z[{zmin:.2f},{zmax:.2f}]  "
                  f"v=[({v[0,0]:.1f},{v[0,1]:.1f}),({v[1,0]:.1f},{v[1,1]:.1f}),({v[2,0]:.1f},{v[2,1]:.1f})]")


if __name__ == "__main__":
    main()
