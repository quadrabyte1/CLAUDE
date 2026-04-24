"""
serial_engraver.py — Per-course serial-number engraving for generated 3MF items.

Each golf course has its own serial counter, starting at 100 and advancing by
one after every successful Generate run.  The serial is engraved as a 1 mm
deep relief (recessed cut) into the back (z=0) face of every item produced in
that Generate call.

Text format: ``s/n: NNN`` (e.g. ``s/n: 100``)
Font size  : 8 point (1 pt = 1/72 inch ≈ 0.3528 mm)
Depth      : 1 mm recessed into the back face

The counter is persisted at ``<course_dir>/serial.json`` with the shape
``{"next_serial": 101}``.  The file is only written *after* the 3MF export
succeeds, so a crash mid-generate never burns a serial number.

Public API:
    peek_next_serial(course) -> int
        Read (without advancing) the serial that would be used on the next
        Generate.  Creates the file at 100 if missing.
    commit_serial(course) -> int
        Advance the course's serial counter by one and persist.  Returns the
        serial that *was* just used (i.e. the value from peek_next_serial
        before this call).
    engrave_serial_on_mesh(mesh, serial_number, ...) -> trimesh.Trimesh
        Return a new mesh with ``s/n: NNN`` carved 1 mm deep into the back
        (z ≈ 0) face.
    engrave_scene_geometries(scene, serial_number) -> None
        In-place: engrave every geometry in a trimesh.Scene.
"""

from __future__ import annotations

import json
import os
from typing import Optional

import numpy as np
import trimesh

# Re-use the robust TextPath → polygon → extrude pipeline from plate_text.py.
# Only the *mesh builder* is reused; sizing here is driven by point-size
# instead of cap-height because a serial number is a fixed-size engraving.
try:
    from plate_text import render_text_mesh as _plate_render_text_mesh
except ImportError:
    # Allow the module to be imported from outside app/ (e.g. for tests)
    import sys
    sys.path.insert(0, os.path.dirname(__file__))
    from plate_text import render_text_mesh as _plate_render_text_mesh


# ── Constants ────────────────────────────────────────────────────────────────

STARTING_SERIAL: int = 100
SERIAL_FILENAME: str = "serial.json"

# Engraving geometry
ENGRAVE_DEPTH_MM: float = 1.0           # 1 mm relief
ENGRAVE_FONT_PT: float = 8.0            # 8 point type
PT_TO_MM: float = 25.4 / 72.0           # 1 pt ≈ 0.3528 mm
ENGRAVE_FONT_FAMILY: str = "DejaVu Sans"
ENGRAVE_BOLD: bool = True               # bold reads better as a relief
# Relative offset (XY) from the part's back-face centroid, in mm.
# (0, 0) keeps the engraving dead-centre on the back face.
ENGRAVE_OFFSET_XY: tuple = (0.0, 0.0)


# ── Course path resolution ───────────────────────────────────────────────────

def _course_dir(course: str) -> str:
    """Resolve a course's root directory under EliteGolfMoments/GolfCourses/.

    Falls back to owner_inbox/ if the course directory doesn't exist (e.g. a
    test run with an unknown course name).
    """
    from generate_stl_3mf import EGM_BASE, OWNER_INBOX
    candidate = os.path.join(EGM_BASE, course)
    if os.path.isdir(candidate):
        return candidate
    # Fallback: per-course subdir under owner_inbox/ so counters are still
    # persisted somewhere deterministic and not colliding with other courses.
    fallback = os.path.join(OWNER_INBOX, "_serials", course or "unknown")
    os.makedirs(fallback, exist_ok=True)
    return fallback


def _serial_path(course: str) -> str:
    return os.path.join(_course_dir(course), SERIAL_FILENAME)


# ── Counter read / write ─────────────────────────────────────────────────────

def _read_counter(path: str) -> int:
    """Read ``next_serial`` from disk; return STARTING_SERIAL if absent/corrupt."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        val = int(data.get("next_serial", STARTING_SERIAL))
        if val < STARTING_SERIAL:
            val = STARTING_SERIAL
        return val
    except (FileNotFoundError, json.JSONDecodeError, ValueError, TypeError):
        return STARTING_SERIAL


def _write_counter(path: str, next_serial: int) -> None:
    """Atomically persist ``next_serial`` to the course's serial.json."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"next_serial": int(next_serial)}, f, indent=2)
        f.write("\n")
    os.replace(tmp, path)


def peek_next_serial(course: str) -> int:
    """Return the serial that the next Generate run will use (no increment).

    Creates the counter file on first read so repeated peeks return the same
    value until commit_serial() is called.
    """
    path = _serial_path(course)
    val = _read_counter(path)
    if not os.path.exists(path):
        _write_counter(path, val)
    return val


def commit_serial(course: str) -> int:
    """Advance the course's counter by one; return the serial *just used*.

    Call AFTER the 3MF is successfully written to disk so a crash doesn't
    burn a serial number.
    """
    path = _serial_path(course)
    used = _read_counter(path)
    _write_counter(path, used + 1)
    return used


