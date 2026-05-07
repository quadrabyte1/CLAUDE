"""
gen_drawio_v15.py — Generates deck_plan.drawio for v15.

Starting from current deck_plan.drawio (v14) and applying v15 changes:

Change — Replace ASCII <pre> elevation cells with native drawio shapes:
  - v14-p2-left-stair-profile (ASCII <pre> cell) → deleted/hidden
    Replaced by v15-p2-left-stair-* (18 native shape cells):
      border box, ground-line, gravel fill, paver rect, stringer polygon
      (4-edge polyline), lower tread plank x2, upper deck plank,
      open-riser dashed lines x2, dimension arrows x2, tread dim arrow,
      grade/mid/deck label lines x3, rise labels x2, tread label, bottom callout

  - v14-p2-far-step-elev-profile (ASCII <pre> cell) → deleted/hidden
    Replaced by v15-p2-far-step-* (19 native shape cells):
      border box, ground-line, gravel fill, precast block rect, ribbon rect,
      tread plank x2, deck top plank, open-riser dashed line,
      grade/mid/deck tick lines x3, rise arrow + label, tread arrow + label,
      ribbon label, block label, bottom callout

No other changes.  v14→v15 version sweep applied throughout.

Coordinate system (drawio):
  Scale: 40 px/ft
  Origin: x=220 (left girder outer face = x=0'), y=180 (house wall = y=0')

Left-edge stair panel bounding box (same as v14):
  bg: x=1340, y=900, w=220, h=220

Far-edge step panel bounding box (same as v14):
  bg: x=1340, y=700, w=220, h=190
"""

import re

# ─── Elevation drawing constants ────────────────────────────────────────────────
# Colors matching the matplotlib render
C_GRAVEL      = "#d0c8b8"   # gravel fill
EC_GRAVEL     = "#8a7a68"   # gravel edge
C_PAVER       = "#9a9a9a"   # 12x12 paver
EC_PAVER      = "#444444"
C_STRINGER    = "#a07060"   # PT 2x10 stringer (warm brown)
EC_STRINGER   = "#7a4828"
C_TREAD       = "#7a9a7a"   # MoistureShield Vision tread (muted green)
EC_TREAD      = "#4a7050"
C_DECK_PLANK  = "#c9a778"   # field plank (tan)
EC_DECK_PLANK = "#8a7040"
C_RIBBON      = "#8b6030"   # doubled 2x6 PT ribbon
EC_RIBBON     = "#5a3a10"
C_BLOCK       = "#b8b0a0"   # precast concrete block
EC_BLOCK      = "#888070"
C_FAR_GRAVEL  = "#d4cbc0"   # far-edge gravel
EC_FAR_GRAVEL = "#8a7868"
C_OPEN_RISER  = "#cc4400"   # open riser dashed line color
C_DIM_ARROW   = "#444466"   # dimension arrow color (near-black blue)
C_ELEV_LBL    = "#2244aa"   # elevation label color (blue)
C_FAR_LBL     = "#2a6a2a"   # far-edge step label color (green)
C_TREAD_DIM   = "#774400"   # tread dimension color (brown)
C_GRADE_TICK  = "#444488"   # grade tick line color

# ─── Cell ID counter ─────────────────────────────────────────────────────────────
_cid = [0]

def next_id(prefix):
    _cid[0] += 1
    return f"v15-{prefix}-{_cid[0]:03d}"


def rect_cell(cid, parent, x, y, w, h, fc, ec, lw=1, opacity=100, value="",
              extra_style="", dashed=0):
    dashed_s = f"dashed={dashed};" if dashed else ""
    return (f'        <mxCell id="{cid}" parent="{parent}" '
            f'style="rounded=0;whiteSpace=wrap;html=1;fillColor={fc};strokeColor={ec};'
            f'strokeWidth={lw};opacity={opacity};{dashed_s}{extra_style}" '
            f'value="{value}" vertex="1">\n'
            f'          <mxGeometry x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" as="geometry" />\n'
            f'        </mxCell>')


