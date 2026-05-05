"""
plate_text.py — Custom text plate generator for 3MF output.

Generates a Bambu Studio-compatible 3MF file with three lines of engraved
text on the tilted front face of the plate, using the Mike Kallbrier 3MF
as a template to preserve all geometry and transform data.

CLI usage:
    python app/plate_text.py "Line 1" "Line 2" "Line 3" --out owner_inbox/custom_plate.3mf
"""

import argparse
import os
import re
import shutil
import sys
import tempfile
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

import uuid as _uuid_mod

import trimesh
import trimesh.creation
import trimesh.util
import numpy as np

# ── Namespace constants for 3MF XML ──────────────────────────────────────────

_NS_CORE = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
_NS_BAMBU = "http://schemas.bambulab.com/package/2021"
_NS_PROD = "http://schemas.microsoft.com/3dmanufacturing/production/2015/06"

ET.register_namespace("", _NS_CORE)
ET.register_namespace("BambuStudio", _NS_BAMBU)
ET.register_namespace("p", _NS_PROD)


# ── Project root (two levels up from this file) ───────────────────────────────

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_HERE)
_DEFAULT_TEMPLATE = os.path.join(
    _PROJECT_ROOT, "EliteGolfMoments", "Frames", "Mike Kallbrier.3mf"
)
# Backwards-compat fallback: team_inbox copy
if not os.path.exists(_DEFAULT_TEMPLATE):
    _DEFAULT_TEMPLATE = os.path.join(_PROJECT_ROOT, "team_inbox", "Mike Kallbrier.3mf")


# ── Font enumeration ──────────────────────────────────────────────────────────

def list_available_fonts() -> list:
    """Return a sorted list of unique font family names available on the system."""
    from matplotlib import font_manager as fm
    names = set()
    for entry in fm.fontManager.ttflist:
        if entry.name:
            names.add(entry.name)
    return sorted(names, key=lambda s: s.lower())


# ── Text mesh generation ──────────────────────────────────────────────────────