# ── Text mesh construction ───────────────────────────────────────────────────

def _build_serial_text_mesh(
    serial_number: int,
    depth_mm: float = ENGRAVE_DEPTH_MM,
    font_pt: float = ENGRAVE_FONT_PT,
    font_family: str = ENGRAVE_FONT_FAMILY,
    bold: bool = ENGRAVE_BOLD,
) -> trimesh.Trimesh:
    """Build an extruded text mesh for ``s/n: NNN``.

    The text is rendered with cap-height ≈ ``font_pt * PT_TO_MM`` so that 8 pt
    maps to ~2.82 mm cap-height — matches print-industry expectations for
    point sizing.

    The returned mesh:
      • is centred on X=0, Y=0 (via ``render_text_mesh``)
      • extrudes in +Z from z=0 to z=depth_mm
    """
    text = f"s/n: {int(serial_number)}"
    # plate_text.render_text_mesh sizes text by *cap-height* in mm.  Convert
    # the requested point-size to mm directly.
    height_mm = float(font_pt) * PT_TO_MM
    return _plate_render_text_mesh(
        text=text,
        height_mm=height_mm,
        depth_mm=depth_mm,
        # Cap the width at something reasonable so the text never overflows
        # even the smallest trap; render_text_mesh shrinks proportionally if
        # needed.  40 mm is ~1.6 in — fits comfortably on any of our parts.
        max_width_mm=40.0,
        font_family=font_family,
        bold=bold,
        italic=False,
    )


# ── Core engraving primitive ─────────────────────────────────────────────────

def _find_back_face_z(mesh: trimesh.Trimesh) -> float:
    """Identify the Z coordinate of the mesh's back (bottom) face.

    All items produced by the pipeline (green surface, fringe, traps) have
    their flat base at z=0.  For robustness we return the *minimum* z, which
    is the build-plate side for any mesh placed upright.
    """
    return float(mesh.bounds[0, 2])


def _centroid_xy(mesh: trimesh.Trimesh) -> tuple:
    """Return the XY centroid of the mesh bounding box (not the volume
    centroid, so it lands at the visual centre of the back face regardless
    of top-surface texture warping).
    """
    bb = mesh.bounds           # shape (2, 3): [min, max] in xyz
    cx = 0.5 * (bb[0, 0] + bb[1, 0])
    cy = 0.5 * (bb[0, 1] + bb[1, 1])
    return float(cx), float(cy)


def _bottom_polygon(mesh: trimesh.Trimesh, plane_tol: float = 0.05):
    """Return a Shapely polygon (possibly MultiPolygon) of the mesh's bottom
    face (z ≈ z_min), or None if it can't be recovered.

    Uses the bottom-face triangulation directly: unions the footprint of
    every triangle whose three verts sit at the mesh's minimum Z, then fixes
    up self-intersections with buffer(0).
    """
    from shapely.geometry import Polygon as _Poly
    from shapely.ops import unary_union as _uu

    verts = np.asarray(mesh.vertices)
    faces = np.asarray(mesh.faces)
    if len(verts) == 0 or len(faces) == 0:
        return None

    z_min = float(verts[:, 2].min())
    z_of_face = verts[faces, 2]
    bm = (np.abs(z_of_face - z_min) < plane_tol).all(axis=1)
    if not bm.any():
        return None

    tris = faces[bm]
    polys = []
    for tri in tris:
        p = _Poly([(float(verts[tri[0], 0]), float(verts[tri[0], 1])),
                   (float(verts[tri[1], 0]), float(verts[tri[1], 1])),
                   (float(verts[tri[2], 0]), float(verts[tri[2], 1]))])
        if not p.is_valid:
            p = p.buffer(0)
        if not p.is_empty and p.area > 1e-6:
            polys.append(p)

    if not polys:
        return None

    try:
        union = _uu(polys)
        if union.is_empty:
            return None
        # Simplify touching edges with a tiny buffer pair (clean up T-junctions)
        union = union.buffer(0)
        return union
    except Exception:
        return None