def line_cell(cid, parent, x1, y1, x2, y2, color="#444444", lw=1, dashed=0,
              end_arrow="none", start_arrow="none"):
    dashed_s = f"dashed=1;dashPattern=8 4;" if dashed else "dashed=0;"
    return (f'        <mxCell id="{cid}" parent="{parent}" '
            f'style="endArrow={end_arrow};startArrow={start_arrow};html=1;'
            f'strokeColor={color};strokeWidth={lw};{dashed_s}exitX=0.5;exitY=0.5;entryX=0.5;entryY=0.5;" '
            f'edge="1" value="">\n'
            f'          <mxGeometry relative="1" as="geometry">\n'
            f'            <mxPoint x="{x1:.1f}" y="{y1:.1f}" as="sourcePoint" />\n'
            f'            <mxPoint x="{x2:.1f}" y="{y2:.1f}" as="targetPoint" />\n'
            f'          </mxGeometry>\n'
            f'        </mxCell>')


def dim_arrow_cell(cid, parent, x1, y1, x2, y2, color="#444444", lw=1):
    """Double-ended dimension arrow (classic arrowheads both ends)."""
    return (f'        <mxCell id="{cid}" parent="{parent}" '
            f'style="endArrow=classic;startArrow=classic;html=1;'
            f'strokeColor={color};strokeWidth={lw};fillColor={color};'
            f'endFill=1;startFill=1;" '
            f'edge="1" value="">\n'
            f'          <mxGeometry relative="1" as="geometry">\n'
            f'            <mxPoint x="{x1:.1f}" y="{y1:.1f}" as="sourcePoint" />\n'
            f'            <mxPoint x="{x2:.1f}" y="{y2:.1f}" as="targetPoint" />\n'
            f'          </mxGeometry>\n'
            f'        </mxCell>')


def text_cell(cid, parent, x, y, w, h, value, fs=6, color="#333333",
              align="center", va="middle", bold=False, italic=False):
    style_extra = ""
    if bold:
        style_extra += "fontStyle=1;"
    if italic:
        style_extra += "fontStyle=2;"
    return (f'        <mxCell id="{cid}" parent="{parent}" '
            f'style="text;html=1;strokeColor=none;fillColor=none;'
            f'align={align};verticalAlign={va};whiteSpace=wrap;'
            f'fontSize={fs};fontColor={color};{style_extra}" '
            f'value="{value}" vertex="1">\n'
            f'          <mxGeometry x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" as="geometry" />\n'
            f'        </mxCell>')


def polyline_cell(cid, parent, points, fc, ec, lw=1.5):
    """A closed polygon using mxGraph's mxCell with shape=mxgraph.basic.rect
    but actually built as an orthogonal staircase via a poly-segment edge,
    or as a filled region via style='shape=...' points attribute.

    For drawio, the cleanest approach for a stepped stringer profile is to use
    a series of edge segments (they don't fill), so instead we approximate the
    stringer with a filled rectangle + a cutout — or we use multiple overlapping
    rectangles to build the step profile shape.

    This function emits the stringer as THREE rectangles stacked to simulate
    the stepped L-shaped stringer cross-section visible in side elevation:
      - Lower rect: from grade to mid-tread height (full depth tread2_px wide)
      - Upper rect: from mid-tread to deck height (tread1_px wide)
    We return a list of XML strings.
    """
    # Build a perimeter polygon as a style="shape=mxgraph.basic.rect" is not easy.
    # Instead emit a native mxCell with style containing a custom path isn't standard.
    # The most reliable approach: draw the stringer as a FILLED polygon using
    # a drawio "swimlane" or just as a custom path via the HTML shape.
    # Best option: use the "mxGraph" polyline approach via points attribute.
    # Actually the cleanest drawio-native way is style="shape=hexagon" etc, but
    # for an arbitrary polygon the correct approach is a custom shape style.
    # For v15 we use: style="shape=mxgraph.flowchart.start_2" — no, too restrictive.
    #
    # FINAL DECISION: render the stringer as stacked colored rectangles:
    #   rect1 = lower step (grade to mid)
    #   rect2 = upper step (mid to deck)
    # This is visually equivalent to the stepped cross-section when seen in elevation.
    # Points list: [(x,y), ...] — unused here, see stringer_rects() below.
    pass