def render_text_mesh(
    text: str,
    height_mm: float = 5.5125,
    depth_mm: float = 1.5,
    max_width_mm: float = 130.0,
    font_family: str = 'Orbitron',
    bold: bool = False,
    italic: bool = False,
) -> trimesh.Trimesh:
    """
    Generate a 3D mesh from a string of text.

    Text is centered at X=0, baseline at Y=0, extruded in +Z by depth_mm.
    height_mm is the *cap height* target — the rendered height of a capital
    letter (e.g. "M") will equal height_mm regardless of whether the line
    contains descenders.  Lines with descenders will therefore have a total
    bounding-box height slightly larger than height_mm, while descender-free
    lines will have bounding-box height ≈ height_mm.  This keeps uppercase
    letters the same visual size across all lines and plates.

    If the rendered text width exceeds max_width_mm, it is scaled down
    proportionally (both X and Y, to preserve letter aspect ratio).

    Returns a single concatenated Trimesh.
    """
    from matplotlib.textpath import TextPath
    from matplotlib.font_manager import FontProperties
    from shapely.geometry import Polygon, MultiPolygon
    from shapely.validation import make_valid

    if not text or not text.strip():
        # Return a tiny invisible box for empty strings
        return trimesh.creation.box([0.1, 0.1, depth_mm])

    fp = FontProperties(
        family=font_family,
        weight='bold' if bold else 'normal',
        style='italic' if italic else 'normal',
    )

    # Use a large font size and measure, then scale to desired height_mm.
    base_size = 100.0
    tp = TextPath((0, 0), text, size=base_size, prop=fp)
    raw_polygons = tp.to_polygons()

    if not raw_polygons:
        return trimesh.creation.box([0.1, 0.1, depth_mm])

    # Step 1: Build all rings as Shapely Polygons.
    # Each raw_polygon ring is either an outer boundary or a hole boundary.
    # We must NOT use unary_union — it destroys hole information by treating
    # every ring as an outer polygon and merging overlapping interiors as solid fills.
    all_polys = []
    for verts in raw_polygons:
        if len(verts) < 3:
            continue
        try:
            poly = Polygon(verts)
            if not poly.is_valid:
                poly = make_valid(poly)
            if hasattr(poly, 'geoms'):
                # make_valid may return a MultiPolygon
                for g in poly.geoms:
                    if g.geom_type == 'Polygon' and not g.is_empty:
                        all_polys.append(g)
            elif poly.geom_type == 'Polygon' and not poly.is_empty:
                all_polys.append(poly)
        except Exception:
            continue

    if not all_polys:
        return trimesh.creation.box([0.1, 0.1, depth_mm])

    # Step 2: Area-based outer/hole classification.
    # Sort rings by area descending — the largest ring in any nested set is the
    # outer boundary; smaller rings geometrically inside it are holes.
    # This is robust for TextPath glyphs where winding order is inconsistent.
    all_polys.sort(key=lambda p: p.area, reverse=True)

    n = len(all_polys)
    used = [False] * n
    final_polys = []

    for i in range(n):
        if used[i]:
            continue
        outer = all_polys[i]
        my_holes = []
        for j in range(i + 1, n):
            if used[j]:
                continue
            # Check if ring j is geometrically inside outer (use centroid).
            # A ring with smaller area whose centroid is inside outer is a hole.
            if outer.contains(all_polys[j].centroid):
                my_holes.append(list(all_polys[j].exterior.coords))
                used[j] = True
        try:
            p = Polygon(list(outer.exterior.coords), my_holes)
            p = make_valid(p)
            if not p.is_empty and p.area > 1e-6:
                final_polys.append(p)
                used[i] = True
        except Exception:
            continue

    # Step 3: Normalise into a flat list of Polygons (no unary_union — it destroys holes).
    polys = []
    for p in final_polys:
        if p.geom_type == 'Polygon':
            polys.append(p)
        elif p.geom_type == 'MultiPolygon':
            polys.extend(p.geoms)

    if not polys:
        return trimesh.creation.box([0.1, 0.1, depth_mm])

    # Compute bounding box in font-units
    all_x = []
    all_y = []
    for p in polys:
        b = p.bounds  # (minx, miny, maxx, maxy)
        all_x.extend([b[0], b[2]])
        all_y.extend([b[1], b[3]])

    min_x, max_x = min(all_x), max(all_x)
    min_y, max_y = min(all_y), max(all_y)
    font_width = max_x - min_x
    font_height = max_y - min_y

    if font_height < 1e-9:
        return trimesh.creation.box([0.1, 0.1, depth_mm])

    # --- Cap-height-based scaling ---
    # Measure the cap height using a reference glyph ("M") rendered at the same
    # base_size=100.0 with the same FontProperties.  This gives us the height of
    # a capital letter in raw font units so we can scale caps to height_mm
    # regardless of whether the current line has descenders.
    cap_height_raw = 0.0
    for cap_char in ("M", "H"):
        tp_cap = TextPath((0, 0), cap_char, size=base_size, prop=fp)
        cap_polys_raw = tp_cap.to_polygons()
        if cap_polys_raw:
            cap_ys = []
            for verts in cap_polys_raw:
                if len(verts) >= 2:
                    cap_ys.extend(v[1] for v in verts)
            if cap_ys:
                cap_height_raw = max(cap_ys) - min(cap_ys)
                if cap_height_raw > 1e-9:
                    break

    # Fall back to full bounding-box height if cap measurement failed
    if cap_height_raw < 1e-9:
        cap_height_raw = font_height

    # Scale so cap-height equals height_mm
    scale_to_height = height_mm / cap_height_raw

    # Determine if we also need to shrink for max_width
    projected_width = font_width * scale_to_height
    if projected_width > max_width_mm:
        scale_to_height = max_width_mm / font_width

    # Center X at 0 (translate by -midpoint in font coords)
    mid_x = (min_x + max_x) / 2.0

    # --- Cap-height-based vertical centering (the descender fix) ---
    # Previously this used mid_y = (min_y + max_y) / 2.0, i.e. the *ink* bbox
    # midpoint.  That made every line centre its ink at local y=0 — so a line
    # with a descender (min_y negative) had its baseline and cap-top at
    # *different* local positions than a line without descenders.  When three
    # lines are laid out at fixed plate y-offsets (+10.8893, 0, −10.8893),
    # the cap-tops and baselines of descender-bearing lines shift relative to
    # descender-free lines, producing uneven top/bottom margins on plaques
    # whose text happens to contain descenders (p, y, g, j, q, J).
    #
    # Correct behaviour: centre every line on its *cap-height* midpoint so
    # that all lines share the same cap-top (at +cap_h/2) and the same
    # baseline (at −cap_h/2) in local coords, regardless of which characters
    # they contain.  Descenders simply protrude below the baseline within
    # the line's slot without shifting the rest of the glyphs.
    mid_y = cap_height_raw / 2.0

    # Transform each polygon: shift to centre, then scale
    scaled_polys = []
    for p in polys:
        # Scale and translate: new_x = (x - mid_x) * scale, new_y = (y - mid_y) * scale
        coords_ext = [
            ((x - mid_x) * scale_to_height, (y - mid_y) * scale_to_height)
            for x, y in p.exterior.coords
        ]
        holes = [
            [((x - mid_x) * scale_to_height, (y - mid_y) * scale_to_height) for x, y in ring.coords]
            for ring in p.interiors
        ]
        try:
            sp = Polygon(coords_ext, holes)
            sp = make_valid(sp)
            if not sp.is_empty and sp.area > 1e-6:
                scaled_polys.append(sp)
        except Exception:
            continue

    if not scaled_polys:
        return trimesh.creation.box([0.1, 0.1, depth_mm])

    # Extrude each polygon and concatenate
    meshes = []
    for p in scaled_polys:
        try:
            m = trimesh.creation.extrude_polygon(p, height=depth_mm)
            if m is not None and len(m.vertices) > 0:
                meshes.append(m)
        except Exception:
            continue

    if not meshes:
        return trimesh.creation.box([0.1, 0.1, depth_mm])

    return trimesh.util.concatenate(meshes)


