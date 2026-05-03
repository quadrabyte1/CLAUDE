"""
render_v6.py  —  Gemma's matplotlib render of deck_plan v6
Produces deck_plan.png at >=2000 px wide, white background.

v6 changes vs v4 (v5 was abandoned mid-flight):
  - Overall finished deck: 23'-6" x 16'-6" (picture-frame outer edge to outer edge)
  - Framing footprint: 23'-0" x 16'-3"
  - 4-side picture frame: house side now has PF board (NEW in v6)
  - Trex Universal Fascia (0.75") on 3 exposed sides (not house side)
  - PF overhangs fascia 2.25" = 3" past rim on 3 exposed sides
  - House-side PF butts wall (no overhang, no fascia)
  - 18 members total across 16'-3" depth:
      Member 1 (y=0): ledger
      Members 2-17 (y=1..16 ft): 16 regular joists at 12" o.c.
      Member 18 (y=16.25 ft): doubled far-side rim (3" final bay)
  - Post spacing along girder: 0', 8'-1.5", 16'-3" (true thirds of 16.25 ft)
  - Blocking rows at 5'-9" and 17'-3" (same as v4)
  - Section detail updated: shows rim/fascia/PF cantilever stack

Coordinate system:
  - X axis = 23 ft direction (along house wall, left->right)
  - Y axis = 16.25 ft direction (out from house, top->bottom)
  - House wall along the TOP of the drawing.
  - Y is inverted (ax.invert_yaxis) so y=0 plots at top.
All measurements in feet unless noted.
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.lines as mlines
import numpy as np

# ── Key dimensions ─────────────────────────────────────────────────────────────
FRAME_W   = 23.0           # framing width (along house), ft
FRAME_D   = 16.25          # framing depth (out from house) = 16'-3", ft
PF_W      = 5.5 / 12       # picture-frame board width, ft  (~0.4583)
FASCIA_T  = 0.75 / 12      # fascia thickness, ft  (0.0625)
PF_OVR    = 3.0 / 12       # PF overhang past rim outer face on 3 exposed sides, ft (0.25)
# Overall = FRAME_W + PF_OVR*2 = 23.5  |  FRAME_D + PF_OVR = 16.5
OVERALL_W = FRAME_W + 2 * PF_OVR   # 23.5 ft
OVERALL_D = FRAME_D + PF_OVR       # 16.5 ft  (house side: no overhang)

# ── Canvas setup ───────────────────────────────────────────────────────────────
FIG_W_IN = 32
FIG_H_IN = 22
DPI = 100

fig, ax = plt.subplots(figsize=(FIG_W_IN, FIG_H_IN), dpi=DPI)
fig.patch.set_facecolor("white")
ax.set_facecolor("white")

# Plan origin: x=0, y=0 is house-face / left edge of FRAMING
ax.set_xlim(-3.5, 32.5)
ax.set_ylim(-3.5, 22.0)
ax.invert_yaxis()   # house at top (y=0 plots at top)
ax.set_aspect("equal")
ax.axis("off")

# ── Color palette (consistent with v4) ────────────────────────────────────────
C_HOUSE    = "#cccccc"
C_LEDGER   = "#f8cecc";  EC_LEDGER  = "#b85450"
C_GIRDER   = "#dae8fc";  EC_GIRDER  = "#6c8ebf"
C_JOIST    = "#d5e8d4";  EC_JOIST   = "#82b366"
C_RIM      = "#fff2cc";  EC_RIM     = "#d6b656"
C_PF       = "#ffe680";  EC_PF      = "#b8860b"   # picture-frame: saturated yellow
C_FASCIA   = "#c8a0e8";  EC_FASCIA  = "#7030a0"   # fascia: purple to distinguish from PF
C_POST_F   = "#e1d5e7";  EC_POST    = "#9673a6"
C_BLOCK    = "#888888"
C_TAPE     = "#ffff99";  EC_TAPE    = "#cccc00"
C_DECK     = "#dddddd";  EC_DECK    = "#888888"
C_NOTE     = "#ffffee";  EC_NOTE    = "#888800"
C_CALLOUT  = "#fff9e6";  EC_CALLOUT = "#cc8800"

def rect(x, y, w, h, fc, ec, lw=1.0, zorder=2, alpha=1.0):
    p = mpatches.FancyBboxPatch((x, y), w, h,
                                boxstyle="square,pad=0",
                                facecolor=fc, edgecolor=ec,
                                linewidth=lw, zorder=zorder, alpha=alpha)
    ax.add_patch(p)
    return p

def label(x, y, text, fs=7, ha="center", va="center", bold=False, color="black",
          rotation=0, zorder=5):
    fw = "bold" if bold else "normal"
    ax.text(x, y, text, fontsize=fs, ha=ha, va=va, fontweight=fw,
            color=color, rotation=rotation, zorder=zorder, clip_on=False)

# ══════════════════════════════════════════════════════════════════════════════
# HOUSE WALL (gray bar above framing, top edge)
# ══════════════════════════════════════════════════════════════════════════════
# House wall spans the full overall width (including PF overhangs on left/right)
rect(-PF_OVR, -1.1, OVERALL_W, 1.0, C_HOUSE, "#444444", lw=2, zorder=3)
label(FRAME_W/2, -0.6,
      "HOUSE WALL  ▲  NORTH  (attached 23’-6” overall edge)",
      fs=11, bold=True)

# ══════════════════════════════════════════════════════════════════════════════
# PICTURE FRAME — HOUSE SIDE (NEW in v6)
# Sits between y=0 (house face) and y=PF_W inward
# No fascia. Butts wall.
# ══════════════════════════════════════════════════════════════════════════════
# House-side PF runs the full overall width
rect(-PF_OVR, 0.0, OVERALL_W, PF_W, C_PF, EC_PF, lw=2.5, zorder=6)
label(FRAME_W/2, PF_W/2,
      "HOUSE-SIDE PICTURE-FRAME BOARD — 5.5\" Trex  |  Butts wall (1/4\" thermal gap)  |  NEW IN v6  |  No fascia on house side",
      fs=6.5, bold=True, color="#6b4400")

# ══════════════════════════════════════════════════════════════════════════════
# GIRDERS — 3 girders at x=0, 11.5, 23.0; each FRAME_D long (16.25 ft)
# ══════════════════════════════════════════════════════════════════════════════
GIRDER_W = 0.35
GIRDER_POSITIONS = [0.0, 11.5, 23.0]
GIRDER_LABELS = [
    "LEFT GIRDER\n(3) 2×10 PT\n@ 0 ft",
    "MIDDLE GIRDER\n(3) 2×10 PT\n@ 11’-6\"",
    "RIGHT GIRDER\n(3) 2×10 PT\n@ 23 ft"
]

for gx, glabel_txt in zip(GIRDER_POSITIONS, GIRDER_LABELS):
    x0 = gx - GIRDER_W / 2
    x0 = max(0.0, min(x0, FRAME_W - GIRDER_W))
    rect(x0, 0.0, GIRDER_W, FRAME_D, C_GIRDER, EC_GIRDER, lw=3, zorder=4)
    ax.text(x0 + GIRDER_W/2, FRAME_D/2, glabel_txt,
            fontsize=5.8, ha="center", va="center", rotation=90,
            fontweight="bold", color="#1a3a6b", zorder=7,
            multialignment="center")

# ══════════════════════════════════════════════════════════════════════════════
# LEDGER — Member 1 (at y=0, house face) — SINGLE 2x10 PT, 23 ft long
# ══════════════════════════════════════════════════════════════════════════════
LEDGER_H = 0.18
rect(0.0, 0.0, FRAME_W, LEDGER_H, C_LEDGER, EC_LEDGER, lw=3.5, zorder=5)
label(FRAME_W/2, LEDGER_H/2,
      "LEDGER — SINGLE 2×10 PT  |  ½\" hot-dip galv lag bolts (or LedgerLOK) @ 16\" o.c. staggered  |  Z-flashing above  |  23’-0\" long",
      fs=6.5, bold=True, color="#5a0000", zorder=8)

# MTWDeck lateral-tie callout
rect(13.0, 0.22, 9.5, 0.55, C_CALLOUT, EC_CALLOUT, lw=1.5, zorder=7)
label(17.75, 0.50,
      "⚠ MTWDeck LATERAL TIE REQ’D — min. 2× Simpson MTWDeck (or equiv.) along ledger\n"
      "per IRC R507.9 / DCA-6: 2× band joist + 2× interior blocking bearing on sill plate",
      fs=6.0, ha="center", va="center", color="#663300", zorder=8)

# Ledger note in left margin
label(-2.2, 0.09,
      "LEDGER\n2×10 PT\n(lag-bolted\n+ Z-flash)\n23’-0\"",
      fs=6.0, ha="center", va="center")

# ══════════════════════════════════════════════════════════════════════════════
# REGULAR JOISTS — Members 2–17 at y = 1,2,...,16 ft (12" o.c.)
# 16 regular joists, each 23'-0" long
# ══════════════════════════════════════════════════════════════════════════════
JOIST_H = 0.09
JOIST_SPACING_FT = 1.0   # 12" = 1 ft

for i in range(1, 17):   # i=1..16 → y = 1..16 ft
    y_pos = i * JOIST_SPACING_FT
    rect(0.0, y_pos - JOIST_H/2, FRAME_W, JOIST_H, C_JOIST, EC_JOIST, lw=1, zorder=3)

# Splice callout on the 9th regular joist (y=9 ft)
splice_y = 9 * JOIST_SPACING_FT
ax.annotate("", xy=(11.5, splice_y), xytext=(12.5, splice_y - 0.8),
            arrowprops=dict(arrowstyle="->", color="#555555", lw=0.8))
label(13.8, splice_y - 0.95,
      "SPLICE over middle girder\n(lap joint + GRK RSS screws) — typ. all joists",
      fs=6, ha="left", va="center")

# ══════════════════════════════════════════════════════════════════════════════
# DOUBLED FAR-SIDE RIM — Member 18 at y=16.25 ft (16'-3")
# Note the 3" final bay (from last 12" o.c. joist at 16'-0" to rim at 16'-3")
# ══════════════════════════════════════════════════════════════════════════════
FAR_RIM_H = 0.22
far_rim_y = FRAME_D - FAR_RIM_H   # top of doubled rim bar
rect(0.0, far_rim_y, FRAME_W, FAR_RIM_H, C_RIM, EC_RIM, lw=3, zorder=5)
label(FRAME_W/2, far_rim_y + FAR_RIM_H/2,
      "FAR-SIDE RIM — (2) 2×10 PT, 23’-0\" long  |  Sits on 3 girders  |  3\" final bay from last 12\" o.c. joist at 16’-0\"",
      fs=7.0, bold=True, zorder=6)

# Arrow calling out the 3" final bay
bay_mid_y = FRAME_D - FAR_RIM_H/2 - 3.0/24   # midpoint of 3" bay
ax.annotate("", xy=(24.0, FRAME_D - FAR_RIM_H), xytext=(24.0, 16.0),
            arrowprops=dict(arrowstyle="<->", color="#cc4400", lw=1.2))
label(24.55, FRAME_D - FAR_RIM_H/2 - 0.05, "3\"\nfinal\nbay", fs=7, bold=True,
      color="#cc4400", ha="left")

# ══════════════════════════════════════════════════════════════════════════════
# SHORT-EDGE RIM JOISTS — left (x=0) and right (x=23), each FRAME_D long
# ══════════════════════════════════════════════════════════════════════════════
RIM_SIDE_W = 0.22
rect(0.0, 0.0, RIM_SIDE_W, FRAME_D, C_RIM, EC_RIM, lw=2, zorder=3)
rect(FRAME_W - RIM_SIDE_W, 0.0, RIM_SIDE_W, FRAME_D, C_RIM, EC_RIM, lw=2, zorder=3)

# ══════════════════════════════════════════════════════════════════════════════
# FASCIA — on 3 exposed sides only (far, left, right). NOT house side.
# Fascia sits on outer face of rim. Drawn OUTSIDE framing footprint.
# ══════════════════════════════════════════════════════════════════════════════
FASCIA_VIS = FASCIA_T   # 0.0625 ft — thin strip
FASCIA_LW = 3.0
FASCIA_ALPHA = 0.85

# Far-side fascia (horizontal, below far rim)
rect(0.0, FRAME_D, FRAME_W, FASCIA_VIS, C_FASCIA, EC_FASCIA, lw=FASCIA_LW,
     zorder=6, alpha=FASCIA_ALPHA)

# Left-side fascia (vertical, to the left of left rim)
rect(-FASCIA_T, 0.0, FASCIA_VIS, FRAME_D, C_FASCIA, EC_FASCIA, lw=FASCIA_LW,
     zorder=6, alpha=FASCIA_ALPHA)

# Right-side fascia (vertical, to the right of right rim)
rect(FRAME_W, 0.0, FASCIA_VIS, FRAME_D, C_FASCIA, EC_FASCIA, lw=FASCIA_LW,
     zorder=6, alpha=FASCIA_ALPHA)

# Fascia label callouts
label(FRAME_W/2, FRAME_D + FASCIA_T/2,
      "TREX UNIVERSAL FASCIA (0.75\") — stainless trim screws to rim",
      fs=6.0, bold=False, color="#5a0070", zorder=8)

# ══════════════════════════════════════════════════════════════════════════════
# PICTURE FRAME — FAR SIDE + LEFT + RIGHT (3 exposed sides)
# PF cantilevered 3" (0.25 ft) past rim outer face
# = sits from rim outer face outward by PF_OVR = 0.25 ft
# But PF board is 5.5" wide; 3" overhang past rim; 2.5" over the rim/fascia
# ══════════════════════════════════════════════════════════════════════════════
# Far-side PF: from (y=FRAME_D) outward by PF_W; x spans full overall width including side PF
# PF band extends from x=-PF_OVR to x=FRAME_W+PF_OVR (the overall width corners)
PF_THICK = PF_W   # 5.5/12 ft

# Far PF
rect(-PF_OVR, FRAME_D + FASCIA_T, OVERALL_W, PF_THICK, C_PF, EC_PF, lw=2.5, zorder=7)
label(FRAME_W/2, FRAME_D + FASCIA_T + PF_THICK/2,
      "FAR PICTURE-FRAME BOARD — 5.5\" Trex  |  2.25\" overhang past fascia  |  3\" past rim",
      fs=6.5, bold=True, color="#6b4400", zorder=9)

# Left PF (from x=-PF_OVR inward PF_W, running from y=0 to far PF top)
# Y range: house-side PF to far-side PF (0 to FRAME_D+FASCIA_T)
rect(-PF_OVR - FASCIA_T, 0.0, PF_THICK, FRAME_D + FASCIA_T, C_PF, EC_PF, lw=2.5, zorder=7)
label(-PF_OVR - FASCIA_T/2 - PF_THICK/2, FRAME_D/2,
      "LEFT PF\n5.5\" Trex\n3\" past rim",
      fs=5.5, bold=True, color="#6b4400", rotation=90, zorder=9)

# Right PF
rect(FRAME_W + FASCIA_T, 0.0, PF_THICK, FRAME_D + FASCIA_T, C_PF, EC_PF, lw=2.5, zorder=7)
label(FRAME_W + FASCIA_T + PF_THICK/2, FRAME_D/2,
      "RIGHT PF\n5.5\" Trex\n3\" past rim",
      fs=5.5, bold=True, color="#6b4400", rotation=90, zorder=9)

# ══════════════════════════════════════════════════════════════════════════════
# POSTS — 9 total (P1-P9)
# 3 per girder at y = 0, 8.125, 16.25 ft (true thirds of 16.25 ft = 8'-1.5")
# ══════════════════════════════════════════════════════════════════════════════
POST_R = 0.38
POST_SQ = 0.22
POST_Y_POSITIONS = [0.0, FRAME_D/2, FRAME_D]   # 0, 8.125, 16.25

posts = []
for i, gx in enumerate(GIRDER_POSITIONS):
    for j, py in enumerate(POST_Y_POSITIONS):
        pnum = i * 3 + j + 1
        posts.append((gx, py, f"P{pnum}"))

for px, py, plabel_txt in posts:
    circ = plt.Circle((px, py), POST_R, fc=C_POST_F, ec=EC_POST, lw=2, zorder=6)
    ax.add_patch(circ)
    sq = mpatches.FancyBboxPatch((px - POST_SQ/2, py - POST_SQ/2),
                                 POST_SQ, POST_SQ,
                                 boxstyle="square,pad=0",
                                 fc=C_POST_F, ec=EC_POST, lw=1.5, zorder=7)
    ax.add_patch(sq)
    label(px, py, plabel_txt, fs=6.5, bold=True, zorder=9)

# ══════════════════════════════════════════════════════════════════════════════
# BLOCKING — dashed gray lines at x=5.75 and x=17.25 ft
# ══════════════════════════════════════════════════════════════════════════════
BLOCKING_X = [5.75, 17.25]
for bx in BLOCKING_X:
    ax.plot([bx, bx], [0.0, FRAME_D],
            color=C_BLOCK, linewidth=2.5, linestyle="--", zorder=3, alpha=0.85)

label(5.75, -1.3, "BLOCKING\n@ 5’-9\"", fs=7, bold=True, color="#555555")
label(17.25, -1.3, "BLOCKING\n@ 17’-3\"", fs=7, bold=True, color="#555555")

# ══════════════════════════════════════════════════════════════════════════════
# JOIST o.c. SPACING CALLOUTS (right side of plan, outside framing)
# ══════════════════════════════════════════════════════════════════════════════
# Show representative arrows at joists 2, 8, 14
for arrow_i in [2, 8, 14]:
    y_lo = (arrow_i - 1) * JOIST_SPACING_FT
    y_hi = arrow_i * JOIST_SPACING_FT
    x_ann = 25.3
    ax.annotate("", xy=(x_ann, y_hi), xytext=(x_ann, y_lo),
                arrowprops=dict(arrowstyle="<->", color="#333333", lw=0.9))
    label(x_ann + 0.45, (y_lo + y_hi) / 2, '12\"', fs=7.5, bold=True, ha="left")

label(26.2, 8.0, "12\" o.c.\ntypical", fs=9, bold=True, ha="left")

# ══════════════════════════════════════════════════════════════════════════════
# DIMENSION ANNOTATIONS
# ══════════════════════════════════════════════════════════════════════════════

# ── Overall 23'-6" (top, above house wall) ────────────────────────────────────
ax.annotate("", xy=(-PF_OVR, -2.2), xytext=(OVERALL_W - PF_OVR, -2.2),
            arrowprops=dict(arrowstyle="<->", color="#000099", lw=1.5))
label(FRAME_W/2, -2.55, "23’-6\"  OVERALL FINISHED SURFACE  (PF outer edge to PF outer edge)",
      fs=9.5, bold=True, color="#000099")

# ── Framing 23'-0" (top, just below overall) ─────────────────────────────────
ax.annotate("", xy=(0.0, -1.7), xytext=(FRAME_W, -1.7),
            arrowprops=dict(arrowstyle="<->", color="#444444", lw=1.2))
label(FRAME_W/2, -1.45, "23’-0\"  (rim joist outer edge — framing footprint)",
      fs=8, bold=False, color="#444444")

# ── Overall 16'-6" (right side, out from house) ───────────────────────────────
right_ann_x = FRAME_W + FASCIA_T + PF_THICK + 0.7
ax.annotate("", xy=(right_ann_x, 0.0),
            xytext=(right_ann_x, OVERALL_D),
            arrowprops=dict(arrowstyle="<->", color="#000099", lw=1.5))
label(right_ann_x + 0.55, OVERALL_D/2,
      "16’-6\" OVERALL\n(PF outer edge\nto wall)", fs=8.5, bold=True,
      color="#000099", rotation=90)

# ── Framing 16'-3" (right side) ───────────────────────────────────────────────
frame_d_ann_x = right_ann_x + 1.2
ax.annotate("", xy=(frame_d_ann_x, 0.0),
            xytext=(frame_d_ann_x, FRAME_D),
            arrowprops=dict(arrowstyle="<->", color="#444444", lw=1.2))
label(frame_d_ann_x + 0.5, FRAME_D/2,
      "16’-3\"\nframing", fs=8, bold=False, color="#444444", rotation=90)

# ── 3" PF overhang annotation (bottom-left corner) ────────────────────────────
# Arrow from rim outer face to PF outer edge on the far side
ax.annotate("", xy=(1.5, FRAME_D), xytext=(1.5, FRAME_D + FASCIA_T + PF_THICK),
            arrowprops=dict(arrowstyle="<->", color="#8B0000", lw=1.2))
label(1.5, FRAME_D + FASCIA_T + PF_THICK + 0.18,
      "PF = 5.5\"  (3\" past rim, 2.25\" past fascia)",
      fs=7, bold=True, color="#8B0000", ha="center")

# ── 0.75" fascia callout (far side) ──────────────────────────────────────────
ax.annotate("", xy=(4.0, FRAME_D), xytext=(4.0, FRAME_D + FASCIA_T),
            arrowprops=dict(arrowstyle="<->", color="#5a0070", lw=1.2))
label(4.0, FRAME_D + FASCIA_T + 0.12,
      "Fascia 0.75\"", fs=6.5, bold=False, color="#5a0070", ha="center")

# Girder position ticks (along top)
for gx, gtxt in zip([0.0, 11.5, 23.0], ["0’", "11’-6\"", "23’-0\""]):
    ax.plot([gx, gx], [-1.4, -0.9], color="#333333", lw=1, zorder=4)
    label(gx, -0.65, gtxt, fs=7.5, bold=True, va="bottom")

# Post spacing along girder (left margin ticks)
for py_v, ptxt in zip([0.0, FRAME_D/2, FRAME_D], ["0’", "8’-1.5\"", "16’-3\""]):
    ax.plot([-1.8, -1.4], [py_v, py_v], color="#555555", lw=0.8)
    label(-2.1, py_v, ptxt, fs=7, bold=False, ha="right")

# Joist span arrows (below plan)
span_y = FRAME_D + FASCIA_T + PF_THICK + 1.0
ax.annotate("", xy=(11.5, span_y), xytext=(0.0, span_y),
            arrowprops=dict(arrowstyle="<->", color="#555577", lw=1.0))
label(5.75, span_y + 0.35, "11’-6\" joist span", fs=7.5, color="#333377")

ax.annotate("", xy=(23.0, span_y), xytext=(11.5, span_y),
            arrowprops=dict(arrowstyle="<->", color="#555577", lw=1.0))
label(17.25, span_y + 0.35, "11’-6\" joist span", fs=7.5, color="#333377")

# ══════════════════════════════════════════════════════════════════════════════
# RIGHT-SIDE PANEL — Title block, framing callout, legend, section detail
# ══════════════════════════════════════════════════════════════════════════════
PX = 27.8    # left edge of right panel
PW = 4.4     # panel width

def panel_box(y0, h, fc="#f5f5f5", ec="#444444", lw=1.5):
    rect(PX, y0, PW, h, fc, ec, lw=lw, zorder=2)

# ── Title block ────────────────────────────────────────────────────────────────
panel_box(-3.2, 6.0, fc="#f5f5f5")
title_lines = [
    'DECK PLAN v6',
    "23’-6\" × 16’-6\"  Overall Finished Surface",
    '12" off grade  |  4-Side Picture Frame',
    "House on 23’-6\" Edge  |  Decking ⊥ House",
    "Fascia on 3 Exposed Sides  |  PF Overhangs 2.25\"",
    "",
    "Scale: 1\" ≈ 1 ft (plot units = ft)",
    "HOUSE = top edge  ▲ NORTH",
    "",
    "Date: 2026-05-01",
    "Gemma — Technical Diagramming Specialist",
]
for i, line in enumerate(title_lines):
    fw = "bold" if i < 5 else "normal"
    fs = 9 if i == 0 else 7.2
    label(PX + PW/2, -3.0 + i * 0.48, line, fs=fs, bold=(fw == "bold"))

# ── Framing direction callout ──────────────────────────────────────────────────
panel_box(3.0, 3.3, fc="#fffde7", ec="#f57f17", lw=2)
label(PX + PW/2, 3.25, "FRAMING DIRECTION", fs=8, bold=True)
label(PX + 0.07, 3.6,  "→ Girders: ⊥ to house (16’-3\" dir.), at 0’, 11’-6\", 23’", fs=6.5, ha="left")
label(PX + 0.07, 3.85, "— Joists: ∥ to house (23’ dir.), 12\" o.c.", fs=6.5, ha="left")
label(PX + 0.07, 4.1,  "· Decking: ⊥ house (runs 16’-3\" direction)", fs=6.5, ha="left")
label(PX + 0.07, 4.4,  "Framing 23’-0\" × 16’-3\" inside PF perimeter;", fs=6.2, ha="left", color="#5a0000")
label(PX + 0.07, 4.62, "overall finished surface 23’-6\" × 16’-6\".", fs=6.2, ha="left", color="#5a0000", bold=True)
label(PX + 0.07, 4.84, "4-side picture frame; fascia under PF on 3 exposed sides;", fs=6.0, ha="left", color="#555555")
label(PX + 0.07, 5.04, "PF overhangs fascia 2.25\" (3\" past rim).", fs=6.0, ha="left", color="#555555")
label(PX + 0.07, 5.24, "18 members (1 ledger + 16 joists + 1 doubled far rim).", fs=6.0, ha="left", color="#555555")
label(PX + 0.07, 5.44, "Final bay = 3\" (16’-0\" to 16’-3\" rim) — normal.", fs=6.0, ha="left", color="#333300")
label(PX + 0.07, 5.64, "Post spacing: 0’, 8’-1.5\", 16’-3\" (⅓ of 16.25 ft).", fs=6.0, ha="left", color="#555555")

# ── Legend ─────────────────────────────────────────────────────────────────────
panel_box(6.5, 12.5, fc="white")
label(PX + PW/2, 6.75, "LEGEND", fs=10, bold=True)

legend_items = [
    (7.25,  C_LEDGER,  EC_LEDGER,  3.5,
     "Ledger — SINGLE 2×10 PT, 23’-0\" long",
     "Lag bolts + Z-flashing; rests on 3 girders at house-end posts",
     "Joists run ∥ to ledger — do NOT hang from it"),
    (8.3, C_GIRDER, EC_GIRDER, 3,
     "Girder — (3) 2×10 PT, 16’-3\" long, ground-contact",
     "Runs ⊥ to house (16’-3\" dir.); 3 @ 0’, 11’-6\", 23’",
     None),
    (9.15, C_JOIST, EC_JOIST, 1,
     "Joist — 2×10 PT, 12\" o.c., 23’-0\" long",
     "16 regular joists + doubled far rim = 18 members total",
     "Final bay 3\" (normal). Spliced over mid girder (lap + GRK RSS)."),
    (10.15, C_RIM, EC_RIM, 2,
     "Far-side rim — (2) 2×10 PT; Short-edge rims — 2×10 PT",
     "Short rims: 16’-3\" long, end-grain hangers (Simpson LSU)",
     None),
    (10.95, C_PF, EC_PF, 2.5,
     "Picture-frame board — 5.5\" Trex (ALL 4 SIDES in v6)",
     "House side: butts wall, no fascia, no overhang",
     "3 exposed sides: cantilever 3\" past rim. Add 2x outboard blocking"),
    (12.05, C_FASCIA, EC_FASCIA, 3,
     "Trex Universal Fascia (0.75\") — 3 EXPOSED SIDES ONLY",
     "Vertical, attached to outer face of rim with stainless trim screws",
     "NOT installed on house side (wall is boundary)"),
    (13.05, C_POST_F, EC_POST, 2,
     "Post (P1–P9) + Footing",
     "6×6 PT on 12\" sonotube footings to frost depth",
     "9 posts; 3 per girder @ 0’, 8’-1.5\", 16’-3\" along girder"),
]

for row in legend_items:
    yt, fc, ec, lw, main, sub1, sub2 = row
    rect(PX + 0.08, yt, 0.55, 0.38, fc, ec, lw=lw, zorder=3)
    label(PX + 0.72, yt + 0.10, main, fs=6.8, bold=True, ha="left")
    label(PX + 0.72, yt + 0.27, sub1, fs=5.9, ha="left", color="#444444")
    if sub2:
        label(PX + 0.72, yt + 0.44, sub2, fs=5.7, ha="left", color="#666666")

# Blocking legend
yt_block = 14.0
ax.plot([PX + 0.08, PX + 0.63], [yt_block + 0.17, yt_block + 0.17],
        color=C_BLOCK, lw=2.5, linestyle="--", zorder=4)
label(PX + 0.72, yt_block + 0.10, "Blocking — solid 2×10 PT between joists", fs=6.8, bold=True, ha="left")
label(PX + 0.72, yt_block + 0.27, "Rows at 5’-9\" and 17’-3\" from left edge", fs=5.9, ha="left", color="#444444")

# ── Fastener / material notes ──────────────────────────────────────────────────
panel_box(14.65, 5.6, fc=C_NOTE, ec=EC_NOTE)
notes = [
    "FASTENER / MATERIAL NOTES",
    "Ledger: ½\" hot-dip galv lag bolts or FastenMaster LedgerLOK,",
    "  16\" o.c. staggered; metal Z-flashing above ledger",
    "Lateral ties: min. 2× Simpson MTWDeck per IRC R507.9 / DCA-6",
    "Joist-to-rim: Simpson LSU/LSC end-grain hangers (short edges)",
    "Joist tape: Zip System or equiv. on every joist top surface",
    "Joist splices: GRK RSS structural screws, lap joint over mid girder",
    "2-ply far rim: ½\" carriage bolts per AWC specs",
    "Framing: 2×10 PT UC4B throughout; posts: 6×6 PT UC4B",
    "Decking: Trex composite; boards run ⊥ to house (16’-3\" dir.)",
    "Footings: 12\" dia. sonotube to frost depth, per local code",
    "Hardware: Simpson ZMAX or stainless throughout",
    "Fascia: 0.75\" Trex Universal Fascia, color-matched,",
    "  attached to rim with stainless trim screws",
    "PF cantilever support: install 2x outboard blocking or",
    "  sub-fascia drop board to back up the 3\" PF cantilever past rim",
    "  (Trex max recommended cantilever w/o backing ≈ 1.5\")",
]
for i, note in enumerate(notes):
    fw = "bold" if i == 0 else "normal"
    fs = 6.5 if i == 0 else 5.9
    label(PX + 0.08, 14.85 + i * 0.305, note, fs=fs, bold=(i == 0), ha="left")

# ══════════════════════════════════════════════════════════════════════════════
# SECTION DETAIL PANEL — updated for v6 rim/fascia/PF cantilever stack
# Right panel, bottom section
# ══════════════════════════════════════════════════════════════════════════════
panel_box(20.5, 1.3, fc="#f9f9f9")  # spacer — actual content below
# Re-use space below fastener notes

SD_Y0 = 20.55
label(PX + PW/2, SD_Y0, "SECTION DETAIL — Rim / Fascia / PF Cantilever (exposed side)", fs=7.5, bold=True)
label(PX + PW/2, SD_Y0 + 0.28, "Vertical slice at far-side or short-side rim, looking along joist", fs=5.8)

# The detail is a miniature vertical stack, drawn to exaggerated scale
# Each layer is a horizontal band; labels to the right
# Detail coordinate: local y increases downward; mapped to figure y
SD_SCALE = 5.0   # px per inch of real thickness for readability
SD_X0 = PX + 0.2
SD_X1 = PX + PW - 0.1
SD_W = SD_X1 - SD_X0
SD_TOP = SD_Y0 + 0.5

# Layer definitions: (real_thick_in, label_text, fc, ec, lw)
sd_layers = [
    # Decking above PF board
    (1.0,  "Trex composite DECKING (on joists, ⊥ house)",   C_DECK,    EC_DECK,   1.5),
    # PF board  — 5.5" wide, 1" thick (typical Trex)
    (1.0,  "PICTURE-FRAME BOARD (5.5\" Trex, 1\" thick)",       C_PF,      EC_PF,     2.5),
    # Joist tape
    (0.2,  "Joist tape",                                         C_TAPE,    EC_TAPE,   1.0),
    # Joist / far rim
    (9.25, "2×10 PT JOIST / FAR RIM (nominal 9.25\" depth)", C_JOIST,  EC_JOIST,  2.0),
    # Fascia — sits on outer face of joist, below top of joist
    (5.0,  "Trex Universal FASCIA (0.75\" × full rim height)", C_FASCIA, EC_FASCIA, 2.5),
    # Post cap
    (0.5,  "Post cap (Simpson BC/E or equiv.)",                  C_POST_F,  EC_POST,   1.0),
    # Post
    (8.0,  "6×6 PT POST",                                    C_POST_F,  EC_POST,   2.0),
]

# Render at exaggerated scale: 1 real inch = 0.035 ft in plot units
SD_SCALE_FT = 0.032   # ft per real inch of thickness (exaggerated for readability)
y_cursor = SD_TOP
for (thick_in, lbl, fc, ec, lw) in sd_layers:
    h = thick_in * SD_SCALE_FT
    rect(SD_X0, y_cursor, SD_W, h, fc, ec, lw=lw, zorder=5)
    label(SD_X0 + SD_W/2, y_cursor + h/2, lbl, fs=5.5, zorder=6)
    y_cursor += h

# Now add clear annotation lines for the overhang
# The PF is at layers[1] → starts at SD_TOP + 1.0*SD_SCALE_FT
PF_top_y = SD_TOP + 1.0 * SD_SCALE_FT
PF_bot_y = SD_TOP + 2.0 * SD_SCALE_FT

# The joist outer face corresponds to the right edge of the SD rect
# Fascia outer face = joist outer face (fascia attached to outer face of rim)
# Since this is a cross-section in plan view it's a vertical detail, show annotation lines
annot_x = SD_X0 - 0.08

# Arrow: PF overhang 2.25" past fascia outer face
# In this detail, that's a horizontal dimension — add a text note instead
label(PX + PW/2, y_cursor + 0.12,
      "▲  3\" PF cantilever past rim outer face",
      fs=6.0, bold=True, color="#8B0000")
label(PX + PW/2, y_cursor + 0.30,
      "2.25\" PF overhang past fascia outer face",
      fs=6.0, bold=False, color="#5a0070")
label(PX + PW/2, y_cursor + 0.48,
      "NOTE: Fascia is at rim outer face (side view).",
      fs=5.6, color="#555555")
label(PX + PW/2, y_cursor + 0.64,
      "PF board sits on top of rim, cantilevering outward.",
      fs=5.6, color="#555555")
label(PX + PW/2, y_cursor + 0.82,
      "Add 2x outboard blocking/sub-fascia drop board",
      fs=5.6, bold=True, color="#8B0000")
label(PX + PW/2, y_cursor + 0.98,
      "to support the 3\" cantilever (Trex max ≈ 1.5\" unsupported).",
      fs=5.6, bold=True, color="#8B0000")

# ══════════════════════════════════════════════════════════════════════════════
# FIGURE TITLE (top-left, outside plan area)
# ══════════════════════════════════════════════════════════════════════════════
ax.text(-3.2, -3.2,
        "Deck Plan v6  —  23’-6\" × 16’-6\" Overall Finished Surface, 12\" off grade,\n"
        "House on 23’-6\" Edge, 4-Side Picture Frame + Fascia on 3 Exposed Sides, Decking ⊥ House",
        fontsize=11, fontweight="bold", va="top", ha="left", color="#222222")

# ══════════════════════════════════════════════════════════════════════════════
# SAVE
# ══════════════════════════════════════════════════════════════════════════════
OUT = "/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/owner_inbox/deck_blueprint/deck_plan.png"
fig.savefig(OUT, dpi=DPI, bbox_inches="tight", facecolor="white")
print(f"Saved: {OUT}")

from PIL import Image
img = Image.open(OUT)
print(f"Size: {img.size[0]}×{img.size[1]} px")