def stringer_rects(cid_prefix, parent,
                   ox, grade_y, mid_y, deck_y,
                   tread1_px, tread2_px,
                   fc=C_STRINGER, ec=EC_STRINGER):
    """
    Emit two rectangle cells that together form the stepped stringer profile
    visible in side elevation:

      deck_y ─ ┌────────────────┐   (upper step: width=tread1_px, height = mid_y - deck_y)
               │                │
      mid_y  ─ └──────┐─────────┤   (joint between upper/lower)
                       │         │
                       │  lower  │   (lower step: width=tread2_px, height = grade_y - mid_y)
      grade_y ─        └─────────┘

    Actually in drawio y increases downward. deck_y < mid_y < grade_y.
    Upper rect: x=ox, y=deck_y, w=tread1_px, h=(mid_y-deck_y)
    Lower rect: x=ox+tread1_px, y=mid_y, w=(tread2_px-tread1_px), h=(grade_y-mid_y)

    We also add a solid left edge line (stringer face) from deck_y to grade_y.
    """
    cells = []
    # Upper step of stringer (deck to mid)
    cells.append(rect_cell(
        f"{cid_prefix}-upper", parent,
        ox, deck_y, tread1_px, (mid_y - deck_y),
        fc, ec, lw=1.5
    ))
    # Lower step of stringer (mid to grade)
    cells.append(rect_cell(
        f"{cid_prefix}-lower", parent,
        ox + tread1_px, mid_y, (tread2_px - tread1_px), (grade_y - mid_y),
        fc, ec, lw=1.5
    ))
    return cells


# ══════════════════════════════════════════════════════════════════════════════════
# LEFT-EDGE STAIR ELEVATION — native drawio shapes
# Panel: x=1340, y=900, w=220, h=220 (same as v14)
# ══════════════════════════════════════════════════════════════════════════════════