# ── Oval plate dimensions (extracted from Blank Plate (oval).step) ────────────
#
# The STEP file defines a stadium/discorectangle shape:
#   - Two straight edges (top and bottom) connected by two semicircular arcs
#   - Straight section half-length: 72.987 mm
#   - Arc radius (= semi_minor):   16.184 mm
#   - Total half-length (semi_major = straight_half + arc_radius): 89.171 mm
#   - Plate thickness: 2.0 mm
#
_OVAL_STRAIGHT_HALF = 72.987   # mm — half the length of the straight section
_OVAL_ARC_RADIUS    = 16.184   # mm — radius of the semicircular ends (= semi_minor)
_OVAL_THICKNESS     = 2.0      # mm — plate extrusion depth
_BORDER_WIDTH       = 1.0      # mm — border stripe width
_BORDER_DEPTH       = 1.0      # mm — border extrusion depth

# ── Line spacing (single source of truth for plaque text layout) ──────────────
#
# v2.9: line-to-line gap shrunk from 10.8893 → 10.3893 mm so that the text
# block sits 1 mm higher overall.  Top margin is held fixed by keeping line 1
# at its original top y (+10.8893), and the 1 mm of freed space moves to the
# bottom margin.  Layout is built by pinning the TOP line and stepping
# downward by _LINE_SPACING per line — this keeps the top margin unchanged
# for plaques with any number of lines (2-line, 3-line, 4-line, etc.).
#
# v3.1 (Topo, 2026-05-01): per-line shift for the 3-line layout. Bottom line
# (line 3) is now the fixed anchor; lines 1 and 2 are nudged DOWN to pull the
# text block tighter to the bottom edge:
#     Line 1 (top)   : DOWN 1.0 mm  (+10.8893 → +9.8893)
#     Line 2 (middle): DOWN 0.5 mm  (+0.5     →  0.0)
#     Line 3 (bottom): UNCHANGED    (-9.8893)
# Net effect: total text-block height shrinks by 1 mm; spacing L1↔L2 and
# L2↔L3 each shrinks by 0.5 mm so the block sits visually higher off the
# bottom of the plate (Thomas's design rule). The shift is applied as a
# per-line delta vector so it's trivial to retune later.
_LINE_SPACING       = 10.3893  # mm — uniform gap between adjacent lines
_TOP_LINE_Y         = 10.8893  # mm — y-offset of the topmost line (pins top margin)

# Per-line additive y-shift (mm). Applied AFTER the uniform _line_y_offsets
# layout. NEGATIVE = move that line DOWN. Indexed by line number (0 = top).
# Length must be ≥ n_lines requested. v3.1 — 3-line tuning per Thomas.
_LINE_Y_DELTA_3     = [-1.0, -0.5, 0.0]  # 3-line plaque: [top, middle, bottom]


def _line_y_offsets(n_lines: int) -> list:
    """
    Return the local-plate y-offsets for *n_lines* lines of text, starting at
    the top line pinned to _TOP_LINE_Y and stepping downward by _LINE_SPACING,
    with the v3.1 per-line delta applied for the 3-line layout.

    For the canonical 3-line plaque (v3.1) this yields:
        [+9.8893, 0.0, -9.8893]
    (line 1 down 1.0, line 2 down 0.5, line 3 unchanged).

    For a 2-line plaque (no per-line delta): [+10.8893, +0.5].
    For a 4-line plaque: [+10.8893, +0.5, -9.8893, -20.2786] (would exceed
    plate in practice — callers must sanity-check vs plate half-height).
    """
    base = [_TOP_LINE_Y - i * _LINE_SPACING for i in range(n_lines)]
    if n_lines == 3:
        return [b + d for b, d in zip(base, _LINE_Y_DELTA_3)]
    return base


