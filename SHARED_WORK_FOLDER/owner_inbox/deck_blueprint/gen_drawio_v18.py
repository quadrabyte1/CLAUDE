"""
gen_drawio_v18.py — Generates deck_plan_v18.drawio for the West Hartford deck.

Built from gen_drawio_v17.py. Foundation/pier layout updated to 5 piers per line.

v18 changes vs. v17:
  - 10 piers total (was 8): 5 per girder line at x=0, 5'-9", 11'-6", 17'-3", 23'-0"
    (spacing = 5'-9" instead of 7'-8")
  - Girder splice recipe updated:
    - Ply 1: 11'-6" + 11'-6", butt joint over center pier at x=11'-6"
    - Ply 2: 5'-9" + 11'-6" + 5'-9", joints over piers at x=5'-9" and x=17'-3"
  - Center pier (x=11'-6") aligns with center joist and breaker board x-coordinate
  - 10 Pylex 50 piers (5 per girder line at x=0, 5'-9", 11'-6", 17'-3", 23'-0")

Coordinate system (drawio pixels):
  Scale: 40 px/ft
  Origin (x=0 ft, y=0 ft):  x_px=220, y_px=180
  So drawio_x = 220 + ft_x * 40
     drawio_y = 180 + ft_y * 40

Page: single-page plan view at A2 landscape (1654×1169 px)

Layers (in order, each toggleable):
  L00 — Default (reserved, parent=1)
  L01 — Patio Outline
  L02 — Foundation / Piers
  L03 — Girders
  L04 — Ledger
  L05 — Joists Regular
  L06 — Joists Center (v17 NEW)
  L07 — Joist Hangers
  L08 — Blocking
  L09 — Decking Left Half
  L10 — Decking Right Half
  L11 — Center Divider Breaker (v17 NEW)
  L12 — Picture Frame
  L13 — Fascia
  L14 — Stairs / Steps
  L15 — Dimensions
  L16 — Callouts
  L17 — Version Badge
  L18 — Title Block
"""

# ─── Scale + origin ───────────────────────────────────────────────────────────
PX_PER_FT = 40.0
OX = 220.0      # drawio x-pixel for x=0 ft (left rim face)
OY = 180.0      # drawio y-pixel for y=0 ft (ledger / house wall)

def px(ft_x):
    """Convert framing x-coordinate (ft) to drawio x-pixel."""
    return OX + ft_x * PX_PER_FT

def py(ft_y):
    """Convert framing y-coordinate (ft) to drawio y-pixel."""
    return OY + ft_y * PX_PER_FT

def fw(ft_w):
    """Convert a width in feet to pixels."""
    return ft_w * PX_PER_FT

# ─── Key geometry (mirrors render_v17.py) ────────────────────────────────────
FRAME_W       = 23.0           # framing width, ft
FRAME_D       = 16.0           # framing depth, ft
PF_W_FT       = 5.4 / 12      # PF board face width, ft (0.45 ft)
FASCIA_T_FT   = 0.67 / 12     # fascia thickness, ft
PF_OVR_FT     = 3.0 / 12      # PF overhang past rim outer face, ft (0.25 ft)
OVERALL_W_FT  = FRAME_W + 2 * PF_OVR_FT   # 23.5 ft
OVERALL_D_FT  = FRAME_D + PF_OVR_FT       # 16.25 ft
PATIO_D_FT    = 16.5

GIRDER_MID_Y_FT  = 8.0        # mid-girder y, ft
GIRDER_RIM_Y_FT  = FRAME_D    # outer-rim girder y, ft
GIRDER_T_FT      = 0.27       # doubled 2×10 visual thickness, ft
GHT_FT           = GIRDER_T_FT / 2

# 5 piers per girder line: 0', 5'-9", 11'-6", 17'-3", 23'-0"
PIER_SPACING_FT = FRAME_W / 4   # 5.75 ft = 5'-9"
PIER_X_FT = [0.0, PIER_SPACING_FT, 2 * PIER_SPACING_FT, 3 * PIER_SPACING_FT, FRAME_W]
PIER_Y_FT = [GIRDER_MID_Y_FT, GIRDER_RIM_Y_FT]
PIER_R_FT    = 0.22
HOLE_R_FT    = 0.35

# 24 regular joists + 1 center joist
JOIST_SPACING_FT = 1.0
JOIST_X_FT = [i * JOIST_SPACING_FT for i in range(24)]  # x=0..23
JOIST_W_FT  = 0.085   # visual width

CENTER_JOIST_X_FT = 11.5   # framing centerline

# Breaker board (center divider)
BREAKER_CL_FT  = CENTER_JOIST_X_FT
BREAKER_X0_FT  = BREAKER_CL_FT - PF_W_FT / 2
BREAKER_X1_FT  = BREAKER_CL_FT + PF_W_FT / 2

# Decking
PLANK_W_FT   = 5.4 / 12
PLANK_GAP_FT = (1.0 / 8) / 12
PLANK_STEP_FT = PLANK_W_FT + PLANK_GAP_FT
PF_INBOARD_FT = 2.4 / 12
FIELD_Y0_FT   = PF_INBOARD_FT
FIELD_Y1_FT   = FRAME_D + PF_OVR_FT - PF_W_FT
FIELD_X0_FT   = PF_INBOARD_FT
FIELD_X1_FT   = FRAME_W - PF_INBOARD_FT
FIELD_DEPTH_FT = FIELD_Y1_FT - FIELD_Y0_FT

import math
NUM_PLANKS = int(math.floor(FIELD_DEPTH_FT / PLANK_STEP_FT))

# Sub-fascia / drop board
DROP_T_FT    = 0.085
far_drop_y_ft = GIRDER_RIM_Y_FT + JOIST_W_FT / 2
fas_y_ft      = far_drop_y_ft + DROP_T_FT
fas_y_end_ft  = fas_y_ft + FASCIA_T_FT

# Left-edge stair
STEP_Y0_FT = 6.0
STEP_Y1_FT = 9.5
LEFT_DECK_X_FT = -PF_OVR_FT - FASCIA_T_FT
STEP_DEPTH_FT  = 16.0 / 12
STEP_X_OUT_FT  = LEFT_DECK_X_FT - STEP_DEPTH_FT
STRINGER_Y_FT  = [STEP_Y0_FT, (STEP_Y0_FT + STEP_Y1_FT) / 2, STEP_Y1_FT]
STRINGER_W_FT  = 2.0 / 12
TREAD_DEPTH_FT = 10.8 / 12
MTREAD_X0_FT   = LEFT_DECK_X_FT - TREAD_DEPTH_FT
GRAVEL_W_FT    = 48.0 / 12
GRAVEL_D_FT    = 18.0 / 12
GRAVEL_Y0_FT   = STEP_Y0_FT - (GRAVEL_W_FT - (STEP_Y1_FT - STEP_Y0_FT)) / 2
GRAVEL_Y1_FT   = GRAVEL_Y0_FT + GRAVEL_W_FT
GRAVEL_X0_FT   = LEFT_DECK_X_FT - GRAVEL_D_FT

# Far-edge step
FAR_STEP_X_RIGHT_FT = OVERALL_W_FT - PF_OVR_FT
FAR_STEP_X_LEFT_FT  = (-PF_OVR_FT + OVERALL_W_FT - PF_OVR_FT) / 2
FAR_TREAD_DEPTH_FT  = (5.4 + 5.4 + 0.125) / 12
FAR_BLOCK_ABS_FT    = [23.0, 20.167, 17.333, 14.5, 11.75]
FAR_BLOCK_X_FT      = [a - PF_OVR_FT for a in FAR_BLOCK_ABS_FT]
FAR_BLOCK_SZ_FT     = 1.0
RIBBON_T_FT         = 2 * (1.5 / 12)   # doubled 2×6 = 3" actual

# ─── Colors ───────────────────────────────────────────────────────────────────
C_PATIO      = "#e8e0d4";  EC_PATIO    = "#a09080"
C_HOUSE      = "#cccccc"
C_LEDGER     = "#f8cecc";  EC_LEDGER   = "#b85450"
C_GIRDER     = "#dae8fc";  EC_GIRDER   = "#6c8ebf"
C_JOIST      = "#d5e8d4";  EC_JOIST    = "#82b366"
C_RIM        = "#fff2cc";  EC_RIM      = "#d6b656"
C_FASCIA     = "#c8a0e8";  EC_FASCIA   = "#7030a0"
C_PIER       = "#5a4030";  EC_PIER     = "#2a1808"
C_PIER_HOLE  = "#b0a898";  EC_HOLE     = "#706050"
C_DROP       = "#c0d8b0";  EC_DROP     = "#507040"
C_HANGER     = "#cc4400";  EC_HANGER   = "#882200"
C_FIELD      = "#b89a68";  EC_FIELD    = "#6a4a2a"
C_PF_TREX    = "#8a6a3a";  EC_PF_TREX  = "#4a2a0a"
C_STRINGER   = "#6a8a5a";  EC_STRINGER = "#2a5a1a"
C_TREAD      = "#c8a878";  EC_TREAD    = "#7a5030"
C_GRAVEL     = "#d0c8b8";  EC_GRAVEL   = "#8a7a68"
C_PAVER      = "#9a9a9a";  EC_PAVER    = "#444444"
C_FAR_RIBBON = "#5a8a5a";  EC_FAR_RIBBON = "#2a5a2a"
C_FAR_TREAD  = "#c8a878";  EC_FAR_TREAD  = "#7a5030"
C_FAR_BLOCK  = "#9a9a9a";  EC_FAR_BLOCK  = "#444444"
C_FAR_GRAVEL = "#d0c8b8";  EC_FAR_GRAVEL = "#8a7a68"
C_CUTJOINT   = "#cc2200"
C_CENTER_JOIST  = "#e08030";  EC_CENTER_JOIST = "#804010"
C_BREAKER       = C_PF_TREX;  EC_BREAKER      = EC_PF_TREX
C_BLOCKING   = "#c8d8c0";  EC_BLOCKING  = "#608060"
C_NOTE       = "#ffffee";  EC_NOTE      = "#888800"
C_CALLOUT    = "#fff9e6";  EC_CALLOUT   = "#cc8800"
C_DIM_LINE   = "#000099"
C_DIM_ALT    = "#333388"