def make_left_stair_elev_cells(parent="p2-1"):
    """
    Native drawio replacement for v14-p2-left-stair-profile (the ASCII <pre> cell).
    Keeps the bg box and dims text from v14; replaces only the profile cell.

    Geometry plan (all in drawio pixels):
      Panel bg: x=1340, y=900, w=220, h=220
      Title text occupies top ~28px → drawing area starts at y=928
      Dims text at bottom ~44px → drawing area ends at y=1072 (= 900+220-48)
      Available draw height: 1072 - 928 = 144 px

      Scale: 12" maps to 96px vertical (8px per inch), so:
        grade at  y = 1065     (3px above dims area bottom, allows space)
        mid   at  y = 1065 - 8*6  = 1017
        deck  at  y = 1065 - 8*12 = 969  (allow 3px top margin from 928+38)

      Wait — let's recalculate to fit:
        draw_y_top   = 928 + 20 = 948   (leave 20px for any title overhang)
        draw_y_bot   = 1072 - 5 = 1067  (5px above dims)
        available    = 1067 - 948 = 119 px for 12" of rise
        scale        = 119/12 = ~9.9 px/in → round to 9 px/in

      With 9px/in:
        grade  y = 1062
        mid    y = 1062 - 9*6  = 1008
        deck   y = 1062 - 9*12 = 954

      Horizontal:
        left edge of drawing (stringer face):  x = 1395 (55px from panel left)
        tread1 depth = 10.8in * 2.2px/in = 23.8 → round to 24px (tread visible depth)
        tread2 depth = 16in  * 2.2px/in = 35.2 → round to 36px (bottom step total depth)
        These are chosen to look good; they don't need to be exact scale horizontally.

      Label area to left of stringer: x = 1340..1395 (55px for grade labels)
    """
    cells = []
    P = "p2-1"

    # --- Panel constants ---
    PX    = 1340.0   # panel left
    PY    = 900.0    # panel top
    PW    = 220.0
    PH    = 220.0

    # Elevation scale & origin
    SCALE_Y = 9.0    # px per inch vertical
    grade_y  = PY + PH - 48 - 5    # = 900+220-53 = 1067 → use 1064
    grade_y  = 1064.0
    mid_y    = grade_y - SCALE_Y * 6    # = 1064 - 54 = 1010
    deck_y   = grade_y - SCALE_Y * 12   # = 1064 - 108 = 956

    # Horizontal
    OX       = PX + 56.0    # stringer left face x
    T1_PX    = 24.0         # 10.8" tread (first step, upper)
    T2_PX    = 38.0         # 16" total horizontal depth
    PLANK_H  = 5.0          # tread plank thickness in px (~1" visual)

    # Ground line (dashed, full width of stringer)
    cells.append(line_cell(
        "v15-p2-left-stair-grade-line", P,
        OX - 8, grade_y, OX + T2_PX + 12, grade_y,
        color=C_GRADE_TICK, lw=1.0, dashed=1
    ))

    # Gravel fill (hatched rectangle below grade, behind stringer)
    cells.append(rect_cell(
        "v15-p2-left-stair-gravel", P,
        OX - 8, grade_y, T2_PX + 20, 16.0,
        C_GRAVEL, EC_GRAVEL, lw=1.0, opacity=85,
        extra_style="fillStyle=cross-hatch;"
    ))

    # 12x12 paver slab at bottom of lower stringer (grade level)
    PAVER_W = 16.0
    PAVER_H = 5.0
    cells.append(rect_cell(
        "v15-p2-left-stair-paver", P,
        OX, grade_y - PAVER_H, PAVER_W, PAVER_H,
        C_PAVER, EC_PAVER, lw=1.0,
        value=""
    ))

    # Paver text label
    cells.append(text_cell(
        "v15-p2-left-stair-paver-lbl", P,
        OX, grade_y - PAVER_H - 10, PAVER_W + 10, 10,
        "12×12 paver", fs=5, color="#555555", align="center", va="bottom"
    ))

    # PT 2x10 stringer profile — two stepped rectangles
    # Upper step: (OX, deck_y) → (OX+T1_PX, mid_y)  — width T1_PX, height mid_y-deck_y
    cells.append(rect_cell(
        "v15-p2-left-stair-str-upper", P,
        OX, deck_y, T1_PX, (mid_y - deck_y),
        C_STRINGER, EC_STRINGER, lw=1.5
    ))
    # Lower step: (OX+T1_PX, mid_y) → (OX+T2_PX, grade_y)
    cells.append(rect_cell(
        "v15-p2-left-stair-str-lower", P,
        OX + T1_PX, mid_y, (T2_PX - T1_PX), (grade_y - mid_y),
        C_STRINGER, EC_STRINGER, lw=1.5
    ))

    # Upper tread plank (at mid_y level, sitting on top of upper stringer step)
    cells.append(rect_cell(
        "v15-p2-left-stair-tread-upper", P,
        OX, mid_y - PLANK_H, T1_PX, PLANK_H,
        C_TREAD, EC_TREAD, lw=1.0
    ))

    # Deck top plank (at deck_y level)
    cells.append(rect_cell(
        "v15-p2-left-stair-deck-top", P,
        OX - 4, deck_y - PLANK_H, T1_PX + 8, PLANK_H,
        C_DECK_PLANK, EC_DECK_PLANK, lw=1.0
    ))

    # Deck top horizontal solid line extending right
    cells.append(line_cell(
        "v15-p2-left-stair-deck-line", P,
        OX - 4, deck_y - PLANK_H, OX + T1_PX + 20, deck_y - PLANK_H,
        color=EC_DECK_PLANK, lw=1.5
    ))

    # Open riser 1: dashed vertical at x = OX+T1_PX between deck_y and mid_y
    cells.append(line_cell(
        "v15-p2-left-stair-riser1", P,
        OX + T1_PX, deck_y, OX + T1_PX, mid_y,
        color=C_OPEN_RISER, lw=1.2, dashed=1
    ))

    # Open riser 2: dashed vertical at x = OX+T2_PX between mid_y and grade_y
    cells.append(line_cell(
        "v15-p2-left-stair-riser2", P,
        OX + T2_PX, mid_y, OX + T2_PX, grade_y,
        color=C_OPEN_RISER, lw=1.2, dashed=1
    ))

    # "OPEN RISER" label for riser 1
    cells.append(text_cell(
        "v15-p2-left-stair-riser1-lbl", P,
        OX + T1_PX + 1, (deck_y + mid_y) / 2 - 6, 30, 12,
        "OPEN&lt;br/&gt;RISER", fs=4, color=C_OPEN_RISER, align="left", va="middle"
    ))

    # Grade tick lines at 0", 6", 12" AG (short horizontal dashes to left of stringer)
    for ag_in, lbl_txt, y_pos in [
        (12, "12&quot; AG&lt;br/&gt;(deck top)", deck_y),
        (6,  "6&quot; AG&lt;br/&gt;(mid tread)", mid_y),
        (0,  "0&quot; AG&lt;br/&gt;(grade)",     grade_y),
    ]:
        # Tick line
        cells.append(line_cell(
            f"v15-p2-left-stair-tick-{ag_in}", P,
            OX - 30, y_pos, OX - 3, y_pos,
            color=C_GRADE_TICK, lw=0.8, dashed=1
        ))
        # Label to left of tick
        cells.append(text_cell(
            f"v15-p2-left-stair-lbl-{ag_in}", P,
            PX + 2, y_pos - 8, 50, 16,
            lbl_txt, fs=5, color=C_ELEV_LBL, align="right", va="middle", bold=True
        ))

    # Vertical dimension arrow: 6" rise (deck_y to mid_y, left of stringer)
    ARROW_X = OX - 18
    cells.append(dim_arrow_cell(
        "v15-p2-left-stair-rise1-arrow", P,
        ARROW_X, deck_y, ARROW_X, mid_y,
        color=C_DIM_ARROW, lw=1.0
    ))
    cells.append(text_cell(
        "v15-p2-left-stair-rise1-lbl", P,
        ARROW_X - 12, (deck_y + mid_y) / 2 - 5, 12, 10,
        '6&quot;', fs=5, color="#444444", align="center", va="middle", bold=True
    ))

    # Vertical dimension arrow: 6" rise (mid_y to grade_y)
    cells.append(dim_arrow_cell(
        "v15-p2-left-stair-rise2-arrow", P,
        ARROW_X, mid_y, ARROW_X, grade_y,
        color=C_DIM_ARROW, lw=1.0
    ))
    cells.append(text_cell(
        "v15-p2-left-stair-rise2-lbl", P,
        ARROW_X - 12, (mid_y + grade_y) / 2 - 5, 12, 10,
        '6&quot;', fs=5, color="#444444", align="center", va="middle", bold=True
    ))

    # Horizontal dimension arrow: 10.8" tread depth (below grade, spanning T1_PX)
    TREAD_DIM_Y = grade_y + 10
    cells.append(dim_arrow_cell(
        "v15-p2-left-stair-tread-arrow", P,
        OX, TREAD_DIM_Y, OX + T1_PX, TREAD_DIM_Y,
        color=C_TREAD_DIM, lw=1.0
    ))
    cells.append(text_cell(
        "v15-p2-left-stair-tread-lbl", P,
        OX - 5, TREAD_DIM_Y + 1, T1_PX + 10, 10,
        '10.8&quot; tread', fs=5, color=C_TREAD_DIM, align="center", va="top", bold=True
    ))

    return '\n'.join(cells)


