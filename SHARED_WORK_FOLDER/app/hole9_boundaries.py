"""
Polygon boundaries for Moffett Field Hole 9 (GolfLogix image).
Source image: team_inbox/Moffett Field 9 (GolfLogix).png
Image size: 679 x 714 pixels.

All coordinates are (x, y) pixel pairs, traced clockwise.
Boundaries were derived from a combination of visual tracing and
pixel-color analysis of the source image.
"""

IMAGE_SIZE = (679, 714)

# ---------------------------------------------------------------------------
# 1. PUTTING GREEN — the colorful contour region inside the black boundary
#    Shield/teardrop shape: wide at top, narrowing toward bottom.
#    Pixel analysis: x=[148-483], y=[69-409] for contour colors.
#    The black outline boundary is slightly outside these extents.
# ---------------------------------------------------------------------------
GREEN_BOUNDARY = [
    # top-left, going across top
    (235, 80),
    (258, 66),
    (285, 56),
    (315, 50),
    (345, 48),
    (375, 50),
    (405, 56),
    (430, 66),
    (452, 80),
    # right side going down
    (470, 98),
    (484, 120),
    (494, 145),
    (500, 172),
    (502, 200),
    (500, 230),
    (494, 258),
    (484, 284),
    (470, 308),
    # bottom-right curving to bottom
    (452, 328),
    (430, 344),
    (405, 358),
    (378, 368),
    (350, 374),
    (322, 374),
    (295, 368),
    # bottom-left curving up
    (270, 356),
    (248, 340),
    (230, 320),
    (216, 296),
    # left side going up
    (206, 270),
    (198, 242),
    (194, 214),
    (192, 186),
    (194, 160),
    (200, 136),
    (210, 114),
    (222, 96),
    (235, 80),
]

# ---------------------------------------------------------------------------
# 2. FRINGE OUTER BOUNDARY — dark green border around green + traps.
#    Stops at the fairway stripe boundary at the bottom.
#    Encompasses the full extent of both sand traps.
# ---------------------------------------------------------------------------
FRINGE_OUTER_BOUNDARY = [
    # top, left to right
    (215, 30),
    (260, 16),
    (310, 8),
    (365, 4),
    (420, 6),
    (470, 16),
    (514, 34),
    (548, 60),
    # upper right going down
    (574, 92),
    (592, 130),
    (604, 172),
    (610, 218),
    (612, 265),
    # right side, descending past green into right trap area
    (614, 310),
    (620, 348),
    (628, 385),
    (634, 420),
    (636, 455),
    (632, 488),
    (624, 516),
    (610, 538),
    (590, 554),
    (566, 564),
    (538, 568),
    # bottom-right to bottom-center
    (508, 566),
    (478, 560),
    (448, 556),
    (418, 556),
    (388, 560),
    (358, 568),
    (328, 576),
    # bottom-left, around left trap
    (298, 580),
    (268, 578),
    (238, 570),
    (212, 556),
    (190, 536),
    (172, 510),
    (158, 480),
    (146, 446),
    (136, 410),
    (128, 374),
    (122, 338),
    (118, 300),
    # left side going up
    (118, 262),
    (122, 226),
    (130, 192),
    (142, 160),
    (158, 130),
    (178, 104),
    (200, 80),
    (210, 54),
    (215, 30),
]

# ---------------------------------------------------------------------------
# 3. SAND TRAP LEFT — large beige blob, lower-left
#    Pixel analysis: center=(104,430), x=[18-191], y=[220-629]
#    The main dense beige area is roughly x=[30-185], y=[240-570]
#    Kidney/peanut shaped, tilted slightly.
# ---------------------------------------------------------------------------
TRAP_LEFT = [
    # top, going clockwise
    (95, 240),
    (120, 232),
    (142, 236),
    (160, 248),
    (172, 268),
    (180, 294),
    (184, 326),
    (186, 360),
    (184, 394),
    (180, 424),
    (176, 448),
    (172, 468),
    (170, 488),
    (172, 510),
    (176, 530),
    (178, 548),
    (174, 564),
    (164, 576),
    (148, 582),
    (130, 580),
    (112, 572),
    (94, 558),
    (78, 540),
    (64, 516),
    (52, 488),
    (42, 456),
    (36, 422),
    (34, 388),
    (36, 354),
    (42, 322),
    (50, 294),
    (62, 270),
    (76, 252),
    (95, 240),
]

# ---------------------------------------------------------------------------
# 4. SAND TRAP RIGHT — large beige blob, lower-right
#    Pixel analysis: center=(539,442), x=[444-628], y=[302-590]
#    Main dense beige area roughly x=[455-625], y=[305-570]
# ---------------------------------------------------------------------------
TRAP_RIGHT = [
    # top, going clockwise
    (520, 308),
    (542, 302),
    (562, 304),
    (580, 312),
    (596, 326),
    (608, 346),
    (618, 370),
    (624, 398),
    (628, 428),
    (626, 458),
    (620, 484),
    (610, 506),
    (598, 524),
    (582, 540),
    (562, 552),
    (540, 560),
    (516, 564),
    (494, 562),
    (476, 556),
    (460, 544),
    (450, 526),
    (444, 504),
    (444, 478),
    (448, 452),
    (454, 428),
    (462, 404),
    (472, 382),
    (484, 362),
    (498, 344),
    (508, 326),
    (520, 308),
]


# ---------------------------------------------------------------------------
# Quick sanity-check / visualization when run directly
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    try:
        from PIL import Image, ImageDraw

        img = Image.open(
            "/Users/fourierflight/GIT/CLAUDE-GitHub/SHARED_WORK_FOLDER/"
            "team_inbox/Moffett Field 9 (GolfLogix).png"
        )
        draw = ImageDraw.Draw(img)

        draw.polygon(GREEN_BOUNDARY, outline="white", width=2)
        draw.polygon(FRINGE_OUTER_BOUNDARY, outline="yellow", width=2)
        draw.polygon(TRAP_LEFT, outline="red", width=2)
        draw.polygon(TRAP_RIGHT, outline="red", width=2)

        out_path = (
            "/Users/fourierflight/GIT/CLAUDE-GitHub/SHARED_WORK_FOLDER/"
            "owner_inbox/debug_hole9_boundaries.png"
        )
        img.save(out_path)
        print(f"Saved overlay to {out_path}")
    except ImportError:
        print("Install Pillow to run the visual sanity check.")