# ─── Cell ID counter ──────────────────────────────────────────────────────────
_cid = [1]

def next_id(tag="c"):
    _cid[0] += 1
    return f"v18-{tag}-{_cid[0]:04d}"


# ─── XML helpers ──────────────────────────────────────────────────────────────

def layer_cell(lid, name):
    if lid == "0":
        return '        <mxCell id="0" />'
    return f'        <mxCell id="{lid}" parent="0" value="{name}" />'


def rect_cell(cid, parent, x, y, w, h, fc, ec, lw=1.0, value="",
              extra_style="", dashed=0, opacity=100, fontsize=7,
              font_color="#333333", font_bold=False):
    """Emit a filled rectangle mxCell."""
    ds = f"dashed=1;dashPattern=8 4;" if dashed else "dashed=0;"
    bold_s = "fontStyle=1;" if font_bold else ""
    return (
        f'        <mxCell id="{cid}" parent="{parent}" '
        f'style="rounded=0;whiteSpace=wrap;html=1;fillColor={fc};strokeColor={ec};'
        f'strokeWidth={lw:.1f};opacity={opacity};{ds}{extra_style}'
        f'fontColor={font_color};fontSize={fontsize};{bold_s}" '
        f'value="{value}" vertex="1">\n'
        f'          <mxGeometry x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" as="geometry" />\n'
        f'        </mxCell>'
    )


def ellipse_cell(cid, parent, cx, cy, r, fc, ec, lw=1.5, value="", opacity=100):
    """Emit an ellipse mxCell, centered at (cx,cy) with radius r."""
    return (
        f'        <mxCell id="{cid}" parent="{parent}" '
        f'style="ellipse;whiteSpace=wrap;html=1;fillColor={fc};strokeColor={ec};'
        f'strokeWidth={lw:.1f};opacity={opacity};" '
        f'value="{value}" vertex="1">\n'
        f'          <mxGeometry x="{cx-r:.1f}" y="{cy-r:.1f}" width="{2*r:.1f}" height="{2*r:.1f}" as="geometry" />\n'
        f'        </mxCell>'
    )


def text_cell(cid, parent, x, y, w, h, value, fs=7, color="#333333",
              align="center", va="middle", bold=False, italic=False):
    fs_s = ""
    if bold and italic:
        fs_s = "fontStyle=3;"
    elif bold:
        fs_s = "fontStyle=1;"
    elif italic:
        fs_s = "fontStyle=2;"
    return (
        f'        <mxCell id="{cid}" parent="{parent}" '
        f'style="text;html=1;strokeColor=none;fillColor=none;'
        f'align={align};verticalAlign={va};whiteSpace=wrap;overflow=hidden;'
        f'fontSize={fs};fontColor={color};{fs_s}" '
        f'value="{value}" vertex="1">\n'
        f'          <mxGeometry x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" as="geometry" />\n'
        f'        </mxCell>'
    )


def line_cell(cid, parent, x1, y1, x2, y2, color="#444444", lw=1.0, dashed=0,
              end_arrow="none", start_arrow="none"):
    ds = "dashed=1;dashPattern=8 4;" if dashed else "dashed=0;"
    return (
        f'        <mxCell id="{cid}" parent="{parent}" '
        f'style="endArrow={end_arrow};startArrow={start_arrow};html=1;'
        f'strokeColor={color};strokeWidth={lw:.1f};{ds}" '
        f'edge="1" value="">\n'
        f'          <mxGeometry relative="1" as="geometry">\n'
        f'            <mxPoint x="{x1:.1f}" y="{y1:.1f}" as="sourcePoint" />\n'
        f'            <mxPoint x="{x2:.1f}" y="{y2:.1f}" as="targetPoint" />\n'
        f'          </mxGeometry>\n'
        f'        </mxCell>'
    )


def dim_arrow(cid, parent, x1, y1, x2, y2, color=C_DIM_LINE, lw=1.2):
    """Double-ended dimension arrow."""
    return (
        f'        <mxCell id="{cid}" parent="{parent}" '
        f'style="endArrow=classic;startArrow=classic;html=1;'
        f'strokeColor={color};strokeWidth={lw:.1f};fillColor={color};'
        f'endFill=1;startFill=1;" '
        f'edge="1" value="">\n'
        f'          <mxGeometry relative="1" as="geometry">\n'
        f'            <mxPoint x="{x1:.1f}" y="{y1:.1f}" as="sourcePoint" />\n'
        f'            <mxPoint x="{x2:.1f}" y="{y2:.1f}" as="targetPoint" />\n'
        f'          </mxGeometry>\n'
        f'        </mxCell>'
    )


# ─── Layer IDs ────────────────────────────────────────────────────────────────
LID_DEFAULT  = "1"          # reserved, parent="0", always exists
LID_PATIO    = "L01-patio"
LID_PIERS    = "L02-piers"
LID_GIRDERS  = "L03-girders"
LID_LEDGER   = "L04-ledger"
LID_JOISTS   = "L05-joists"
LID_CJ       = "L06-center-joist"
LID_HANGERS  = "L07-hangers"
LID_BLOCKING = "L08-blocking"
LID_DECK_L   = "L09-deck-left"
LID_DECK_R   = "L10-deck-right"
LID_BREAKER  = "L11-breaker"
LID_PF       = "L12-picture-frame"
LID_FASCIA   = "L13-fascia"
LID_STAIRS   = "L14-stairs"
LID_DIMS     = "L15-dims"
LID_CALLOUTS = "L16-callouts"
LID_BADGE    = "L17-badge"
LID_TITLE    = "L18-title"


# ══════════════════════════════════════════════════════════════════════════════
# Layer content generators
# ══════════════════════════════════════════════════════════════════════════════

def make_patio_layer():
    cells = []
    L = LID_PATIO

    # Full patio footprint (background)
    cells.append(rect_cell(
        next_id("patio"), L,
        px(-PF_OVR_FT), py(0.0),
        fw(OVERALL_W_FT), fw(PATIO_D_FT),
        C_PATIO, EC_PATIO, lw=2.5, opacity=40,
        value="EXISTING CONCRETE PATIO  23&#39;-6&quot; × 16&#39;-6&quot;"
    ))

    # Exposed 3" strip at far edge (deck stops at 16'-3", patio at 16'-6")
    exposed_h_ft = PATIO_D_FT - OVERALL_D_FT
    cells.append(rect_cell(
        next_id("patio-exposed"), L,
        px(-PF_OVR_FT), py(OVERALL_D_FT),
        fw(OVERALL_W_FT), fw(exposed_h_ft),
        "#d0c4b0", "#7a6a58", lw=2.5, opacity=85,
        value="3&quot; EXPOSED PATIO STRIP (deck does not extend to patio edge)"
    ))

    # House wall
    cells.append(rect_cell(
        next_id("house"), L,
        px(-PF_OVR_FT), py(-1.2),
        fw(OVERALL_W_FT), fw(1.1),
        C_HOUSE, "#444444", lw=2.0, opacity=80,
        value="&lt;b&gt;HOUSE WALL  ▲ NORTH  (23&#39;-6&quot; overall edge)&lt;/b&gt;",
        fontsize=11, font_bold=True, font_color="#222222"
    ))

    return '\n'.join(cells)