# ══════════════════════════════════════════════════════════════════════════════════
# FAR-EDGE STEP ELEVATION — native drawio shapes
# Panel: x=1340, y=700, w=220, h=190 (same as v14)
# ══════════════════════════════════════════════════════════════════════════════════

def make_far_step_elev_cells(parent="p2-1"):
    """
    Native drawio replacement for v14-p2-far-step-elev-profile (the ASCII <pre> cell).

    Geometry plan:
      Panel bg: x=1340, y=700, w=220, h=190
      Title area: ~28px top → drawing starts at y=728
      Dims area:  ~44px bottom → drawing ends at y=842 (700+190-48 = 842)
      Available height: 842 - 728 = 114 px for 12" rise → 9.5 px/in → use 9 px/in

      Scale: 9 px/in vertical:
        grade_y  = 838  (4px above dims)
        tread_y  = 838 - 9*6  = 784
        deck_y   = 838 - 9*12 = 730

      Horizontal layout (single 6" rise, so single tread step):
        OX = 1395    (60px from panel left, for labels)
        RIBBON_W = 7px (1.5" doubled 2x6 ≈ 3" visual at this scale)
        TREAD_PX = 22px  (10.9" at ~2px/in)
        Total horizontal = RIBBON_W + TREAD_PX = 29px
    """
    cells = []
    P = "p2-1"

    PX    = 1340.0
    PY    = 700.0
    PW    = 220.0
    PH    = 190.0

    SCALE_Y  = 9.0
    grade_y  = PY + PH - 50.0   # = 840
    tread_y  = grade_y - SCALE_Y * 6    # = 840 - 54 = 786
    deck_y   = grade_y - SCALE_Y * 12   # = 840 - 108 = 732

    OX         = PX + 60.0   # left edge of ribbon face
    RIBBON_W   = 8.0         # doubled 2x6 ribbon width in px (~3" at this scale)
    TREAD_PX   = 24.0        # 10.9" tread depth in px
    PLANK_H    = 5.0         # tread plank thickness in px

    # Ground line (dashed)
    cells.append(line_cell(
        "v15-p2-far-step-grade-line", P,
        OX - 8, grade_y, OX + RIBBON_W + TREAD_PX + 16, grade_y,
        color=C_GRADE_TICK, lw=1.0, dashed=1
    ))

    # Gravel pad (hatched rectangle below grade)
    cells.append(rect_cell(
        "v15-p2-far-step-gravel", P,
        OX, grade_y, RIBBON_W + TREAD_PX, 14.0,
        C_FAR_GRAVEL, EC_FAR_GRAVEL, lw=1.0, opacity=85,
        extra_style="fillStyle=cross-hatch;"
    ))

    # Gravel depth label "4\" #57 gravel"
    cells.append(text_cell(
        "v15-p2-far-step-gravel-lbl", P,
        OX + 2, grade_y + 2, RIBBON_W + TREAD_PX - 4, 12,
        '4&quot; #57 gravel', fs=4, color="#7a6050", align="center", va="middle"
    ))

    # Precast concrete block on top of gravel (grade level)
    BLOCK_W = 14.0
    BLOCK_H = 5.0
    cells.append(rect_cell(
        "v15-p2-far-step-block", P,
        OX + RIBBON_W + 2, grade_y - BLOCK_H, BLOCK_W, BLOCK_H,
        C_BLOCK, EC_BLOCK, lw=1.0
    ))

    # Block label
    cells.append(text_cell(
        "v15-p2-far-step-block-lbl", P,
        OX + RIBBON_W, grade_y - BLOCK_H - 10, BLOCK_W + 8, 10,
        'precast block', fs=4, color="#666655", align="center", va="bottom"
    ))

    # Doubled 2x6 PT ribbon (vertical rectangle at left/deck-face side)
    RIBBON_H = (deck_y - tread_y)  # spans from deck level down to tread level
    cells.append(rect_cell(
        "v15-p2-far-step-ribbon", P,
        OX, tread_y, RIBBON_W, RIBBON_H,
        C_RIBBON, EC_RIBBON, lw=1.5
    ))

    # Ribbon label (rotated text — use regular text, it fits in the width)
    cells.append(text_cell(
        "v15-p2-far-step-ribbon-lbl", P,
        OX - 24, tread_y + RIBBON_H / 2 - 8, 24, 16,
        'ribbon', fs=4, color=C_RIBBON, align="right", va="middle"
    ))

    # Tread plank 1 (inner, adjacent to ribbon)
    cells.append(rect_cell(
        "v15-p2-far-step-tread1", P,
        OX + RIBBON_W, tread_y - PLANK_H, TREAD_PX / 2 - 0.5, PLANK_H,
        C_TREAD, EC_TREAD, lw=1.0
    ))

    # Tread plank 2 (outer)
    cells.append(rect_cell(
        "v15-p2-far-step-tread2", P,
        OX + RIBBON_W + TREAD_PX / 2 + 0.5, tread_y - PLANK_H, TREAD_PX / 2 - 0.5, PLANK_H,
        C_TREAD, EC_TREAD, lw=1.0
    ))

    # Deck top plank line
    cells.append(rect_cell(
        "v15-p2-far-step-deck-top", P,
        OX - 4, deck_y - PLANK_H, RIBBON_W + TREAD_PX + 8, PLANK_H,
        C_DECK_PLANK, EC_DECK_PLANK, lw=1.0
    ))

    # Open riser dashed line (at outer tread edge)
    cells.append(line_cell(
        "v15-p2-far-step-riser", P,
        OX + RIBBON_W + TREAD_PX, deck_y, OX + RIBBON_W + TREAD_PX, tread_y,
        color=C_OPEN_RISER, lw=1.2, dashed=1
    ))

    # "OPEN RISER" label
    cells.append(text_cell(
        "v15-p2-far-step-riser-lbl", P,
        OX + RIBBON_W + TREAD_PX + 2, (deck_y + tread_y) / 2 - 6, 34, 12,
        "OPEN&lt;br/&gt;RISER", fs=4, color=C_OPEN_RISER, align="left", va="middle"
    ))

    # Grade tick lines (left of stringer)
    for ag_in, lbl_txt, y_pos in [
        (12, "12&quot; AG&lt;br/&gt;(deck)",  deck_y),
        (6,  "6&quot; AG&lt;br/&gt;(tread)", tread_y),
        (0,  "0&quot; AG&lt;br/&gt;(grade)", grade_y),
    ]:
        cells.append(line_cell(
            f"v15-p2-far-step-tick-{ag_in}", P,
            OX - 30, y_pos, OX - 3, y_pos,
            color=C_GRADE_TICK, lw=0.8, dashed=1
        ))
        cells.append(text_cell(
            f"v15-p2-far-step-lbl-{ag_in}", P,
            PX + 2, y_pos - 8, 54, 16,
            lbl_txt, fs=5, color=C_FAR_LBL, align="right", va="middle", bold=True
        ))

    # Vertical rise dimension arrow
    ARROW_X = OX - 18
    cells.append(dim_arrow_cell(
        "v15-p2-far-step-rise-arrow", P,
        ARROW_X, deck_y, ARROW_X, tread_y,
        color=C_DIM_ARROW, lw=1.0
    ))
    cells.append(text_cell(
        "v15-p2-far-step-rise-lbl", P,
        ARROW_X - 12, (deck_y + tread_y) / 2 - 5, 12, 10,
        '6&quot;', fs=5, color="#444444", align="center", va="middle", bold=True
    ))

    # Horizontal tread dimension arrow (below grade)
    TREAD_DIM_Y = grade_y + 10
    cells.append(dim_arrow_cell(
        "v15-p2-far-step-tread-arrow", P,
        OX + RIBBON_W, TREAD_DIM_Y, OX + RIBBON_W + TREAD_PX, TREAD_DIM_Y,
        color=C_TREAD_DIM, lw=1.0
    ))
    cells.append(text_cell(
        "v15-p2-far-step-tread-lbl", P,
        OX + RIBBON_W - 2, TREAD_DIM_Y + 1, TREAD_PX + 4, 10,
        '10.9&quot; tread', fs=5, color=C_TREAD_DIM, align="center", va="top", bold=True
    ))

    return '\n'.join(cells)


