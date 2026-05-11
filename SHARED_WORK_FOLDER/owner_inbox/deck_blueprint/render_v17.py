"""
render_v17.py  —  Gemma's matplotlib render of deck_plan v17
Produces deck_plan_v17.png at >=2000 px wide, white background.

v17 = v16 + center joist + center divider/breaker board:

  v16 baseline:
    - 2 girder lines parallel to house (x-direction, 23'-0" long each)
      - Mid-girder line at y=8'-0"
      - Outer-rim girder line at y=16'-0"
      - Each girder = DOUBLED 2×10 PT SYP (fits Pylex 3.5" saddle + shims)
    - 24 joists perpendicular to house (y-direction, 16'-0" each in 2 segments)
      - Face-hung to ledger (y=0), mid-girder (y=8'-0"), outer-rim (y=16'-0")
    - Decking runs parallel to house (x-direction)
    - 8 piers (4 per girder line)

  v17 additions:
    - 1 extra "center" joist at x=11'-6" framing (x=11'-9" finish)
      - Between existing joists at x=11'-0" and x=12'-0"
      - Same 2x10 PT, 2 segments, face-hung at ledger/mid-girder/outer-rim
      - Rendered in distinct amber color to flag as special
    - 1 center divider (breaker) board at x=11'-9" finish (on the center joist)
      - MoistureShield Vision 5.4" x 1.0" x 16'-0", y-direction
      - Same composite as picture-frame stock, same color
    - Decking updated: every row now TWO 11'-9" pieces butting at breaker
      - Left half: from house-side PF inner edge to breaker left edge
      - Right half: from breaker right edge to far-side PF inner edge

Coordinate system (same as v7+):
  - X axis = 23 ft direction (along house wall, left->right)
  - Y axis = 16 ft direction (out from house, top->bottom)
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
from matplotlib.patches import Polygon as MplPolygon, FancyBboxPatch, Rectangle
from matplotlib.collections import PatchCollection

# ── Key dimensions ─────────────────────────────────────────────────────────────
FRAME_W    = 23.0           # framing width (along house), ft
FRAME_D    = 16.0           # framing depth, ft (16'-0")
PF_W       = 5.4 / 12      # PF board width in ft = 0.45 ft
FASCIA_T   = 0.67 / 12     # fascia thickness, ft
PF_OVR     = 3.0 / 12      # PF overhang past rim outer face (3" = 0.25 ft)
OVERALL_W  = FRAME_W + 2 * PF_OVR    # 23.5 ft = 23'-6"
OVERALL_D  = FRAME_D + PF_OVR        # 16.25 ft = 16'-3"

# Original patio depth (fixed — does not change)
PATIO_D    = 16.5           # 16'-6"

# ── v16 GIRDER POSITIONS (x-direction, parallel to house) ─────────────────────
GIRDER_MID_Y  = 8.0         # mid-girder line at y=8'-0"
GIRDER_RIM_Y  = FRAME_D     # outer-rim girder line at y=16'-0"
GIRDER_T      = 0.27        # doubled 2×10 = 3" nominal → ~0.27 ft rendered (visual)
GHT           = GIRDER_T / 2

# ── v16 PIER POSITIONS ────────────────────────────────────────────────────────
# 4 piers per girder line at x=0, 7'-8", 15'-4", 23'-0"
PIER_X_SPACING = 23.0 / 3          # 7.667 ft ≈ 7'-8"
PIER_X = [0.0, PIER_X_SPACING, 2 * PIER_X_SPACING, FRAME_W]
PIER_Y = [GIRDER_MID_Y, GIRDER_RIM_Y]

# ── v16 JOIST POSITIONS (y-direction, perpendicular to house) ─────────────────
# 24 joists at 12" o.c. from x=0 to x=23'-0"
# Actually 24 joists across 23'-0": 23 spaces of 12" + rim joists at x=0 and x=23
# Per task: 24 joists at 12" o.c. across 23'-0" framing width
JOIST_SPACING_X = 1.0       # 12" o.c.
JOIST_X = [i * JOIST_SPACING_X for i in range(24)]   # x=0 to x=23
JOIST_W = 0.085             # joist thickness rendered (visual width in x)

# Joist segments:
# Seg A: y=0 (ledger face) to y=GIRDER_MID_Y=8'-0"
# Seg B: y=GIRDER_MID_Y=8'-0" to y=GIRDER_RIM_Y=16'-0"
SEG_A_Y0 = 0.0
SEG_A_Y1 = GIRDER_MID_Y
SEG_B_Y0 = GIRDER_MID_Y
SEG_B_Y1 = GIRDER_RIM_Y

# ── v17: CENTER JOIST + BREAKER ──────────────────────────────────────────────
# Center joist at x=11'-6" framing (between existing joists at x=11' and x=12')
CENTER_JOIST_X = 11.5        # ft (framing centerline)
# Finished surface center = 11'-9" from left PF outer edge
# = 11'-6" framing + 3" (PF overhang on left side)
# But in our coordinate system, x=0 is left rim face. Left PF outer edge = -PF_OVR.
# So finish center = CENTER_JOIST_X + PF_OVR = 11.5 + 0.25 = 11.75 ft from left PF edge = 11'-9"
CENTER_JOIST_FRAMING_X = CENTER_JOIST_X   # 11.5 ft in framing coords

# Breaker board: centered on center joist in finish coords
# In framing coords, breaker centerline = CENTER_JOIST_X = 11.5 ft
# Breaker width = PF_W = 5.4/12 ft
BREAKER_CL_X   = CENTER_JOIST_X           # framing coordinate centerline
BREAKER_X0     = BREAKER_CL_X - PF_W / 2  # left edge of breaker (framing coords)
BREAKER_X1     = BREAKER_CL_X + PF_W / 2  # right edge of breaker (framing coords)

# ── Decking (x-direction, parallel to house) ──────────────────────────────────
# Planks run x-direction, spaced in y (joist direction)
# v16: decking parallel to house
PLANK_W    = 5.4 / 12       # 0.45 ft (plank face width, in y direction)
PLANK_GAP  = (1.0/8) / 12   # 0.01042 ft
PLANK_STEP = PLANK_W + PLANK_GAP

# PF inboard overlap on each side = 2.4" = 0.20 ft
PF_INBOARD = 2.4 / 12

# Field plank Y range (between PF boards)
FIELD_Y0   = PF_INBOARD
FIELD_Y1   = FRAME_D + PF_OVR - PF_W   # = OVERALL_D - PF_W
FIELD_DEPTH_FT = FIELD_Y1 - FIELD_Y0

# Number of field planks spanning y-direction
NUM_PLANKS = int(np.floor(FIELD_DEPTH_FT / PLANK_STEP))
# Each plank runs full x from x=PF_INBOARD to x=FRAME_W-PF_INBOARD — but
# planks are 23'-6" long which exceeds 20-ft stock → butt joint over joist
FIELD_X0   = PF_INBOARD
FIELD_X1   = FRAME_W - PF_INBOARD
FIELD_LEN  = FIELD_X1 - FIELD_X0

# v17: no floating butt joint — decking splits at breaker board (handled below)
BUTT_JOINT_X = CENTER_JOIST_X   # ft — kept for reference; actual split at breaker edges

# ── Plank dimensions (all in feet) ────────────────────────────────────────────
# (Same values as v15 for consistency)

# ── LEFT-EDGE step dimensions — UNCHANGED from v14/v15 ───────────────────────
STEP_Y0    = 6.0
STEP_Y1    = 9.5
STEP_W     = STEP_Y1 - STEP_Y0

LEFT_DECK_X = -PF_OVR - FASCIA_T
STEP_DEPTH = 16.0 / 12
STEP_X_OUT = LEFT_DECK_X - STEP_DEPTH
STRINGER_Y = [STEP_Y0, (STEP_Y0 + STEP_Y1) / 2, STEP_Y1]
STRINGER_W_FT = 2.0 / 12

TREAD_DEPTH  = 10.8 / 12
MTREAD_X0   = LEFT_DECK_X - TREAD_DEPTH
MTREAD_X1   = LEFT_DECK_X

GRAVEL_W    = 48.0 / 12
GRAVEL_D    = 18.0 / 12
GRAVEL_Y0   = STEP_Y0 - (GRAVEL_W - STEP_W) / 2
GRAVEL_Y1   = GRAVEL_Y0 + GRAVEL_W
GRAVEL_X0   = LEFT_DECK_X - GRAVEL_D
GRAVEL_X1   = LEFT_DECK_X
PAVER_SZ    = 1.0

# ── FAR-EDGE STEP dimensions (v13, unchanged) ─────────────────────────────────
FAR_STEP_X_RIGHT = OVERALL_W - PF_OVR
FAR_STEP_X_LEFT  = (-PF_OVR + OVERALL_W - PF_OVR) / 2
FAR_STEP_LEN = FAR_STEP_X_RIGHT - FAR_STEP_X_LEFT

FAR_STEP_Y_ATTACH = OVERALL_D

FAR_TREAD_DEPTH = (5.4 + 5.4 + 0.125) / 12

FAR_GRAVEL_Y0 = OVERALL_D
FAR_GRAVEL_Y1 = FAR_GRAVEL_Y0 + FAR_TREAD_DEPTH + 4.0/12 + 0.2

FAR_BLOCK_ABS  = [23.0, 20.167, 17.333, 14.5, 11.75]
FAR_BLOCK_X    = [a - PF_OVR for a in FAR_BLOCK_ABS]
FAR_BLOCK_SZ   = 1.0

DROP_T = 0.085
far_drop_y = GIRDER_RIM_Y + JOIST_W
FAR_DROP_BOARD_FACE = far_drop_y + DROP_T + FASCIA_T

fas_y = far_drop_y + DROP_T
fas_y_end = fas_y + FASCIA_T

# ── Canvas setup ───────────────────────────────────────────────────────────────
FIG_W_IN = 38
FIG_H_IN = 28
DPI = 100

fig, ax = plt.subplots(figsize=(FIG_W_IN, FIG_H_IN), dpi=DPI)
fig.patch.set_facecolor("white")
ax.set_facecolor("white")

ax.set_xlim(-6.5, 37.0)
ax.set_ylim(-5.5, 28.0)
ax.invert_yaxis()
ax.set_aspect("equal")
ax.axis("off")

# ── Color palette (same as v15) ────────────────────────────────────────────────
C_HOUSE     = "#cccccc"
C_PATIO     = "#e8e0d4"
EC_PATIO    = "#a09080"
C_LEDGER    = "#f8cecc";  EC_LEDGER  = "#b85450"
C_GIRDER    = "#dae8fc";  EC_GIRDER  = "#6c8ebf"
C_JOIST     = "#d5e8d4";  EC_JOIST   = "#82b366"
C_RIM       = "#fff2cc";  EC_RIM     = "#d6b656"
C_FASCIA    = "#c8a0e8";  EC_FASCIA  = "#7030a0"
C_PIER      = "#5a4030";  EC_PIER    = "#2a1808"
C_PIER_HOLE = "#b0a898";  EC_HOLE    = "#706050"
C_DROP      = "#c0d8b0";  EC_DROP    = "#507040"
C_BLOCK     = "#888888"
C_HANGER    = "#cc4400";  EC_HANGER  = "#882200"

C_FIELD     = "#b89a68"
EC_FIELD    = "#6a4a2a"
C_PF_TREX   = "#8a6a3a"
EC_PF_TREX  = "#4a2a0a"
C_NOTE      = "#ffffee";  EC_NOTE    = "#888800"
C_CALLOUT   = "#fff9e6";  EC_CALLOUT = "#cc8800"

C_STRINGER  = "#6a8a5a";  EC_STRINGER = "#2a5a1a"
C_TREAD     = "#c8a878";  EC_TREAD    = "#7a5030"
C_GRAVEL    = "#d0c8b8";  EC_GRAVEL   = "#8a7a68"
C_PAVER     = "#9a9a9a";  EC_PAVER    = "#444444"
C_CUTJOINT  = "#cc2200"

C_FAR_RIBBON = "#5a8a5a"; EC_FAR_RIBBON = "#2a5a2a"
C_FAR_TREAD  = "#c8a878"; EC_FAR_TREAD  = "#7a5030"
C_FAR_BLOCK  = "#9a9a9a"; EC_FAR_BLOCK  = "#444444"
C_FAR_GRAVEL = "#d0c8b8"; EC_FAR_GRAVEL = "#8a7a68"

C_PATIO_EXPOSED  = "#d0c4b0"
EC_PATIO_EXPOSED = "#7a6a58"

C_BUTT_JOINT = "#cc0044"   # butt joint seam in decking (not used in v17 field)

# v17 additions
C_CENTER_JOIST  = "#e08030"  # amber — center joist distinct color
EC_CENTER_JOIST = "#804010"
C_BREAKER       = C_PF_TREX  # breaker = same color as picture-frame stock
EC_BREAKER      = EC_PF_TREX

FRAME_ALPHA = 0.38

# ── Helper functions ───────────────────────────────────────────────────────────
def rect(x, y, w, h, fc, ec, lw=1.0, zorder=2, alpha=1.0):
    p = FancyBboxPatch((x, y), w, h,
                       boxstyle="square,pad=0",
                       facecolor=fc, edgecolor=ec,
                       linewidth=lw, zorder=zorder, alpha=alpha)
    ax.add_patch(p)
    return p

def label(x, y, text, fs=7, ha="center", va="center", bold=False, color="black",
          rotation=0, zorder=5, alpha=1.0):
    fw = "bold" if bold else "normal"
    ax.text(x, y, text, fontsize=fs, ha=ha, va=va, fontweight=fw,
            color=color, rotation=rotation, zorder=zorder, clip_on=False, alpha=alpha)

# Panel area (right-side info column)
PX = 29.5
PW = 5.5

def panel_box(y0, h, fc="#f5f5f5", ec="#444444", lw=1.5):
    rect(PX, y0, PW, h, fc, ec, lw=lw, zorder=2)

# ══════════════════════════════════════════════════════════════════════════════
# ══ VERSION BADGE — upper-left corner ════════════════════════════════════════
# ══════════════════════════════════════════════════════════════════════════════
BADGE_X = -6.4
BADGE_Y = -5.4
BADGE_W = 4.8    # slightly wider to fit subtitle
BADGE_H = 1.8

badge = FancyBboxPatch((BADGE_X, BADGE_Y), BADGE_W, BADGE_H,
                       boxstyle="round,pad=0.05",
                       facecolor="#1a1a1a", edgecolor="#1a1a1a",
                       linewidth=2, zorder=50)
ax.add_patch(badge)

ax.text(BADGE_X + BADGE_W / 2, BADGE_Y + BADGE_H * 0.35,
        "v17",
        fontsize=36, fontweight="bold",
        ha="center", va="center",
        color="white", zorder=51, clip_on=False)

ax.text(BADGE_X + BADGE_W / 2, BADGE_Y + BADGE_H * 0.76,
        "Center joist + breaker divider",
        fontsize=7.5, fontweight="normal",
        ha="center", va="center",
        color="#cccccc", zorder=51, clip_on=False)

# ══════════════════════════════════════════════════════════════════════════════
# ══ CHANGE-CALLOUTS OVERLAY (right of badge) ══════════════════════════════════
# ══════════════════════════════════════════════════════════════════════════════
CHBOX_X = BADGE_X + BADGE_W + 0.3
CHBOX_Y = BADGE_Y - 0.1
CHBOX_W = 9.2
CHBOX_H = 2.0

rect(CHBOX_X, CHBOX_Y, CHBOX_W, CHBOX_H, "#fff8e8", "#cc6600", lw=2.0, zorder=50)
label(CHBOX_X + CHBOX_W / 2, CHBOX_Y + 0.22,
      "v17 CHANGES vs. v16",
      fs=9, bold=True, color="#8B3300", zorder=51)

change_lines = [
    "• +1 center joist at x=11'-6\" framing (16'-0\" in 2 seg; hangers at ledger, mid-girder, outer-rim)",
    "• +1 center divider / breaker board (MoistureShield Vision PF stock, 5.4\"W x 16'-0\" y-direction, x=11'-9\" finish)",
    "• Decking now 11'-9\" + 11'-9\" per row — butt against breaker on both sides at x=11'-9\" finish",
    "• Decking material change: was ~49 x 16-ft planks; now ~72 x 12-ft planks cut to 11'-9\"",
]
for i, line in enumerate(change_lines):
    label(CHBOX_X + 0.15, CHBOX_Y + 0.52 + i * 0.30,
          line, fs=6.2, bold=False, color="#4a2200", ha="left", zorder=51)

# ══════════════════════════════════════════════════════════════════════════════
# ══ BACKGROUND: FRAMING LAYER ════════════════════════════════════════════════
# ══════════════════════════════════════════════════════════════════════════════

# ── Full patio background ─────────────────────────────────────────────────────
rect(-PF_OVR, 0.0, OVERALL_W, PATIO_D,
     C_PATIO, EC_PATIO, lw=2.5, zorder=1, alpha=0.40)
hatch_rect = Rectangle((-PF_OVR, 0.0), OVERALL_W, PATIO_D,
                        hatch='....', fill=False, edgecolor="#c0b090",
                        linewidth=0, zorder=1, alpha=0.18)
ax.add_patch(hatch_rect)

label(-PF_OVR + OVERALL_W/2, FRAME_D/2 + 1.5,
      "EXISTING CONCRETE PATIO  (background — 23'-6\" × 16'-6\" — framing layer @ 40% opacity)",
      fs=6.5, bold=False, color="#9b7050", zorder=2, alpha=FRAME_ALPHA)

# ── v14: Exposed patio strip (3" beyond deck far edge) ────────────────────────
EXPOSED_Y0 = OVERALL_D
EXPOSED_Y1 = PATIO_D
EXPOSED_H  = EXPOSED_Y1 - EXPOSED_Y0

exposed_bg = FancyBboxPatch((-PF_OVR, EXPOSED_Y0), OVERALL_W, EXPOSED_H,
                              boxstyle="square,pad=0",
                              facecolor=C_PATIO_EXPOSED, edgecolor=EC_PATIO_EXPOSED,
                              linewidth=2.5, zorder=9, alpha=0.85)
ax.add_patch(exposed_bg)

exposed_hatch = Rectangle((-PF_OVR, EXPOSED_Y0), OVERALL_W, EXPOSED_H,
                            hatch='////', fill=False, edgecolor="#9a8878",
                            linewidth=0, zorder=10, alpha=0.60)
ax.add_patch(exposed_hatch)

ax.plot([-PF_OVR, OVERALL_W - PF_OVR], [PATIO_D, PATIO_D],
        color=EC_PATIO_EXPOSED, linewidth=2.5, linestyle="-", zorder=11)

label(-PF_OVR + OVERALL_W/2, (EXPOSED_Y0 + EXPOSED_Y1)/2,
      "3\" EXPOSED PATIO (deck does NOT extend to patio edge on far side)",
      fs=7.5, bold=True, color="#5a4a38", zorder=12)

strip_ann_x = OVERALL_W - PF_OVR + 0.6
ax.annotate("", xy=(strip_ann_x, EXPOSED_Y0), xytext=(strip_ann_x, EXPOSED_Y1),
            arrowprops=dict(arrowstyle="<->", color="#5a4a38", lw=1.2))
label(strip_ann_x + 0.55, (EXPOSED_Y0 + EXPOSED_Y1)/2,
      "3\"", fs=7.0, bold=True, color="#5a4a38", rotation=90, ha="center")

# ── House wall ────────────────────────────────────────────────────────────────
rect(-PF_OVR, -1.2, OVERALL_W, 1.1, C_HOUSE, "#444444", lw=2, zorder=3, alpha=FRAME_ALPHA)
label(FRAME_W/2, -0.65,
      "HOUSE WALL  ▲ NORTH  (23'-6\" overall edge)",
      fs=10, bold=True, alpha=FRAME_ALPHA)

# ── v16: Ledger ───────────────────────────────────────────────────────────────
LEDGER_H = 0.18
rect(0.0, 0.0, FRAME_W, LEDGER_H, C_LEDGER, EC_LEDGER, lw=2.5, zorder=5, alpha=FRAME_ALPHA)

# Ledger fastener callout
ledger_callout_x = FRAME_W + 0.6
ledger_callout_y = -0.15
ledger_callout_w = 10.0
ledger_callout_h = 1.6
rect(ledger_callout_x, ledger_callout_y, ledger_callout_w, ledger_callout_h,
     "#fff8ee", EC_CALLOUT, lw=1.5, zorder=16)
label(ledger_callout_x + ledger_callout_w/2, ledger_callout_y + 0.22,
      "LEDGER: ½\" HDG carriage bolts, back-blocked from basement,",
      fs=6.2, bold=True, color="#663300", ha="center", zorder=17)
label(ledger_callout_x + ledger_callout_w/2, ledger_callout_y + 0.55,
      "clustered at joist connections; ½\" HDG lag at 18\" OC two-row staggered",
      fs=6.2, bold=False, color="#333300", ha="center", zorder=17)
label(ledger_callout_x + ledger_callout_w/2, ledger_callout_y + 0.88,
      "between connections (IRC R507.9.1.3). Wall = wood-frame, no masonry.",
      fs=6.2, bold=False, color="#333300", ha="center", zorder=17)
label(ledger_callout_x + ledger_callout_w/2, ledger_callout_y + 1.21,
      "Basement access confirmed for back-blocking. Peel-and-stick + Z-flashing retained.",
      fs=6.2, bold=False, color="#333300", ha="center", zorder=17)
ax.annotate("", xy=(FRAME_W + 0.05, LEDGER_H/2),
            xytext=(ledger_callout_x, ledger_callout_y + ledger_callout_h/2),
            arrowprops=dict(arrowstyle="->", color=EC_CALLOUT, lw=1.0),
            zorder=17)

# ── v16: GIRDER LINES (x-direction, parallel to house) ───────────────────────
# Mid-girder at y=8'-0", Outer-rim at y=16'-0"
# Draw as horizontal bands

for gy in [GIRDER_MID_Y, GIRDER_RIM_Y]:
    y0 = gy - GHT
    y1 = gy + GHT
    # Draw girder as a filled rect across full framing width
    rect(0.0, y0, FRAME_W, GIRDER_T, C_GIRDER, EC_GIRDER, lw=2.5, zorder=6, alpha=FRAME_ALPHA)
    # Cross-hatch girder to visually distinguish
    g_hatch = Rectangle((0.0, y0), FRAME_W, GIRDER_T,
                          hatch='///', fill=False, edgecolor=EC_GIRDER,
                          linewidth=0, zorder=7, alpha=FRAME_ALPHA * 0.8)
    ax.add_patch(g_hatch)

# Girder labels (at full opacity for clarity)
label(FRAME_W / 2, GIRDER_MID_Y - GHT - 0.12,
      "MID-GIRDER — Doubled 2×10 PT SYP  |  y=8'-0\"  |  23'-0\" long",
      fs=7.5, bold=True, color=EC_GIRDER, zorder=30)

label(FRAME_W / 2, GIRDER_RIM_Y + GHT + 0.18,
      "OUTER-RIM GIRDER — Doubled 2×10 PT SYP  |  y=16'-0\"  |  23'-0\" long",
      fs=7.5, bold=True, color=EC_GIRDER, zorder=30)

# ── v16: JOISTS (y-direction, perpendicular to house) ─────────────────────────
# 24 joists at 12" o.c.; each in 2 segments split at mid-girder y=8'-0"
# Rim joists at x=0 and x=23 are drawn with doubled thickness + RIM color

for i, jx in enumerate(JOIST_X):
    is_rim_x = (i == 0 or i == len(JOIST_X) - 1)
    jw = JOIST_W * 2 if is_rim_x else JOIST_W
    fc = C_RIM if is_rim_x else C_JOIST
    ec = EC_RIM if is_rim_x else EC_JOIST
    lw = 2.0 if is_rim_x else 1.0
    x0 = jx - jw / 2

    # Segment A: ledger (y=0 + ledger thickness) to mid-girder top
    rect(x0, LEDGER_H, jw, SEG_A_Y1 - GHT - LEDGER_H,
         fc, ec, lw=lw, zorder=4, alpha=FRAME_ALPHA)
    # Segment B: mid-girder bottom to outer-rim top
    rect(x0, SEG_B_Y0 + GHT, jw, SEG_B_Y1 - GHT - (SEG_B_Y0 + GHT),
         fc, ec, lw=lw, zorder=4, alpha=FRAME_ALPHA)

# ── v17: CENTER JOIST (extra, amber-colored) ─────────────────────────────────
cj_x0 = CENTER_JOIST_FRAMING_X - JOIST_W / 2
# Segment A
rect(cj_x0, LEDGER_H, JOIST_W, SEG_A_Y1 - GHT - LEDGER_H,
     C_CENTER_JOIST, EC_CENTER_JOIST, lw=2.5, zorder=5, alpha=FRAME_ALPHA + 0.25)
# Segment B
rect(cj_x0, SEG_B_Y0 + GHT, JOIST_W, SEG_B_Y1 - GHT - (SEG_B_Y0 + GHT),
     C_CENTER_JOIST, EC_CENTER_JOIST, lw=2.5, zorder=5, alpha=FRAME_ALPHA + 0.25)

# Center joist callout
ax.annotate(
    "CENTER JOIST\nx=11'-6\" framing\n(x=11'-9\" finish)\n2x10 PT — 2 seg\nHangers: ledger +\nmid-girder + outer-rim",
    xy=(CENTER_JOIST_FRAMING_X, GIRDER_MID_Y / 2),
    xytext=(CENTER_JOIST_FRAMING_X - 4.5, GIRDER_MID_Y / 2 - 1.8),
    fontsize=6.0, ha="center", color=EC_CENTER_JOIST, fontweight="bold",
    arrowprops=dict(arrowstyle="->", color=EC_CENTER_JOIST, lw=1.2),
    zorder=35, clip_on=False,
    bbox=dict(boxstyle="round,pad=0.3", facecolor="#fff4e0", edgecolor=EC_CENTER_JOIST, lw=1.5))

# Joist spacing callout (horizontal dimension arrow between first two joists)
joist_ann_y = GIRDER_MID_Y + 0.55
ax.annotate("", xy=(JOIST_X[0], joist_ann_y), xytext=(JOIST_X[1], joist_ann_y),
            arrowprops=dict(arrowstyle="<->", color="#226633", lw=1.1))
label((JOIST_X[0] + JOIST_X[1]) / 2, joist_ann_y + 0.25,
      "12\" o.c.", fs=6.5, bold=True, color="#226633")

# Joist count callout
label(FRAME_W / 2, GIRDER_MID_Y + GHT + 0.55,
      "24 JOISTS @ 12\" o.c. + 1 CENTER JOIST @ x=11'-6\" framing  (y-dir, 2 seg each)  — 50 segments total",
      fs=6.5, bold=True, color="#226633", zorder=30)

# ── v16: Rim/end framing lines ────────────────────────────────────────────────
# End-rim boards at x=0 and x=FRAME_W run y-direction to close the frame
# (These are the double-thick rim joists at each end)

# ── v16: Drop-board sub-fascia ────────────────────────────────────────────────
# Far sub-fascia below outer-rim girder
DROP_T_V = 0.085
far_drop_y_v = GIRDER_RIM_Y + JOIST_W
rect(0.0, far_drop_y_v, FRAME_W, DROP_T_V, C_DROP, EC_DROP, lw=2, zorder=5, alpha=FRAME_ALPHA)

# Left drop-board (y-direction)
left_drop_x_v = -GHT - DROP_T_V
rect(left_drop_x_v, 0.0, DROP_T_V, FRAME_D, C_DROP, EC_DROP, lw=2, zorder=5, alpha=FRAME_ALPHA)
# Right drop-board
right_drop_x_v = FRAME_W + GHT
rect(right_drop_x_v, 0.0, DROP_T_V, FRAME_D, C_DROP, EC_DROP, lw=2, zorder=5, alpha=FRAME_ALPHA)

# ── Fascia ────────────────────────────────────────────────────────────────────
fas_y_v = far_drop_y_v + DROP_T_V
fas_y_end_v = fas_y_v + FASCIA_T
rect(0.0, fas_y_v, FRAME_W, FASCIA_T, C_FASCIA, EC_FASCIA, lw=2, zorder=6, alpha=FRAME_ALPHA)
rect(-FASCIA_T, 0.0, FASCIA_T, fas_y_end_v, C_FASCIA, EC_FASCIA, lw=2, zorder=6, alpha=FRAME_ALPHA)
rect(FRAME_W, 0.0, FASCIA_T, fas_y_end_v, C_FASCIA, EC_FASCIA, lw=2, zorder=6, alpha=FRAME_ALPHA)

# ── v16: PIERS (8 total: 4 per girder line) ──────────────────────────────────
PIER_R  = 0.22
HOLE_R  = 0.35

for py in PIER_Y:
    for px in PIER_X:
        hole = plt.Circle((px, py), HOLE_R, fc=C_PIER_HOLE, ec=EC_HOLE,
                          lw=1.0, zorder=5, alpha=FRAME_ALPHA * 0.7)
        ax.add_patch(hole)
        pier = plt.Circle((px, py), PIER_R, fc=C_PIER, ec=EC_PIER,
                          lw=1.5, zorder=8, alpha=FRAME_ALPHA)
        ax.add_patch(pier)

# Pier saddle label (one callout points to one pier)
ax.annotate("Pylex 50 helical pier\n+ 10555 saddle (typ.)\n8 piers total",
            xy=(PIER_X[1], GIRDER_MID_Y),
            xytext=(PIER_X[1] - 2.0, GIRDER_MID_Y - 2.5),
            fontsize=6.5, ha="center", color=C_PIER, fontweight="bold",
            arrowprops=dict(arrowstyle="->", color=C_PIER, lw=1.2),
            zorder=30, clip_on=False,
            bbox=dict(boxstyle="round,pad=0.3", facecolor="#fdf0e0", edgecolor=C_PIER, lw=1.5))

# Pier spacing annotations along mid-girder
for i in range(len(PIER_X) - 1):
    px0 = PIER_X[i]
    px1 = PIER_X[i + 1]
    ann_y = GIRDER_MID_Y - GHT - 0.55
    ax.annotate("", xy=(px0, ann_y), xytext=(px1, ann_y),
                arrowprops=dict(arrowstyle="<->", color="#333388", lw=1.0))
    label((px0 + px1) / 2, ann_y - 0.22, "7'-8\"", fs=6.5, bold=True, color="#333388")

# Pier count callout (framing layer)
label(FRAME_W / 2, GIRDER_RIM_Y + GHT + 1.1,
      "8 PIERS (v16: 4 per girder line; spans = 7'-8\" each — within DCA-6 doubled-2×10 limit of 8'-9\" at 8' joist span)",
      fs=6.5, bold=True, color="#5a3010", zorder=10, alpha=FRAME_ALPHA + 0.2)

# Mid-girder y-position dimension (right side)
mid_dim_x = FRAME_W + 1.2
ax.annotate("", xy=(mid_dim_x, 0.0), xytext=(mid_dim_x, GIRDER_MID_Y),
            arrowprops=dict(arrowstyle="<->", color="#333388", lw=1.1))
label(mid_dim_x + 0.55, GIRDER_MID_Y / 2,
      "8'-0\"\nmid-girder", fs=7.0, bold=True, color="#333388", rotation=90, ha="center")

# ══════════════════════════════════════════════════════════════════════════════
# ══ LEFT-EDGE STEP ASSEMBLY — Plan view (UNCHANGED from v14/v15) ═════════════
# ══════════════════════════════════════════════════════════════════════════════

# ── Gravel pad ────────────────────────────────────────────────────────────────
gravel_patch = FancyBboxPatch((GRAVEL_X0, GRAVEL_Y0), GRAVEL_D, GRAVEL_W,
                               boxstyle="square,pad=0",
                               facecolor=C_GRAVEL, edgecolor=EC_GRAVEL,
                               linewidth=1.5, zorder=6, alpha=0.85)
ax.add_patch(gravel_patch)
gravel_hatch = Rectangle((GRAVEL_X0, GRAVEL_Y0), GRAVEL_D, GRAVEL_W,
                           hatch='...', fill=False, edgecolor="#6a5a48",
                           linewidth=0, zorder=7, alpha=0.7)
ax.add_patch(gravel_hatch)
label(GRAVEL_X0 + GRAVEL_D/2, GRAVEL_Y0 - 0.18,
      "#57 gravel pad\n48\"×18\"",
      fs=5.5, bold=False, color="#6a5a48", ha="center", zorder=8)

# ── Precast pavers ────────────────────────────────────────────────────────────
for py in STRINGER_Y:
    px_paver = GRAVEL_X0
    pv = FancyBboxPatch((px_paver, py - PAVER_SZ/2), PAVER_SZ, PAVER_SZ,
                         boxstyle="square,pad=0",
                         facecolor=C_PAVER, edgecolor=EC_PAVER,
                         linewidth=1.5, zorder=9)
    ax.add_patch(pv)

label(GRAVEL_X0 + PAVER_SZ/2, GRAVEL_Y0 + GRAVEL_W + 0.18,
      "12\"×12\"\nprecast\npavers",
      fs=5.5, bold=False, color="#444444", ha="center", zorder=10)

# ── 3 PT stringers ────────────────────────────────────────────────────────────
GIRDER_L_FACE = -GHT   # left edge of frame (joists at x=0 act as end rim)
STRINGER_T    = 2.0 / 12

for sy in STRINGER_Y:
    st = FancyBboxPatch((STEP_X_OUT, sy - STRINGER_T/2),
                         abs(STEP_X_OUT - LEFT_DECK_X), STRINGER_T,
                         boxstyle="square,pad=0",
                         facecolor=C_STRINGER, edgecolor=EC_STRINGER,
                         linewidth=1.5, zorder=11)
    ax.add_patch(st)

label(STEP_X_OUT + (LEFT_DECK_X - STEP_X_OUT)/2,
      STEP_Y0 - 0.22,
      "2×10 PT stringers (3)\nSimpson LSCZ to left rim",
      fs=5.5, bold=True, color=EC_STRINGER, ha="center", zorder=12)

# ── Middle tread ──────────────────────────────────────────────────────────────
tread_lw = 0.6
for i in range(2):
    tx = MTREAD_X0 - i * (PLANK_W + PLANK_GAP)
    tr = FancyBboxPatch((tx, STEP_Y0), PLANK_W, STEP_W,
                         boxstyle="square,pad=0",
                         facecolor=C_TREAD, edgecolor=EC_TREAD,
                         linewidth=tread_lw, zorder=13)
    ax.add_patch(tr)

label(MTREAD_X0 - PLANK_W, (STEP_Y0 + STEP_Y1)/2,
      "Middle tread\n2×5.4\" MoistureShield Vision\nrunning ∥ L edge\n(6\" AG, open risers)",
      fs=5.3, bold=True, color=EC_TREAD, ha="center", va="center",
      rotation=90, zorder=14)

# ── Open riser indicator ─────────────────────────────────────────────────────
ax.annotate("OPEN\nRISER",
            xy=(LEFT_DECK_X - PLANK_W*2 - PLANK_GAP*1 - 0.05, (STEP_Y0 + STEP_Y1)/2),
            xytext=(LEFT_DECK_X - PLANK_W*2 - PLANK_GAP*1 - 0.35, (STEP_Y0 + STEP_Y1)/2 - 0.8),
            fontsize=5.0, ha="center", color="#884400", fontweight="bold",
            arrowprops=dict(arrowstyle="->", color="#884400", lw=0.8),
            zorder=15, clip_on=False)

# ── Cut joints in PF and fascia at step opening ──────────────────────────────
CJ_X0 = STEP_X_OUT - 0.1
CJ_X1 = LEFT_DECK_X + 0.05

ax.plot([CJ_X0, CJ_X1], [STEP_Y0, STEP_Y0],
        color=C_CUTJOINT, linewidth=2.0, linestyle="-", zorder=20,
        solid_capstyle='butt')
ax.plot([CJ_X0, CJ_X1], [STEP_Y1, STEP_Y1],
        color=C_CUTJOINT, linewidth=2.0, linestyle="-", zorder=20,
        solid_capstyle='butt')

label(LEFT_DECK_X - TREAD_DEPTH/2, STEP_Y0 - 0.08,
      "CUT JOINT y=6'-0\"  (PF & fascia terminate)",
      fs=5.0, bold=True, color=C_CUTJOINT, ha="center", zorder=21)
label(LEFT_DECK_X - TREAD_DEPTH/2, STEP_Y1 + 0.08,
      "CUT JOINT y=9'-6\"  (PF & fascia resume)",
      fs=5.0, bold=True, color=C_CUTJOINT, ha="center", zorder=21)

# ── Dimension: step width and depth ──────────────────────────────────────────
ax.annotate("", xy=(STEP_X_OUT - 0.05, STEP_Y0), xytext=(STEP_X_OUT - 0.05, STEP_Y1),
            arrowprops=dict(arrowstyle="<->", color="#2244aa", lw=1.2))
label(STEP_X_OUT - 0.35, (STEP_Y0 + STEP_Y1)/2,
      "42\"\nstep\nwidth",
      fs=6.0, bold=True, color="#2244aa", rotation=90, ha="center")

ax.annotate("", xy=(LEFT_DECK_X, STEP_Y1 + 0.30), xytext=(STEP_X_OUT, STEP_Y1 + 0.30),
            arrowprops=dict(arrowstyle="<->", color="#2244aa", lw=1.2))
label((LEFT_DECK_X + STEP_X_OUT)/2, STEP_Y1 + 0.55,
      "16\" step depth",
      fs=6.0, bold=True, color="#2244aa", ha="center")

# ══════════════════════════════════════════════════════════════════════════════
# ══ FAR-EDGE STEP — Plan view (unchanged from v14/v15) ════════════════════════
# ══════════════════════════════════════════════════════════════════════════════
FAR_STEP_TREAD_Y0 = OVERALL_D
FAR_STEP_TREAD_Y1 = OVERALL_D + FAR_TREAD_DEPTH
FAR_STEP_GRAVEL_Y1 = OVERALL_D + FAR_TREAD_DEPTH + 4.0/12 + 0.25

# ── Gravel pad for far-edge step ──────────────────────────────────────────────
far_gravel_patch = FancyBboxPatch(
    (FAR_STEP_X_LEFT - 0.2, FAR_STEP_TREAD_Y0),
    (FAR_STEP_X_RIGHT - FAR_STEP_X_LEFT + 0.4),
    (FAR_STEP_GRAVEL_Y1 - FAR_STEP_TREAD_Y0),
    boxstyle="square,pad=0",
    facecolor=C_FAR_GRAVEL, edgecolor=EC_FAR_GRAVEL,
    linewidth=1.5, zorder=6, alpha=0.80)
ax.add_patch(far_gravel_patch)
far_gravel_hatch = Rectangle(
    (FAR_STEP_X_LEFT - 0.2, FAR_STEP_TREAD_Y0),
    (FAR_STEP_X_RIGHT - FAR_STEP_X_LEFT + 0.4),
    (FAR_STEP_GRAVEL_Y1 - FAR_STEP_TREAD_Y0),
    hatch='...', fill=False, edgecolor="#6a5a48",
    linewidth=0, zorder=7, alpha=0.65)
ax.add_patch(far_gravel_hatch)
label((FAR_STEP_X_LEFT + FAR_STEP_X_RIGHT) / 2,
      FAR_STEP_GRAVEL_Y1 + 0.22,
      "4\" compacted #57 gravel pad\n(outside deck footprint — beyond y=16'-3\")",
      fs=5.5, bold=False, color="#6a5a48", ha="center", zorder=8)

# ── Doubled 2×6 PT ribbon ────────────────────────────────────────────────────
RIBBON_T   = 2 * (1.5/12)
RIBBON_Y0  = fas_y_v
RIBBON_Y1  = RIBBON_Y0 + RIBBON_T
far_ribbon = FancyBboxPatch(
    (FAR_STEP_X_LEFT, RIBBON_Y0),
    FAR_STEP_X_RIGHT - FAR_STEP_X_LEFT,
    RIBBON_T,
    boxstyle="square,pad=0",
    facecolor=C_FAR_RIBBON, edgecolor=EC_FAR_RIBBON,
    linewidth=2.0, zorder=13)
ax.add_patch(far_ribbon)
label((FAR_STEP_X_LEFT + FAR_STEP_X_RIGHT) / 2, RIBBON_Y0 + RIBBON_T/2,
      "Doubled 2×6 PT SYP ribbon — lag-bolted to outer rim/drop-board",
      fs=5.5, bold=True, color="white", ha="center", zorder=14)

# ── Two MoistureShield tread planks ──────────────────────────────────────────
for i in range(2):
    tread_x0 = FAR_STEP_X_LEFT
    tread_y0 = RIBBON_Y1 + i * (PLANK_W + PLANK_GAP)
    tread_len = FAR_STEP_X_RIGHT - FAR_STEP_X_LEFT
    tr_far = FancyBboxPatch(
        (tread_x0, tread_y0),
        tread_len,
        PLANK_W,
        boxstyle="square,pad=0",
        facecolor=C_FAR_TREAD, edgecolor=EC_FAR_TREAD,
        linewidth=0.8, zorder=13)
    ax.add_patch(tr_far)

tread_mid_y = RIBBON_Y1 + PLANK_W + PLANK_GAP/2
label((FAR_STEP_X_LEFT + FAR_STEP_X_RIGHT)/2, tread_mid_y,
      "2× MoistureShield Vision 5.4\" planks  |  10.9\" tread depth  |  ⊥ house  |  open riser  |  6\" AG",
      fs=5.8, bold=True, color=EC_FAR_TREAD, ha="center", zorder=15)

# ── 5 Precast concrete deck blocks ────────────────────────────────────────────
far_tread_outer_y = RIBBON_Y1 + 2 * PLANK_W + PLANK_GAP
block_y0 = far_tread_outer_y + 0.05

for bx in FAR_BLOCK_X:
    b = FancyBboxPatch(
        (bx - FAR_BLOCK_SZ/2, block_y0),
        FAR_BLOCK_SZ,
        FAR_BLOCK_SZ,
        boxstyle="square,pad=0",
        facecolor=C_FAR_BLOCK, edgecolor=EC_FAR_BLOCK,
        linewidth=1.5, zorder=14)
    ax.add_patch(b)

label((FAR_STEP_X_LEFT + FAR_STEP_X_RIGHT)/2,
      block_y0 + FAR_BLOCK_SZ + 0.22,
      "5× precast concrete deck blocks (12\"×12\") @ ≈28\" OC on #57 gravel pad",
      fs=5.5, bold=True, color="#444444", ha="center", zorder=15)

ax.annotate("", xy=(FAR_BLOCK_X[0], block_y0 + FAR_BLOCK_SZ + 0.10),
            xytext=(FAR_BLOCK_X[1], block_y0 + FAR_BLOCK_SZ + 0.10),
            arrowprops=dict(arrowstyle="<->", color="#555555", lw=0.9))
label((FAR_BLOCK_X[0] + FAR_BLOCK_X[1])/2, block_y0 + FAR_BLOCK_SZ + 0.35,
      "~28\" OC", fs=5.5, bold=False, color="#555555", ha="center")

# ── Dimension annotations: far-edge step ─────────────────────────────────────
ann_y_far = FAR_STEP_GRAVEL_Y1 + 0.55
ax.annotate("", xy=(FAR_STEP_X_LEFT, ann_y_far), xytext=(FAR_STEP_X_RIGHT, ann_y_far),
            arrowprops=dict(arrowstyle="<->", color="#2244aa", lw=1.3))
label((FAR_STEP_X_LEFT + FAR_STEP_X_RIGHT)/2, ann_y_far + 0.30,
      "11'-9\" far-edge step (right corner → midpoint)",
      fs=7.0, bold=True, color="#2244aa", ha="center")

step_depth_ann_x = FAR_STEP_X_RIGHT + 0.5
ax.annotate("", xy=(step_depth_ann_x, OVERALL_D),
            xytext=(step_depth_ann_x, far_tread_outer_y),
            arrowprops=dict(arrowstyle="<->", color="#2244aa", lw=1.1))
label(step_depth_ann_x + 0.55, (OVERALL_D + far_tread_outer_y)/2,
      "10.9\"\ntread\ndepth",
      fs=6.0, bold=True, color="#2244aa", rotation=90, ha="center")

# ── Seasonal heave callout ────────────────────────────────────────────────────
heave_callout_x = FAR_STEP_X_LEFT - 3.0
heave_callout_y = OVERALL_D + 0.1
heave_callout_w = 8.2
heave_callout_h = 1.5
rect(heave_callout_x, heave_callout_y, heave_callout_w, heave_callout_h,
     "#fff0e0", "#cc4400", lw=1.8, zorder=16)
label(heave_callout_x + heave_callout_w/2, heave_callout_y + 0.28,
      "SEASONAL HEAVE NOTE (Hollis): shallow precast blocks WILL heave 1/4-1/2\" per cycle.",
      fs=6.2, bold=True, color="#8B0000", ha="center", zorder=17)
label(heave_callout_x + heave_callout_w/2, heave_callout_y + 0.62,
      "This is a decorative/convenience step, NOT frost-depth founded.",
      fs=6.0, bold=False, color="#555500", ha="center", zorder=17)
label(heave_callout_x + heave_callout_w/2, heave_callout_y + 0.95,
      "Homeowner has accepted this trade-off. Tiger Claw TC-G or Cortex fasteners",
      fs=6.0, bold=False, color="#555500", ha="center", zorder=17)
label(heave_callout_x + heave_callout_w/2, heave_callout_y + 1.28,
      "match main deck spec. Step is separate from and does not affect left-edge stair.",
      fs=6.0, bold=False, color="#555500", ha="center", zorder=17)

# ── Open riser indicator for far-edge step ────────────────────────────────────
ax.annotate("OPEN RISER\n(no riser board)",
            xy=((FAR_STEP_X_LEFT + FAR_STEP_X_RIGHT)/2, OVERALL_D + FAR_TREAD_DEPTH * 0.4),
            xytext=((FAR_STEP_X_LEFT + FAR_STEP_X_RIGHT)/2 + 3.5, OVERALL_D + FAR_TREAD_DEPTH * 0.4),
            fontsize=5.5, ha="left", color="#884400", fontweight="bold",
            arrowprops=dict(arrowstyle="->", color="#884400", lw=0.9),
            zorder=17, clip_on=False)

# ══════════════════════════════════════════════════════════════════════════════
# ══ FOREGROUND: DECKING — x-direction (parallel to house) ════════════════════
# ══════════════════════════════════════════════════════════════════════════════
# v17: planks run x-direction (parallel to house)
# Each row = TWO 11'-9" half-planks butting against the center breaker board.
# Left half:  FIELD_X0  →  BREAKER_X0
# Right half: BREAKER_X1 → FIELD_X1
# The breaker board occupies [BREAKER_X0, BREAKER_X1] in framing coords.

# Draw field planks (split at breaker)
for i in range(NUM_PLANKS):
    y_bot = FIELD_Y0 + i * PLANK_STEP
    if y_bot + PLANK_W > FIELD_Y1 + 0.01:
        break
    # Left half plank (house side to left edge of breaker)
    rect(FIELD_X0, y_bot, BREAKER_X0 - FIELD_X0, PLANK_W,
         C_FIELD, EC_FIELD, lw=0.5, zorder=7)
    # Right half plank (right edge of breaker to far side)
    rect(BREAKER_X1, y_bot, FIELD_X1 - BREAKER_X1, PLANK_W,
         C_FIELD, EC_FIELD, lw=0.5, zorder=7)

# Center BREAKER BOARD — same color as PF stock, runs y-direction
# Drawn OVER field planks (higher zorder)
rect(BREAKER_X0, FIELD_Y0, PF_W, FIELD_Y1 - FIELD_Y0,
     C_BREAKER, EC_BREAKER, lw=2.0, zorder=9)

# Breaker board callout
ax.annotate(
    "CENTER DIVIDER\n(BREAKER BOARD)\nMoistureShield Vision\n5.4\" x 16'-0\"\ny-direction\nButt joint on both sides",
    xy=(BREAKER_CL_X, FIELD_Y0 + 3.0),
    xytext=(BREAKER_CL_X + 3.2, FIELD_Y0 + 1.5),
    fontsize=6.2, ha="left", color=EC_PF_TREX, fontweight="bold",
    arrowprops=dict(arrowstyle="->", color=EC_PF_TREX, lw=1.2),
    zorder=20, clip_on=False,
    bbox=dict(boxstyle="round,pad=0.3", facecolor="#f5ead8", edgecolor=EC_PF_TREX, lw=1.5))

# Plank labels (count every ~10 planks)
labeled_planks_v17 = list(range(0, NUM_PLANKS, max(1, NUM_PLANKS // 5)))
labeled_planks_v17.append(NUM_PLANKS - 1)
for i in labeled_planks_v17:
    y_ctr = FIELD_Y0 + i * PLANK_STEP + PLANK_W / 2
    if y_ctr > FIELD_Y1:
        break
    # Label on left half
    label(FIELD_X0 + (BREAKER_X0 - FIELD_X0) * 0.25, y_ctr,
          f"{i+1}",
          fs=4.8, bold=True, color="#4a2a08", zorder=10)

# Decking direction label
label(FIELD_X0 - 0.35, FIELD_Y0 + FIELD_DEPTH_FT / 2,
      f"← {NUM_PLANKS} rows →\n2x 11'-9\" halves\n5.4\" ea. + 1/8\" gap\n∥ house\nButt at breaker",
      fs=6.5, ha="right", bold=True, color="#4a2a08", zorder=10)

# ── Picture-frame boards ──────────────────────────────────────────────────────
HOUSE_PF_X0 = -PF_OVR
HOUSE_PF_X1 = OVERALL_W - PF_OVR
HOUSE_PF_Y0 = 0.0
HOUSE_PF_Y1 = PF_W

FAR_PF_X0 = -PF_OVR
FAR_PF_X1 = OVERALL_W - PF_OVR
FAR_PF_Y0 = FRAME_D + PF_OVR - PF_W
FAR_PF_Y1 = FRAME_D + PF_OVR   # = OVERALL_D

lx = -PF_OVR - FASCIA_T
LEFT_PF_X0 = lx - PF_W
LEFT_PF_X1 = lx

rx = FRAME_W + FASCIA_T
RIGHT_PF_X0 = rx
RIGHT_PF_X1 = rx + PF_W

# House-side PF
rect(HOUSE_PF_X0, HOUSE_PF_Y0, HOUSE_PF_X1 - HOUSE_PF_X0, PF_W,
     C_PF_TREX, EC_PF_TREX, lw=1.5, zorder=8)
label((HOUSE_PF_X0 + HOUSE_PF_X1)/2, HOUSE_PF_Y0 + PF_W/2,
      "HOUSE-SIDE PF — 5.4\" MoistureShield Vision  |  23'-6\" long  |  Butted at house wall  |  Butted corners (inside)",
      fs=5.8, bold=True, color="#3a1a00", zorder=11)

# Far-side PF
rect(FAR_PF_X0, FAR_PF_Y0, FAR_PF_X1 - FAR_PF_X0, PF_W,
     C_PF_TREX, EC_PF_TREX, lw=1.5, zorder=8)
label((FAR_PF_X0 + FAR_PF_X1)/2, FAR_PF_Y0 + PF_W/2,
      "FAR-SIDE PF — 5.4\" MoistureShield Vision  |  23'-6\" long  |  MITERED corners (outside) <- 45 deg",
      fs=5.8, bold=True, color="#3a1a00", zorder=11)

# LEFT PF — interrupted at step opening y=6'-0" to y=9'-6"
rect(LEFT_PF_X0, 0.0, PF_W, STEP_Y0,
     C_PF_TREX, EC_PF_TREX, lw=1.5, zorder=8)

left_pf_seg2_verts = np.array([
    [LEFT_PF_X0, STEP_Y1     ],
    [LEFT_PF_X1, STEP_Y1     ],
    [LEFT_PF_X1, FAR_PF_Y0   ],
    [LEFT_PF_X0, FAR_PF_Y1   ],
])
left_pf_seg2 = MplPolygon(left_pf_seg2_verts,
                            closed=True,
                            facecolor=C_PF_TREX, edgecolor=EC_PF_TREX,
                            linewidth=1.5, zorder=8)
ax.add_patch(left_pf_seg2)

label(LEFT_PF_X0 + PF_W/2, STEP_Y0/2,
      "LEFT PF\n5.4\"\nMoistureShield",
      fs=4.8, bold=True, color="#3a1a00", rotation=90, zorder=11)
label(LEFT_PF_X0 + PF_W/2, STEP_Y1 + (FAR_PF_Y0 - STEP_Y1)/2,
      "LEFT PF\n5.4\"",
      fs=4.8, bold=True, color="#3a1a00", rotation=90, zorder=11)

# RIGHT PF — full mitered polygon
right_pf_verts = np.array([
    [RIGHT_PF_X1, 0.0       ],
    [RIGHT_PF_X0, 0.0       ],
    [RIGHT_PF_X0, FAR_PF_Y0 ],
    [RIGHT_PF_X1, FAR_PF_Y1 ],
])
right_pf_poly = MplPolygon(right_pf_verts,
                            closed=True,
                            facecolor=C_PF_TREX, edgecolor=EC_PF_TREX,
                            linewidth=1.5, zorder=8)
ax.add_patch(right_pf_poly)
label(RIGHT_PF_X0 + PF_W/2, (0.0 + FAR_PF_Y0)/2,
      "RIGHT PF\n5.4\" MoistureShield\n16'-3\" long",
      fs=5.3, bold=True, color="#3a1a00", rotation=90, zorder=11)

# Miter seam lines
miter_lw = 2.5
miter_color = EC_PF_TREX

ax.plot([LEFT_PF_X1, LEFT_PF_X0],
        [FAR_PF_Y0,  FAR_PF_Y1],
        color=miter_color, lw=miter_lw, zorder=12, solid_capstyle='round')

ax.plot([RIGHT_PF_X0, RIGHT_PF_X1],
        [FAR_PF_Y0,   FAR_PF_Y1],
        color=miter_color, lw=miter_lw, zorder=12, solid_capstyle='round')

# Miter corner labels
label(LEFT_PF_X0 - 0.25, FAR_PF_Y1 + 0.20,
      "Outside corner\n45 deg miter",
      fs=5.5, bold=True, color="#5a1a00", ha="center", zorder=12)
ax.annotate("", xy=(LEFT_PF_X0 + 0.05, FAR_PF_Y1 - 0.08),
            xytext=(LEFT_PF_X0 - 0.25, FAR_PF_Y1 + 0.12),
            arrowprops=dict(arrowstyle="->", color="#5a1a00", lw=0.9))

label(RIGHT_PF_X1 + 0.25, FAR_PF_Y1 + 0.20,
      "Outside corner\n45 deg miter",
      fs=5.5, bold=True, color="#5a1a00", ha="center", zorder=12)
ax.annotate("", xy=(RIGHT_PF_X1 - 0.05, FAR_PF_Y1 - 0.08),
            xytext=(RIGHT_PF_X1 + 0.25, FAR_PF_Y1 + 0.12),
            arrowprops=dict(arrowstyle="->", color="#5a1a00", lw=0.9))

label(LEFT_PF_X1 - 0.05, HOUSE_PF_Y1 + 0.12,
      "Inside corner\n(butted)",
      fs=5.0, color="#777777", ha="center", zorder=10)
label(RIGHT_PF_X0 + 0.05, HOUSE_PF_Y1 + 0.12,
      "Inside corner\n(butted)",
      fs=5.0, color="#777777", ha="center", zorder=10)

# ══════════════════════════════════════════════════════════════════════════════
# ══ DIMENSION ANNOTATIONS ════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════════════════════════════

# Overall 23'-6" (top)
ax.annotate("", xy=(-PF_OVR, -3.2), xytext=(OVERALL_W - PF_OVR, -3.2),
            arrowprops=dict(arrowstyle="<->", color="#000099", lw=1.6))
label(FRAME_W/2, -3.55, "23'-6\"  OVERALL FINISHED SURFACE  (PF outer edge to outer edge)",
      fs=10, bold=True, color="#000099")

# Framing 23'-0"
ax.annotate("", xy=(0.0, -2.7), xytext=(FRAME_W, -2.7),
            arrowprops=dict(arrowstyle="<->", color="#444444", lw=1.2))
label(FRAME_W/2, -2.45, "23'-0\"  framing footprint (rim outer edge)",
      fs=8, bold=False, color="#444444")

# Pier spacing (top annotation)
ax.annotate("", xy=(0.0, -1.9), xytext=(PIER_X[1], -1.9),
            arrowprops=dict(arrowstyle="<->", color="#333388", lw=1.1))
label(PIER_X[1]/2, -1.65, "7'-8\"  pier spacing (typ.)", fs=7.5, bold=True, color="#333388")

# Depth annotations (right side)
right_ann = RIGHT_PF_X1 + 0.9

# Deck overall 16'-3"
ax.annotate("", xy=(right_ann, 0.0), xytext=(right_ann, OVERALL_D),
            arrowprops=dict(arrowstyle="<->", color="#000099", lw=1.6))
label(right_ann + 0.6, OVERALL_D/2,
      "16'-3\"\nOVERALL\nDECK\n(PF outer\nto wall)",
      fs=8.5, bold=True, color="#000099", rotation=90)

# Patio total 16'-6"
patio_ann = right_ann + 1.6
ax.annotate("", xy=(patio_ann, 0.0), xytext=(patio_ann, PATIO_D),
            arrowprops=dict(arrowstyle="<->", color="#7a6a58", lw=1.2))
label(patio_ann + 0.6, PATIO_D/2,
      "16'-6\"\nPATIO\n(total)",
      fs=7.5, bold=False, color="#7a6a58", rotation=90)

# Joist segment A dimension
ax.annotate("", xy=(right_ann + 3.2, 0.0), xytext=(right_ann + 3.2, GIRDER_MID_Y),
            arrowprops=dict(arrowstyle="<->", color="#226633", lw=1.1))
label(right_ann + 3.8, GIRDER_MID_Y / 2,
      "8'-0\"\njoist\nseg A",
      fs=7.0, bold=True, color="#226633", rotation=90)

# Joist segment B dimension
ax.annotate("", xy=(right_ann + 3.2, GIRDER_MID_Y), xytext=(right_ann + 3.2, GIRDER_RIM_Y),
            arrowprops=dict(arrowstyle="<->", color="#226633", lw=1.1))
label(right_ann + 3.8, (GIRDER_MID_Y + GIRDER_RIM_Y) / 2,
      "8'-0\"\njoist\nseg B",
      fs=7.0, bold=True, color="#226633", rotation=90)

# Step y-position annotations on left side
ax.annotate("", xy=(LEFT_PF_X0 - 0.7, 0.0), xytext=(LEFT_PF_X0 - 0.7, STEP_Y0),
            arrowprops=dict(arrowstyle="<->", color="#2244aa", lw=1.0))
label(LEFT_PF_X0 - 0.95, STEP_Y0/2,
      "6'-0\"", fs=6.0, bold=True, color="#2244aa", rotation=90)

ax.plot([LEFT_PF_X0 - 0.5, LEFT_PF_X0], [STEP_Y0, STEP_Y0],
        color="#2244aa", lw=0.8, linestyle="--", zorder=4)
ax.plot([LEFT_PF_X0 - 0.5, LEFT_PF_X0], [STEP_Y1, STEP_Y1],
        color="#2244aa", lw=0.8, linestyle="--", zorder=4)

# Outer rim y-coordinate callout
ax.annotate("outer rim / outer-girder y=16'-0\"",
            xy=(FRAME_W/2, GIRDER_RIM_Y),
            xytext=(FRAME_W/2 + 5.5, GIRDER_RIM_Y - 0.5),
            fontsize=6.5, ha="left", color=EC_GIRDER, fontweight="bold",
            arrowprops=dict(arrowstyle="->", color=EC_GIRDER, lw=1.1),
            zorder=20, clip_on=False,
            bbox=dict(boxstyle="round,pad=0.2", facecolor="#fffff0", edgecolor=EC_GIRDER, lw=1.2))

# ── v17: CENTER DETAIL DIMENSIONS ────────────────────────────────────────────
# Dimension annotation: left PF edge to breaker centerline = 11'-9"
# In our axes: left PF outer edge = -PF_OVR; breaker CL (framing) = BREAKER_CL_X
# finish CL = BREAKER_CL_X + PF_OVR = 11.75 ft = 11'-9"
center_dim_y = -1.15   # above the top of the drawing
ax.annotate("", xy=(-PF_OVR, center_dim_y), xytext=(BREAKER_CL_X, center_dim_y),
            arrowprops=dict(arrowstyle="<->", color=EC_CENTER_JOIST, lw=1.4))
label((-PF_OVR + BREAKER_CL_X) / 2, center_dim_y - 0.28,
      "11'-9\"  (left PF edge → breaker CL)",
      fs=7.0, bold=True, color=EC_CENTER_JOIST)

ax.annotate("", xy=(BREAKER_CL_X, center_dim_y), xytext=(OVERALL_W - PF_OVR, center_dim_y),
            arrowprops=dict(arrowstyle="<->", color=EC_CENTER_JOIST, lw=1.4))
label((BREAKER_CL_X + OVERALL_W - PF_OVR) / 2, center_dim_y - 0.28,
      "11'-9\"  (breaker CL → right PF edge)",
      fs=7.0, bold=True, color=EC_CENTER_JOIST)

# Breaker width callout
ax.annotate(f"Breaker\n5.4\" wide",
            xy=(BREAKER_CL_X, center_dim_y + 0.08),
            xytext=(BREAKER_CL_X + 1.2, center_dim_y - 0.55),
            fontsize=5.8, ha="left", color=EC_BREAKER, fontweight="bold",
            arrowprops=dict(arrowstyle="->", color=EC_BREAKER, lw=0.9),
            zorder=25, clip_on=False)

# Center joist x=11'-6" framing tick
ax.plot([CENTER_JOIST_FRAMING_X, CENTER_JOIST_FRAMING_X],
        [-2.2, 0.0],
        color=EC_CENTER_JOIST, lw=1.0, linestyle=":", zorder=4)
label(CENTER_JOIST_FRAMING_X, -2.38,
      "x=11'-6\" framing\n(center joist)",
      fs=6.0, bold=True, color=EC_CENTER_JOIST, ha="center")

# ══════════════════════════════════════════════════════════════════════════════
# ══ LEFT-EDGE STAIR — SIDE ELEVATION INSET (unchanged from v14/v15) ══════════
# ══════════════════════════════════════════════════════════════════════════════
PX_EL = PX + 0.2
EL_Y0 = 19.5
EL_W  = PW - 0.4
EL_H  = 5.5

rect(PX_EL, EL_Y0, EL_W, EL_H, "#f8f8f0", "#446688", lw=2.0, zorder=20)
label(PX_EL + EL_W/2, EL_Y0 + 0.25,
      "LEFT-EDGE STAIR — SIDE ELEVATION (unchanged from v14)",
      fs=8.0, bold=True, color="#2244aa", ha="center", zorder=21)

EL_Y_GRADE  = EL_Y0 + EL_H - 0.8
EL_FT_SCALE = 2.2

def ag_to_py(ag_inches):
    return EL_Y_GRADE - (ag_inches / 12.0) * EL_FT_SCALE

EL_X_LEFT  = PX_EL + 0.5
EL_X_RIGHT = PX_EL + EL_W - 0.5
EL_STEP_W  = (EL_X_RIGHT - EL_X_LEFT) * 0.6

grade_py = ag_to_py(0)
mid_py   = ag_to_py(6)
deck_py  = ag_to_py(12)

EL_STRINGER_X0 = EL_X_LEFT + 0.3
EL_STRINGER_X1 = EL_STRINGER_X0 + EL_STEP_W

# Ground / gravel
gravel_el = FancyBboxPatch((EL_STRINGER_X0 - 0.2, grade_py),
                             EL_STEP_W + 0.4, EL_Y_GRADE - grade_py + 0.3,
                             boxstyle="square,pad=0",
                             facecolor=C_GRAVEL, edgecolor=EC_GRAVEL,
                             linewidth=1.2, zorder=21)
ax.add_patch(gravel_el)
paver_el = FancyBboxPatch((EL_STRINGER_X0, grade_py - 0.12),
                            0.4, 0.12,
                            boxstyle="square,pad=0",
                            facecolor=C_PAVER, edgecolor=EC_PAVER,
                            linewidth=1.2, zorder=22)
ax.add_patch(paver_el)
label(EL_STRINGER_X0 + 0.2, grade_py - 0.06,
      "paver", fs=4.5, color="#444444", ha="center", zorder=23)

tread1_depth = (10.8/12.0) * EL_FT_SCALE
tread2_depth = (16.0/12.0) * EL_FT_SCALE

stringer_verts = [
    (EL_STRINGER_X0, deck_py),
    (EL_STRINGER_X0 + tread1_depth, deck_py),
    (EL_STRINGER_X0 + tread1_depth, mid_py),
    (EL_STRINGER_X0 + tread2_depth, mid_py),
    (EL_STRINGER_X0 + tread2_depth, grade_py),
    (EL_STRINGER_X0, grade_py),
]
stringer_patch_el = MplPolygon(stringer_verts, closed=True,
                                facecolor=C_STRINGER, edgecolor=EC_STRINGER,
                                linewidth=2.0, zorder=24)
ax.add_patch(stringer_patch_el)

tread_t = (1.0/12.0) * EL_FT_SCALE
for i in range(2):
    tp_x0 = EL_STRINGER_X0 + i * (tread1_depth / 2)
    tp = FancyBboxPatch((tp_x0, mid_py - tread_t), tread1_depth / 2 - 0.02, tread_t,
                         boxstyle="square,pad=0",
                         facecolor=C_TREAD, edgecolor=EC_TREAD,
                         linewidth=1.0, zorder=25)
    ax.add_patch(tp)

deck_t = (1.0/12.0) * EL_FT_SCALE
deck_el = FancyBboxPatch((EL_STRINGER_X0 - 0.1, deck_py - deck_t),
                           tread1_depth + 0.2, deck_t,
                           boxstyle="square,pad=0",
                           facecolor=C_FIELD, edgecolor=EC_FIELD,
                           linewidth=1.0, zorder=25)
ax.add_patch(deck_el)

ax.plot([EL_STRINGER_X0 + tread1_depth, EL_STRINGER_X0 + tread1_depth],
        [deck_py, mid_py],
        color="#cc4400", lw=1.0, linestyle="--", zorder=26)
label(EL_STRINGER_X0 + tread1_depth + 0.05, (deck_py + mid_py)/2,
      "OPEN\nRISER", fs=4.5, bold=True, color="#cc4400", ha="left", zorder=27)

ax.plot([EL_STRINGER_X0 + tread2_depth, EL_STRINGER_X0 + tread2_depth],
        [mid_py, grade_py],
        color="#cc4400", lw=1.0, linestyle="--", zorder=26)
label(EL_STRINGER_X0 + tread2_depth + 0.05, (mid_py + grade_py)/2,
      "OPEN\nRISER", fs=4.5, bold=True, color="#cc4400", ha="left", zorder=27)

for ag_in, lbl_txt in [(12, "12\" AG\n(deck top)"), (6, "6\" AG\n(mid tread)"), (0, "0\" AG\n(grade)")]:
    py_pos = ag_to_py(ag_in)
    ax.plot([EL_STRINGER_X0 - 0.5, EL_STRINGER_X0 - 0.05], [py_pos, py_pos],
            color="#444488", lw=0.8, linestyle=":", zorder=24)
    label(EL_STRINGER_X0 - 0.55, py_pos, lbl_txt, fs=5.5, bold=True, color="#2244aa",
          ha="right", va="center", zorder=28)

ax.annotate("", xy=(EL_STRINGER_X0 - 0.25, deck_py),
            xytext=(EL_STRINGER_X0 - 0.25, mid_py),
            arrowprops=dict(arrowstyle="<->", color="#666666", lw=0.9))
label(EL_STRINGER_X0 - 0.25, (deck_py + mid_py)/2,
      "6\"", fs=5.5, bold=True, color="#444444", ha="right", zorder=28)

ax.annotate("", xy=(EL_STRINGER_X0 - 0.25, mid_py),
            xytext=(EL_STRINGER_X0 - 0.25, grade_py),
            arrowprops=dict(arrowstyle="<->", color="#666666", lw=0.9))
label(EL_STRINGER_X0 - 0.25, (mid_py + grade_py)/2,
      "6\"", fs=5.5, bold=True, color="#444444", ha="right", zorder=28)

ax.annotate("", xy=(EL_STRINGER_X0, grade_py + 0.12),
            xytext=(EL_STRINGER_X0 + tread1_depth, grade_py + 0.12),
            arrowprops=dict(arrowstyle="<->", color="#774400", lw=0.9))
label(EL_STRINGER_X0 + tread1_depth/2, grade_py + 0.25,
      "10.8\"", fs=5.5, bold=True, color="#774400", ha="center", zorder=28)

label(PX_EL + EL_W/2, EL_Y0 + EL_H - 0.25,
      "2 risers @ 6\" each | OPEN risers (no riser board) | 3 PT 2×10 stringers",
      fs=5.5, bold=False, color="#333333", ha="center", zorder=28)

# ══════════════════════════════════════════════════════════════════════════════
# ══ FAR-EDGE STEP — SIDE ELEVATION INSET (unchanged from v14/v15) ═════════════
# ══════════════════════════════════════════════════════════════════════════════
FAR_EL_X  = PX + 0.2
FAR_EL_Y0 = 14.5
FAR_EL_W  = PW - 0.4
FAR_EL_H  = 4.5

rect(FAR_EL_X, FAR_EL_Y0, FAR_EL_W, FAR_EL_H, "#f8f8f0", "#2a6a2a", lw=2.0, zorder=20)
label(FAR_EL_X + FAR_EL_W/2, FAR_EL_Y0 + 0.25,
      "FAR-EDGE STEP — SIDE ELEVATION (unchanged from v14)",
      fs=8.0, bold=True, color="#2a6a2a", ha="center", zorder=21)

FAR_EL_GRADE  = FAR_EL_Y0 + FAR_EL_H - 0.7
FAR_EL_SCALE  = 1.8

def far_ag_to_py(ag_inches):
    return FAR_EL_GRADE - (ag_inches / 12.0) * FAR_EL_SCALE

FAR_EL_X0 = FAR_EL_X + 0.6
FAR_EL_X1 = FAR_EL_X + FAR_EL_W - 0.3
FAR_TREAD_W_PLOT = (FAR_TREAD_DEPTH) * FAR_EL_SCALE

far_deck_py  = far_ag_to_py(12)
far_tread_py = far_ag_to_py(6)
far_grade_py = far_ag_to_py(0)

far_gravel_el = FancyBboxPatch(
    (FAR_EL_X0 - 0.1, far_grade_py),
    FAR_EL_X1 - FAR_EL_X0 + 0.2,
    FAR_EL_GRADE - far_grade_py + 0.2,
    boxstyle="square,pad=0",
    facecolor=C_FAR_GRAVEL, edgecolor=EC_FAR_GRAVEL,
    linewidth=1.2, zorder=21)
ax.add_patch(far_gravel_el)
far_block_el = FancyBboxPatch(
    (FAR_EL_X0 + 0.1, far_grade_py - 0.12),
    0.45, 0.12,
    boxstyle="square,pad=0",
    facecolor=C_FAR_BLOCK, edgecolor=EC_FAR_BLOCK,
    linewidth=1.2, zorder=22)
ax.add_patch(far_block_el)
label(FAR_EL_X0 + 0.33, far_grade_py - 0.06,
      "precast\nblock", fs=4.2, color="#444444", ha="center", zorder=23)

ribbon_py = far_deck_py
ribbon_h  = (3.0/12) * FAR_EL_SCALE
ribbon_el = FancyBboxPatch(
    (FAR_EL_X0, ribbon_py - ribbon_h),
    (1.5/12) * FAR_EL_SCALE,
    ribbon_h,
    boxstyle="square,pad=0",
    facecolor=C_FAR_RIBBON, edgecolor=EC_FAR_RIBBON,
    linewidth=1.5, zorder=24)
ax.add_patch(ribbon_el)
label(FAR_EL_X0 + (1.5/12) * FAR_EL_SCALE / 2, ribbon_py - ribbon_h / 2,
      "ribbon", fs=4.2, color="white", ha="center", zorder=25)

for i in range(2):
    tp_y0 = far_tread_py - (i+1) * (1.0/12.0) * FAR_EL_SCALE
    tp_far = FancyBboxPatch(
        (FAR_EL_X0 + (1.5/12) * FAR_EL_SCALE, tp_y0),
        FAR_TREAD_W_PLOT,
        (1.0/12.0) * FAR_EL_SCALE,
        boxstyle="square,pad=0",
        facecolor=C_FAR_TREAD, edgecolor=EC_FAR_TREAD,
        linewidth=1.0, zorder=24)
    ax.add_patch(tp_far)

deck_t_far = (1.0/12.0) * FAR_EL_SCALE
deck_el_far = FancyBboxPatch(
    (FAR_EL_X0 - 0.15, far_deck_py - deck_t_far),
    FAR_TREAD_W_PLOT + 0.3, deck_t_far,
    boxstyle="square,pad=0",
    facecolor=C_FIELD, edgecolor=EC_FIELD,
    linewidth=1.0, zorder=24)
ax.add_patch(deck_el_far)

ax.plot([FAR_EL_X0 + (1.5/12) * FAR_EL_SCALE + FAR_TREAD_W_PLOT,
         FAR_EL_X0 + (1.5/12) * FAR_EL_SCALE + FAR_TREAD_W_PLOT],
        [far_deck_py, far_tread_py],
        color="#cc4400", lw=1.0, linestyle="--", zorder=26)
label(FAR_EL_X0 + (1.5/12) * FAR_EL_SCALE + FAR_TREAD_W_PLOT + 0.05,
      (far_deck_py + far_tread_py)/2,
      "OPEN\nRISER", fs=4.5, bold=True, color="#cc4400", ha="left", zorder=27)

for ag_in, lbl_txt in [(12, "12\" AG\n(deck)"), (6, "6\" AG\n(tread)"), (0, "0\" AG\n(grade)")]:
    py_pos = far_ag_to_py(ag_in)
    ax.plot([FAR_EL_X0 - 0.5, FAR_EL_X0 - 0.05], [py_pos, py_pos],
            color="#444488", lw=0.8, linestyle=":", zorder=24)
    label(FAR_EL_X0 - 0.55, py_pos, lbl_txt, fs=5.0, bold=True, color="#2a6a2a",
          ha="right", va="center", zorder=28)

ax.annotate("", xy=(FAR_EL_X0 - 0.2, far_deck_py),
            xytext=(FAR_EL_X0 - 0.2, far_tread_py),
            arrowprops=dict(arrowstyle="<->", color="#666666", lw=0.9))
label(FAR_EL_X0 - 0.2, (far_deck_py + far_tread_py)/2,
      "6\"", fs=5.0, bold=True, color="#444444", ha="right", zorder=28)

ax.annotate("", xy=(FAR_EL_X0 + (1.5/12) * FAR_EL_SCALE, far_grade_py + 0.1),
            xytext=(FAR_EL_X0 + (1.5/12) * FAR_EL_SCALE + FAR_TREAD_W_PLOT, far_grade_py + 0.1),
            arrowprops=dict(arrowstyle="<->", color="#774400", lw=0.9))
label(FAR_EL_X0 + (1.5/12) * FAR_EL_SCALE + FAR_TREAD_W_PLOT/2,
      far_grade_py + 0.25,
      "10.9\"", fs=5.0, bold=True, color="#774400", ha="center", zorder=28)

label(FAR_EL_X + FAR_EL_W/2, FAR_EL_Y0 + FAR_EL_H - 0.22,
      "1 riser @ 6\" | OPEN riser | doubled 2x6 PT ribbon | 5 precast blocks @ 28\" OC",
      fs=5.3, bold=False, color="#333333", ha="center", zorder=28)

# ══════════════════════════════════════════════════════════════════════════════
# RIGHT-SIDE PANEL — Title block and legend
# ══════════════════════════════════════════════════════════════════════════════
panel_box(-5.2, 6.5, fc="#f5f5f5")
title_lines = [
    "West Hartford Deck — v17 (Proposed) — Center Joist + Breaker Divider",
    "23'-6\" × 16'-3\"  Overall Finished Surface  (patio = 23'-6\" × 16'-6\")",
    "MoistureShield Vision  |  Decking ∥ House  |  4-Side Picture Frame + Center Breaker",
    "L-edge step: 42\" wide @ 6'-0\" | Far-edge step: 11'-9\" @ right corner",
    "House on 23'-6\" Edge  NORTH",
    "",
    "Scale: 1\" = 1 ft (plot units = ft)",
    "HOUSE = top edge",
    "",
    "Date: 2026-05-09",
    "Gemma — Technical Diagramming Specialist",
    "(v17: v16 + center joist x=11'-6\" framing + center breaker divider;",
    " decking 2x 11'-9\" halves per row; butted at breaker both sides)",
]
for i, line in enumerate(title_lines):
    fw = "bold" if i < 5 else "normal"
    fs = 8.0 if i == 0 else 7.0
    label(PX + PW/2, -5.0 + i * 0.48, line, fs=fs, bold=(fw == "bold"))

# ── Framing summary box ────────────────────────────────────────────────────────
panel_box(1.5, 6.5, fc="#eef5ff", ec="#336699", lw=2.5)
label(PX + PW/2, 1.75, "v17 FRAMING SUMMARY", fs=9.5, bold=True, color="#1a3366")

framing_lines = [
    ("Footprint:", "23'-6\" × 16'-3\" overall (PF outer to PF outer)"),
    ("Framing:", "23'-0\" × 16'-0\""),
    ("Ledger:", "Full-width at y=0, x-direction"),
    ("Mid-girder:", "Doubled 2×10 PT SYP | y=8'-0\" | 23'-0\" long"),
    ("Outer-rim girder:", "Doubled 2×10 PT SYP | y=16'-0\" | 23'-0\" long"),
    ("Pier saddle:", "Pylex 10555 (3.5\" saddle) + shims — fits doubled 2×10"),
    ("Piers:", "8 total (4 per girder) @ x=0, 7'-8\", 15'-4\", 23'-0\""),
    ("Pier span:", "7'-8\" (within DCA-6 limit of 8'-9\" at 8'-0\" joist span)"),
    ("Joists:", "24 × 2×10 PT SYP @ 12\" o.c. | y-direction | 2 seg PLUS center joist"),
    ("Center joist:", "2×10 PT | x=11'-6\" framing (x=11'-9\" finish) | 2 segments"),
    ("Joist spans:", "8'-0\" each (seg A: ledger to mid-girder; seg B: mid to rim)"),
    ("Center breaker:", "MoistureShield Vision 5.4\" x 16'-0\" | y-direction | x=11'-9\" finish"),
    ("Decking:", "MoistureShield Vision 5.4\" | ∥ house | 2x 11'-9\" halves per row"),
    ("Stock:", "~72 x 12-ft planks cut to 11'-9\" (left & right halves)"),
]
for i, (lbl_a, lbl_b) in enumerate(framing_lines):
    y_row = 2.2 + i * 0.36
    bold_row = "Piers:" in lbl_a or "Joists:" in lbl_a or "girder:" in lbl_a
    label(PX + 0.08, y_row, lbl_a, fs=5.8, bold=True, ha="left",
          color="#1a3366" if bold_row else "#333333")
    label(PX + 1.9, y_row, lbl_b, fs=5.8, bold=False, ha="left",
          color="#224488" if bold_row else "#444444")

# ── Legend ─────────────────────────────────────────────────────────────────────
panel_box(8.2, 8.3, fc="white")
label(PX + PW/2, 8.45, "LEGEND — v17", fs=10.0, bold=True)

y_leg = 9.05
rect(PX + 0.08, y_leg, 0.60, 0.40, C_FIELD, EC_FIELD, lw=1.0, zorder=3)
label(PX + 0.78, y_leg + 0.09, "Field plank — 5.4\" MoistureShield Vision (composite, capped)", fs=6.8, bold=True, ha="left")
label(PX + 0.78, y_leg + 0.26, "Runs parallel to house (x-direction) | Butt joint @ x=11'-6\" over joist", fs=5.8, ha="left", color="#444444")

y_leg = 9.85
rect(PX + 0.08, y_leg, 0.60, 0.40, C_PF_TREX, EC_PF_TREX, lw=1.5, zorder=3)
label(PX + 0.78, y_leg + 0.09, "Picture-frame (PF) — 5.4\" MoistureShield Vision, all 4 sides", fs=6.8, bold=True, ha="left")
label(PX + 0.78, y_leg + 0.26, "L-side PF interrupted at L-edge step opening (y=6'-0\" to y=9'-6\")", fs=5.8, ha="left", color="#444444")

y_leg = 10.65
rect(PX + 0.08, y_leg, 0.60, 0.40, C_GIRDER, EC_GIRDER, lw=2.5, zorder=3, alpha=0.9)
label(PX + 0.78, y_leg + 0.09, "Girder — Doubled 2×10 PT SYP | x-direction | 2 girder lines", fs=6.8, bold=True, ha="left")
label(PX + 0.78, y_leg + 0.26, "Mid @ y=8'-0\", Outer-rim @ y=16'-0\" | Fits Pylex 3.5\" saddle", fs=5.8, ha="left", color="#444444")

y_leg = 11.45
rect(PX + 0.08, y_leg, 0.60, 0.40, C_JOIST, EC_JOIST, lw=1.5, zorder=3)
label(PX + 0.78, y_leg + 0.09, "Joist — 2×10 PT SYP | y-direction | 24 joists @ 12\" o.c.", fs=6.8, bold=True, ha="left")
label(PX + 0.78, y_leg + 0.26, "2 segments each | face-hung to ledger, mid-girder, outer-rim", fs=5.8, ha="left", color="#444444")

y_leg = 12.25
circ = plt.Circle((PX + 0.38, y_leg + 0.20), 0.18, fc=C_PIER, ec=EC_PIER, lw=1.5, zorder=3)
ax.add_patch(circ)
label(PX + 0.78, y_leg + 0.09, "Pylex 50 helical pier + 10555 saddle — 8 total", fs=6.8, bold=True, ha="left")
label(PX + 0.78, y_leg + 0.26, "4 per girder line @ 7'-8\" spacing | x=0, 7'-8\", 15'-4\", 23'-0\"", fs=5.8, ha="left", color="#444444")

y_leg = 13.05
rect(PX + 0.08, y_leg, 0.60, 0.40, C_CENTER_JOIST, EC_CENTER_JOIST, lw=2.5, zorder=3)
label(PX + 0.78, y_leg + 0.09, "CENTER JOIST (v17 new) — 2x10 PT | x=11'-6\" framing", fs=6.8, bold=True, ha="left", color=EC_CENTER_JOIST)
label(PX + 0.78, y_leg + 0.26, "Between 11'-0\" and 12'-0\" joists | hangers at ledger, mid-girder, outer-rim", fs=5.8, ha="left", color="#444444")

y_leg = 13.85
rect(PX + 0.08, y_leg, 0.60, 0.40, C_BREAKER, EC_BREAKER, lw=2, zorder=3)
label(PX + 0.78, y_leg + 0.09, "CENTER BREAKER (v17 new) — MoistureShield Vision 5.4\"", fs=6.8, bold=True, ha="left", color=EC_PF_TREX)
label(PX + 0.78, y_leg + 0.26, "Runs y-direction @ x=11'-9\" finish | 16'-0\" long | PF stock", fs=5.8, ha="left", color="#444444")

y_leg = 14.65
rect(PX + 0.08, y_leg, 0.60, 0.40, C_STRINGER, EC_STRINGER, lw=2, zorder=3)
label(PX + 0.78, y_leg + 0.09, "L-edge stair stringer — 2×10 PT cut stringer (3 total)", fs=6.8, bold=True, ha="left")
label(PX + 0.78, y_leg + 0.26, "Attached to left rim via Simpson LSCZ stringer hangers", fs=5.8, ha="left", color="#444444")

y_leg = 15.45
rect(PX + 0.08, y_leg, 0.60, 0.40, C_FAR_RIBBON, EC_FAR_RIBBON, lw=2, zorder=3)
label(PX + 0.78, y_leg + 0.09, "Far-edge step ribbon — doubled 2×6 PT SYP", fs=6.8, bold=True, ha="left")
label(PX + 0.78, y_leg + 0.26, "Lag-bolted to outer rim face; 11'-9\" long, right corner to midpoint", fs=5.8, ha="left", color="#444444")

# ══════════════════════════════════════════════════════════════════════════════
# SAVE
# ══════════════════════════════════════════════════════════════════════════════
out_path = "/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/owner_inbox/deck_blueprint/deck_plan_v17.png"
fig.savefig(out_path, dpi=DPI, bbox_inches="tight", facecolor="white")
print(f"Saved: {out_path}")

out_pdf = "/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/owner_inbox/deck_blueprint/deck_plan_v17.pdf"
fig.savefig(out_pdf, bbox_inches="tight", facecolor="white")
print(f"Saved: {out_pdf}")

print(f"FRAME_W:            {FRAME_W:.4f} ft = {FRAME_W*12:.1f}\"")
print(f"FRAME_D:            {FRAME_D:.4f} ft = {FRAME_D*12:.1f}\"")
print(f"OVERALL_W:          {OVERALL_W:.4f} ft = {OVERALL_W*12:.1f}\" = 23'-6\"")
print(f"OVERALL_D:          {OVERALL_D:.4f} ft = {OVERALL_D*12:.2f}\" = 16'-3\"")
print(f"PATIO_D:            {PATIO_D:.4f} ft = {PATIO_D*12:.1f}\"")
print(f"Exposed patio strip:{(PATIO_D - OVERALL_D)*12:.2f}\"")
print(f"GIRDER_MID_Y:       {GIRDER_MID_Y:.4f} ft = {GIRDER_MID_Y*12:.1f}\"")
print(f"GIRDER_RIM_Y:       {GIRDER_RIM_Y:.4f} ft = {GIRDER_RIM_Y*12:.1f}\"")
print(f"PIER_X:             {[f'{x:.3f}' for x in PIER_X]}  ft")
print(f"PIER_X spacing:     {PIER_X_SPACING:.4f} ft = {PIER_X_SPACING*12:.2f}\" = 7'-{PIER_X_SPACING*12-7*12:.2f}\"")
print(f"Joist count:        {len(JOIST_X)} field joists + 1 center joist")
print(f"Field plank count:  {NUM_PLANKS} rows x 2 halves (11'-9\" each)")
print(f"CENTER_JOIST_X:     {CENTER_JOIST_FRAMING_X:.4f} ft = {CENTER_JOIST_FRAMING_X*12:.1f}\" framing")
print(f"BREAKER_CL_X:       {BREAKER_CL_X:.4f} ft = {BREAKER_CL_X*12:.1f}\" framing = {(BREAKER_CL_X+PF_OVR)*12:.1f}\" finish")
print(f"BREAKER_X0:         {BREAKER_X0:.4f} ft framing")
print(f"BREAKER_X1:         {BREAKER_X1:.4f} ft framing")
print(f"Left half plank:    {BREAKER_X0 - FIELD_X0:.4f} ft = {(BREAKER_X0 - FIELD_X0)*12:.1f}\"")
print(f"Right half plank:   {FIELD_X1 - BREAKER_X1:.4f} ft = {(FIELD_X1 - BREAKER_X1)*12:.1f}\"")
print(f"FAR_PF_Y0:          {FAR_PF_Y0:.4f}  FAR_PF_Y1={OVERALL_D:.4f}")