def make_piers_layer():
    cells = []
    L = LID_PIERS
    pier_r_px   = fw(PIER_R_FT)
    hole_r_px   = fw(HOLE_R_FT)

    labels = {
        (0, 0): "A1", (1, 0): "A2", (2, 0): "A3", (3, 0): "A4", (4, 0): "A5",
        (0, 1): "B1", (1, 1): "B2", (2, 1): "B3", (3, 1): "B4", (4, 1): "B5",
    }

    for yi, pyr in enumerate(PIER_Y_FT):
        for xi, pxr in enumerate(PIER_X_FT):
            cx = px(pxr)
            cy = py(pyr)
            lbl = labels[(xi, yi)]

            # Hole outline (light circle behind pier)
            cells.append(ellipse_cell(
                next_id("hole"), L,
                cx, cy, hole_r_px,
                C_PIER_HOLE, EC_HOLE, lw=1.0, opacity=50
            ))
            # Pier body
            cells.append(ellipse_cell(
                next_id("pier"), L,
                cx, cy, pier_r_px,
                C_PIER, EC_PIER, lw=1.5,
                value=f"&lt;b&gt;{lbl}&lt;/b&gt;",
                opacity=90
            ))
            # Label below pier
            cells.append(text_cell(
                next_id("pier-lbl"), L,
                cx - 28, cy + pier_r_px + 2, 56, 12,
                f"Pylex 50  {pxr:.2f}&#39;, {pyr:.0f}&#39;",
                fs=6, color="#5a3010", align="center"
            ))

    # Pier spacing label
    for i in range(len(PIER_X_FT) - 1):
        x0 = px(PIER_X_FT[i])
        x1 = px(PIER_X_FT[i + 1])
        ann_y = py(GIRDER_MID_Y_FT) - fw(GHT_FT) - 22
        cells.append(dim_arrow(
            next_id("pier-span-arr"), L,
            x0, ann_y, x1, ann_y,
            color=C_DIM_ALT, lw=1.0
        ))
        cells.append(text_cell(
            next_id("pier-span-lbl"), L,
            (x0 + x1) / 2 - 25, ann_y - 14, 50, 12,
            "5&#39;-9&quot; (typ.)", fs=7, bold=True, color=C_DIM_ALT
        ))

    # Saddle callout
    callout_x = px(PIER_X_FT[1]) - fw(2.0)
    callout_y = py(GIRDER_MID_Y_FT) - fw(2.5)
    cells.append(rect_cell(
        next_id("saddle-box"), L,
        callout_x, callout_y, 160, 56,
        "#fdf0e0", C_PIER, lw=1.5,
        value=(
            "&lt;b&gt;Pylex 50 helical pier&lt;/b&gt;&lt;br/&gt;"
            "Pylex 10555 saddle (3.5&quot; wide)&lt;br/&gt;"
            "Doubled 2×10 girder in saddle&lt;br/&gt;"
            "&lt;b&gt;10 piers total&lt;/b&gt;"
        ),
        fontsize=7, font_color=C_PIER
    ))

    return '\n'.join(cells)


def make_girders_layer():
    cells = []
    L = LID_GIRDERS

    for gy_ft in [GIRDER_MID_Y_FT, GIRDER_RIM_Y_FT]:
        y_top = py(gy_ft - GHT_FT)
        h     = fw(GIRDER_T_FT)
        x_left = px(0.0)
        w      = fw(FRAME_W)
        is_mid = (gy_ft == GIRDER_MID_Y_FT)
        lbl_name = "MID-GIRDER" if is_mid else "OUTER-RIM GIRDER"

        cells.append(rect_cell(
            next_id("girder"), L,
            x_left, y_top, w, h,
            C_GIRDER, EC_GIRDER, lw=2.5, opacity=80,
            value=f"&lt;b&gt;{lbl_name} — Doubled 2×10 PT SYP  |  y={gy_ft:.0f}&#39;-0&quot;  |  23&#39;-0&quot; long&lt;/b&gt;",
            fontsize=8, font_bold=True, font_color=EC_GIRDER
        ))

        # Splice marks v18:
        #   Ply 1: butt joint at x=11'-6" (center pier)
        #   Ply 2: joints at x=5'-9" and x=17'-3" (piers 2 and 4)
        for splice_x_ft, ply_label in [
            (PIER_X_FT[2], "Ply1"),   # x=11'-6", center pier
            (PIER_X_FT[1], "Ply2a"),  # x=5'-9", pier 2
            (PIER_X_FT[3], "Ply2b"),  # x=17'-3", pier 4
        ]:
            sx = px(splice_x_ft)
            # Subtle tick: short dashed line, thinner than v17
            cells.append(line_cell(
                next_id("splice"), L,
                sx, y_top, sx, y_top + h,
                color="#996633", lw=1.2, dashed=1
            ))
            cells.append(text_cell(
                next_id("splice-lbl"), L,
                sx - 18, y_top - 14, 36, 12,
                f"SPLICE ({ply_label})", fs=5, color="#996633", bold=True
            ))

    # Girder-to-girder dimension (y-direction, right side)
    dim_x = px(FRAME_W) + 30
    cells.append(dim_arrow(
        next_id("mid-girder-dim"), L,
        dim_x, py(0.0), dim_x, py(GIRDER_MID_Y_FT),
        color=EC_GIRDER, lw=1.2
    ))
    cells.append(text_cell(
        next_id("mid-girder-dim-lbl"), L,
        dim_x + 4, py(GIRDER_MID_Y_FT / 2) - 20, 80, 40,
        "8&#39;-0&quot;\nmid-girder\n(y from ledger)", fs=7, bold=True, color=EC_GIRDER
    ))

    cells.append(dim_arrow(
        next_id("rim-girder-dim"), L,
        dim_x, py(GIRDER_MID_Y_FT), dim_x, py(GIRDER_RIM_Y_FT),
        color=EC_GIRDER, lw=1.2
    ))
    cells.append(text_cell(
        next_id("rim-girder-dim-lbl"), L,
        dim_x + 4, py((GIRDER_MID_Y_FT + GIRDER_RIM_Y_FT) / 2) - 20, 80, 40,
        "8&#39;-0&quot;\nouter-rim\ngirder", fs=7, bold=True, color=EC_GIRDER
    ))

    return '\n'.join(cells)


def make_ledger_layer():
    cells = []
    L = LID_LEDGER
    LEDGER_H_FT = 0.18
    cells.append(rect_cell(
        next_id("ledger"), L,
        px(0.0), py(0.0), fw(FRAME_W), fw(LEDGER_H_FT),
        C_LEDGER, EC_LEDGER, lw=3.0, opacity=90,
        value=(
            "&lt;b&gt;LEDGER — SINGLE 2×10 PT UC4B  |  23&#39;-0&quot; long  |  "
            "½&quot; HDG lags @ 18&quot; o.c. staggered + through-bolts at girder connections  |  "
            "Peel-and-stick + Z-flashing  |  Flush top @ 11&quot; AG&lt;/b&gt;"
        ),
        fontsize=7, font_bold=True, font_color="#5a0000"
    ))
    return '\n'.join(cells)


def make_joists_regular_layer():
    cells = []
    L = LID_JOISTS
    LEDGER_H_FT = 0.18

    for i, jx_ft in enumerate(JOIST_X_FT):
        is_rim = (i == 0 or i == len(JOIST_X_FT) - 1)
        jw_ft  = JOIST_W_FT * 2 if is_rim else JOIST_W_FT
        fc     = C_RIM if is_rim else C_JOIST
        ec     = EC_RIM if is_rim else EC_JOIST
        lw_val = 2.0 if is_rim else 1.0
        x0     = px(jx_ft - jw_ft / 2)
        w_px   = fw(jw_ft)

        # Segment A: ledger to mid-girder top
        seg_a_y0 = py(LEDGER_H_FT)
        seg_a_h  = fw(GIRDER_MID_Y_FT - GHT_FT - LEDGER_H_FT)
        cells.append(rect_cell(
            next_id("joist-a"), L,
            x0, seg_a_y0, w_px, seg_a_h,
            fc, ec, lw=lw_val, opacity=70
        ))

        # Segment B: mid-girder far face to outer-rim top
        seg_b_y0 = py(GIRDER_MID_Y_FT + GHT_FT)
        seg_b_h  = fw(GIRDER_RIM_Y_FT - GHT_FT - (GIRDER_MID_Y_FT + GHT_FT))
        cells.append(rect_cell(
            next_id("joist-b"), L,
            x0, seg_b_y0, w_px, seg_b_h,
            fc, ec, lw=lw_val, opacity=70
        ))

    # Count label
    cells.append(text_cell(
        next_id("joist-count-lbl"), L,
        px(0.0), py(GIRDER_MID_Y_FT + GHT_FT) + 4, fw(FRAME_W), 18,
        "&lt;b&gt;24 JOISTS @ 12&quot; o.c. (y-dir, 2 segments each) + 1 CENTER JOIST @ x=11&#39;-6&quot; framing — 50 segments total&lt;/b&gt;",
        fs=7, bold=True, color="#226633", align="center"
    ))

    # Spacing arrow between first two joists
    j0 = px(JOIST_X_FT[0])
    j1 = px(JOIST_X_FT[1])
    ann_y = py(GIRDER_MID_Y_FT) + fw(GHT_FT) + 22
    cells.append(dim_arrow(
        next_id("joist-space-arr"), L,
        j0, ann_y, j1, ann_y,
        color="#226633", lw=1.0
    ))
    cells.append(text_cell(
        next_id("joist-space-lbl"), L,
        (j0 + j1) / 2 - 16, ann_y + 2, 32, 12,
        "12&quot; o.c.", fs=6, bold=True, color="#226633"
    ))

    return '\n'.join(cells)