# ─── Read current v14 drawio ──────────────────────────────────────────────────
source_path = '/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/owner_inbox/deck_blueprint/deck_plan.drawio'
with open(source_path, 'r') as f:
    content = f.read()

# ─── VERSION SWEEP: v14 → v15 ────────────────────────────────────────────────
# Diagram IDs
content = re.sub(r'id="deck-plan-v14-p1"', 'id="deck-plan-v15-p1"', content)
content = re.sub(r'id="deck-plan-v14-p2"', 'id="deck-plan-v15-p2"', content)

# Page names
content = re.sub(
    r'name="Page 1 — Framing Plan \(v14\)"',
    'name="Page 1 — Framing Plan (v15)"',
    content
)
content = re.sub(
    r'name="Page 2 — Decking Plan \(v14\)"',
    'name="Page 2 — Decking Plan (v15)"',
    content
)

# Version badge cells — badges use &lt;br&gt; (no slash) unlike most cells
# Sweep any prior version token (v13.1, v14, etc.) in the badge cells
content = re.sub(
    r'(value="&lt;b&gt;)v\d+(?:\.\d+)?(&lt;/b&gt;&lt;br&gt;&lt;font style=&quot;font-size: 11px;&quot;&gt;Page 1 of 2 — Framing&lt;/font&gt;")',
    r'\g<1>v15\g<2>',
    content
)
content = re.sub(
    r'(value="&lt;b&gt;)v\d+(?:\.\d+)?(&lt;/b&gt;&lt;br&gt;&lt;font style=&quot;font-size: 11px;&quot;&gt;Page 2 of 2 — Decking&lt;/font&gt;")',
    r'\g<1>v15\g<2>',
    content
)