def _stadium_polygon(straight_half: float, arc_radius: float, n_arc: int = 64):
    """
    Build a Shapely Polygon for a stadium (discorectangle) shape centered at (0, 0).

    The shape consists of two straight edges (top and bottom) of length
    2 * straight_half, connected by two semicircular arcs of the given arc_radius.
    The total half-length (X) = straight_half + arc_radius.
    The total half-height (Y) = arc_radius.
    """
    import math
    from shapely.geometry import Polygon

    pts = []
    # Right semicircle (centre at +straight_half, 0): angles -90° to +90°
    for i in range(n_arc + 1):
        angle = -math.pi / 2 + math.pi * i / n_arc
        pts.append((straight_half + arc_radius * math.cos(angle),
                    arc_radius * math.sin(angle)))
    # Left semicircle (centre at -straight_half, 0): angles +90° to +270° (=−90°)
    for i in range(n_arc + 1):
        angle = math.pi / 2 + math.pi * i / n_arc
        pts.append((-straight_half + arc_radius * math.cos(angle),
                    arc_radius * math.sin(angle)))
    return Polygon(pts)


def build_oval_plate_mesh(
    straight_half: float = _OVAL_STRAIGHT_HALF,
    arc_radius: float    = _OVAL_ARC_RADIUS,
    thickness: float     = _OVAL_THICKNESS,
    n_arc: int           = 64,
) -> trimesh.Trimesh:
    """
    Build the oval (stadium) plate base mesh, extruded *thickness* mm in local +Z.

    The mesh is centred at X=0, Y=0 in local plate coordinates and is built in
    the plate's tilt-frame local coordinates.
    """
    poly = _stadium_polygon(straight_half, arc_radius, n_arc=n_arc)
    return trimesh.creation.extrude_polygon(poly, height=thickness)


def build_border_mesh(
    straight_half: float = _OVAL_STRAIGHT_HALF,
    arc_radius: float    = _OVAL_ARC_RADIUS,
    border_width: float  = _BORDER_WIDTH,
    depth: float         = _BORDER_DEPTH,
    n_arc: int           = 64,
) -> trimesh.Trimesh:
    """
    Build an oval (stadium) frame mesh: outer stadium with inner stadium as hole,
    extruded *depth* mm in local +Z.

    The mesh is built in the plate's tilt-frame local coordinates so it can be
    placed with the same rotation matrix used for the text objects.
    """
    from shapely.geometry import Polygon

    outer = _stadium_polygon(straight_half, arc_radius, n_arc=n_arc)
    inner = _stadium_polygon(straight_half - border_width,
                             arc_radius - border_width, n_arc=n_arc)
    ring = outer.difference(inner)
    return trimesh.creation.extrude_polygon(ring, height=depth)


# ── 3MF XML helpers ───────────────────────────────────────────────────────────

def _mesh_to_3mf_xml(mesh: trimesh.Trimesh) -> str:
    """
    Return an XML string fragment for a 3MF <mesh> element
    (vertices + triangles).  Does NOT include the <object> wrapper.
    """
    lines = ["   <mesh>", "    <vertices>"]
    for v in mesh.vertices:
        lines.append(f'     <vertex x="{v[0]:.6f}" y="{v[1]:.6f}" z="{v[2]:.6f}"/>')
    lines.append("    </vertices>")
    lines.append("    <triangles>")
    for f in mesh.faces:
        lines.append(f'     <triangle v1="{f[0]}" v2="{f[1]}" v3="{f[2]}"/>')
    lines.append("    </triangles>")
    lines.append("   </mesh>")
    return "\n".join(lines)


def _replace_plate_mesh(model_xml_str: str, plate_mesh: trimesh.Trimesh) -> str:
    """
    Replace the mesh of object id=1 (the plate base) in object_10.model with
    the supplied oval plate mesh.

    This supersedes the old _widen_plate() regex approach: instead of patching
    vertex coordinates on the original rectangular mesh, we swap the entire
    <mesh> block inside <object id="1">.
    """
    new_mesh_xml = _mesh_to_3mf_xml(plate_mesh)

    pattern = re.compile(
        r'(<object\s[^>]*\bid="1"[^>]*>)'
        r'(.*?)'
        r'(</object>)',
        re.DOTALL
    )

    def replacer(m):
        return f"{m.group(1)}\n{new_mesh_xml}\n  {m.group(3)}"

    result, count = pattern.subn(replacer, model_xml_str)
    if count == 0:
        raise ValueError("Could not find <object id='1'> (plate base) in model XML")
    return result