def make_center_joist_layer():
    cells = []
    L = LID_CJ
    LEDGER_H_FT = 0.18
    cj_x0 = px(CENTER_JOIST_X_FT - JOIST_W_FT / 2)
    cj_w  = fw(JOIST_W_FT)

    # Segment A
    cells.append(rect_cell(
        next_id("cj-a"), L,
        cj_x0, py(LEDGER_H_FT),
        cj_w, fw(GIRDER_MID_Y_FT - GHT_FT - LEDGER_H_FT),
        C_CENTER_JOIST, EC_CENTER_JOIST, lw=2.5, opacity=90
    ))
    # Segment B
    cells.append(rect_cell(
        next_id("cj-b"), L,
        cj_x0, py(GIRDER_MID_Y_FT + GHT_FT),
        cj_w, fw(GIRDER_RIM_Y_FT - GHT_FT - (GIRDER_MID_Y_FT + GHT_FT)),
        C_CENTER_JOIST, EC_CENTER_JOIST, lw=2.5, opacity=90
    ))

    # Callout box
    box_x = cj_x0 - fw(4.5)
    box_y = py(GIRDER_MID_Y_FT / 2) - fw(1.8)
    cells.append(rect_cell(
        next_id("cj-callout"), L,
        box_x, box_y, 180, 80,
        "#fff4e0", EC_CENTER_JOIST, lw=1.5,
        value=(
            "&lt;b&gt;CENTER JOIST (v17 NEW)&lt;/b&gt;&lt;br/&gt;"
            "x=11&#39;-6&quot; framing  (x=11&#39;-9&quot; finish)&lt;br/&gt;"
            "2×10 PT UC4B — 2 segments&lt;br/&gt;"
            "LUS210Z hangers: ledger + mid-girder + outer-rim&lt;br/&gt;"
            "Provides bearing for center divider breaker"
        ),
        fontsize=7, font_bold=False, font_color=EC_CENTER_JOIST
    ))

    # Tick at x=11'-6"
    tx = px(CENTER_JOIST_X_FT)
    cells.append(line_cell(
        next_id("cj-tick"), L,
        tx, py(0.0) - 30, tx, py(0.0),
        color=EC_CENTER_JOIST, lw=1.5, dashed=1
    ))
    cells.append(text_cell(
        next_id("cj-tick-lbl"), L,
        tx - 50, py(0.0) - 46, 100, 18,
        "x=11&#39;-6&quot; framing", fs=7, bold=True, color=EC_CENTER_JOIST
    ))

    return '\n'.join(cells)


def make_hangers_layer():
    """LUS210Z hanger markers at each joist end (4 attachment points per joist row)."""
    cells = []
    L = LID_HANGERS
    HANGER_W_FT = 0.10
    HANGER_H_FT = 0.08
    LEDGER_H_FT = 0.18

    joist_rows = JOIST_X_FT + [CENTER_JOIST_X_FT]

    for jx_ft in joist_rows:
        cx = px(jx_ft)
        hw = fw(HANGER_W_FT)
        hh = fw(HANGER_H_FT)
        hx = cx - hw / 2

        # At ledger
        cells.append(rect_cell(
            next_id("hgr"), L,
            hx, py(LEDGER_H_FT) - hh / 2, hw, hh,
            C_HANGER, EC_HANGER, lw=1.0, opacity=80
        ))
        # Mid-girder house face
        cells.append(rect_cell(
            next_id("hgr"), L,
            hx, py(GIRDER_MID_Y_FT - GHT_FT) - hh, hw, hh,
            C_HANGER, EC_HANGER, lw=1.0, opacity=80
        ))
        # Mid-girder far face
        cells.append(rect_cell(
            next_id("hgr"), L,
            hx, py(GIRDER_MID_Y_FT + GHT_FT), hw, hh,
            C_HANGER, EC_HANGER, lw=1.0, opacity=80
        ))
        # Outer-rim girder inboard face
        cells.append(rect_cell(
            next_id("hgr"), L,
            hx, py(GIRDER_RIM_Y_FT - GHT_FT) - hh, hw, hh,
            C_HANGER, EC_HANGER, lw=1.0, opacity=80
        ))

    # Legend label
    cells.append(text_cell(
        next_id("hgr-legend"), L,
        px(FRAME_W) + 10, py(0.0), 200, 24,
        "&lt;b&gt;▲ Simpson LUS210Z HDG (typ.)&lt;/b&gt;&lt;br/&gt;"
        "100 total: 25×ledger + 25×mid-girder-S + 25×mid-girder-N + 25×outer-rim",
        fs=6, color=C_HANGER, align="left"
    ))

    return '\n'.join(cells)


def make_blocking_layer():
    """Two rows of blocking perpendicular to joists (x-direction)."""
    cells = []
    L = LID_BLOCKING
    BLOCK_H_FT = JOIST_W_FT   # same visual thickness as joist
    BLOCK_ROWS_Y_FT = [4.0, 12.0]   # mid-span of each joist bay

    for by_ft in BLOCK_ROWS_Y_FT:
        # One block per joist bay across 23'-0"
        for i in range(len(JOIST_X_FT) - 1):
            bx0_ft = JOIST_X_FT[i] + JOIST_W_FT / 2
            bx1_ft = JOIST_X_FT[i + 1] - JOIST_W_FT / 2
            bw_ft  = bx1_ft - bx0_ft
            cells.append(rect_cell(
                next_id("blk"), L,
                px(bx0_ft), py(by_ft - BLOCK_H_FT / 2),
                fw(bw_ft), fw(BLOCK_H_FT),
                C_BLOCKING, EC_BLOCKING, lw=0.8, opacity=70
            ))

        cells.append(text_cell(
            next_id("blk-lbl"), L,
            px(0.0), py(by_ft) - 10, fw(FRAME_W), 14,
            f"BLOCKING ROW @ y={by_ft:.0f}&#39;-0&quot; (2×10 PT, 10¼&quot; cuts, typ. per bay)",
            fs=6, bold=True, color=EC_BLOCKING, align="center"
        ))

    return '\n'.join(cells)


def make_decking_left_layer():
    """Left half field planks: FIELD_X0 to BREAKER_X0 in x, spaced in y."""
    cells = []
    L = LID_DECK_L

    left_len_ft = BREAKER_X0_FT - FIELD_X0_FT

    for i in range(NUM_PLANKS):
        y_bot_ft = FIELD_Y0_FT + i * PLANK_STEP_FT
        if y_bot_ft + PLANK_W_FT > FIELD_Y1_FT + 0.02:
            break
        cells.append(rect_cell(
            next_id("dk-l"), L,
            px(FIELD_X0_FT), py(y_bot_ft),
            fw(left_len_ft), fw(PLANK_W_FT),
            C_FIELD, EC_FIELD, lw=0.5, opacity=90
        ))

    # Count label
    cells.append(text_cell(
        next_id("dk-l-lbl"), L,
        px(FIELD_X0_FT), py(FIELD_Y0_FT + FIELD_DEPTH_FT / 2) - 18, fw(left_len_ft), 40,
        f"&lt;b&gt;← {NUM_PLANKS} rows (left half)&lt;/b&gt;&lt;br/&gt;"
        "2× 11&#39;-9&quot; halves&lt;br/&gt;5.4&quot; ea. + ⅛&quot; gap&lt;br/&gt;"
        "Parallel to house&lt;br/&gt;Butt at breaker",
        fs=7, bold=False, color="#4a2a08", align="center"
    ))

    return '\n'.join(cells)


def make_decking_right_layer():
    """Right half field planks: BREAKER_X1 to FIELD_X1 in x."""
    cells = []
    L = LID_DECK_R

    right_len_ft = FIELD_X1_FT - BREAKER_X1_FT

    for i in range(NUM_PLANKS):
        y_bot_ft = FIELD_Y0_FT + i * PLANK_STEP_FT
        if y_bot_ft + PLANK_W_FT > FIELD_Y1_FT + 0.02:
            break
        cells.append(rect_cell(
            next_id("dk-r"), L,
            px(BREAKER_X1_FT), py(y_bot_ft),
            fw(right_len_ft), fw(PLANK_W_FT),
            C_FIELD, EC_FIELD, lw=0.5, opacity=90
        ))

    return '\n'.join(cells)


def make_breaker_layer():
    """Center divider breaker board (y-direction, MoistureShield Vision PF stock)."""
    cells = []
    L = LID_BREAKER

    cells.append(rect_cell(
        next_id("brk"), L,
        px(BREAKER_X0_FT), py(FIELD_Y0_FT),
        fw(PF_W_FT), fw(FIELD_Y1_FT - FIELD_Y0_FT),
        C_BREAKER, EC_BREAKER, lw=2.5, opacity=95,
        value=(
            "&lt;b&gt;CENTER DIVIDER&lt;/b&gt;&lt;br/&gt;"
            "BREAKER BOARD&lt;br/&gt;"
            "MoistureShield Vision&lt;br/&gt;"
            "5.4&quot; × 16&#39;-0&quot;&lt;br/&gt;"
            "Cortex screws @ 12&quot; o.c."
        ),
        fontsize=6, font_color="#3a1a00"
    ))

    # Dimension: left PF edge → breaker CL = 11'-9"
    ann_y = py(0.0) - 38
    cells.append(dim_arrow(
        next_id("brk-dim-l"), L,
        px(-PF_OVR_FT), ann_y, px(BREAKER_CL_FT), ann_y,
        color=EC_CENTER_JOIST, lw=1.4
    ))
    cells.append(text_cell(
        next_id("brk-dim-l-lbl"), L,
        px((-PF_OVR_FT + BREAKER_CL_FT) / 2) - 55, ann_y - 14, 110, 12,
        "11&#39;-9&quot;  (left PF edge → breaker CL)",
        fs=7, bold=True, color=EC_CENTER_JOIST
    ))

    cells.append(dim_arrow(
        next_id("brk-dim-r"), L,
        px(BREAKER_CL_FT), ann_y, px(OVERALL_W_FT - PF_OVR_FT), ann_y,
        color=EC_CENTER_JOIST, lw=1.4
    ))
    cells.append(text_cell(
        next_id("brk-dim-r-lbl"), L,
        px((BREAKER_CL_FT + OVERALL_W_FT - PF_OVR_FT) / 2) - 55, ann_y - 14, 110, 12,
        "11&#39;-9&quot;  (breaker CL → right PF edge)",
        fs=7, bold=True, color=EC_CENTER_JOIST
    ))

    return '\n'.join(cells)


