"""
gps_heightmap.py -- GPS-altitude heightmap backend for the EGM Generate pipeline.

Converts raw GPS point clouds (from GolfIntelligence .gps files) into a
grid-based heightmap that is API-compatible with the existing image-gradient
backend in gradient_surface_diagnostic.py.

Design choice: Option B (separate sibling module).
Rationale: gradient_surface_diagnostic.py already carries a heavy OpenCV/image
dependency tree.  Keeping GPS logic in a dedicated module means:
  - cleaner imports (no cv2 needed here)
  - independent test surface
  - gradient_surface_diagnostic.py can import HeightmapResult cleanly
  - easier future v0.2 bumps without touching the image path

Public API
----------
    result = build_heightmap_from_gps(
        gps_path=Path("Stanford (8).gps"),
        bbox=(lat_min, lng_min, lat_max, lng_max),
        green_polygon_latlng=[(lat, lng), ...],
        approach_m=8.0,
        grid_size=(200, 200),
        vert_exag=1.0,
    )

See HeightmapResult dataclass for output fields.

v0.1.0 -- 2026-09-23 -- Topo
"""

from __future__ import annotations

__version__ = "0.1.0"

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np
from scipy.interpolate import griddata
from shapely.geometry import Point as ShapelyPoint
from shapely.geometry import Polygon as ShapelyPolygon


# ---------------------------------------------------------------------------
# Public result type
# ---------------------------------------------------------------------------

@dataclass
class HeightmapResult:
    """
    Heightmap produced from GPS points.  Field shapes match the 200x200
    grid returned by the image-gradient backend in gradient_surface_diagnostic.py
    so Sienna can swap backends without touching callers.

    Coordinate convention
    ---------------------
    All distances are in millimetres.  The local origin (0, 0) is placed at
    the SW corner of the bounding box (lat_min, lng_min).  East is +X (mm),
    North is +Y (mm).

    heights_mm
        2-D array shape (grid_size[1], grid_size[0]) -- [row=Y, col=X].
        Height in millimetres above the *minimum* GPS altitude inside the
        bbox (i.e. the lowest captured point is 0 mm, others are positive).
        Cells outside the green+approach mask are NaN.

    mask
        2-D bool array, same shape.  True where heights_mm is valid.

    grid_x_mm / grid_y_mm
        1-D arrays of grid-cell centre positions in mm (local frame).

    origin_latlng
        (lat, lng) of the (0, 0) mm origin -- SW bbox corner.

    raw_points_used
        Number of GPS points included after bbox filtering.

    bbox_m
        (east_min, north_min, east_max, north_max) in local metres.
        Useful for editor preview scaling.

    interpolation_notes
        List of warning strings accumulated during processing (sparse data,
        cubic fallback, etc.).  Empty list means everything went smoothly.
    """

    heights_mm: np.ndarray
    mask: np.ndarray
    grid_x_mm: np.ndarray
    grid_y_mm: np.ndarray
    origin_latlng: tuple[float, float]
    raw_points_used: int
    bbox_m: tuple[float, float, float, float]
    interpolation_notes: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Stage 1: Parse .gps file
# ---------------------------------------------------------------------------

def parse_gps_file(gps_path: Path) -> list[dict]:
    """
    Parse a GolfIntelligence .gps file.

    The file format is:
      - 0-N lines of UI text / metadata (variable; may include blank lines,
        headers, tab-delimited tables, etc.)
      - A JSON object starting with '{' that contains 'geoHashCells'

    Returns the raw list of cell dicts from 'geoHashCells'.  Each dict has
    the shape:
        {
          "gpsCoordinate": {"latitude": ..., "longitude": ..., "altitude": ...},
          "geoHash": "..."
        }

    Raises
    ------
    ValueError
        If no JSON object is found, or the JSON lacks 'geoHashCells'.
    """
    raw = Path(gps_path).read_text(encoding="utf-8", errors="replace")
    lines = raw.splitlines()

    json_start: Optional[int] = None
    for i, line in enumerate(lines):
        if line.strip().startswith("{"):
            json_start = i
            break
    if json_start is None:
        raise ValueError(f"No JSON object found in {gps_path}")

    json_text = "\n".join(lines[json_start:])
    data = json.loads(json_text)

    if "geoHashCells" not in data:
        raise ValueError(
            f"JSON in {gps_path} does not contain 'geoHashCells' key. "
            f"Found keys: {list(data.keys())}"
        )

    return data["geoHashCells"]