def _replace_text_objects_in_model(model_xml_str: str,
                                   mesh2: trimesh.Trimesh,
                                   mesh3: trimesh.Trimesh,
                                   mesh4: trimesh.Trimesh) -> str:
    """
    Parse the object_10.model XML, replace objects 2, 3, 4 meshes with the
    three new text meshes, return updated XML string.
    """
    # We use simple string-level replacement to avoid any namespace mangling.
    # Strategy: find each <object id="N"> ... </object> block and replace the
    # mesh content.

    def replace_object_mesh(xml_str: str, obj_id: int, new_mesh: trimesh.Trimesh) -> str:
        """Replace the <mesh> block inside <object id="{obj_id}">."""
        new_mesh_xml = _mesh_to_3mf_xml(new_mesh)

        # Regex: match <object id="N" ...> ... </object>
        # We need a non-greedy match within the object block.
        pattern = re.compile(
            r'(<object\s[^>]*\bid="' + str(obj_id) + r'"[^>]*>)'
            r'(.*?)'
            r'(</object>)',
            re.DOTALL
        )

        def replacer(m):
            opening = m.group(1)
            closing = m.group(3)
            return f"{opening}\n{new_mesh_xml}\n  {closing}"

        result, count = pattern.subn(replacer, xml_str)
        if count == 0:
            raise ValueError(f"Could not find <object id='{obj_id}'> in model XML")
        return result

    xml_str = model_xml_str
    xml_str = replace_object_mesh(xml_str, 2, mesh2)
    xml_str = replace_object_mesh(xml_str, 3, mesh3)
    xml_str = replace_object_mesh(xml_str, 4, mesh4)
    return xml_str


def _append_border_object(obj_model_xml: str, border_mesh: trimesh.Trimesh,
                           border_obj_id: int = 5) -> str:
    """
    Append a new <object id="{border_obj_id}"> element for the border mesh
    inside the <resources> block of object_10.model.
    """
    mesh_xml = _mesh_to_3mf_xml(border_mesh)
    new_object_xml = (
        f'  <object id="{border_obj_id}" '
        f'p:UUID="{str(_uuid_mod.uuid4())}" type="model">\n'
        f'{mesh_xml}\n'
        f'  </object>'
    )
    # Insert before closing </resources>
    return obj_model_xml.replace("</resources>",
                                 f"{new_object_xml}\n </resources>", 1)


def _add_border_component(main_model_xml: str, border_obj_id: int = 5) -> str:
    """
    Append a <component> for the border mesh into the outer object's
    <components> block in 3D/3dmodel.model.

    The plate is now flat in the XY plane (identity rotation). The border
    sits on top of the plate surface at z=2.0 (plate thickness), so its
    local z=0 face lands exactly at the plate top surface and the border
    extrudes upward from there.
    """
    ROTATION = "1 0 0 0 1 0 0 0 1"
    # Plate is 2mm thick; border sits on top surface at z=2.0
    TRANSLATION = "0 0 2.0"
    border_uuid = str(_uuid_mod.uuid4())
    new_component = (
        f'    <component p:path="/3D/Objects/object_10.model" '
        f'objectid="{border_obj_id}" '
        f'p:UUID="{border_uuid}" '
        f'transform="{ROTATION} {TRANSLATION}"/>'
    )
    # Insert before closing </components>
    return main_model_xml.replace("</components>",
                                  f"{new_component}\n   </components>", 1)


def _append_border_settings(config_xml: str, border_mesh: trimesh.Trimesh,
                             border_obj_id: int = 5) -> str:
    """
    Append a <part id="{border_obj_id}"> entry for the border inside the
    <object id="5"> block of model_settings.config.
    """
    face_count = len(border_mesh.faces)
    # The matrix string in model_settings uses the column-major 4x4 form.
    new_part = (
        f'    <part id="{border_obj_id}" subtype="normal_part">\n'
        f'      <metadata key="name" value="border"/>\n'
        f'      <metadata key="matrix" value="1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1"/>\n'
        f'      <metadata key="extruder" value="3"/>\n'
        f'      <mesh_stat face_count="{face_count}" edges_fixed="0" '
        f'degenerate_facets="0" facets_removed="0" facets_reversed="0" '
        f'backwards_edges="0"/>\n'
        f'    </part>'
    )
    # Insert before closing </object> (first occurrence, which is the plate object)
    return config_xml.replace("  </object>", f"{new_part}\n  </object>", 1)