def make_picture_frame_layer():
    cells = []
    L = LID_PF

    # House-side PF (y=0, x from -PF_OVR to OVERALL_W - PF_OVR)
    cells.append(rect_cell(
        next_id("pf-house"), L,
        px(-PF_OVR_FT), py(0.0), fw(OVERALL_W_FT), fw(PF_W_FT),
        C_PF_TREX, EC_PF_TREX, lw=2.0, opacity=95,
        value=(
            "&lt;b&gt;HOUSE-SIDE PF — 5.4&quot; MoistureShield Vision  |  23&#39;-6&quot; long  |  "
            "Butted corners (inside)&lt;/b&gt;"
        ),
        fontsize=7, font_bold=True, font_color="#3a1a00"
    ))

    # Far-side PF (y=OVERALL_D - PF_W, x full)
    far_pf_y0_ft = FRAME_D + PF_OVR_FT - PF_W_FT
    cells.append(rect_cell(
        next_id("pf-far"), L,
        px(-PF_OVR_FT), py(far_pf_y0_ft), fw(OVERALL_W_FT), fw(PF_W_FT),
        C_PF_TREX, EC_PF_TREX, lw=2.0, opacity=95,
        value=(
            "&lt;b&gt;FAR-SIDE PF — 5.4&quot; MoistureShield Vision  |  23&#39;-6&quot; long  |  "
            "MITERED corners (outside) 45°&lt;/b&gt;"
        ),
        fontsize=7, font_bold=True, font_color="#3a1a00"
    ))

    # Left-side PF — two segments (interrupted at stair opening y=6'-0" to y=9'-6")
    left_pf_x0_ft = -(PF_OVR_FT + FASCIA_T_FT + PF_W_FT)
    # Segment 1: y=0 to y=STEP_Y0
    cells.append(rect_cell(
        next_id("pf-left-s1"), L,
        px(left_pf_x0_ft), py(0.0), fw(PF_W_FT), fw(STEP_Y0_FT),
        C_PF_TREX, EC_PF_TREX, lw=2.0, opacity=95,
        value="&lt;b&gt;LEFT PF 5.4&quot;&lt;/b&gt;"
    ))
    # Segment 2: y=STEP_Y1 to y=far_pf_y0
    cells.append(rect_cell(
        next_id("pf-left-s2"), L,
        px(left_pf_x0_ft), py(STEP_Y1_FT), fw(PF_W_FT), fw(far_pf_y0_ft - STEP_Y1_FT),
        C_PF_TREX, EC_PF_TREX, lw=2.0, opacity=95,
        value="&lt;b&gt;LEFT PF 5.4&quot;&lt;/b&gt;"
    ))

    # Right-side PF — full y=0 to far_pf_y0
    right_pf_x0_ft = FRAME_W + FASCIA_T_FT
    cells.append(rect_cell(
        next_id("pf-right"), L,
        px(right_pf_x0_ft), py(0.0), fw(PF_W_FT), fw(far_pf_y0_ft),
        C_PF_TREX, EC_PF_TREX, lw=2.0, opacity=95,
        value="&lt;b&gt;RIGHT PF 5.4&quot; MoistureShield  |  16&#39;-3&quot;&lt;/b&gt;"
    ))

    # Miter corner labels
    cells.append(text_cell(
        next_id("miter-lbl-l"), L,
        px(left_pf_x0_ft) - 70, py(OVERALL_D_FT) + 2, 70, 24,
        "Outside corner&lt;br/&gt;45° miter",
        fs=6, color="#5a1a00", align="right"
    ))
    cells.append(text_cell(
        next_id("miter-lbl-r"), L,
        px(right_pf_x0_ft + PF_W_FT) + 2, py(OVERALL_D_FT) + 2, 70, 24,
        "Outside corner&lt;br/&gt;45° miter",
        fs=6, color="#5a1a00", align="left"
    ))

    return '\n'.join(cells)


def make_fascia_layer():
    cells = []
    L = LID_FASCIA

    # Far-side fascia (y direction: from outer-rim girder far edge outward)
    fas_y0_px = py(fas_y_ft)
    fas_h_px  = fw(FASCIA_T_FT)
    cells.append(rect_cell(
        next_id("fas-far"), L,
        px(0.0), fas_y0_px, fw(FRAME_W), fas_h_px,
        C_FASCIA, EC_FASCIA, lw=2.0, opacity=90,
        value="&lt;b&gt;FAR FASCIA — Composite 0.67&quot; × 11.25&quot;&lt;/b&gt;"
    ))

    # Left-side fascia (x-direction rect, y = 0 to fas_y0)
    fas_x_left = px(0.0) - fw(FASCIA_T_FT)
    cells.append(rect_cell(
        next_id("fas-left"), L,
        fas_x_left, py(0.0), fw(FASCIA_T_FT), fw(fas_y_ft + FASCIA_T_FT),
        C_FASCIA, EC_FASCIA, lw=2.0, opacity=90,
        value="&lt;b&gt;L FASCIA&lt;/b&gt;"
    ))

    # Right-side fascia
    cells.append(rect_cell(
        next_id("fas-right"), L,
        px(FRAME_W), py(0.0), fw(FASCIA_T_FT), fw(fas_y_ft + FASCIA_T_FT),
        C_FASCIA, EC_FASCIA, lw=2.0, opacity=90,
        value="&lt;b&gt;R FASCIA&lt;/b&gt;"
    ))

    # Drop board (sub-fascia) at far side
    drop_y0_px = py(GIRDER_RIM_Y_FT + JOIST_W_FT / 2)
    drop_h_px  = fw(DROP_T_FT)
    cells.append(rect_cell(
        next_id("drop-far"), L,
        px(0.0), drop_y0_px, fw(FRAME_W), drop_h_px,
        C_DROP, EC_DROP, lw=1.5, opacity=80,
        value="Drop board / sub-fascia"
    ))

    return '\n'.join(cells)


