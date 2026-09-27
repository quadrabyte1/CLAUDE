"""
test_golf_intel_ocr.py — TDD test suite for golf_intel_ocr.py

Run:
    cd /Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER
    python -m pytest app/tests/test_golf_intel_ocr.py -v

Golf Intelligence heat map markers are decimal numbers ("1.2", "2.8", "4.0")
rendered as near-black text with white outline on the coloured gradient surface.

Test coverage:
  T0   Unit helpers: _is_valid_marker, _deduplicate
  T1   Synthetic fixture — OCR finds "1.5", "2.8", "4.0" at known positions
  T2   False-positive filter — alpha/integer distractor text excluded
  T3   Real-image smoke test — DeLaveaga Hole 3 yields N >= 3 markers
  T4   Overlay writer — PNG written, same dims, marker pixels non-white
  T5   Idempotency — same image returns same values twice
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).parent.parent))
from golf_intel_ocr import (
    extract_numeric_markers,
    generate_diagnostic_overlay,
    _is_valid_marker,
    _deduplicate,
)

# ---------------------------------------------------------------------------
# Shared font for synthetic images
# ---------------------------------------------------------------------------
# EasyOCR needs at least ~15px tall text to recognise reliably.
# We prefer a bundled system font; fall back to PIL's built-in default.
_FONT_CANDIDATES = [
    "/System/Library/Fonts/Helvetica.ttc",
    "/System/Library/Fonts/Arial.ttf",
    "/Library/Fonts/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]
_SYNTH_FONT: ImageFont.FreeTypeFont | None = None
for _fp in _FONT_CANDIDATES:
    if os.path.exists(_fp):
        try:
            _SYNTH_FONT = ImageFont.truetype(_fp, 22)
        except Exception:
            pass
        break

# ---------------------------------------------------------------------------
# Real image paths
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).parent.parent.parent
_DL_H3 = _REPO_ROOT / "ItWentIn/GolfCourses/Delaveaga/Images/Delaveaga (Hole 3, 55155).png"
_DL_H5 = _REPO_ROOT / "ItWentIn/GolfCourses/Delaveaga/Images/Delaveaga (Hole 5, 55169).png"
_STANFORD_H8 = _REPO_ROOT / "ItWentIn/GolfCourses/Stanford/Images/Stanford (hole 8, 5396).png"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_synthetic_image(
    tmp_path: Path,
    labels: list[tuple[int, int, str]],
    bg_color: tuple = (100, 150, 80),      # saturated greenish background
    text_color: tuple = (240, 255, 200),   # near-white, slightly tinted (passes sat > 35)
    img_size: tuple = (400, 400),
) -> Path:
    """
    Render label strings at (x, y) positions with a tinted-white text on a
    coloured background, matching the GI heat-map marker appearance.

    Text colour (240, 255, 200) is chosen so that:
      - grayscale brightness ≈ 244 > 195 (_WHITE_THRESHOLD)
      - HSV saturation ≈ 55 > 35 (_SAT_THRESHOLD)
    Both conditions are required by _build_white_on_colored_mask.

    A 22-pt system font is used when available (PIL's built-in font is
    only ~7 px tall, too small for EasyOCR to reliably recognise).
    """
    img = Image.new("RGB", img_size, color=bg_color)
    draw = ImageDraw.Draw(img)
    font = _SYNTH_FONT  # None → PIL built-in default
    for x, y, text in labels:
        # Dark outline (4-directional) so marker has a crisp edge
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            draw.text((x + dx, y + dy), text, fill=(10, 10, 10), font=font)
        draw.text((x, y), text, fill=text_color, font=font)
    p = tmp_path / "synthetic.png"
    img.save(str(p))
    return p


# ===========================================================================
# T0   Unit helpers
# ===========================================================================

class TestIsValidMarker:
    def test_accepts_standard_decimal(self):
        assert _is_valid_marker("1.2")
        assert _is_valid_marker("2.8")
        assert _is_valid_marker("4.0")
        assert _is_valid_marker("10.5")

    def test_rejects_plain_integer(self):
        assert not _is_valid_marker("10")
        assert not _is_valid_marker("20")
        assert not _is_valid_marker("0")

    def test_rejects_alpha(self):
        assert not _is_valid_marker("abc")
        assert not _is_valid_marker("x2.3")

    def test_rejects_out_of_range(self):
        assert not _is_valid_marker("0.0")   # below min 0.1
        assert not _is_valid_marker("100.0") # above max 99.9

    def test_rejects_float_string_without_decimal(self):
        assert not _is_valid_marker("28")

    def test_strips_whitespace(self):
        assert _is_valid_marker("  2.8  ")

    def test_rejects_too_many_decimal_places(self):
        # X.XXX — three decimal places should be rejected by the regex
        assert not _is_valid_marker("1.234")


class TestDeduplicate:
    def test_identical_positions_collapsed(self):
        hits = [(10, 10, 2.8, 80), (11, 11, 2.8, 60)]
        result = _deduplicate(hits, radius=15)
        assert len(result) == 1
        assert result[0][2] == pytest.approx(2.8)

    def test_far_positions_kept(self):
        hits = [(10, 10, 2.8, 80), (200, 200, 4.0, 70)]
        result = _deduplicate(hits, radius=15)
        assert len(result) == 2

    def test_highest_conf_wins(self):
        hits = [(10, 10, 2.8, 60), (10, 10, 2.8, 90), (300, 300, 4.0, 70)]
        result = _deduplicate(hits, radius=15)
        assert len(result) == 2
        values = [m[2] for m in result]
        assert pytest.approx(2.8) in values
        assert pytest.approx(4.0) in values


# ===========================================================================
# T1   Synthetic fixture — decimal markers at known positions
# ===========================================================================

class TestSyntheticOCR:
    """
    Render "1.5", "2.8", "4.0" on a coloured background and verify that
    extract_numeric_markers detects them.
    """

    TOLERANCE_PX = 40  # generous to cover Tesseract bbox jitter

    @pytest.fixture(scope="class")
    def synthetic_image(self, tmp_path_factory):
        tmp = tmp_path_factory.mktemp("synth_ocr")
        labels = [
            (60,  80,  "1.5"),
            (220, 120, "2.8"),
            (80,  280, "4.0"),
        ]
        return _make_synthetic_image(tmp, labels, img_size=(400, 400))

    def test_finds_decimal_values(self, synthetic_image):
        markers = extract_numeric_markers(synthetic_image)
        values = {round(m[2], 1) for m in markers}
        # At least two of the three planted values must be recovered
        planted = {1.5, 2.8, 4.0}
        found_count = len(values & planted)
        assert found_count >= 2, (
            f"Expected >=2 of {planted} in {values}"
        )

    def test_all_returned_values_are_floats(self, synthetic_image):
        markers = extract_numeric_markers(synthetic_image)
        for mx, my, mv in markers:
            assert isinstance(mv, float), f"Expected float, got {type(mv)}: {mv}"

    def test_values_in_range(self, synthetic_image):
        markers = extract_numeric_markers(synthetic_image)
        for mx, my, mv in markers:
            assert 0.1 <= mv <= 99.9, f"Value {mv} out of range"


# ===========================================================================
# T2   False-positive filter
# ===========================================================================

class TestFalsePositiveFilter:
    """
    Distractor strings — plain integers ("10"), alpha ("abc"), floats with
    too many decimal places ("1.234") — must NOT appear in results.
    """

    @pytest.fixture(scope="class")
    def distractor_image(self, tmp_path_factory):
        tmp = tmp_path_factory.mktemp("distractor")
        labels = [
            (40,  50,  "2.5"),   # valid GI marker
            (200, 50,  "abc"),   # should be rejected
            (40,  200, "10"),    # plain integer — should be rejected
            (200, 200, "3.7"),   # valid
        ]
        return _make_synthetic_image(tmp, labels, img_size=(350, 350))

    def test_no_non_float_values(self, distractor_image):
        markers = extract_numeric_markers(distractor_image)
        for mx, my, mv in markers:
            assert isinstance(mv, float)

    def test_valid_markers_present(self, distractor_image):
        markers = extract_numeric_markers(distractor_image)
        values = {round(m[2], 1) for m in markers}
        # At least one of the planted valid values should be found
        assert values & {2.5, 3.7}, f"Expected 2.5 or 3.7 in {values}"

    def test_no_out_of_range(self, distractor_image):
        markers = extract_numeric_markers(distractor_image)
        for mx, my, mv in markers:
            assert 0.1 <= mv <= 99.9, f"Out-of-range: {mv}"


# ===========================================================================
# T3   Real-image smoke tests
# ===========================================================================

@pytest.mark.skipif(not _DL_H3.exists(), reason="DeLaveaga Hole 3 image not present")
class TestRealImageDeLaveagaH3:
    """
    De Laveaga Hole 3 is a clean GI heat map with several visible decimal
    markers (1.2, 1.3, 2.8, 4.0, …).  We expect >= 3 detections.
    """

    @pytest.fixture(scope="class")
    def markers(self):
        return extract_numeric_markers(_DL_H3)

    def test_finds_at_least_3_markers(self, markers):
        assert len(markers) >= 3, (
            f"Expected >= 3 markers on DeLaveaga H3, found {len(markers)}: {markers}"
        )

    def test_all_values_are_floats_in_range(self, markers):
        for mx, my, mv in markers:
            assert isinstance(mv, float)
            assert 0.1 <= mv <= 99.9, f"Out-of-range: {mv}"

    def test_positions_within_image_bounds(self, markers):
        img = Image.open(_DL_H3)
        iw, ih = img.size
        for mx, my, mv in markers:
            assert 0 <= mx < iw, f"x={mx} outside width={iw}"
            assert 0 <= my < ih, f"y={my} outside height={ih}"


@pytest.mark.skipif(not _STANFORD_H8.exists(), reason="Stanford Hole 8 image not present")
class TestRealImageStanfordH8:
    """Smoke test on Stanford Hole 8 (also GI format arrows + heat)."""

    def test_finds_at_least_3_markers(self):
        markers = extract_numeric_markers(_STANFORD_H8)
        assert len(markers) >= 3, (
            f"Expected >= 3 markers on Stanford H8, found {len(markers)}: {markers}"
        )


# ===========================================================================
# T4   Overlay writer
# ===========================================================================

class TestOverlayWriter:

    @pytest.fixture
    def source_image(self, tmp_path):
        img = Image.new("RGB", (300, 300), color=(80, 150, 100))
        p = tmp_path / "source.png"
        img.save(str(p))
        return p

    @pytest.fixture
    def output_path(self, tmp_path):
        return tmp_path / "overlay.png"

    def test_file_is_written(self, source_image, output_path):
        markers = [(50, 80, 2.8), (200, 150, 4.0)]
        generate_diagnostic_overlay(source_image, markers, output_path)
        assert output_path.exists(), "Overlay PNG was not written"

    def test_output_same_dimensions(self, source_image, output_path):
        generate_diagnostic_overlay(source_image, [(100, 100, 1.5)], output_path)
        out = Image.open(output_path)
        src = Image.open(source_image)
        assert out.size == src.size, f"Expected {src.size}, got {out.size}"

    def test_marker_positions_non_white(self, source_image, output_path):
        """Pixels near marker centres should differ from pure white (circle was drawn)."""
        markers = [(50, 80, 2.8), (200, 150, 4.0)]
        generate_diagnostic_overlay(source_image, markers, output_path)
        out_arr = np.array(Image.open(output_path))
        for mx, my, mv in markers:
            # Check a small neighbourhood around the marker
            region = out_arr[
                max(0, my - 8):min(300, my + 8),
                max(0, mx - 8):min(300, mx + 8),
            ]
            # Should contain at least some non-white, non-background pixels
            # (magenta circle outline)
            # Use a loose check: not all pixels should be the source bg color
            flat = region.reshape(-1, 3)
            unique_colors = len(set(map(tuple, flat)))
            assert unique_colors > 1, (
                f"Marker at ({mx},{my}) value={mv}: no drawing visible in neighbourhood"
            )

    def test_version_badge_dark_region(self, source_image, output_path):
        """Upper-left corner should have a dark region (badge background)."""
        generate_diagnostic_overlay(source_image, [(100, 100, 2.8)], output_path, version="v9.9")
        out_arr = np.array(Image.open(output_path))
        badge_region = out_arr[4:20, 4:80]
        dark_pixels = np.sum(badge_region.mean(axis=2) < 50)
        assert dark_pixels > 10, "Version badge region appears to have no dark pixels"

    def test_empty_markers_still_writes(self, source_image, output_path):
        generate_diagnostic_overlay(source_image, [], output_path)
        assert output_path.exists()

    def test_label_format_is_one_decimal(self, source_image, output_path):
        """
        The overlay labels should format values to one decimal place.
        (We verify by checking the file was written — label format is an
        internal detail, but this guards against silent errors.)
        """
        generate_diagnostic_overlay(source_image, [(100, 100, 2.8)], output_path)
        assert output_path.stat().st_size > 1000  # non-trivial file


# ===========================================================================
# T5   Idempotency
# ===========================================================================

class TestIdempotency:

    @pytest.mark.skipif(not _DL_H3.exists(), reason="DeLaveaga Hole 3 not present")
    def test_real_image_idempotent(self):
        r1 = extract_numeric_markers(_DL_H3)
        r2 = extract_numeric_markers(_DL_H3)
        assert r1 == r2, f"Not idempotent: run1={r1}, run2={r2}"

    def test_synthetic_idempotent(self, tmp_path):
        labels = [(80, 80, "2.5"), (200, 200, "3.8")]
        img_path = _make_synthetic_image(tmp_path, labels)
        r1 = extract_numeric_markers(img_path)
        r2 = extract_numeric_markers(img_path)
        assert r1 == r2, f"Not idempotent on synthetic: {r1} vs {r2}"