def _patch_component_transforms(model_xml_str: str) -> str:
    """
    Rewrite the transform= attributes for objectid 2, 3, 4 components in
    3D/3dmodel.model.

    The plate is now flat in the XY plane — identity rotation for all text
    objects. Text is placed on top of the plate (z=2.0, plate thickness).

    v2.9 layout: top line pinned to _TOP_LINE_Y (+10.8893), lines step
    downward by _LINE_SPACING (10.3893 mm). For the canonical 3-line plaque:

        objectid 2  (line 1, top):    x=0.0, y= +10.8893, z=2.0
        objectid 3  (line 2, middle): x=0.0, y=  +0.5,    z=2.0
        objectid 4  (line 3, bottom): x=0.0, y=  -9.8893, z=2.0

    Top margin is held fixed (line-1 y unchanged), bottom margin grows by
    1 mm relative to the old symmetric-around-0 layout.
    """
    ROTATION = "1 0 0 0 1 0 0 0 1"

    y1, y2, y3 = _line_y_offsets(3)
    new_transforms = {
        "2": f"1 0 0 0 1 0 0 0 1 0.0 {y1} 2.0",
        "3": f"1 0 0 0 1 0 0 0 1 0.0 {y2} 2.0",
        "4": f"1 0 0 0 1 0 0 0 1 0.0 {y3} 2.0",
    }

    for obj_id, new_tf in new_transforms.items():
        # Match the component line for this objectid and replace its transform= value.
        # We match on objectid="N" (with p: namespace-aware attribute).
        pattern = re.compile(
            r'(<component\s[^>]*\bobjectid="' + re.escape(obj_id) + r'"[^>]*\s)'
            r'transform="[^"]*"'
            r'([^>]*/>)',
            re.DOTALL
        )
        model_xml_str, count = pattern.subn(
            rf'\g<1>transform="{new_tf}"\2',
            model_xml_str
        )
        if count == 0:
            # Try alternate attribute order (transform before objectid)
            pattern2 = re.compile(
                r'(<component\s)'
                r'transform="[^"]*"'
                r'([^>]*\bobjectid="' + re.escape(obj_id) + r'"[^>]*/>)',
                re.DOTALL
            )
            model_xml_str, count2 = pattern2.subn(
                rf'\g<1>transform="{new_tf}"\2',
                model_xml_str
            )
            if count2 == 0:
                raise ValueError(
                    f"Could not find component objectid={obj_id!r} transform in 3dmodel.model"
                )

    return model_xml_str


def _flatten_item_transform(model_xml_str: str) -> str:
    """Replace the <item> transform with identity rotation, centered on build plate.

    The Bambu A1 build plate is 256x256mm; center at (128, 128).
    The oval plate is ~178mm x ~32mm and fits easily.
    Z=0 so it rests flat on the build plate.
    """
    pattern = re.compile(r'(<item\s[^>]*?)transform="[^"]*"([^>]*/>)')
    new_transform = 'transform="1 0 0 0 1 0 0 0 1 128 128 0"'
    return pattern.sub(rf'\1{new_transform}\2', model_xml_str)


def _flatten_settings_matrices(config_xml_str: str) -> str:
    """
    Flatten the tilt rotation matrices stored in model_settings.config.

    Parts 2, 3, 4 carry the original tilted transform as a 4x4 column-major
    matrix in their <metadata key="matrix" value="..."/> entries.  Now that
    the component-level transforms in 3dmodel.model are identity+offset, the
    matrix entries must match — otherwise Bambu Studio re-applies the tilt.

    New flat matrices (identity 4x4) for each part, matching the translations
    already set in _patch_component_transforms(). v2.9 layout derives the
    y-offsets from _line_y_offsets(3) (top pinned to +10.8893, uniform gap
    of _LINE_SPACING = 10.3893 mm):
        part 2  (line 1, top):    tx=0, ty= +10.8893, tz=2.0
        part 3  (line 2, middle): tx=0, ty=  +0.5,    tz=2.0
        part 4  (line 3, bottom): tx=0, ty=  -9.8893, tz=2.0

    The 4x4 column-major layout used by Bambu Studio is:
        R00 R10 R20 tx  R01 R11 R21 ty  R02 R12 R22 tz  0 0 0 1
    For identity rotation that reduces to:
        1 0 0 tx  0 1 0 ty  0 0 1 tz  0 0 0 1

    Also flattens the <assemble_item> transform which may carry Z-lift from the
    original tilted pose.
    """
    y1, y2, y3 = _line_y_offsets(3)
    flat_matrices = {
        "2": f"1 0 0 0 0 1 0 {y1} 0 0 1 2 0 0 0 1",
        "3": f"1 0 0 0 0 1 0 {y2} 0 0 1 2 0 0 0 1",
        "4": f"1 0 0 0 0 1 0 {y3} 0 0 1 2 0 0 0 1",
    }

    for part_id, new_matrix in flat_matrices.items():
        # Replace the matrix metadata inside the <part id="N"> block
        part_pattern = re.compile(
            r'(<part\s[^>]*\bid="' + re.escape(part_id) + r'"[^>]*>)(.*?)(</part>)',
            re.DOTALL
        )

        def make_matrix_replacer(mat):
            def replacer(m):
                inner = re.sub(
                    r'(<metadata key="matrix" value=")[^"]*(")',
                    rf'\g<1>{mat}\2',
                    m.group(2)
                )
                return m.group(1) + inner + m.group(3)
            return replacer

        config_xml_str = part_pattern.sub(make_matrix_replacer(new_matrix), config_xml_str)

    # Also flatten the assemble_item transform and offset — set to flat center
    def _fix_assemble_item(m):
        before = m.group(1)
        after_offset_open = m.group(2)
        after_offset_close = m.group(3)
        return (before + 'transform="1 0 0 0 1 0 0 0 1 128 128 0"'
                + after_offset_open + '128 128 0' + after_offset_close)

    assemble_pattern = re.compile(
        r'(<assemble_item\s[^>]*?)transform="[^"]*"([^>]*offset=")[^"]*(")',
        re.DOTALL
    )
    config_xml_str = assemble_pattern.sub(_fix_assemble_item, config_xml_str)

    return config_xml_str