def make_stairs_layer():
    cells = []
    L = LID_STAIRS

    # ── LEFT-EDGE STAIR — plan view ──────────────────────────────────────────
    # Gravel pad
    cells.append(rect_cell(
        next_id("stair-gravel"), L,
        px(GRAVEL_X0_FT), py(GRAVEL_Y0_FT),
        fw(GRAVEL_D_FT), fw(GRAVEL_W_FT),
        C_GRAVEL, EC_GRAVEL, lw=1.5, opacity=85,
        value="#57 gravel pad 48&quot;×18&quot;"
    ))

    # 3 precast pavers (12"×12" each)
    PAVER_SZ_FT = 1.0
    for sy_ft in STRINGER_Y_FT:
        cells.append(rect_cell(
            next_id("paver"), L,
            px(GRAVEL_X0_FT), py(sy_ft - PAVER_SZ_FT / 2),
            fw(PAVER_SZ_FT), fw(PAVER_SZ_FT),
            C_PAVER, EC_PAVER, lw=1.5,
            value="12&quot;×12&quot; paver"
        ))

    # 3 PT cut stringers
    for sy_ft in STRINGER_Y_FT:
        cells.append(rect_cell(
            next_id("stringer"), L,
            px(STEP_X_OUT_FT), py(sy_ft - STRINGER_W_FT / 2),
            fw(abs(STEP_X_OUT_FT - LEFT_DECK_X_FT)), fw(STRINGER_W_FT),
            C_STRINGER, EC_STRINGER, lw=1.5
        ))

    # Stringer label
    cells.append(text_cell(
        next_id("stringer-lbl"), L,
        px(STEP_X_OUT_FT) - 5, py(STEP_Y0_FT) - 20, fw(abs(LEFT_DECK_X_FT - STEP_X_OUT_FT)) + 10, 18,
        "&lt;b&gt;2×10 PT stringers (3) — Simpson LSCZ to left rim&lt;/b&gt;",
        fs=6, bold=True, color=EC_STRINGER, align="center"
    ))

    # Middle treads (2 MoistureShield planks side-by-side, parallel to left edge)
    for i in range(2):
        tx_ft = MTREAD_X0_FT - i * (PLANK_W_FT + PLANK_GAP_FT)
        cells.append(rect_cell(
            next_id("tread"), L,
            px(tx_ft), py(STEP_Y0_FT),
            fw(PLANK_W_FT), fw(STEP_Y1_FT - STEP_Y0_FT),
            C_TREAD, EC_TREAD, lw=1.0
        ))

    cells.append(text_cell(
        next_id("tread-lbl"), L,
        px(MTREAD_X0_FT - PLANK_W_FT) - 2, py((STEP_Y0_FT + STEP_Y1_FT) / 2) - 30, 70, 60,
        "Middle tread&lt;br/&gt;2×5.4&quot;&lt;br/&gt;MoistureShield&lt;br/&gt;Vision&lt;br/&gt;6&quot; AG open risers",
        fs=5, color=EC_TREAD, align="center"
    ))

    # Cut joint lines at step opening
    step_x0_px = px(STEP_X_OUT_FT) - 4
    step_x1_px = px(LEFT_DECK_X_FT) + 2
    for sy_ft in [STEP_Y0_FT, STEP_Y1_FT]:
        cells.append(line_cell(
            next_id("cutjoint"), L,
            step_x0_px, py(sy_ft), step_x1_px, py(sy_ft),
            color=C_CUTJOINT, lw=2.0
        ))
    cells.append(text_cell(
        next_id("cutjoint-lbl-top"), L,
        px(STEP_X_OUT_FT) - 2, py(STEP_Y0_FT) - 12, 120, 11,
        "&lt;b&gt;CUT JOINT y=6&#39;-0&quot; (PF &amp; fascia terminate)&lt;/b&gt;",
        fs=5, bold=True, color=C_CUTJOINT
    ))
    cells.append(text_cell(
        next_id("cutjoint-lbl-bot"), L,
        px(STEP_X_OUT_FT) - 2, py(STEP_Y1_FT) + 2, 120, 11,
        "&lt;b&gt;CUT JOINT y=9&#39;-6&quot; (PF &amp; fascia resume)&lt;/b&gt;",
        fs=5, bold=True, color=C_CUTJOINT
    ))

    # Step dimensions
    cells.append(dim_arrow(
        next_id("step-w-arr"), L,
        px(STEP_X_OUT_FT) - 14, py(STEP_Y0_FT), px(STEP_X_OUT_FT) - 14, py(STEP_Y1_FT),
        color="#2244aa", lw=1.2
    ))
    cells.append(text_cell(
        next_id("step-w-lbl"), L,
        px(STEP_X_OUT_FT) - 56, py((STEP_Y0_FT + STEP_Y1_FT) / 2) - 18, 40, 36,
        "42&quot;&lt;br/&gt;step&lt;br/&gt;width",
        fs=6, bold=True, color="#2244aa"
    ))
    cells.append(dim_arrow(
        next_id("step-d-arr"), L,
        px(STEP_X_OUT_FT), py(STEP_Y1_FT) + 22, px(LEFT_DECK_X_FT), py(STEP_Y1_FT) + 22,
        color="#2244aa", lw=1.2
    ))
    cells.append(text_cell(
        next_id("step-d-lbl"), L,
        px((STEP_X_OUT_FT + LEFT_DECK_X_FT) / 2) - 36, py(STEP_Y1_FT) + 26, 72, 12,
        "16&quot; step depth", fs=6, bold=True, color="#2244aa"
    ))

    # ── FAR-EDGE STEP — plan view ─────────────────────────────────────────────
    # Gravel pad
    far_gravel_y0 = OVERALL_D_FT
    far_gravel_h  = FAR_TREAD_DEPTH_FT + 4.0/12 + 0.25
    cells.append(rect_cell(
        next_id("far-gravel"), L,
        px(FAR_STEP_X_LEFT_FT) - 8, py(far_gravel_y0),
        fw(FAR_STEP_X_RIGHT_FT - FAR_STEP_X_LEFT_FT) + 16, fw(far_gravel_h),
        C_FAR_GRAVEL, EC_FAR_GRAVEL, lw=1.5, opacity=80,
        value="4&quot; compacted #57 gravel pad (beyond y=16&#39;-3&quot;)"
    ))

    # Doubled 2×6 PT ribbon
    ribbon_y0_ft = fas_y_ft
    cells.append(rect_cell(
        next_id("far-ribbon"), L,
        px(FAR_STEP_X_LEFT_FT), py(ribbon_y0_ft),
        fw(FAR_STEP_X_RIGHT_FT - FAR_STEP_X_LEFT_FT), fw(RIBBON_T_FT),
        C_FAR_RIBBON, EC_FAR_RIBBON, lw=2.0,
        value="&lt;b&gt;Doubled 2×6 PT SYP ribbon — lag-bolted to outer rim&lt;/b&gt;",
        fontsize=6, font_color="white"
    ))

    # 2 MoistureShield tread planks (far-edge step)
    ribbon_y1_ft = ribbon_y0_ft + RIBBON_T_FT
    for i in range(2):
        tread_y0_ft = ribbon_y1_ft + i * (PLANK_W_FT + PLANK_GAP_FT)
        cells.append(rect_cell(
            next_id("far-tread"), L,
            px(FAR_STEP_X_LEFT_FT), py(tread_y0_ft),
            fw(FAR_STEP_X_RIGHT_FT - FAR_STEP_X_LEFT_FT), fw(PLANK_W_FT),
            C_FAR_TREAD, EC_FAR_TREAD, lw=1.0,
            value="2× MoistureShield Vision 5.4&quot; | 10.9&quot; tread | open riser | 6&quot; AG"
        ))

    # 5 precast concrete blocks
    far_tread_outer_y_ft = ribbon_y1_ft + 2 * PLANK_W_FT + PLANK_GAP_FT + 0.05
    for bx_ft in FAR_BLOCK_X_FT:
        cells.append(rect_cell(
            next_id("far-block"), L,
            px(bx_ft - FAR_BLOCK_SZ_FT / 2), py(far_tread_outer_y_ft),
            fw(FAR_BLOCK_SZ_FT), fw(FAR_BLOCK_SZ_FT),
            C_FAR_BLOCK, EC_FAR_BLOCK, lw=1.5,
            value="12&quot;×12&quot;&lt;br/&gt;block"
        ))

    cells.append(text_cell(
        next_id("far-block-lbl"), L,
        px(FAR_STEP_X_LEFT_FT), py(far_tread_outer_y_ft + FAR_BLOCK_SZ_FT) + 4,
        fw(FAR_STEP_X_RIGHT_FT - FAR_STEP_X_LEFT_FT), 14,
        "5× precast concrete blocks (12&quot;×12&quot;) @ ≈28&quot; OC on #57 gravel",
        fs=6, color="#444444", align="center"
    ))

    # Far-step dimension
    cells.append(dim_arrow(
        next_id("far-step-dim"), L,
        px(FAR_STEP_X_LEFT_FT), py(far_gravel_y0 + far_gravel_h) + 22,
        px(FAR_STEP_X_RIGHT_FT), py(far_gravel_y0 + far_gravel_h) + 22,
        color="#2244aa", lw=1.3
    ))
    cells.append(text_cell(
        next_id("far-step-dim-lbl"), L,
        px((FAR_STEP_X_LEFT_FT + FAR_STEP_X_RIGHT_FT) / 2) - 70, py(far_gravel_y0 + far_gravel_h) + 26, 140, 14,
        "11&#39;-9&quot; far-edge step (right corner → midpoint)",
        fs=7, bold=True, color="#2244aa"
    ))

    return '\n'.join(cells)


