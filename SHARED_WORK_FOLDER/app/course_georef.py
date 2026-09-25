"""
course_georef.py — pixel ↔ lat/lng conversion for golf-course images.

The ``courseGeoRef`` block in an EGM file stores the geo-referencing
information for the course's source image:

    {
        "imageWidth":       1024,
        "imageHeight":      1024,
        "swCornerLatLng":   [lat_sw, lng_sw],   # bottom-left of image
        "neCornerLatLng":   [lat_ne, lng_ne],   # top-right of image
    }

Coordinate convention
---------------------
- Pixel (0, 0) is the **top-left** of the image (screen/canvas convention).
- The SW (south-west) corner of the *geographic* bounding box corresponds to
  the **bottom-left pixel** — i.e. ``(0, imageHeight)``.
- The NE (north-east) corner corresponds to the **top-right pixel** —
  i.e. ``(imageWidth, 0)``.
- Linear interpolation is used for all conversions. Flat-earth ENU error is
  < 0.1% for any bbox smaller than ~2 km; golf courses are well within this.

Public API
----------
pixel_to_latlng(px_x, px_y, georef) -> (lat, lng)
latlng_to_pixel(lat, lng, georef)   -> (px_x, px_y)
validate_georef(georef)             -> None  (raises ValueError on bad input)
"""

from __future__ import annotations


__version__ = "1.0.0"


# ──────────────────────────────────────────────────────────────────────────────
# Validation
# ──────────────────────────────────────────────────────────────────────────────

_REQUIRED_KEYS = ("imageWidth", "imageHeight", "swCornerLatLng", "neCornerLatLng")


def validate_georef(georef: dict) -> None:
    """Raise ValueError with a clear message if *georef* is unusable.

    Checks
    ------
    * All four required keys are present.
    * imageWidth > 0 and imageHeight > 0.
    * swCornerLatLng / neCornerLatLng are [lat, lng] pairs (len == 2).
    * SW latitude < NE latitude (image is north-up).
    * SW longitude < NE longitude (image spans west → east).
    """
    if georef is None:
        raise ValueError(
            "courseGeoRef is not set for this course. "
            "Open the Geo-ref dialog (⚙) and enter the SW and NE corner "
            "lat/lng of the course image."
        )
    missing = [k for k in _REQUIRED_KEYS if k not in georef]
    if missing:
        raise ValueError(f"courseGeoRef missing required keys: {missing}")

    w = georef["imageWidth"]
    h = georef["imageHeight"]
    if not (isinstance(w, (int, float)) and w > 0):
        raise ValueError(f"courseGeoRef.imageWidth must be a positive number, got {w!r}")
    if not (isinstance(h, (int, float)) and h > 0):
        raise ValueError(f"courseGeoRef.imageHeight must be a positive number, got {h!r}")

    sw = georef["swCornerLatLng"]
    ne = georef["neCornerLatLng"]
    if not (isinstance(sw, (list, tuple)) and len(sw) == 2):
        raise ValueError(f"courseGeoRef.swCornerLatLng must be [lat, lng], got {sw!r}")
    if not (isinstance(ne, (list, tuple)) and len(ne) == 2):
        raise ValueError(f"courseGeoRef.neCornerLatLng must be [lat, lng], got {ne!r}")

    lat_sw, lng_sw = float(sw[0]), float(sw[1])
    lat_ne, lng_ne = float(ne[0]), float(ne[1])

    if lat_sw >= lat_ne:
        raise ValueError(
            f"courseGeoRef: SW latitude ({lat_sw}) must be < NE latitude ({lat_ne}). "
            "Verify the corner order (SW = bottom-left, NE = top-right)."
        )
    if lng_sw >= lng_ne:
        raise ValueError(
            f"courseGeoRef: SW longitude ({lng_sw}) must be < NE longitude ({lng_ne}). "
            "Verify the corner order (SW = bottom-left, NE = top-right)."
        )


# ──────────────────────────────────────────────────────────────────────────────
# Conversions
# ──────────────────────────────────────────────────────────────────────────────

def pixel_to_latlng(
    px_x: float,
    px_y: float,
    georef: dict,
) -> tuple[float, float]:
    """Convert image pixel coordinates to (lat, lng).

    Parameters
    ----------
    px_x, px_y : float
        Pixel coordinates; (0, 0) is the **top-left** of the image.
    georef : dict
        A ``courseGeoRef`` block from an EGM file.

    Returns
    -------
    (lat, lng) : tuple[float, float]
    """
    validate_georef(georef)

    w = float(georef["imageWidth"])
    h = float(georef["imageHeight"])
    lat_sw, lng_sw = float(georef["swCornerLatLng"][0]), float(georef["swCornerLatLng"][1])
    lat_ne, lng_ne = float(georef["neCornerLatLng"][0]), float(georef["neCornerLatLng"][1])

    # Normalise pixel coords to [0, 1] fractions
    # px_x = 0 → west edge (lng_sw); px_x = w → east edge (lng_ne)
    frac_x = px_x / w
    # px_y = 0 → top (north, lat_ne); px_y = h → bottom (south, lat_sw)
    frac_y = px_y / h

    lng = lng_sw + frac_x * (lng_ne - lng_sw)
    lat = lat_ne - frac_y * (lat_ne - lat_sw)   # Y-axis flip: top = north

    return float(lat), float(lng)


def latlng_to_pixel(
    lat: float,
    lng: float,
    georef: dict,
) -> tuple[float, float]:
    """Convert (lat, lng) to image pixel coordinates.

    Parameters
    ----------
    lat, lng : float
        Geographic coordinates.
    georef : dict
        A ``courseGeoRef`` block from an EGM file.

    Returns
    -------
    (px_x, px_y) : tuple[float, float]
        Pixel coordinates; (0, 0) is the top-left of the image.
        Values are not clamped — out-of-bounds points return negative or
        > image-size coordinates.
    """
    validate_georef(georef)

    w = float(georef["imageWidth"])
    h = float(georef["imageHeight"])
    lat_sw, lng_sw = float(georef["swCornerLatLng"][0]), float(georef["swCornerLatLng"][1])
    lat_ne, lng_ne = float(georef["neCornerLatLng"][0]), float(georef["neCornerLatLng"][1])

    frac_x = (lng - lng_sw) / (lng_ne - lng_sw)
    frac_y = (lat_ne - lat) / (lat_ne - lat_sw)   # Y-axis flip

    px_x = frac_x * w
    px_y = frac_y * h

    return float(px_x), float(px_y)


def green_polygon_px_to_latlng(
    green_pts_px: list[dict],
    georef: dict,
) -> list[tuple[float, float]]:
    """Convert a list of ``{x, y}`` pixel dicts (green polygon from EGM) to
    a list of ``(lat, lng)`` tuples suitable for passing to
    ``build_heightmap_from_gps``.

    Parameters
    ----------
    green_pts_px : list[dict]
        Each dict has keys ``"x"`` and ``"y"`` in image-pixel coordinates.
    georef : dict
        courseGeoRef block.

    Returns
    -------
    list[tuple[float, float]]
        ``[(lat, lng), ...]``
    """
    validate_georef(georef)
    return [
        pixel_to_latlng(float(pt["x"]), float(pt["y"]), georef)
        for pt in green_pts_px
    ]