def _choose_engraving_centre(
    mesh: trimesh.Trimesh,
    preferred_xy: tuple,
    text_width_mm: float,
    text_height_mm: float,
) -> tuple:
    """Pick an XY centre for the engraving that lies on the part's back face
    and keeps the text rectangle inside the back-face polygon.

    Strategy:
    1. If the preferred point (usually the bounding-box centroid) lies on
       the back face AND the text rectangle around it stays inside the
       polygon, use it.
    2. Otherwise, find the *representative_point* of the back polygon (a
       Shapely-guaranteed interior point), then shift if the text rectangle
       overhangs an edge.
    3. Final fallback: the polygon's point-on-surface (centroid-ish but
       always interior).
    """
    from shapely.geometry import Point as _Pt, Polygon as _Poly
    from shapely.affinity import translate as _translate

    poly = _bottom_polygon(mesh)
    if poly is None:
        return preferred_xy

    # Helper: test whether a WxH rect centred at (x,y) stays entirely inside poly
    def _rect_inside(x: float, y: float) -> bool:
        margin = 1.0   # mm of breathing room around text
        w = text_width_mm + 2 * margin
        h = text_height_mm + 2 * margin
        rect = _Poly([(x - w / 2, y - h / 2),
                      (x + w / 2, y - h / 2),
                      (x + w / 2, y + h / 2),
                      (x - w / 2, y + h / 2)])
        return poly.contains(rect)

    # (1) Preferred point
    px, py = float(preferred_xy[0]), float(preferred_xy[1])
    if poly.contains(_Pt(px, py)) and _rect_inside(px, py):
        return px, py

    # (2) Representative interior point
    try:
        rp = poly.representative_point()
        rx, ry = float(rp.x), float(rp.y)
        if _rect_inside(rx, ry):
            return rx, ry
    except Exception:
        pass

    # (3) Search along a ring of candidate offsets from the bounding-box
    #     centre — prefer staying near the user-visible centre of the part.
    bb = mesh.bounds
    cx = 0.5 * (bb[0, 0] + bb[1, 0])
    cy = 0.5 * (bb[0, 1] + bb[1, 1])
    half_x = 0.5 * (bb[1, 0] - bb[0, 0])
    half_y = 0.5 * (bb[1, 1] - bb[0, 1])
    inset = max(text_width_mm, text_height_mm) * 0.8 + 2.0
    # Ring at ~70% of the way from centre to edge — prefers the middle of a
    # frame-shaped piece (e.g. fringe).  Uses 24 angles.
    for frac in (0.75, 0.6, 0.5, 0.85, 0.35):
        r_x = max(half_x - inset, 1.0) * frac
        r_y = max(half_y - inset, 1.0) * frac
        for k in range(24):
            ang = 2 * np.pi * k / 24
            x = cx + r_x * np.cos(ang)
            y = cy + r_y * np.sin(ang)
            if poly.contains(_Pt(x, y)) and _rect_inside(x, y):
                return float(x), float(y)

    # (4) Last resort — shrink the text rectangle check and just return rep point
    try:
        rp = poly.representative_point()
        return float(rp.x), float(rp.y)
    except Exception:
        return preferred_xy