def make_dims_layer():
    cells = []
    L = LID_DIMS

    # ── Overall 23'-6" (top) ─────────────────────────────────────────────────
    top_ann_y = py(0.0) - 80
    cells.append(dim_arrow(
        next_id("dim-overall-w"), L,
        px(-PF_OVR_FT), top_ann_y,
        px(OVERALL_W_FT - PF_OVR_FT), top_ann_y,
        color=C_DIM_LINE, lw=1.6
    ))
    cells.append(text_cell(
        next_id("dim-overall-w-lbl"), L,
        px(FRAME_W / 2) - 200, top_ann_y - 16, 400, 14,
        "23&#39;-6&quot;  OVERALL FINISHED SURFACE  (PF outer edge to outer edge)",
        fs=10, bold=True, color=C_DIM_LINE
    ))

    # Framing 23'-0"
    mid_ann_y = py(0.0) - 56
    cells.append(dim_arrow(
        next_id("dim-frame-w"), L,
        px(0.0), mid_ann_y, px(FRAME_W), mid_ann_y,
        color="#444444", lw=1.2
    ))
    cells.append(text_cell(
        next_id("dim-frame-w-lbl"), L,
        px(FRAME_W / 2) - 150, mid_ann_y - 14, 300, 12,
        "23&#39;-0&quot;  framing footprint (rim outer edge to rim outer edge)",
        fs=8, color="#444444"
    ))

    # Right-side depth annotations
    right_ann_x = px(OVERALL_W_FT - PF_OVR_FT) + 36

    # 16'-3" overall deck
    cells.append(dim_arrow(
        next_id("dim-overall-d"), L,
        right_ann_x, py(0.0), right_ann_x, py(OVERALL_D_FT),
        color=C_DIM_LINE, lw=1.6
    ))
    cells.append(text_cell(
        next_id("dim-overall-d-lbl"), L,
        right_ann_x + 4, py(OVERALL_D_FT / 2) - 30, 80, 60,
        "16&#39;-3&quot;&lt;br/&gt;OVERALL&lt;br/&gt;DECK&lt;br/&gt;(PF outer&lt;br/&gt;to wall)",
        fs=9, bold=True, color=C_DIM_LINE
    ))

    # 16'-6" patio
    patio_ann_x = right_ann_x + 64
    cells.append(dim_arrow(
        next_id("dim-patio-d"), L,
        patio_ann_x, py(0.0), patio_ann_x, py(PATIO_D_FT),
        color="#7a6a58", lw=1.2
    ))
    cells.append(text_cell(
        next_id("dim-patio-d-lbl"), L,
        patio_ann_x + 4, py(PATIO_D_FT / 2) - 20, 60, 40,
        "16&#39;-6&quot;&lt;br/&gt;PATIO&lt;br/&gt;total",
        fs=8, color="#7a6a58"
    ))

    # Joist segment dimensions
    seg_ann_x = right_ann_x + 118
    cells.append(dim_arrow(
        next_id("dim-seg-a"), L,
        seg_ann_x, py(0.0), seg_ann_x, py(GIRDER_MID_Y_FT),
        color="#226633", lw=1.1
    ))
    cells.append(text_cell(
        next_id("dim-seg-a-lbl"), L,
        seg_ann_x + 4, py(GIRDER_MID_Y_FT / 2) - 18, 60, 36,
        "8&#39;-0&quot;&lt;br/&gt;joist&lt;br/&gt;seg A",
        fs=7, bold=True, color="#226633"
    ))

    cells.append(dim_arrow(
        next_id("dim-seg-b"), L,
        seg_ann_x, py(GIRDER_MID_Y_FT), seg_ann_x, py(GIRDER_RIM_Y_FT),
        color="#226633", lw=1.1
    ))
    cells.append(text_cell(
        next_id("dim-seg-b-lbl"), L,
        seg_ann_x + 4, py((GIRDER_MID_Y_FT + GIRDER_RIM_Y_FT) / 2) - 18, 60, 36,
        "8&#39;-0&quot;&lt;br/&gt;joist&lt;br/&gt;seg B",
        fs=7, bold=True, color="#226633"
    ))

    # Step y positions left
    left_ann_x = px(-PF_OVR_FT - FASCIA_T_FT - PF_W_FT) - 50
    cells.append(dim_arrow(
        next_id("dim-step-y0"), L,
        left_ann_x, py(0.0), left_ann_x, py(STEP_Y0_FT),
        color="#2244aa", lw=1.0
    ))
    cells.append(text_cell(
        next_id("dim-step-y0-lbl"), L,
        left_ann_x - 38, py(STEP_Y0_FT / 2) - 8, 36, 16,
        "6&#39;-0&quot;", fs=6, bold=True, color="#2244aa"
    ))

    return '\n'.join(cells)


def make_callouts_layer():
    cells = []
    L = LID_CALLOUTS

    # Ledger callout
    lc_x = px(FRAME_W) + 24
    lc_y = py(0.0) - 8
    cells.append(rect_cell(
        next_id("callout-ledger"), L,
        lc_x, lc_y, 220, 66,
        "#fff8ee", EC_CALLOUT, lw=1.5,
        value=(
            "&lt;b&gt;LEDGER: ½&quot; HDG carriage bolts, back-blocked from&lt;/b&gt;&lt;br/&gt;"
            "&lt;b&gt;basement; ½&quot; HDG lag @ 18&quot; OC two-row staggered&lt;/b&gt;&lt;br/&gt;"
            "between connections (IRC R507.9.1.3). Wood-frame wall.&lt;br/&gt;"
            "Peel-and-stick + Z-flashing + kick-out at ends.&lt;br/&gt;"
            "DTT2Z lateral connectors (4× per IRC R507.9)."
        ),
        fontsize=6, font_color="#663300"
    ))

    # Pier saddle callout
    pc_x = px(PIER_X_FT[1]) - fw(2.5)
    pc_y = py(GIRDER_MID_Y_FT - 3.0)
    cells.append(rect_cell(
        next_id("callout-pier"), L,
        pc_x, pc_y, 180, 70,
        "#fdf0e0", C_PIER, lw=1.5,
        value=(
            "&lt;b&gt;PYLEX 50 HELICAL PIER + 10555 SADDLE&lt;/b&gt;&lt;br/&gt;"
            "10 piers total — 5 per girder line&lt;br/&gt;"
            "Pier spacing: 5&#39;-9&quot; (within DCA-6 limit of 8&#39;-2&quot;)&lt;br/&gt;"
            "¼&quot; cedar/HDPE shims each side in saddle&lt;br/&gt;"
            "Doubled 2×10 (3.0&quot; wide) fits 3.5&quot; saddle"
        ),
        fontsize=6, font_color=C_PIER
    ))

    # Hanger count callout
    hc_x = px(FRAME_W) + 24
    hc_y = py(GIRDER_MID_Y_FT) - 18
    cells.append(rect_cell(
        next_id("callout-hangers"), L,
        hc_x, hc_y, 220, 44,
        "#fff0e8", EC_HANGER, lw=1.5,
        value=(
            "&lt;b&gt;SIMPSON LUS210Z HDG — 100 total (order 110)&lt;/b&gt;&lt;br/&gt;"
            "25 @ ledger + 25 @ mid-girder S face + 25 @ mid-girder N face&lt;br/&gt;"
            "+ 25 @ outer-rim inboard face = 100 × 14 nails = 1,400 fasteners"
        ),
        fontsize=6, font_color=EC_HANGER
    ))

    # Decking callout
    dc_x = px(0.0) - 220
    dc_y = py(FIELD_Y0_FT)
    cells.append(rect_cell(
        next_id("callout-decking"), L,
        dc_x, dc_y, 200, 90,
        "#f8f4e8", EC_PF_TREX, lw=1.5,
        value=(
            "&lt;b&gt;FIELD DECKING (v17)&lt;/b&gt;&lt;br/&gt;"
            "MoistureShield Vision 5.4&quot; composite&lt;br/&gt;"
            "Runs x-direction (∥ house)&lt;br/&gt;"
            "Two 11&#39;-9&quot; halves per row,&lt;br/&gt;"
            "butting center divider breaker&lt;br/&gt;"
            "Tiger Claw TC-G hidden fasteners&lt;br/&gt;"
            f"{NUM_PLANKS} rows total (≈72×12-ft boards ordered)"
        ),
        fontsize=6, font_color="#4a2a08"
    ))

    # v17 change summary box
    cs_x = px(-PF_OVR_FT) + fw(PF_W_FT + 0.5)
    cs_y = py(0.0) - 140
    cells.append(rect_cell(
        next_id("callout-changes"), L,
        cs_x, cs_y, 400, 80,
        "#fff8e8", "#cc6600", lw=2.0,
        value=(
            "&lt;b&gt;v18 CHANGES vs. v17 — FOUNDATION / PIER LAYOUT ONLY&lt;/b&gt;&lt;br/&gt;"
            "• 8 piers → 10 piers (+2): one extra per girder line between existing positions&lt;br/&gt;"
            "• Pier spacing 7&#39;-8&quot; → 5&#39;-9&quot; (shorter spans, stronger bearing)&lt;br/&gt;"
            "• Girder splice recipe: was 16&#39;+8&#39; over 1 pier → now Ply1 11&#39;-6&quot;+11&#39;-6&quot; over center pier (x=11&#39;-6&quot;),&lt;br/&gt;"
            "  Ply2 5&#39;-9&quot;+11&#39;-6&quot;+5&#39;-9&quot; over piers 2 &amp; 4 (x=5&#39;-9&quot;, x=17&#39;-3&quot;)&lt;br/&gt;"
            "• Center pier (A3/B3 at x=11&#39;-6&quot;) aligns with center joist x-coordinate and breaker board centerline"
        ),
        fontsize=7, font_color="#4a2200", font_bold=False
    ))

    # Seasonal heave note
    heave_x = px(FAR_STEP_X_LEFT_FT - 3.0)
    heave_y = py(OVERALL_D_FT + 0.1)
    cells.append(rect_cell(
        next_id("callout-heave"), L,
        heave_x, heave_y, 300, 58,
        "#fff0e0", "#cc4400", lw=1.8,
        value=(
            "&lt;b&gt;SEASONAL HEAVE NOTE (Hollis): shallow precast blocks WILL heave ¼-½&quot; per cycle.&lt;/b&gt;&lt;br/&gt;"
            "This is a decorative/convenience step, NOT frost-depth founded.&lt;br/&gt;"
            "Homeowner has accepted this trade-off.&lt;br/&gt;"
            "Step is separate from and does not affect left-edge stair."
        ),
        fontsize=6, font_color="#8B0000"
    ))

    # DCA-6 note
    dca_x = px(FRAME_W) + 24
    dca_y = py(GIRDER_RIM_Y_FT) + 30
    cells.append(rect_cell(
        next_id("callout-dca"), L,
        dca_x, dca_y, 220, 44,
        "#e8f0ff", "#333388", lw=1.5,
        value=(
            "&lt;b&gt;DCA-6 TABLE 3A CHECK (bring to permit office):&lt;/b&gt;&lt;br/&gt;"
            "Doubled 2×10 SYP @ 8-ft joist span → max girder span 8&#39;-2&quot;&lt;br/&gt;"
            "v18 pier spacing = 5&#39;-9&quot; — passes with ≈2&#39;-5&quot; margin"
        ),
        fontsize=6, font_color="#333388"
    ))

    # v18 geometric coincidence callout: center pier aligns with center joist x
    center_pier_px = px(CENTER_JOIST_X_FT)  # x=11'-6" = x=11.5 ft
    align_callout_x = center_pier_px - 90
    align_callout_y = py(GIRDER_MID_Y_FT) + fw(GHT_FT) + 8
    cells.append(rect_cell(
        next_id("callout-align"), L,
        align_callout_x, align_callout_y, 180, 52,
        "#e8ffe8", "#228822", lw=1.8,
        value=(
            "&lt;b&gt;★ v18 ALIGNMENT (x=11&#39;-6&quot;)&lt;/b&gt;&lt;br/&gt;"
            "Center pier A3/B3 lands at same x as&lt;br/&gt;"
            "center joist &amp; breaker board CL.&lt;br/&gt;"
            "Pier on girder (y=8&#39; or 16&#39;); joist runs y-dir."
        ),
        fontsize=6, font_color="#145214"
    ))

    return '\n'.join(cells)