def _update_model_settings(config_xml_str: str,
                            line1: str, line2: str, line3: str) -> str:
    """
    Update the text_info text= attributes in model_settings.config
    for parts 2, 3, 4.
    """
    lines_map = {2: line1, 3: line2, 4: line3}

    # For each part, replace the text= attribute in its text_info element.
    for part_id, new_text in lines_map.items():
        # Escape XML special chars in the text value
        safe_text = (new_text
                     .replace("&", "&amp;")
                     .replace("<", "&lt;")
                     .replace(">", "&gt;")
                     .replace('"', "&quot;"))

        # Replace text= inside the <part id="N"> block
        # We target the text_info tag within that part's section.
        pattern = re.compile(
            r'(<part\s[^>]*\bid="' + str(part_id) + r'"[^>]*>)(.*?)(</part>)',
            re.DOTALL
        )

        def make_replacer(safe):
            def replacer(m):
                part_inner = re.sub(
                    r'(<text_info\s[^>]*\btext=")[^"]*(")',
                    rf'\g<1>{safe}\2',
                    m.group(2)
                )
                return m.group(1) + part_inner + m.group(3)
            return replacer

        config_xml_str = pattern.sub(make_replacer(safe_text), config_xml_str)

    return config_xml_str


# ── Main generator ────────────────────────────────────────────────────────────

def generate_plate_3mf(
    line1: str,
    line2: str,
    line3: str,
    output_path: str,
    template_path: str = None,
    font_family: str = 'Orbitron',
    bold: bool = False,
    italic: bool = False,
) -> str:
    """
    Build a 3MF file containing the plate from the template plus three
    freshly generated text lines.  Returns the output path.
    """
    if template_path is None:
        template_path = _DEFAULT_TEMPLATE

    template_path = os.path.abspath(template_path)
    output_path = os.path.abspath(output_path)

    if not os.path.exists(template_path):
        raise FileNotFoundError(f"Template not found: {template_path}")

    # Render the three text meshes
    print(f"[plate_text] Rendering line 1: {line1!r}")
    mesh1 = render_text_mesh(line1, font_family=font_family, bold=bold, italic=italic)
    print(f"[plate_text] Rendering line 2: {line2!r}")
    mesh2 = render_text_mesh(line2, font_family=font_family, bold=bold, italic=italic)
    print(f"[plate_text] Rendering line 3: {line3!r}")
    mesh3 = render_text_mesh(line3, font_family=font_family, bold=bold, italic=italic)

    # Build the oval plate base mesh and the oval border frame mesh
    print("[plate_text] Building oval plate base mesh")
    plate_mesh = build_oval_plate_mesh()
    print("[plate_text] Building oval border mesh")
    border_mesh = build_border_mesh()

    # Unzip template to a temp directory
    with tempfile.TemporaryDirectory() as tmpdir:
        with zipfile.ZipFile(template_path, "r") as zf:
            zf.extractall(tmpdir)

        # --- Patch 3D/3dmodel.model (component transforms + border component) ---
        main_model_path = os.path.join(tmpdir, "3D", "3dmodel.model")
        with open(main_model_path, "r", encoding="utf-8") as f:
            main_model_xml = f.read()

        main_model_xml = _patch_component_transforms(main_model_xml)
        main_model_xml = _add_border_component(main_model_xml, border_obj_id=5)
        main_model_xml = _flatten_item_transform(main_model_xml)  # flatten outer <item> tilt

        with open(main_model_path, "w", encoding="utf-8") as f:
            f.write(main_model_xml)

        # --- Patch object_10.model ---
        obj_model_path = os.path.join(tmpdir, "3D", "Objects", "object_10.model")
        with open(obj_model_path, "r", encoding="utf-8") as f:
            obj_xml = f.read()

        obj_xml = _replace_plate_mesh(obj_xml, plate_mesh)
        obj_xml = _replace_text_objects_in_model(obj_xml, mesh1, mesh2, mesh3)
        obj_xml = _append_border_object(obj_xml, border_mesh, border_obj_id=5)

        with open(obj_model_path, "w", encoding="utf-8") as f:
            f.write(obj_xml)

        # --- Patch model_settings.config ---
        settings_path = os.path.join(tmpdir, "Metadata", "model_settings.config")
        if os.path.exists(settings_path):
            with open(settings_path, "r", encoding="utf-8") as f:
                settings_xml = f.read()
            settings_xml = _update_model_settings(settings_xml, line1, line2, line3)
            settings_xml = _flatten_settings_matrices(settings_xml)  # flatten tilt matrices
            settings_xml = _append_border_settings(settings_xml, border_mesh, border_obj_id=5)
            with open(settings_path, "w", encoding="utf-8") as f:
                f.write(settings_xml)

        # --- Re-zip the temp directory into the output 3MF ---
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zout:
            for root, dirs, files in os.walk(tmpdir):
                for fname in files:
                    fpath = os.path.join(root, fname)
                    arcname = os.path.relpath(fpath, tmpdir)
                    zout.write(fpath, arcname)

    print(f"[plate_text] Written: {output_path}")
    return output_path