def extract_latlng_alt(cells: list[dict]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Extract parallel arrays of latitude, longitude, altitude from cell list.

    Returns
    -------
    lats, lngs, alts : np.ndarray shape (N,)
    """
    lats = np.array([c["gpsCoordinate"]["latitude"]  for c in cells], dtype=np.float64)
    lngs = np.array([c["gpsCoordinate"]["longitude"] for c in cells], dtype=np.float64)
    alts = np.array([c["gpsCoordinate"]["altitude"]  for c in cells], dtype=np.float64)
    return lats, lngs, alts


# ---------------------------------------------------------------------------
# Stage 2: Coordinate projection (ENU, metres)
# ---------------------------------------------------------------------------

def latlng_to_enu_metres(
    lats: np.ndarray,
    lngs: np.ndarray,
    origin_lat: float,
    origin_lng: float,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Project latitude/longitude to local East-North (metres) using a flat-earth
    approximation accurate to ~0.1% within a 10 km radius.

    The scale factors are computed from the actual origin latitude, not a
    hard-coded constant, so the same function works for any course location.

    Parameters
    ----------
    lats, lngs : np.ndarray
        WGS-84 coordinates.
    origin_lat, origin_lng : float
        Reference point that maps to (0, 0) m.

    Returns
    -------
    east_m, north_m : np.ndarray
        Signed offsets in metres from the origin.
    """
    lat_m_per_deg = 111_320.0
    lng_m_per_deg = 111_320.0 * math.cos(math.radians(origin_lat))
    north_m = (lats - origin_lat) * lat_m_per_deg
    east_m  = (lngs - origin_lng) * lng_m_per_deg
    return east_m, north_m


# ---------------------------------------------------------------------------
# Stage 3: Bbox filtering
# ---------------------------------------------------------------------------

def filter_by_bbox(
    lats: np.ndarray,
    lngs: np.ndarray,
    alts: np.ndarray,
    bbox: tuple[float, float, float, float],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Return only points whose (lat, lng) falls inside the bounding box.

    Parameters
    ----------
    bbox : (lat_min, lng_min, lat_max, lng_max)
    """
    lat_min, lng_min, lat_max, lng_max = bbox
    mask = (
        (lats >= lat_min) & (lats <= lat_max) &
        (lngs >= lng_min) & (lngs <= lng_max)
    )
    return lats[mask], lngs[mask], alts[mask]


# ---------------------------------------------------------------------------
# Stage 4: Green + approach mask
# ---------------------------------------------------------------------------

def build_approach_polygon(
    green_polygon_latlng: list[tuple[float, float]],
    origin_lat: float,
    origin_lng: float,
    approach_m: float,
) -> ShapelyPolygon:
    """
    Return a Shapely polygon in local-metre space representing the green polygon
    expanded outward by approach_m metres.

    Parameters
    ----------
    green_polygon_latlng : [(lat, lng), ...]
        Dense outline of the green in geographic coordinates.
    origin_lat, origin_lng : float
        ENU origin (SW bbox corner).
    approach_m : float
        Buffer distance in metres.

    Returns
    -------
    ShapelyPolygon in (east_m, north_m) metre coordinates.
    """
    lats = np.array([p[0] for p in green_polygon_latlng])
    lngs = np.array([p[1] for p in green_polygon_latlng])
    east_m, north_m = latlng_to_enu_metres(lats, lngs, origin_lat, origin_lng)
    poly_coords = list(zip(east_m, north_m))
    green_poly = ShapelyPolygon(poly_coords)
    if not green_poly.is_valid:
        green_poly = green_poly.buffer(0)  # auto-repair self-intersections
    approach_poly = green_poly.buffer(approach_m)
    return approach_poly


def compute_mask(
    grid_east_m: np.ndarray,
    grid_north_m: np.ndarray,
    approach_poly: ShapelyPolygon,
) -> np.ndarray:
    """
    Build a 2-D bool mask for grid cells inside the approach polygon.

    Parameters
    ----------
    grid_east_m : 1-D array of grid column centres (metres)
    grid_north_m : 1-D array of grid row centres (metres)
    approach_poly : Shapely polygon (green + buffer)

    Returns
    -------
    mask : np.ndarray shape (len(grid_north_m), len(grid_east_m))
           True where the grid cell is inside the polygon.
    """
    rows = len(grid_north_m)
    cols = len(grid_east_m)
    mask = np.zeros((rows, cols), dtype=bool)
    for r, n in enumerate(grid_north_m):
        for c, e in enumerate(grid_east_m):
            mask[r, c] = approach_poly.contains(ShapelyPoint(e, n))
    return mask


# ---------------------------------------------------------------------------
# Stage 5: Surface interpolation
# ---------------------------------------------------------------------------

def interpolate_heights(
    east_m: np.ndarray,
    north_m: np.ndarray,
    alts: np.ndarray,
    grid_east_m: np.ndarray,
    grid_north_m: np.ndarray,
    notes: list[str],
) -> np.ndarray:
    """
    Interpolate GPS altitude onto a regular grid using griddata.

    Strategy:
      1. Try cubic interpolation.
      2. If cubic produces > 50% NaN, fall back to linear.
      3. Fill any remaining NaN cells with nearest-neighbour.

    Parameters
    ----------
    east_m, north_m, alts : 1-D arrays of input points
    grid_east_m, grid_north_m : 1-D arrays defining the output grid
    notes : mutable list -- warnings are appended here

    Returns
    -------
    GZ : 2-D array shape (len(grid_north_m), len(grid_east_m))
         Raw interpolated altitude in metres.  May still contain NaN at
         grid edges or outside the convex hull of the input points; those
         cells will be masked out downstream.
    """
    GE, GN = np.meshgrid(grid_east_m, grid_north_m)
    pts_xy = np.column_stack([east_m, north_m])

    if len(pts_xy) < 3:
        notes.append(
            f"Only {len(pts_xy)} GPS point(s) inside bbox -- cannot interpolate; "
            "using nearest-neighbour fill only."
        )
        GZ = griddata(pts_xy, alts, (GE, GN), method="nearest")
        return GZ

    # --- cubic first ---
    try:
        GZ = griddata(pts_xy, alts, (GE, GN), method="cubic")
        nan_frac = np.isnan(GZ).mean()
        if nan_frac > 0.5:
            raise RuntimeError(
                f"Cubic produced {nan_frac*100:.0f}% NaN -- falling back to linear"
            )
    except Exception as exc:
        notes.append(f"Cubic interpolation fallback: {exc}")
        GZ = griddata(pts_xy, alts, (GE, GN), method="linear")
        nan_frac = np.isnan(GZ).mean()

    # --- nearest-neighbour fill for edge NaN ---
    if np.isnan(GZ).any():
        GZ_nn = griddata(pts_xy, alts, (GE, GN), method="nearest")
        nan_mask = np.isnan(GZ)
        GZ[nan_mask] = GZ_nn[nan_mask]
        notes.append(
            f"Nearest-neighbour fill applied to {nan_mask.sum()} edge/hull cells "
            f"({nan_mask.sum() / GZ.size * 100:.1f}% of grid)."
        )

    return GZ


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def build_heightmap_from_gps(
    gps_path: Path,
    bbox: tuple[float, float, float, float],
    green_polygon_latlng: list[tuple[float, float]],
    approach_m: float = 8.0,
    grid_size: tuple[int, int] = (200, 200),
    vert_exag: float = 1.0,
) -> HeightmapResult:
    """
    Build a heightmap grid from a GPS point cloud.

    Parameters
    ----------
    gps_path : Path
        Path to a GolfIntelligence .gps file.
    bbox : (lat_min, lng_min, lat_max, lng_max)
        Geographic bounding box; only GPS points inside this box are used.
    green_polygon_latlng : [(lat, lng), ...]
        Dense polygon outline of the green.  Should have at least 4 vertices.
        Clockwise or counterclockwise winding is both accepted.
    approach_m : float
        Distance in metres outside the green polygon to include in the mask.
        Typical range 5-10 m.  Default 8.0.
    grid_size : (cols, rows)
        Number of grid cells in (X=East, Y=North) directions.
        Default (200, 200).  Larger values = finer detail but slower mask
        computation (O(cols * rows) point-in-polygon tests).
    vert_exag : float
        Multiply final height values by this factor before returning.
        1.0 = real elevation; 3-10 typical for print legibility.
        Applied AFTER converting to mm so downstream code sees mm.

    Returns
    -------
    HeightmapResult
        heights_mm  : 2-D float64 array shape (rows, cols).
                      Height in mm above min GPS altitude in bbox.
                      NaN outside mask.
        mask        : 2-D bool array, True where heights_mm is valid.
        grid_x_mm   : 1-D array, East grid centres in mm.
        grid_y_mm   : 1-D array, North grid centres in mm.
        origin_latlng : SW bbox corner (lat_min, lng_min).
        raw_points_used : count of GPS points after bbox filter.
        bbox_m      : (east_min, north_min, east_max, north_max) in metres.
        interpolation_notes : warning strings (empty = all went well).

    Non-obvious behaviours
    ----------------------
    - heights_mm is zero-referenced to the minimum GPS altitude inside the
      bbox, not to sea level.  This keeps values small and print-friendly.
    - Cubic interpolation can produce small under-shoots (wiggles) beyond
      the actual altitude range.  These are physically harmless for EGM
      surface rendering but would show as slightly negative values if
      vert_exag is small and the surface is very flat.  The caller may clamp
      if desired.
    - NaN cells outside the mask are intentional -- callers should treat them
      as "no geometry here".
    - The projection uses a flat-earth approximation.  Accuracy is < 0.1% for
      bounding boxes smaller than ~2 km on a side (all golf greens qualify).
    """
    notes: list[str] = []

    # -- parse --
    cells = parse_gps_file(gps_path)
    lats_all, lngs_all, alts_all = extract_latlng_alt(cells)

    # -- filter to bbox --
    lats, lngs, alts = filter_by_bbox(lats_all, lngs_all, alts_all, bbox)
    raw_points_used = int(len(lats))
    if raw_points_used == 0:
        raise ValueError(
            f"No GPS points found inside bbox {bbox}. "
            f"File contains {len(lats_all)} points; check bbox coordinates."
        )
    if raw_points_used < 10:
        notes.append(
            f"Only {raw_points_used} GPS points inside bbox -- "
            "heightmap quality may be poor."
        )

    # -- ENU projection --
    origin_lat, origin_lng = bbox[0], bbox[1]
    east_m, north_m = latlng_to_enu_metres(lats, lngs, origin_lat, origin_lng)

    # bbox extents in local metres
    lat_min, lng_min, lat_max, lng_max = bbox
    lat_m_per_deg = 111_320.0
    lng_m_per_deg = 111_320.0 * math.cos(math.radians(origin_lat))
    bbox_east_max_m  = (lat_max - lat_min) * lat_m_per_deg   # note: lat -> north
    bbox_north_max_m = (lng_max - lng_min) * lng_m_per_deg   # note: lng -> east
    # correct assignment:
    bbox_north_max_m = (lat_max - lat_min) * lat_m_per_deg
    bbox_east_max_m  = (lng_max - lng_min) * lng_m_per_deg
    bbox_m = (0.0, 0.0, float(bbox_east_max_m), float(bbox_north_max_m))

    # -- grid definition (metres) --
    cols, rows = grid_size
    grid_east_m  = np.linspace(0.0, bbox_east_max_m,  cols)
    grid_north_m = np.linspace(0.0, bbox_north_max_m, rows)

    # -- green+approach mask --
    approach_poly = build_approach_polygon(
        green_polygon_latlng, origin_lat, origin_lng, approach_m
    )
    mask = compute_mask(grid_east_m, grid_north_m, approach_poly)

    if not mask.any():
        notes.append(
            "No grid cells fall inside the green+approach polygon. "
            "Check that green_polygon_latlng is within the bbox."
        )

    # -- interpolate raw altitudes (metres) onto grid --
    GZ_m = interpolate_heights(east_m, north_m, alts, grid_east_m, grid_north_m, notes)

    # -- zero-reference, convert to mm, apply vert_exag, apply mask --
    alt_min = float(GZ_m[mask].min()) if mask.any() else float(GZ_m.min())
    GZ_mm = (GZ_m - alt_min) * 1000.0 * vert_exag  # metres -> mm, scaled

    heights_mm = GZ_mm.copy()
    heights_mm[~mask] = np.nan

    # -- grid centres in mm --
    grid_x_mm = grid_east_m  * 1000.0
    grid_y_mm = grid_north_m * 1000.0

    return HeightmapResult(
        heights_mm=heights_mm,
        mask=mask,
        grid_x_mm=grid_x_mm,
        grid_y_mm=grid_y_mm,
        origin_latlng=(origin_lat, origin_lng),
        raw_points_used=raw_points_used,
        bbox_m=bbox_m,
        interpolation_notes=notes,
    )