def _try_repair_for_boolean(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
    """Best-effort mesh repair to help boolean engines accept non-manifold
    inputs (duplicated verts, inconsistent winding, small holes).

    Returns a *new* mesh; the original is left untouched.
    """
    m = mesh.copy()
    try:
        m.merge_vertices()
    except Exception:
        pass
    try:
        m.remove_duplicate_faces()
    except Exception:
        pass
    try:
        m.remove_degenerate_faces()
    except Exception:
        pass
    try:
        trimesh.repair.fix_normals(m)
    except Exception:
        pass
    try:
        trimesh.repair.fix_inversion(m)
    except Exception:
        pass
    try:
        trimesh.repair.fix_winding(m)
    except Exception:
        pass
    try:
        trimesh.repair.fill_holes(m)
    except Exception:
        pass
    return m


def _boolean_difference(a: trimesh.Trimesh, b: trimesh.Trimesh) -> Optional[trimesh.Trimesh]:
    """Try every boolean engine trimesh exposes until one succeeds.

    First attempts on the raw inputs; on failure tries again with best-effort
    repairs applied to ``a``.  Returns None if every attempt fails — caller
    can then fall back to the un-engraved original mesh (or a different
    engraving strategy).
    """
    engines = ("manifold", "blender", "scad")

    def _try(a_mesh: trimesh.Trimesh, b_mesh: trimesh.Trimesh) -> Optional[trimesh.Trimesh]:
        last: Optional[Exception] = None
        for engine in engines:
            try:
                result = trimesh.boolean.difference([a_mesh, b_mesh], engine=engine)
            except Exception as exc:
                last = exc
                continue
            if result is None:
                continue
            if len(result.vertices) == 0 or len(result.faces) == 0:
                continue
            return result
        if last is not None:
            # Surface the last error when all engines failed on this pass
            print(f"[serial_engraver]   boolean.difference: all engines failed "
                  f"(last error: {last})")
        return None

    # Pass 1: raw inputs
    result = _try(a, b)
    if result is not None:
        return result

    # Pass 2: repair the target mesh (cutter is built cleanly already) and
    # try again.  Covers "manifold refused: not 2-manifold" style failures.
    repaired = _try_repair_for_boolean(a)
    if repaired is a or repaired.vertices.shape == a.vertices.shape:
        # No change — don't waste a retry
        pass
    else:
        result = _try(repaired, b)
        if result is not None:
            return result
    # One more try with the repaired mesh regardless (merge_vertices alone
    # can change face topology without vertex count changes).
    result = _try(repaired, b)
    if result is not None:
        return result
    return None


def _engrave_by_vertex_push(
    mesh: trimesh.Trimesh,
    text_polys_xy,
    depth_mm: float,
) -> Optional[trimesh.Trimesh]:
    """Fallback engraving: push every back-face (z ≈ z_min) vertex that falls
    inside the text polygon footprint *up* by ``depth_mm``.

    This creates a recessed impression without a boolean operation.  It
    won't produce crisp glyph edges (resolution is limited by the existing
    triangulation), but it reliably marks non-manifold meshes with a visible
    serial-number impression.

    Returns a new mesh, or None if no back-face vertices could be found.
    """
    from shapely.geometry import Point as _Pt, MultiPolygon as _MP

    verts = mesh.vertices.copy()
    if len(verts) == 0:
        return None

    z_min = float(verts[:, 2].min())
    # "back face" = within 0.05 mm of z_min
    tol = 0.05
    back_mask = np.abs(verts[:, 2] - z_min) < tol
    if not back_mask.any():
        return None

    # Union the text polygons for fast contains() check
    if not text_polys_xy:
        return None
    if len(text_polys_xy) == 1:
        test_geom = text_polys_xy[0]
    else:
        from shapely.ops import unary_union
        test_geom = unary_union(text_polys_xy)

    moved = 0
    for vi in np.where(back_mask)[0]:
        x, y = float(verts[vi, 0]), float(verts[vi, 1])
        if test_geom.contains(_Pt(x, y)):
            verts[vi, 2] = z_min + depth_mm
            moved += 1

    if moved == 0:
        return None

    new_mesh = mesh.copy()
    new_mesh.vertices = verts
    try:
        trimesh.repair.fix_normals(new_mesh)
    except Exception:
        pass
    print(f"[serial_engraver]   vertex-push fallback: pushed {moved} "
          f"back-face vertex(es) up by {depth_mm} mm")
    return new_mesh


def _engrave_by_plane_surgery(
    mesh: trimesh.Trimesh,
    text_polys_xy,
    depth_mm: float,
    plane_tol: float = 0.02,
) -> Optional[trimesh.Trimesh]:
    """Rebuild the bottom face (z ≈ z_min) to carry a recessed text pocket.

    This is a geometry-surgery fallback for meshes that trimesh's boolean
    engines can't handle (non-manifold, self-intersecting, etc.).  It only
    assumes the mesh has a flat bottom at its lowest Z coordinate — which is
    true for every item our pipeline produces (green surface, fringe, traps).

    Strategy
    --------
    1. Identify all faces whose three vertices lie within ``plane_tol`` of
       z_min (= the bottom cap).
    2. Recover the 2-D bottom-polygon boundary by extracting boundary edges
       of the bottom face set (edges used by exactly one bottom face), then
       tracing them into closed loops.
    3. Subtract the text polygons from that boundary polygon → new bottom
       triangulation (extruded to a zero-thickness set of triangles at z_min).
    4. Triangulate the text polygons at z_min + depth (the ceiling of the
       pocket).
    5. Stitch vertical walls from the text-polygon perimeter at z_min up to
       z_min + depth.
    6. Drop original bottom faces, append new bottom + pocket + wall faces,
       rebuild the mesh, clean up.
    """
    from shapely.geometry import Polygon as _Poly, MultiPolygon as _MP
    from shapely.ops import unary_union as _uu
    from collections import defaultdict

    if not text_polys_xy:
        return None

    verts = np.asarray(mesh.vertices)
    faces = np.asarray(mesh.faces)
    if len(verts) == 0 or len(faces) == 0:
        return None

    z_min = float(verts[:, 2].min())

    # Boolean mask over faces: True if all 3 verts are within plane_tol of z_min
    z_of_face_verts = verts[faces, 2]              # (F, 3)
    bot_mask = (np.abs(z_of_face_verts - z_min) < plane_tol).all(axis=1)
    n_bot = int(bot_mask.sum())
    if n_bot == 0:
        print(f"[serial_engraver]   plane-surgery: no bottom faces at z={z_min:.3f} — abort")
        return None

    bot_faces = faces[bot_mask]

    # --- 2. Recover the bottom polygon boundary from the bottom-face edges.
    #     An edge is a boundary edge if it belongs to exactly one bottom face
    #     (treating undirected edges).
    edge_count: dict = defaultdict(int)
    for a, b, c in bot_faces:
        for e in ((a, b), (b, c), (c, a)):
            key = (min(e), max(e))
            edge_count[key] += 1

    boundary_edges = [e for e, n in edge_count.items() if n == 1]
    if not boundary_edges:
        print("[serial_engraver]   plane-surgery: no boundary edges found — abort")
        return None

    # Build adjacency to trace loops
    adj: dict = defaultdict(list)
    for a, b in boundary_edges:
        adj[a].append(b)
        adj[b].append(a)

    loops_vidx: list = []
    visited_edges: set = set()
    for a0, b0 in boundary_edges:
        key0 = (min(a0, b0), max(a0, b0))
        if key0 in visited_edges:
            continue
        # Trace a loop starting at a0
        loop = [a0]
        prev = None
        cur = a0
        while True:
            neighbors = [n for n in adj[cur] if n != prev]
            if not neighbors:
                break
            # Prefer an unvisited edge
            found = None
            for n in neighbors:
                k = (min(cur, n), max(cur, n))
                if k not in visited_edges:
                    found = n
                    break
            if found is None:
                break
            visited_edges.add((min(cur, found), max(cur, found)))
            loop.append(found)
            prev, cur = cur, found
            if cur == a0:
                break
        if len(loop) >= 3:
            loops_vidx.append(loop)

    if not loops_vidx:
        print("[serial_engraver]   plane-surgery: failed to trace any loops — abort")
        return None

    # Convert vertex-index loops to XY polygons (drop the closing repeat if any)
    loops_xy: list = []
    for loop in loops_vidx:
        ring = [tuple(verts[vi, :2]) for vi in loop]
        if ring[0] == ring[-1]:
            ring = ring[:-1]
        if len(ring) >= 3:
            loops_xy.append(ring)

    # The bottom cap may be a polygon-with-holes (e.g. fringe has green
    # cutout + tee-pin bore).  Shapely can build it as a list of
    # Polygons — we'll union them and then fix up with buffer(0).
    raw_polys = []
    for ring in loops_xy:
        try:
            p = _Poly(ring)
            if not p.is_valid:
                p = p.buffer(0)
            if not p.is_empty:
                raw_polys.append(p)
        except Exception:
            continue
    if not raw_polys:
        print("[serial_engraver]   plane-surgery: no valid bottom polygon — abort")
        return None

    # Sort by area DESC; largest is the outer; everything strictly inside is
    # a hole.  Same classification algorithm as plate_text.py.
    raw_polys.sort(key=lambda p: p.area, reverse=True)
    used = [False] * len(raw_polys)
    final: list = []
    for i in range(len(raw_polys)):
        if used[i]:
            continue
        outer = raw_polys[i]
        holes = []
        for j in range(i + 1, len(raw_polys)):
            if used[j]:
                continue
            if outer.contains(raw_polys[j].centroid):
                holes.append(list(raw_polys[j].exterior.coords))
                used[j] = True
        try:
            pp = _Poly(list(outer.exterior.coords), holes)
            if not pp.is_valid:
                pp = pp.buffer(0)
            if not pp.is_empty:
                final.append(pp)
                used[i] = True
        except Exception:
            continue
    if not final:
        print("[serial_engraver]   plane-surgery: final polygon assembly failed — abort")
        return None

    bottom_poly = _uu(final)   # may be a MultiPolygon

    # Union the text polygons (the cut-out shape)
    text_union = _uu(text_polys_xy)

    # Clip text to the bottom polygon so we never carve past the part's
    # footprint (e.g. if the serial centre is near an edge)
    text_clipped = text_union.intersection(bottom_poly)
    if text_clipped.is_empty:
        print("[serial_engraver]   plane-surgery: text doesn't land inside bottom — skipping engraving")
        return None

    # New bottom face shape: bottom polygon minus text
    new_bottom = bottom_poly.difference(text_clipped)
    if new_bottom.is_empty:
        print("[serial_engraver]   plane-surgery: bottom-minus-text empty — abort")
        return None

    # --- 3..5. Build replacement geometry via two small extrusions ---
    # (a) new bottom cap at z_min (one-sided): build a 0-height extrusion and
    #     keep only the BOTTOM triangles (z ≈ 0 after extrude_polygon).
    # (b) pocket ceiling at z_min + depth: bottom of a thin slab extruded
    #     upward from that height, but we only need its TOP triangles.
    # (c) vertical walls: built from text_clipped perimeter, z_min .. z_min+depth.
    # Helper duplicated below — but we need it here too for `new_bottom`
    def _as_polygon_list_outer(geom):
        if geom is None or geom.is_empty:
            return []
        if geom.geom_type == "Polygon":
            return [geom]
        if geom.geom_type == "MultiPolygon":
            return list(geom.geoms)
        if geom.geom_type == "GeometryCollection":
            return [g for g in geom.geoms if g.geom_type == "Polygon" and not g.is_empty]
        return []

    new_bottom_list = _as_polygon_list_outer(new_bottom)
    if not new_bottom_list:
        print("[serial_engraver]   plane-surgery: new bottom polygon is empty — abort")
        return None

    try:
        bot_verts_list = []
        bot_faces_list = []
        vert_offset_b = 0
        for nb in new_bottom_list:
            bsl = trimesh.creation.extrude_polygon(nb, height=0.001)
            z0 = bsl.vertices[:, 2]
            bm = z0 < 0.0005
            fmask = bm[bsl.faces].all(axis=1)
            verts_sub = bsl.vertices.copy()
            verts_sub[:, 2] = z_min
            # Flip winding so new bottom normals point −Z (outward = downward)
            faces_sub = bsl.faces[fmask]
            faces_sub = np.stack([faces_sub[:, 0], faces_sub[:, 2], faces_sub[:, 1]], axis=1)
            faces_sub = faces_sub + vert_offset_b
            bot_verts_list.append(verts_sub)
            bot_faces_list.append(faces_sub)
            vert_offset_b += len(verts_sub)
        bot_slab_verts = np.concatenate(bot_verts_list, axis=0)
        new_bot_faces = np.concatenate(bot_faces_list, axis=0)
    except Exception as exc:
        print(f"[serial_engraver]   plane-surgery: new-bottom extrude failed: {exc}")
        return None

    # Helper: normalise text_clipped (Polygon or MultiPolygon) → list of Polygons
    def _as_polygon_list(geom):
        if geom is None or geom.is_empty:
            return []
        if geom.geom_type == "Polygon":
            return [geom]
        if geom.geom_type == "MultiPolygon":
            return list(geom.geoms)
        if geom.geom_type == "GeometryCollection":
            return [g for g in geom.geoms if g.geom_type == "Polygon" and not g.is_empty]
        return []

    text_polys_list = _as_polygon_list(text_clipped)
    if not text_polys_list:
        print("[serial_engraver]   plane-surgery: text_clipped produced no polygons")
        return None

    # Pocket ceiling: extrude each text polygon as a zero-thin slab; keep
    # BOTTOM faces.  Normals already point −Z (downward = into the cavity).
    pocket_verts_list = []
    pocket_faces_list = []
    vert_offset_pocket = 0
    try:
        for tp in text_polys_list:
            psl = trimesh.creation.extrude_polygon(tp, height=0.001)
            zp = psl.vertices[:, 2]
            pm = zp < 0.0005
            pfmask = pm[psl.faces].all(axis=1)
            verts_sub = psl.vertices.copy()
            verts_sub[:, 2] = z_min + depth_mm
            faces_sub = psl.faces[pfmask] + vert_offset_pocket
            pocket_verts_list.append(verts_sub)
            pocket_faces_list.append(faces_sub)
            vert_offset_pocket += len(verts_sub)
        pocket_verts = (np.concatenate(pocket_verts_list, axis=0)
                        if pocket_verts_list else np.zeros((0, 3)))
        new_pocket_faces = (np.concatenate(pocket_faces_list, axis=0)
                            if pocket_faces_list else np.zeros((0, 3), dtype=int))
    except Exception as exc:
        print(f"[serial_engraver]   plane-surgery: pocket-ceiling extrude failed: {exc}")
        return None

    # Walls: extrude each text polygon by depth_mm, keep side faces only.
    wall_verts_list = []
    wall_faces_list = []
    vert_offset_wall = 0
    try:
        for tp in text_polys_list:
            wsl = trimesh.creation.extrude_polygon(tp, height=depth_mm)
            zw = wsl.vertices[:, 2]
            bot_w = zw < 0.0005
            top_w = zw > (depth_mm - 0.0005)
            sm = ~(bot_w[wsl.faces].all(axis=1) | top_w[wsl.faces].all(axis=1))
            verts_sub = wsl.vertices.copy()
            verts_sub[:, 2] += z_min
            faces_sub = wsl.faces[sm]
            # Flip winding for inward normals
            faces_sub = np.stack([faces_sub[:, 0], faces_sub[:, 2], faces_sub[:, 1]], axis=1)
            faces_sub = faces_sub + vert_offset_wall
            wall_verts_list.append(verts_sub)
            wall_faces_list.append(faces_sub)
            vert_offset_wall += len(verts_sub)
        wall_verts = (np.concatenate(wall_verts_list, axis=0)
                      if wall_verts_list else np.zeros((0, 3)))
        new_wall_faces = (np.concatenate(wall_faces_list, axis=0)
                          if wall_faces_list else np.zeros((0, 3), dtype=int))
    except Exception as exc:
        print(f"[serial_engraver]   plane-surgery: wall extrude failed: {exc}")
        return None

    # --- 6. Reassemble: original mesh minus old bottom faces, plus new pieces ---
    remaining_faces = faces[~bot_mask]

    # Concatenate everything: original verts + new pieces' verts.
    # We rebuild the mesh by concatenating via trimesh.util.concatenate so
    # trimesh handles the index remapping.
    m_remain = trimesh.Trimesh(vertices=verts, faces=remaining_faces, process=False)
    m_bot    = trimesh.Trimesh(vertices=bot_slab_verts, faces=new_bot_faces, process=False)
    m_ceil   = trimesh.Trimesh(vertices=pocket_verts, faces=new_pocket_faces, process=False)
    m_walls  = trimesh.Trimesh(vertices=wall_verts, faces=new_wall_faces, process=False)

    try:
        combined = trimesh.util.concatenate([m_remain, m_bot, m_ceil, m_walls])
    except Exception as exc:
        print(f"[serial_engraver]   plane-surgery: concatenate failed: {exc}")
        return None

    # Merge close vertices so the new bottom edges stitch into the walls
    try:
        combined.merge_vertices()
    except Exception:
        pass

    print(f"[serial_engraver]   plane-surgery: removed {n_bot} old-bottom faces, "
          f"added {len(new_bot_faces)}+{len(new_pocket_faces)}+{len(new_wall_faces)} "
          f"new faces (bottom/pocket/walls)")
    return combined


def _build_text_polygons_xy(
    serial_number: int,
    font_pt: float,
    cx: float,
    cy: float,
    mirror_y: bool = True,
):
    """Return the 2-D Shapely polygon(s) for ``s/n: NNN`` rendered at the
    given centre, for use by the vertex-push fallback.  Matches the mesh
    produced by _build_serial_text_mesh in shape & orientation.
    """
    from matplotlib.textpath import TextPath
    from matplotlib.font_manager import FontProperties
    from shapely.geometry import Polygon as _Poly
    from shapely.validation import make_valid as _make_valid

    fp = FontProperties(
        family=ENGRAVE_FONT_FAMILY,
        weight="bold" if ENGRAVE_BOLD else "normal",
        style="normal",
    )
    text = f"s/n: {int(serial_number)}"
    base_size = 100.0
    tp = TextPath((0, 0), text, size=base_size, prop=fp)
    raw = tp.to_polygons()
    if not raw:
        return []

    # Measure cap-height so we can scale the XY footprint the same way the
    # 3-D mesh does.
    cap_raw = 0.0
    for ch in ("M", "H"):
        tp_c = TextPath((0, 0), ch, size=base_size, prop=fp)
        pp = tp_c.to_polygons()
        if pp:
            ys = np.concatenate([np.asarray(p)[:, 1] for p in pp if len(p) >= 2])
            if ys.size:
                cap_raw = float(ys.max() - ys.min())
                if cap_raw > 1e-9:
                    break
    if cap_raw < 1e-9:
        return []

    target_cap_mm = float(font_pt) * PT_TO_MM
    scale = target_cap_mm / cap_raw

    # Centre: text-path bbox midpoint in raw units → shift to (cx, cy) after
    # scaling, with the cap-midpoint at cy.
    all_pts = np.concatenate([np.asarray(p) for p in raw if len(p) >= 2])
    mid_x = 0.5 * (all_pts[:, 0].min() + all_pts[:, 0].max())
    mid_y = cap_raw / 2.0   # cap-height midpoint (matches _plate_render_text_mesh)

    ysign = -1.0 if mirror_y else 1.0

    polys: list = []
    for verts in raw:
        if len(verts) < 3:
            continue
        coords = [
            (
                (v[0] - mid_x) * scale + cx,
                ((v[1] - mid_y) * scale) * ysign + cy,
            )
            for v in verts
        ]
        try:
            p = _Poly(coords)
            if not p.is_valid:
                p = _make_valid(p)
            # Keep only polygonal pieces
            if hasattr(p, "geoms"):
                for g in p.geoms:
                    if getattr(g, "geom_type", "") == "Polygon" and not g.is_empty:
                        polys.append(g)
            elif getattr(p, "geom_type", "") == "Polygon" and not p.is_empty:
                polys.append(p)
        except Exception:
            continue
    return polys


def engrave_serial_on_mesh(
    mesh: trimesh.Trimesh,
    serial_number: int,
    depth_mm: float = ENGRAVE_DEPTH_MM,
    font_pt: float = ENGRAVE_FONT_PT,
    offset_xy: tuple = ENGRAVE_OFFSET_XY,
) -> trimesh.Trimesh:
    """Return a copy of ``mesh`` with ``s/n: NNN`` cut 1 mm deep into the
    back (lowest-Z) face.

    The text reads *correctly* when looking straight at the back face — i.e.
    we mirror the glyphs about the X axis so they are not reversed when the
    print is flipped over (otherwise the text would be a mirror image).
    """
    if mesh is None:
        return mesh

    # 1. Build text mesh: extrudes from z=0 to z=depth_mm, centred on origin
    try:
        text_mesh = _build_serial_text_mesh(
            serial_number=serial_number,
            depth_mm=depth_mm,
            font_pt=font_pt,
        )
    except Exception as exc:
        print(f"[serial_engraver] WARNING: text mesh build failed: {exc}")
        return mesh

    # 2. Mirror the text about the X axis so it reads correctly when the
    #    part is flipped over to view the back.
    text_mesh = text_mesh.copy()
    T_flip = np.eye(4)
    T_flip[1, 1] = -1.0      # reflect Y
    text_mesh.apply_transform(T_flip)
    # Reflection inverts face winding; fix normals so the mesh is still
    # outward-facing (important for a robust boolean).
    try:
        trimesh.repair.fix_normals(text_mesh)
    except Exception:
        pass

    # 3. Position the text: prefer the back-face centroid but fall back to
    #    an interior point of the back polygon if the centroid is over a
    #    hole (e.g. the fringe, whose centre is the green cutout).
    z_back = _find_back_face_z(mesh)
    cx, cy = _centroid_xy(mesh)

    # Measure the rendered text rectangle so we can test it fits
    tbb = text_mesh.bounds
    text_w = float(tbb[1, 0] - tbb[0, 0])
    text_h = float(tbb[1, 1] - tbb[0, 1])

    preferred = (cx + float(offset_xy[0]), cy + float(offset_xy[1]))
    tx, ty = _choose_engraving_centre(
        mesh,
        preferred_xy=preferred,
        text_width_mm=text_w,
        text_height_mm=text_h,
    )
    # We want the cut to span z in [z_back, z_back + depth_mm] — i.e. the
    # relief floor sits exactly depth_mm above the back face.  To guarantee
    # the cutter fully crosses the back plane (so manifold booleans don't
    # produce slivers), we extend BOTH ends by a small epsilon: build the
    # cutter tall enough to project below the back face and still reach
    # z_back + depth.
    eps = 0.05
    # Stretch the cutter vertically by eps on the bottom only.  The cutter
    # was built with z ∈ [0, depth_mm] — shift DOWN by eps so its bottom
    # dips below z_back while its top stays at exactly z_back + depth_mm.
    bottom_verts_mask = text_mesh.vertices[:, 2] < (depth_mm * 0.5)
    text_mesh.vertices[bottom_verts_mask, 2] -= eps
    tz = z_back
    text_mesh.apply_translation((tx, ty, tz))

    # 4. Engraving strategy chain — try in order of increasing fallback:
    #    (a) boolean.difference (crisp, requires manifold input)
    #    (b) plane-surgery on the back face (robust to non-manifold tops;
    #        only assumes a flat bottom at z_min, which our pipeline always
    #        produces)
    #    (c) vertex-push impression (low-resolution but always runs)
    engraved = _boolean_difference(mesh, text_mesh)
    if engraved is None:
        print(f"[serial_engraver]   boolean failed for mesh "
              f"(verts={len(mesh.vertices)}, faces={len(mesh.faces)}); "
              f"trying plane-surgery fallback…")
        text_polys_xy = _build_text_polygons_xy(
            serial_number=serial_number,
            font_pt=font_pt,
            cx=tx,
            cy=ty,
            mirror_y=True,
        )
        engraved = _engrave_by_plane_surgery(mesh, text_polys_xy, depth_mm)
        if engraved is None:
            print(f"[serial_engraver]   plane-surgery failed; "
                  f"trying vertex-push fallback…")
            engraved = _engrave_by_vertex_push(mesh, text_polys_xy, depth_mm)
        if engraved is None:
            print(f"[serial_engraver] WARNING: all engraving strategies "
                  f"failed; returning un-engraved original.")
            return mesh

    # 5. Light repair — fix any small manifold glitches introduced by the
    #    boolean.  Never hard-fail: caller expects a mesh back no matter what.
    try:
        trimesh.repair.fix_normals(engraved)
        if not engraved.is_watertight:
            trimesh.repair.fill_holes(engraved)
    except Exception:
        pass

    return engraved


def engrave_scene_geometries(scene: trimesh.Scene, serial_number: int) -> dict:
    """Replace every geometry in ``scene`` with its engraved copy, in place.

    Returns a dict summary: ``{geom_name: {"engraved": bool, "watertight": bool}}``
    for logging.
    """
    summary: dict = {}
    # scene.geometry is an OrderedDict; iterate over a snapshot of items so we
    # can mutate the dict during iteration.
    for name in list(scene.geometry.keys()):
        original = scene.geometry[name]
        try:
            engraved = engrave_serial_on_mesh(original, serial_number)
        except Exception as exc:
            print(f"[serial_engraver]   '{name}' — engraving raised: {exc}")
            engraved = original
        was_modified = engraved is not original
        scene.geometry[name] = engraved
        summary[name] = {
            "engraved": was_modified,
            "watertight": bool(getattr(engraved, "is_watertight", False)),
            "faces": int(len(engraved.faces)),
        }
        flag = "engraved" if was_modified else "unchanged (fallback)"
        wt = "watertight" if summary[name]["watertight"] else "NOT watertight"
        print(f"[serial_engraver]   '{name}': {flag}, {wt}, "
              f"{summary[name]['faces']} faces")
    return summary


# ── CLI helper (quick smoke test) ────────────────────────────────────────────

if __name__ == "__main__":
    import sys as _sys
    # Build a little demo slab and engrave it, writing to owner_inbox/
    slab = trimesh.creation.box(extents=(60.0, 30.0, 10.0))
    # Shift so base sits at z=0 (matches our pipeline's convention)
    slab.apply_translation((0.0, 0.0, 5.0))
    serial = int(_sys.argv[1]) if len(_sys.argv) > 1 else 100
    cut = engrave_serial_on_mesh(slab, serial_number=serial)
    from generate_stl_3mf import OWNER_INBOX as _OI
    out = os.path.join(_OI, f"serial_engraver_demo_{serial}.stl")
    cut.export(out)
    print(f"Wrote demo: {out}")
    print(f"Watertight: {cut.is_watertight}")