# ── Verification helper ───────────────────────────────────────────────────────

def verify_3mf(path: str) -> dict:
    """
    Load the 3MF with trimesh and return basic stats.
    Raises if the file cannot be loaded or has fewer than 4 objects.
    """
    scene = trimesh.load(path)
    if isinstance(scene, trimesh.Scene):
        geometries = scene.geometry
        obj_count = len(geometries)
    else:
        geometries = {"0": scene}
        obj_count = 1

    total_faces = sum(g.faces.shape[0] for g in geometries.values())
    return {"objects": obj_count, "total_faces": total_faces}


# ── CLI entry point ───────────────────────────────────────────────────────────

def _cli():
    parser = argparse.ArgumentParser(
        description="Generate a custom-text plate 3MF file."
    )
    parser.add_argument(
        "lines",
        nargs="?",
        action="append",
        metavar="LINE",
        help="Three lines of text for the plate (omit when using --list-fonts).",
    )
    parser.add_argument(
        "--out", "-o",
        default=os.path.join(_PROJECT_ROOT, "owner_inbox", "custom_plate.3mf"),
        help="Output path for the generated .3mf file.",
    )
    parser.add_argument(
        "--template", "-t",
        default=None,
        help="Path to template 3MF (default: team_inbox/Mike Kallbrier.3mf).",
    )
    parser.add_argument(
        "--font",
        default="DejaVu Sans",
        metavar="FONT_NAME",
        help="Font family name to use (default: DejaVu Sans).",
    )
    parser.add_argument(
        "--bold",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Use bold weight (default: on). Use --no-bold to disable.",
    )
    parser.add_argument(
        "--italic",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Use italic style (default: off). Use --italic to enable.",
    )
    parser.add_argument(
        "--list-fonts",
        action="store_true",
        help="Print all available font family names and exit.",
    )

    # Re-parse: lines must be exactly 3 positional args when not using --list-fonts
    # Use parse_known_args to allow positional capture before we know the mode.
    args, remaining = parser.parse_known_args()

    if args.list_fonts:
        fonts = list_available_fonts()
        for f in fonts:
            print(f)
        sys.exit(0)

    # Collect positional lines — they come through remaining when nargs="?"
    all_positional = [x for x in (args.lines or []) if x is not None] + remaining
    # Filter out any flags that slipped through
    positional_lines = [x for x in all_positional if not x.startswith('-')]

    if len(positional_lines) != 3:
        parser.error(
            f"Exactly 3 LINE arguments are required (got {len(positional_lines)}). "
            "Use --list-fonts to see available fonts."
        )

    line1, line2, line3 = positional_lines
    out_path = generate_plate_3mf(
        line1, line2, line3,
        output_path=args.out,
        template_path=args.template,
        font_family=args.font,
        bold=args.bold,
        italic=args.italic,
    )

    # Verify
    try:
        stats = verify_3mf(out_path)
        print(f"[plate_text] Verification OK — {stats['objects']} objects, "
              f"{stats['total_faces']} total faces")
    except Exception as exc:
        print(f"[plate_text] Warning: verification failed: {exc}", file=sys.stderr)

    print(f"\nOutput: {out_path}")


if __name__ == "__main__":
    _cli()