def make_badge_layer():
    cells = []
    L = LID_BADGE

    badge_x = px(-PF_OVR_FT)
    badge_y = py(0.0) - 178
    badge_w = 160
    badge_h = 90

    # Badge background
    cells.append(rect_cell(
        next_id("badge-bg"), L,
        badge_x, badge_y, badge_w, badge_h,
        "#1a1a1a", "#1a1a1a", lw=2.0,
        extra_style="arcSize=12;rounded=1;"
    ))

    # "v18" large text
    cells.append(text_cell(
        next_id("badge-v18"), L,
        badge_x, badge_y + 8, badge_w, 52,
        "&lt;b&gt;v18&lt;/b&gt;",
        fs=36, color="white", bold=True
    ))

    # Subtitle
    cells.append(text_cell(
        next_id("badge-sub"), L,
        badge_x, badge_y + 62, badge_w, 20,
        "10 piers / 5&#39;-9&quot; spacing",
        fs=9, color="#cccccc"
    ))

    return '\n'.join(cells)


def make_title_layer():
    cells = []
    L = LID_TITLE

    # Bottom-right title block
    tb_w = 300
    tb_h = 90
    tb_x = px(OVERALL_W_FT - PF_OVR_FT) + 80   # right of diagram
    tb_y = py(OVERALL_D_FT) - tb_h / 2

    cells.append(rect_cell(
        next_id("title-bg"), L,
        tb_x, tb_y, tb_w, tb_h,
        "#f0f0f0", "#333333", lw=2.0
    ))
    cells.append(text_cell(
        next_id("title-main"), L,
        tb_x + 4, tb_y + 4, tb_w - 8, 28,
        "&lt;b&gt;DECK PLAN v18 — FRAMING + DECKING PLAN&lt;/b&gt;",
        fs=10, bold=True, color="#111111", align="center"
    ))
    cells.append(text_cell(
        next_id("title-addr"), L,
        tb_x + 4, tb_y + 34, tb_w - 8, 14,
        "West Hartford CT — 23&#39;-6&quot; × 16&#39;-3&quot; attached deck",
        fs=7, color="#333333", align="center"
    ))
    cells.append(text_cell(
        next_id("title-date"), L,
        tb_x + 4, tb_y + 50, tb_w - 8, 14,
        "Date: 2026-05-10  |  Gemma — Technical Diagramming Specialist",
        fs=7, color="#555555", align="center"
    ))
    cells.append(text_cell(
        next_id("title-sub"), L,
        tb_x + 4, tb_y + 66, tb_w - 8, 18,
        "v18 = 10 piers / 5&#39;-9&quot; spacing + updated girder splice scheme",
        fs=6, color="#666666", align="center", italic=True
    ))

    return '\n'.join(cells)


# ══════════════════════════════════════════════════════════════════════════════
# Assemble the drawio XML
# ══════════════════════════════════════════════════════════════════════════════

def build_drawio():
    layer_defs = [
        layer_cell("0", ""),             # root (required)
        layer_cell(LID_DEFAULT, ""),      # default layer (id=1, parent=0)
        layer_cell(LID_PATIO,    "Patio Outline"),
        layer_cell(LID_PIERS,    "Foundation / Piers"),
        layer_cell(LID_GIRDERS,  "Girders"),
        layer_cell(LID_LEDGER,   "Ledger"),
        layer_cell(LID_JOISTS,   "Joists — Regular"),
        layer_cell(LID_CJ,       "Joists — Center (v17 NEW)"),
        layer_cell(LID_HANGERS,  "Joist Hangers"),
        layer_cell(LID_BLOCKING, "Blocking"),
        layer_cell(LID_DECK_L,   "Decking — Left Half"),
        layer_cell(LID_DECK_R,   "Decking — Right Half"),
        layer_cell(LID_BREAKER,  "Center Divider / Breaker (v17 NEW)"),
        layer_cell(LID_PF,       "Picture Frame Perimeter"),
        layer_cell(LID_FASCIA,   "Fascia"),
        layer_cell(LID_STAIRS,   "Stairs / Steps"),
        layer_cell(LID_DIMS,     "Dimensions"),
        layer_cell(LID_CALLOUTS, "Callouts"),
        layer_cell(LID_BADGE,    "Version Badge"),
        layer_cell(LID_TITLE,    "Title Block"),
    ]

    content_parts = [
        make_patio_layer(),
        make_piers_layer(),
        make_girders_layer(),
        make_ledger_layer(),
        make_joists_regular_layer(),
        make_center_joist_layer(),
        make_hangers_layer(),
        make_blocking_layer(),
        make_decking_left_layer(),
        make_decking_right_layer(),
        make_breaker_layer(),
        make_picture_frame_layer(),
        make_fascia_layer(),
        make_stairs_layer(),
        make_dims_layer(),
        make_callouts_layer(),
        make_badge_layer(),
        make_title_layer(),
    ]

    layer_xml  = '\n'.join(layer_defs)
    content_xml = '\n'.join(content_parts)

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<mxfile host="app.diagrams.net" type="device">
  <diagram id="deck-plan-v18-p1" name="Page 1 — Framing + Decking Plan (v18)">
    <mxGraphModel dx="4988" dy="1865" grid="1" gridSize="10"
                  guides="1" tooltips="1" connect="1"
                  arrows="1" fold="1" page="1"
                  pageScale="1" pageWidth="2338" pageHeight="1654"
                  math="0" shadow="0">
      <root>
{layer_xml}
{content_xml}
      </root>
    </mxGraphModel>
  </diagram>
</mxfile>"""
    return xml


# ─── Main ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    out_path = "/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/owner_inbox/deck_blueprint/deck_plan_v18.drawio"
    xml = build_drawio()
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(xml)
    print(f"Written: {out_path}")
    print(f"File size: {len(xml):,} bytes  ({len(xml.encode('utf-8')):,} bytes UTF-8)")
    print(f"Cell count (mxCell): {xml.count('<mxCell')}")
    print(f"Layer count (parent=\"0\"): {xml.count('parent=\"0\"')}")
    print(f"NUM_PLANKS per half: {NUM_PLANKS}")
    print(f"Pier count (5 per line × 2 lines): {len(PIER_X_FT) * len(PIER_Y_FT)}")
    print(f"Pier X positions (ft): {PIER_X_FT}")
    # Verify pier IDs
    pier_cell_count = xml.count('next_id("pier"')  # count in source, not in output
    pier_id_count = sum(1 for line in xml.split('\n') if 'id="v18-pier-' in line)
    print(f"Pier ellipse cells in output: {pier_id_count}")
    print()
    # Verify layers are present
    layer_checks = [
        "Patio Outline", "Foundation / Piers", "Girders", "Ledger",
        "Joists — Regular", "Joists — Center (v17 NEW)", "Joist Hangers",
        "Blocking", "Decking — Left Half", "Decking — Right Half",
        "Center Divider / Breaker (v17 NEW)", "Picture Frame Perimeter",
        "Fascia", "Stairs / Steps", "Dimensions", "Callouts",
        "Version Badge", "Title Block",
    ]
    print("Layer verification:")
    all_ok = True
    for lname in layer_checks:
        found = f'value="{lname}"' in xml
        status = "OK" if found else "MISSING"
        if not found:
            all_ok = False
        print(f"  [{status}] {lname}")
    print()
    if all_ok:
        print("All layers verified OK.")
    else:
        print("WARNING: some layers are missing.")
    print()
    # Verify mxGraphModel layer indicator
    if 'parent="0"' in xml:
        print("OK: File contains mxCell parent=\"0\" layer markup.")
    else:
        print("WARNING: No layer markup found.")