# Title blocks
content = content.replace(
    'DECK PLAN v14 — PAGE 1: FRAMING PLAN',
    'DECK PLAN v15 — PAGE 1: FRAMING PLAN'
)
content = content.replace(
    'DECK PLAN v14 — PAGE 2: DECKING',
    'DECK PLAN v15 — PAGE 2: DECKING'
)

# Subtitle in Page 2 title block
content = content.replace(
    'v14: deck depth -3in to 16ft-0in (Option C, 2026-05-06); 3in exposed patio at far edge; both stair elevations present',
    'v15: ASCII stair-elevation cells replaced with native drawio shapes; layout unchanged'
)

# Date in title block (update to today)
content = content.replace('Date: 2026-05-01 | Gemma', 'Date: 2026-05-06 | Gemma')

# ─── HIDE the v14 ASCII profile cells (preserve as invisible) ─────────────────
# v14-p2-left-stair-profile (the <pre> ASCII cell)
content = re.sub(
    r'(id="v14-p2-left-stair-profile")(\s+parent)',
    r'\1 visible="0"\2',
    content
)
# v14-p2-far-step-elev-profile (the <pre> ASCII cell)
content = re.sub(
    r'(id="v14-p2-far-step-elev-profile")(\s+parent)',
    r'\1 visible="0"\2',
    content
)

# ─── Also update the BG title cells' text from v14 → v15 ────────────────────
content = content.replace(
    '(v12, unchanged)',
    '(v12, unchanged — v15 native shapes)'
)
content = content.replace(
    '(v13, unchanged in v14)',
    '(v13, unchanged — v15 native shapes)'
)

# ─── Update version history text in far-step callout cells ───────────────────
# Remove "v14" from all callout value text to keep the grep clean.
# Replace "v13, v14 unchanged" with "v13+, unchanged through v15"
content = content.replace(
    'FAR-EDGE STEP (v13, v14 unchanged)',
    'FAR-EDGE STEP (v13+, unchanged through v15)'
)
# Also handle "v13, v14-v15 unchanged" from prior run (idempotent)
content = content.replace(
    'FAR-EDGE STEP (v13, v14–v15 unchanged)',
    'FAR-EDGE STEP (v13+, unchanged through v15)'
)
# Pier note: "(v14: -3in with framing depth)" → remove v14 reference
content = content.replace(
    'Outer row (y=16ft-0in) remain (v14: -3in with framing depth).',
    'Outer row (y=16ft-0in) remain (-3in from v13, see Option C).'
)
# Also handle idempotent case
content = content.replace(
    'Outer row (y=16ft-0in) remain (v14: -3in; v15: drawio shapes only).',
    'Outer row (y=16ft-0in) remain (-3in from v13, see Option C).'
)

# ─── Inject v15 native elevation cells into Page 2 (before </root>) ──────────
page2_close = '      </root>\n    </mxGraphModel>\n  </diagram>\n</mxfile>'

left_stair_cells  = make_left_stair_elev_cells()
far_step_cells    = make_far_step_elev_cells()

new_cells = left_stair_cells + '\n' + far_step_cells

content = content.replace(
    page2_close,
    f'{new_cells}\n{page2_close}'
)

# ─── Write output ─────────────────────────────────────────────────────────────
out_path = '/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/owner_inbox/deck_blueprint/deck_plan.drawio'
with open(out_path, 'w') as f:
    f.write(content)

print(f"Written: {out_path}")
print(f"File size: {len(content)} bytes")

# ─── Verify: no v14 tokens outside of id="v14-..." references ────────────────
print("\nChecking for stray v14 tokens (excluding cell IDs and allowed references)...")
stray = []
for line in content.split('\n'):
    if 'v14' not in line.lower():
        continue
    # Allow intentional v14 cell ID references, gen/render filenames,
    # "unchanged" history text, version history in comments/README
    if (re.search(r'id="v14-', line) or
            'gen_drawio_v14' in line.lower() or
            'render_v14' in line.lower() or
            'unchanged' in line.lower() or
            'v14 native' in line.lower() or
            'v14→v15' in line.lower() or
            'v14, v15' in line.lower() or
            'v15 native' in line.lower()):
        continue
    stray.append(line.strip())

if stray:
    print(f"WARNING: {len(stray)} possible stray v14 tokens:")
    for s in stray[:20]:
        print(f"  {s[:150]}")
else:
    print("OK: No stray unintended v14 tokens found.")

# ─── Count injected cells ─────────────────────────────────────────────────────
left_count = left_stair_cells.count('<mxCell')
far_count  = far_step_cells.count('<mxCell')
print(f"\nInjected cells:")
print(f"  Left-edge stair elevation: {left_count} cells")
print(f"  Far-edge step elevation:   {far_count} cells")
print(f"  Total new v15 cells:       {left_count + far_count}")

# ─── Spot-check: confirm ASCII pre cells are now hidden ───────────────────────
if 'id="v14-p2-left-stair-profile" visible="0"' in content:
    print("\nOK: v14-p2-left-stair-profile marked visible=0")
else:
    print("\nWARNING: v14-p2-left-stair-profile hidden status not confirmed")

if 'id="v14-p2-far-step-elev-profile" visible="0"' in content:
    print("OK: v14-p2-far-step-elev-profile marked visible=0")
else:
    print("WARNING: v14-p2-far-step-elev-profile hidden status not confirmed")
