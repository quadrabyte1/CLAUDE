"""
render_v8.py  —  Gemma's matplotlib render of deck_plan v8  (Page 2: Decking Plan)
Produces deck_plan.png at >=2000 px wide, white background.

v8 adds the Trex decking layer on top of the v7 framing.
This script renders PAGE 2 (Decking Plan), which shows:
  - Framing at 40% opacity in background (all v7 elements)
  - Deck planks at full opacity on top:
      - 4-side picture-frame (PF) in Trex-tan (darker)
      - 48 field planks running ⊥ house (in depth/16' direction)
      - Mitered corners at the 2 outside corners (bottom-left, bottom-right)
      - Butted corners at the 2 inside corners (top-left, top-right against house)
  - Updated title block and legend for v8 / Page 2

Coordinate system (unchanged from v7):
  - X axis = 23 ft direction (along house wall, left→right)
  - Y axis = 16.25 ft direction (out from house, top→bottom)
  - House wall along the TOP of the drawing.
  - Y is inverted (ax.invert_yaxis) so y=0 plots at top.
All measurements in feet unless noted.

Plank math (verified):
  Field planks:
    Width: 5.5" = 0.4583 ft
    Gap: 1/8" = 0.01042 ft
    Effective spacing center-to-center: 5.625" = 0.46875 ft
    Length: 15'-7" = 187" (house-side PF outer edge y=5.5" to far-side PF inner edge y=198.5")
    Field area width: 22'-7" = 271" (framing 23'-0" minus 2 × 2.5" PF inboard overlap)
    Count: 271" / 5.625" = 48.18 → 48 planks (last spacing ~5.7" — acceptable)
  PF planks (all 5.5" wide = 0.4583 ft):
    House-side: 23'-6" long (overall width), y=0..5.5" from wall
    Far-side: 23'-6" long, y=16'-0.5"..16'-6" (3" cantilever past rim)
    Left-side: 16'-6" long (overall depth), x=-3"..2.5" (3" past rim left face)
    Right-side: symmetric
  Total boards: 48 field (16-ft) + 4 PF boards → ~52; +10% waste → order ~55
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.lines as mlines
import numpy as np
from matplotlib.patches import Polygon as MplPolygon, FancyBboxPatch, Rectangle

# ── Key dimensions ─────────────────────────────────────────────────────────────
FRAME_W    = 23.0           # framing width (along house), ft
FRAME_D    = 16.25          # framing depth (out from house) = 16'-3", ft
PF_W       = 5.5 / 12      # PF board width in ft = 0.4583 ft
FASCIA_T   = 0.75 / 12     # fascia thickness, ft
PF_OVR     = 3.0 / 12      # PF overhang past rim outer face (3" = 0.25 ft)
OVERALL_W  = FRAME_W + 2 * PF_OVR    # 23.5 ft = 23'-6"
OVERALL_D  = FRAME_D + PF_OVR        # 16.5 ft = 16'-6"

# Girder positions
GIRDER_X   = [0.0, 11.5, 23.0]
GIRDER_W   = 0.38

# Joist rows
JOIST_SPACING = 1.0
RIM_Y         = FRAME_D

# Pier positions
PIER_Y     = [1.0, 8.125, FRAME_D]

# ── Plank dimensions (all in feet) ────────────────────────────────────────────
PLANK_W    = 5.5 / 12       # 0.4583 ft (actual face width)
PLANK_GAP  = (1.0/8) / 12   # 0.01042 ft
PLANK_STEP = PLANK_W + PLANK_GAP  # 0.46875 ft (5.625" center-to-center)

# PF inboard overlap on each side = 2.5" = 0.2083 ft
PF_INBOARD = 2.5 / 12

# Field plank X range (inside of PF boards on both sides)
FIELD_X0   = PF_INBOARD              # 2.5" in from framing left rim = x=2.5"
FIELD_X1   = FRAME_W - PF_INBOARD    # 22'-9.5" from left — WAIT: right rim outer = 23'-0"; PF sits from x=22'-9.5" to x=23'-0"+3"
# Actually: field starts at right face of left-side PF's inboard edge
# Left-side PF occupies x = -3"..+2.5" → inner edge (right edge) at +2.5" = +PF_INBOARD
# Right-side PF occupies x = 22'-9.5"..23'-0"+3" → inner edge (left edge) at 22'-9.5"
FIELD_X0   = PF_INBOARD              # 2.5" = 0.2083 ft
FIELD_X1   = FRAME_W - PF_INBOARD    # 22'-9.5" = 22.7917 ft
FIELD_WIDTH_FT = FIELD_X1 - FIELD_X0   # 22'-7" = 22.5833 ft = 271"
NUM_PLANKS = 48

# Field plank Y range: from house-side PF outer edge (y=PF_W) to far-side PF inner edge
# House-side PF: y=0..PF_W (5.5") → outer edge at y=PF_W
# Far-side PF: sits y = (FRAME_D + PF_OVR - PF_W)..(FRAME_D + PF_OVR)
#   = 16'-0.5"..16'-6"
#   Inner (near) edge of far-side PF = FRAME_D + PF_OVR - PF_W = 16.0417 ft
FIELD_Y0   = PF_W                           # 5.5" = 0.4583 ft (inner edge of house-side PF)
FIELD_Y1   = FRAME_D + PF_OVR - PF_W       # far-side PF inner edge
FIELD_LEN  = FIELD_Y1 - FIELD_Y0           # 15'-7" in ft

# Verify field length in inches
_field_len_in = FIELD_LEN * 12
# FRAME_D=16.25 ft, PF_OVR=0.25 ft, PF_W=0.4583 ft
# FIELD_Y1 = 16.25 + 0.25 - 0.4583 = 16.0417 ft
# FIELD_Y0 = 0.4583 ft
# FIELD_LEN = 15.5833 ft = 187.0" = 15'-7"  ✓

# ── Canvas setup ───────────────────────────────────────────────────────────────
FIG_W_IN = 34
FIG_H_IN = 24
DPI = 100

fig, ax = plt.subplots(figsize=(FIG_W_IN, FIG_H_IN), dpi=DPI)
fig.patch.set_facecolor("white")
ax.set_facecolor("white")

ax.set_xlim(-4.5, 34.5)
ax.set_ylim(-4.5, 24.0)
ax.invert_yaxis()
ax.set_aspect("equal")
ax.axis("off")

# ── Color palette ──────────────────────────────────────────────────────────────
# Framing colors (same as v7 — drawn at reduced alpha for background)
C_HOUSE     = "#cccccc"
C_PATIO     = "#e8e0d4"
EC_PATIO    = "#a09080"
C_LEDGER    = "#f8cecc";  EC_LEDGER  = "#b85450"
C_GIRDER    = "#dae8fc";  EC_GIRDER  = "#6c8ebf"
C_JOIST     = "#d5e8d4";  EC_JOIST   = "#82b366"
C_RIM       = "#fff2cc";  EC_RIM     = "#d6b656"
C_PF_OLD    = "#ffe680";  EC_PF_OLD  = "#b8860b"  # v7 PF (hidden in page 2)
C_FASCIA    = "#c8a0e8";  EC_FASCIA  = "#7030a0"
C_PIER      = "#5a4030";  EC_PIER    = "#2a1808"
C_PIER_HOLE = "#b0a898";  EC_HOLE    = "#706050"
C_DROP      = "#c0d8b0";  EC_DROP    = "#507040"
C_BLOCK     = "#888888"
C_HANGER    = "#ff8c00"

# Trex decking colors (new for v8)
C_FIELD     = "#c9a778"   # Trex-tan field planks
EC_FIELD    = "#7a5a3a"   # field plank stroke
C_PF_TREX  = "#a07a4a"   # PF planks (slightly darker to distinguish)
EC_PF_TREX = "#5a3a1a"   # PF plank stroke
C_NOTE      = "#ffffee";  EC_NOTE    = "#888800"
C_CALLOUT   = "#fff9e6";  EC_CALLOUT = "#cc8800"

# Framing background alpha (page 2 — muted)
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

def panel_box(y0, h, fc="#f5f5f5", ec="#444444", lw=1.5):
    rect(PX, y0, PW, h, fc, ec, lw=lw, zorder=2)

# ══════════════════════════════════════════════════════════════════════════════
# ══ BACKGROUND: FRAMING LAYER (all v7 elements at FRAME_ALPHA opacity) ══════
# ══════════════════════════════════════════════════════════════════════════════

# ── Patio background ──────────────────────────────────────────────────────────
rect(-PF_OVR, 0.0, OVERALL_W, OVERALL_D - PF_OVR,
     C_PATIO, EC_PATIO, lw=2.5, zorder=1, alpha=0.40)
hatch_rect = Rectangle((-PF_OVR, 0.0), OVERALL_W, FRAME_D + PF_OVR,
                        hatch='....', fill=False, edgecolor="#c0b090",
                        linewidth=0, zorder=1, alpha=0.18)
ax.add_patch(hatch_rect)

label(-PF_OVR + OVERALL_W/2, FRAME_D/2 + 1.5,
      "EXISTING CONCRETE PATIO  (background — framing layer @ 40% opacity)",
      fs=6.5, bold=False, color="#9b7050", zorder=2, alpha=FRAME_ALPHA)

# ── House wall (background) ───────────────────────────────────────────────────
rect(-PF_OVR, -1.2, OVERALL_W, 1.1, C_HOUSE, "#444444", lw=2, zorder=3, alpha=FRAME_ALPHA)
label(FRAME_W/2, -0.65,
      "HOUSE WALL  ▲ NORTH  (23'-6\" overall edge)",
      fs=10, bold=True, alpha=FRAME_ALPHA)

# ── Girders (background) ──────────────────────────────────────────────────────
GHW = GIRDER_W / 2
for gx in GIRDER_X:
    x0 = max(0.0, gx - GHW)
    x0 = min(x0, FRAME_W - GIRDER_W)
    rect(x0, 0.0, GIRDER_W, FRAME_D, C_GIRDER, EC_GIRDER, lw=2, zorder=4, alpha=FRAME_ALPHA)

# ── Ledger (background) ───────────────────────────────────────────────────────
LEDGER_H = 0.18
rect(0.0, 0.0, FRAME_W, LEDGER_H, C_LEDGER, EC_LEDGER, lw=2.5, zorder=5, alpha=FRAME_ALPHA)

# ── Joist segments (background) ───────────────────────────────────────────────
SEG_A_X0 = GIRDER_X[0] + GHW
SEG_A_X1 = GIRDER_X[1] - GHW
SEG_B_X0 = GIRDER_X[1] + GHW
SEG_B_X1 = GIRDER_X[2] - GHW
JOIST_H = 0.085

all_rows = [(i * JOIST_SPACING, False) for i in range(1, 17)]
all_rows.append((RIM_Y, True))

for y_pos, is_rim in all_rows:
    h = JOIST_H * 2 if is_rim else JOIST_H
    fc = C_RIM if is_rim else C_JOIST
    ec = EC_RIM if is_rim else EC_JOIST
    lw = 2.0 if is_rim else 1.0
    rect(SEG_A_X0, y_pos - h/2, SEG_A_X1 - SEG_A_X0, h,
         fc, ec, lw=lw, zorder=3, alpha=FRAME_ALPHA)
    rect(SEG_B_X0, y_pos - h/2, SEG_B_X1 - SEG_B_X0, h,
         fc, ec, lw=lw, zorder=3, alpha=FRAME_ALPHA)

# ── Drop-board sub-fascia (background) ───────────────────────────────────────
DROP_T = 0.085
left_drop_x = -GHW - DROP_T
right_drop_x = GIRDER_X[2] + GHW
far_drop_y = RIM_Y + JOIST_H

rect(left_drop_x, 0.0, DROP_T, FRAME_D, C_DROP, EC_DROP, lw=2, zorder=5, alpha=FRAME_ALPHA)
rect(right_drop_x, 0.0, DROP_T, FRAME_D, C_DROP, EC_DROP, lw=2, zorder=5, alpha=FRAME_ALPHA)
rect(0.0, far_drop_y, FRAME_W, DROP_T, C_DROP, EC_DROP, lw=2, zorder=5, alpha=FRAME_ALPHA)

# ── Fascia (background) ───────────────────────────────────────────────────────
fas_y = far_drop_y + DROP_T
rect(0.0, fas_y, FRAME_W, FASCIA_T, C_FASCIA, EC_FASCIA, lw=2, zorder=6, alpha=FRAME_ALPHA)
rect(-FASCIA_T, 0.0, FASCIA_T, fas_y, C_FASCIA, EC_FASCIA, lw=2, zorder=6, alpha=FRAME_ALPHA)
rect(FRAME_W, 0.0, FASCIA_T, fas_y, C_FASCIA, EC_FASCIA, lw=2, zorder=6, alpha=FRAME_ALPHA)

# ── Piers (background) ────────────────────────────────────────────────────────
PIER_R  = 0.22
HOLE_R  = 0.35
for i, gx in enumerate(GIRDER_X):
    for j, py in enumerate(PIER_Y):
        hole = plt.Circle((gx, py), HOLE_R, fc=C_PIER_HOLE, ec=EC_HOLE,
                          lw=1.0, zorder=5, alpha=FRAME_ALPHA * 0.7)
        ax.add_patch(hole)
        pier = plt.Circle((gx, py), PIER_R, fc=C_PIER, ec=EC_PIER,
                          lw=1.5, zorder=8, alpha=FRAME_ALPHA)
        ax.add_patch(pier)

# ── Field blocking dashed lines (background) ──────────────────────────────────
for bx in [5.75, 17.25]:
    ax.plot([bx, bx], [1.0, FRAME_D],
            color=C_BLOCK, linewidth=2.0, linestyle="--",
            zorder=3, alpha=FRAME_ALPHA * 0.8)

# ══════════════════════════════════════════════════════════════════════════════
# ══ FOREGROUND: TREX DECK PLANKS ════════════════════════════════════════════
# ══════════════════════════════════════════════════════════════════════════════

# ── Picture-frame planks — draw FIRST so field sits on top at overlapping zones ──
# But PF sits on top of field at corners, so draw PF AFTER field. Actually PF
# is the border; field fills the interior (stops at PF inner edge). Draw order:
# PF first (zorder 8), field fills in behind (zorder 7) — no, field runs
# from FIELD_Y0 to FIELD_Y1 which is exactly the interior. Draw PF LAST (highest z).

# PLANK ZORDERS:
#  Field planks: zorder=7
#  PF planks: zorder=8 (on top of field at any overlap)
#  Labels: zorder=10

# ── 48 field planks ──────────────────────────────────────────────────────────
# Field planks run in the Y direction (⊥ house).
# Planks are 5.5" wide in the X direction, spaced 5.625" apart.
# First plank left edge at FIELD_X0; planks march rightward.
# Last plank starts at FIELD_X0 + 47 * PLANK_STEP.
# Check: 47 × 5.625" = 264.375"; plank ends at 264.375" + 5.5" = 269.875" < 271" ✓
# Remaining gap after plank 48: 271" - 269.875" = 1.125" — absorbed into gap after last plank.
# (Last gap is wider: 271 - 48×5.5 - 47×0.125 = 271 - 264 - 5.875 = 1.125" gap on right side)
# That's fine — slight clearance at right PF.

for i in range(NUM_PLANKS):
    x_left = FIELD_X0 + i * PLANK_STEP
    rect(x_left, FIELD_Y0, PLANK_W, FIELD_LEN,
         C_FIELD, EC_FIELD, lw=0.5, zorder=7)

# Count labels: field plank 1, 12, 24, 36, 48
labeled_planks = [0, 11, 23, 35, 47]  # 0-indexed
for i in labeled_planks:
    x_ctr = FIELD_X0 + i * PLANK_STEP + PLANK_W / 2
    y_ctr = FIELD_Y0 + FIELD_LEN / 2
    label(x_ctr, y_ctr,
          f"{i+1}\nof 48",
          fs=4.8, bold=True, color="#5a3010", rotation=90, zorder=10)

# Overall field count callout (left of field area)
label(FIELD_X0 - 0.35, FIELD_Y0 + FIELD_LEN/2,
      "← 48 field planks →\n5.5\" ea. + 1/8\" gap\n16-ft Trex, cut 15'-7\"\nrunning ⊥ house",
      fs=6.5, ha="right", bold=True, color="#5a3010", zorder=10)

# ── Picture-frame boards ──────────────────────────────────────────────────────
# House-side PF: y = 0..PF_W, x = -PF_OVR..OVERALL_W-PF_OVR = -0.25..23.25
HOUSE_PF_X0 = -PF_OVR
HOUSE_PF_X1 = OVERALL_W - PF_OVR   # = 23.25 ft
HOUSE_PF_Y0 = 0.0
HOUSE_PF_Y1 = PF_W

# Far-side PF: y = FRAME_D+PF_OVR-PF_W .. FRAME_D+PF_OVR
FAR_PF_X0 = -PF_OVR
FAR_PF_X1 = OVERALL_W - PF_OVR
FAR_PF_Y0 = FRAME_D + PF_OVR - PF_W   # 16.0417 ft
FAR_PF_Y1 = FRAME_D + PF_OVR          # 16.5 ft

# Left-side PF: x = -PF_OVR-FASCIA_T-PF_W .. -PF_OVR-FASCIA_T+PF_W? No.
# Left-side PF outer (left) edge: 3" past framing left rim (x=0) → x = -PF_OVR = -0.25 ft
# Left-side PF inner (right) edge: at x = -PF_OVR + PF_W = -0.25+0.4583 = 0.2083 ft = PF_INBOARD
# But we need to sit outside fascia too. Fascia is 0.75" between rim and PF.
# Actually the spec says PF outer edge is 3" past rim outer face.
# Rim left outer face ≈ x=0-GHW ≈ x=-0.19 (but for the PF layout we use x=0 as the reference).
# The spec in render_v7 shows: lx = -PF_OVR - FASCIA_T; PF from lx-PF_W to lx
# Let's use the same geometry:
lx = -PF_OVR - FASCIA_T       # left outer edge of PF = -0.25 - 0.0625 = -0.3125 ft
LEFT_PF_X0 = lx - PF_W        # outer edge (leftmost)
LEFT_PF_X1 = lx               # inner edge = right edge
LEFT_PF_Y0 = 0.0              # starts at house wall
LEFT_PF_Y1 = FRAME_D + PF_OVR  # goes to far PF outer edge (16'-6")

# Right-side PF: symmetric
rx = FRAME_W + FASCIA_T        # right inner edge of PF
RIGHT_PF_X0 = rx
RIGHT_PF_X1 = rx + PF_W

# PF spans in Y: full deck depth 0..16'-6"
RIGHT_PF_Y0 = 0.0
RIGHT_PF_Y1 = FRAME_D + PF_OVR

# Draw the 4 PF planks
# House-side PF (full rectangle, no miters needed at top corners — butted)
rect(HOUSE_PF_X0, HOUSE_PF_Y0, HOUSE_PF_X1 - HOUSE_PF_X0, PF_W,
     C_PF_TREX, EC_PF_TREX, lw=1.5, zorder=8)
label((HOUSE_PF_X0 + HOUSE_PF_X1)/2, HOUSE_PF_Y0 + PF_W/2,
      "HOUSE-SIDE PF — 5.5\" Trex  |  23'-6\" long  |  Butted at house wall  |  Butted corners (inside)",
      fs=5.8, bold=True, color="#3a1a00", zorder=11)

# Far-side PF (full rectangle — mitered corners at bottom-left and bottom-right)
rect(FAR_PF_X0, FAR_PF_Y0, FAR_PF_X1 - FAR_PF_X0, PF_W,
     C_PF_TREX, EC_PF_TREX, lw=1.5, zorder=8)
label((FAR_PF_X0 + FAR_PF_X1)/2, FAR_PF_Y0 + PF_W/2,
      "FAR-SIDE PF — 5.5\" Trex  |  23'-6\" long  |  MITERED corners (outside) ← 45°",
      fs=5.8, bold=True, color="#3a1a00", zorder=11)

# Left-side PF — full height, miters will be drawn as polygons over the rect corners
rect(LEFT_PF_X0, LEFT_PF_Y0, PF_W, LEFT_PF_Y1 - LEFT_PF_Y0,
     C_PF_TREX, EC_PF_TREX, lw=1.5, zorder=8)
label(LEFT_PF_X0 + PF_W/2, (LEFT_PF_Y0 + LEFT_PF_Y1)/2,
      "LEFT PF\n5.5\" Trex\n16'-6\" long",
      fs=5.3, bold=True, color="#3a1a00", rotation=90, zorder=11)

# Right-side PF
rect(RIGHT_PF_X0, RIGHT_PF_Y0, PF_W, RIGHT_PF_Y1 - RIGHT_PF_Y0,
     C_PF_TREX, EC_PF_TREX, lw=1.5, zorder=8)
label(RIGHT_PF_X0 + PF_W/2, (RIGHT_PF_Y0 + RIGHT_PF_Y1)/2,
      "RIGHT PF\n5.5\" Trex\n16'-6\" long",
      fs=5.3, bold=True, color="#3a1a00", rotation=90, zorder=11)

# ── Mitered corner treatment — 2 outside corners (bottom-left, bottom-right) ─
# The miter is a 45° cut where two PF boards meet.
# At bottom-left: left-side PF and far-side PF meet.
#   Left-side PF lower-right corner: (LEFT_PF_X1, FAR_PF_Y0)
#   Far-side PF left: (FAR_PF_X0, FAR_PF_Y0) = (-PF_OVR, FAR_PF_Y0)
#   Miter cut: diagonal from outer corner (-PF_OVR - FASCIA_T, FAR_PF_Y1)
#   to inner corner intersection of the two boards.
# Draw white triangle to mask the overlap square corner,
# then draw a diagonal miter line.
# Simpler: just draw a diagonal line across the corner square.

miter_lw = 2.5
miter_color = EC_PF_TREX

# Bottom-left miter corner:
#   Corner square spans x=[LEFT_PF_X0..LEFT_PF_X1] × y=[FAR_PF_Y0..FAR_PF_Y1]
#   = x=[lx-PF_W..lx] × y=[FAR_PF_Y0..FAR_PF_Y0+PF_W]
BL_x0 = LEFT_PF_X0;  BL_x1 = LEFT_PF_X1  # = lx-PF_W, lx
BL_y0 = FAR_PF_Y0;   BL_y1 = FAR_PF_Y1   # = FAR_PF_Y0, FAR_PF_Y0+PF_W
# The miter diagonal goes from outer corner (left, far) to inner corner (right, near)
# outer corner: (BL_x0, BL_y1)  [bottom-left of the square]
# inner corner: (BL_x1, BL_y0)  [top-right of the square]
ax.plot([BL_x0, BL_x1], [BL_y1, BL_y0],
        color=miter_color, lw=miter_lw, zorder=12, linestyle="-")

# Bottom-right miter corner:
#   x=[RIGHT_PF_X0..RIGHT_PF_X1] × y=[FAR_PF_Y0..FAR_PF_Y1]
BR_x0 = RIGHT_PF_X0; BR_x1 = RIGHT_PF_X1
BR_y0 = FAR_PF_Y0;   BR_y1 = FAR_PF_Y1
# outer corner: (BR_x1, BR_y1)  [bottom-right of the square]
# inner corner: (BR_x0, BR_y0)  [top-left of the square]
ax.plot([BR_x1, BR_x0], [BR_y1, BR_y0],
        color=miter_color, lw=miter_lw, zorder=12, linestyle="-")

# Small miter corner label annotations
label(BL_x0 - 0.25, BL_y1 + 0.20,
      "Outside corner\n45° miter",
      fs=5.5, bold=True, color="#5a1a00", ha="center", zorder=12)
ax.annotate("", xy=(BL_x0 + 0.05, BL_y1 - 0.08),
            xytext=(BL_x0 - 0.25, BL_y1 + 0.12),
            arrowprops=dict(arrowstyle="->", color="#5a1a00", lw=0.9))

label(BR_x1 + 0.25, BR_y1 + 0.20,
      "Outside corner\n45° miter",
      fs=5.5, bold=True, color="#5a1a00", ha="center", zorder=12)
ax.annotate("", xy=(BR_x1 - 0.05, BR_y1 - 0.08),
            xytext=(BR_x1 + 0.25, BR_y1 + 0.12),
            arrowprops=dict(arrowstyle="->", color="#5a1a00", lw=0.9))

# Inside corner labels (top-left, top-right against house)
label(BL_x1 - 0.05, HOUSE_PF_Y1 + 0.12,
      "Inside corner\n(butted)",
      fs=5.0, color="#777777", ha="center", zorder=10)
label(BR_x0 + 0.05, HOUSE_PF_Y1 + 0.12,
      "Inside corner\n(butted)",
      fs=5.0, color="#777777", ha="center", zorder=10)

# ── Mitered corner inset / zoom detail (bottom of drawing) ───────────────────
# Show one bottom-left corner at ~4x zoom, with explicit 45° call-out
INSET_CX = -1.5    # center x of inset
INSET_CY = 21.0    # center y of inset (below main plan)
INSET_SCALE = 4.0  # scale factor (1 ft in plan → 4 ft in inset)
INSET_BOX_W = 3.8
INSET_BOX_H = 2.8

# Box frame
rect(INSET_CX - INSET_BOX_W/2, INSET_CY - 0.2,
     INSET_BOX_W, INSET_BOX_H, "#fdf8f0", "#5a3a1a", lw=2.0, zorder=15)

label(INSET_CX, INSET_CY + 0.12,
      "OUTSIDE CORNER DETAIL (bottom-left, approx. 4× scale)",
      fs=7.5, bold=True, color="#3a1a00", zorder=16)

# Draw inset PF planks (scaled, with explicit miter)
# Left-side PF: width = PF_W * INSET_SCALE = 1.83 ft wide in inset
# Far-side PF: same height
INS_PFW = PF_W * INSET_SCALE  # 1.833 ft
INS_X_LEFT = INSET_CX - INSET_BOX_W/2 + 0.15  # inset left edge
INS_Y_TOP  = INSET_CY + 0.45

# Far-side PF (horizontal band)
rect(INS_X_LEFT, INS_Y_TOP + INS_PFW, INSET_BOX_W - 0.3, INS_PFW,
     C_PF_TREX, EC_PF_TREX, lw=1.5, zorder=16)
label(INS_X_LEFT + (INSET_BOX_W - 0.3)/2, INS_Y_TOP + INS_PFW + INS_PFW/2,
      "Far-side PF (5.5\")", fs=6.0, bold=True, color="#3a1a00", zorder=17)

# Left-side PF (vertical band)
rect(INS_X_LEFT, INS_Y_TOP, INS_PFW, INS_PFW,
     C_PF_TREX, EC_PF_TREX, lw=1.5, zorder=16)
label(INS_X_LEFT + INS_PFW/2, INS_Y_TOP + INS_PFW/2,
      "Left\nPF\n(5.5\")", fs=6.0, bold=True, color="#3a1a00", rotation=0, zorder=17)

# 45° miter line across the corner square
ax.plot([INS_X_LEFT, INS_X_LEFT + INS_PFW],
        [INS_Y_TOP + INS_PFW, INS_Y_TOP],
        color=EC_PF_TREX, lw=3.0, zorder=18)

# Angle arc to show 45°
theta = np.linspace(np.pi, 1.25 * np.pi, 30)
arc_r = INS_PFW * 0.35
ax.plot(INS_X_LEFT + arc_r * np.cos(theta),
        INS_Y_TOP + INS_PFW + arc_r * np.sin(theta),
        color="#aa3300", lw=1.5, zorder=18)
label(INS_X_LEFT + INS_PFW * 0.55, INS_Y_TOP + INS_PFW * 0.55,
      "45°", fs=7.5, bold=True, color="#aa3300", zorder=19)

label(INS_X_LEFT + INS_PFW + 0.05, INS_Y_TOP + INS_PFW + 0.15,
      "← outer corner", fs=5.5, color="#5a1a00", ha="left", zorder=17)

# ══════════════════════════════════════════════════════════════════════════════
# DIMENSION ANNOTATIONS
# ══════════════════════════════════════════════════════════════════════════════

# Overall 23'-6" (top)
ax.annotate("", xy=(-PF_OVR, -2.5), xytext=(OVERALL_W - PF_OVR, -2.5),
            arrowprops=dict(arrowstyle="<->", color="#000099", lw=1.6))
label(FRAME_W/2, -2.85, "23'-6\"  OVERALL FINISHED SURFACE  (PF outer edge to outer edge)",
      fs=10, bold=True, color="#000099")

# Framing 23'-0" (just below overall)
ax.annotate("", xy=(0.0, -2.0), xytext=(FRAME_W, -2.0),
            arrowprops=dict(arrowstyle="<->", color="#444444", lw=1.2))
label(FRAME_W/2, -1.75, "23'-0\"  framing footprint (rim outer edge)",
      fs=8, bold=False, color="#444444")

# Overall 16'-6" (right side)
right_ann = RIGHT_PF_X1 + 0.9
ax.annotate("", xy=(right_ann, 0.0), xytext=(right_ann, OVERALL_D),
            arrowprops=dict(arrowstyle="<->", color="#000099", lw=1.6))
label(right_ann + 0.6, OVERALL_D/2,
      "16'-6\"\nOVERALL\n(PF outer\nto wall)",
      fs=8.5, bold=True, color="#000099", rotation=90)

# Field width annotation
ax.annotate("", xy=(FIELD_X0, -1.4), xytext=(FIELD_X1, -1.4),
            arrowprops=dict(arrowstyle="<->", color="#7a3a00", lw=1.2))
label((FIELD_X0 + FIELD_X1)/2, -1.15,
      "22'-7\"  field plank area (271\")",
      fs=7.5, bold=True, color="#7a3a00")

# Field length annotation (right side)
field_ann_x = FIELD_X1 + 0.6
ax.annotate("", xy=(field_ann_x, FIELD_Y0), xytext=(field_ann_x, FIELD_Y1),
            arrowprops=dict(arrowstyle="<->", color="#7a3a00", lw=1.2))
label(field_ann_x + 0.7, (FIELD_Y0 + FIELD_Y1)/2,
      "15'-7\"\nfield\nplank\nlength\n(187\")",
      fs=7.5, bold=True, color="#7a3a00", rotation=90)

# Plank width callout (between planks 1 and 2)
plank0_ctr = FIELD_X0 + 0 * PLANK_STEP + PLANK_W/2
plank1_ctr = FIELD_X0 + 1 * PLANK_STEP + PLANK_W/2
gap_x = FIELD_X0 + PLANK_W   # right edge of plank 1 = gap start
ax.annotate("", xy=(FIELD_X0, -0.9), xytext=(FIELD_X0 + PLANK_W, -0.9),
            arrowprops=dict(arrowstyle="<->", color="#5a3010", lw=1.0))
label(FIELD_X0 + PLANK_W/2, -0.65, "5.5\"", fs=6.5, bold=True, color="#5a3010")
ax.annotate("", xy=(FIELD_X0 + PLANK_W, -0.9),
            xytext=(FIELD_X0 + PLANK_STEP, -0.9),
            arrowprops=dict(arrowstyle="<->", color="#5a3010", lw=0.8))
label(FIELD_X0 + PLANK_W + PLANK_GAP/2, -0.65, "⅛\"", fs=6.0, color="#5a3010")

# PF width callout (far-side PF)
ax.annotate("", xy=(-PF_OVR, OVERALL_D + 0.25),
            xytext=(-PF_OVR + PF_W, OVERALL_D + 0.25),
            arrowprops=dict(arrowstyle="<->", color="#5a3a1a", lw=1.0))
label(-PF_OVR + PF_W/2, OVERALL_D + 0.55, "5.5\"\nPF", fs=6.5, bold=True, color="#5a3a1a")

# ══════════════════════════════════════════════════════════════════════════════
# RIGHT-SIDE PANEL — Title block and legend for Page 2
# ══════════════════════════════════════════════════════════════════════════════
PX = 28.5
PW = 5.5

# ── Title block ────────────────────────────────────────────────────────────────
panel_box(-4.2, 6.5, fc="#f5f5f5")
title_lines = [
    "DECK PLAN v8 — PAGE 2: DECKING",
    "23'-6\" × 16'-6\"  Overall Finished Surface",
    "Trex Transcend  |  ⊥ House  |  4-Side Picture Frame",
    "Framing shown at 40% opacity (background)",
    "House on 23'-6\" Edge  ▲ NORTH",
    "",
    "Scale: 1\" ≈ 1 ft (plot units = ft)",
    "HOUSE = top edge",
    "",
    "Date: 2026-05-01",
    "Gemma — Technical Diagramming Specialist",
    "(Framing unchanged from Page 1 / v7)",
]
for i, line in enumerate(title_lines):
    fw = "bold" if i < 5 else "normal"
    fs = 9.0 if i == 0 else 7.5
    label(PX + PW/2, -4.0 + i * 0.50, line, fs=fs, bold=(fw == "bold"))

# ── Plank count summary box ────────────────────────────────────────────────────
panel_box(2.5, 5.5, fc="#fdf5e8", ec="#a07a4a", lw=2.5)
label(PX + PW/2, 2.75, "PLANK COUNT SUMMARY", fs=9.5, bold=True, color="#5a3010")
count_lines = [
    ("Field planks:", "48 × 16-ft Trex Transcend"),
    ("", "  cut to 15'-7\" | waste ~5\"/board"),
    ("PF — house side:", "1 board, 23'-6\" length"),
    ("PF — far side:", "1 board, 23'-6\" length"),
    ("", "  (use 24-ft or splice 2× 12-ft over joist)"),
    ("PF — left side:", "1 board, 16'-6\" length"),
    ("PF — right side:", "1 board, 16'-6\" length"),
    ("", "  (16-ft boards, field-cut)"),
    ("Board subtotal:", "52 boards"),
    ("+10% waste:", "~5 boards"),
    ("TOTAL ORDER:", "~57 boards (planning est.)"),
    ("", "  Hollis will produce precise BOM."),
]
for i, (lbl_a, lbl_b) in enumerate(count_lines):
    y_row = 3.2 + i * 0.35
    bold_row = lbl_a in ("Board subtotal:", "+10% waste:", "TOTAL ORDER:")
    color_a = "#8B0000" if bold_row else "#333333"
    label(PX + 0.08, y_row, lbl_a, fs=6.2, bold=bold_row, ha="left", color=color_a)
    label(PX + 2.0, y_row, lbl_b, fs=6.2, bold=bold_row, ha="left",
          color="#5a3010" if bold_row else "#444444")

# ── Legend ─────────────────────────────────────────────────────────────────────
panel_box(8.2, 13.0, fc="white")
label(PX + PW/2, 8.45, "LEGEND — PAGE 2: DECKING", fs=10.0, bold=True)

# Trex field plank
y_leg = 9.05
rect(PX + 0.08, y_leg, 0.60, 0.40, C_FIELD, EC_FIELD, lw=1.0, zorder=3)
label(PX + 0.78, y_leg + 0.09, "Field plank — 5.5\" Trex Transcend (or equiv. composite)", fs=6.8, bold=True, ha="left")
label(PX + 0.78, y_leg + 0.26, "48 planks, 16-ft cut to 15'-7\", running ⊥ house @ 5.625\" c-c", fs=5.8, ha="left", color="#444444")

# Trex PF plank
y_leg = 9.85
rect(PX + 0.08, y_leg, 0.60, 0.40, C_PF_TREX, EC_PF_TREX, lw=1.5, zorder=3)
label(PX + 0.78, y_leg + 0.09, "Picture-frame (PF) — 5.5\" Trex, all 4 sides", fs=6.8, bold=True, ha="left")
label(PX + 0.78, y_leg + 0.26, "House & far sides: 23'-6\"; left & right sides: 16'-6\"", fs=5.8, ha="left", color="#444444")

# Gap callout
y_leg = 10.65
ax.plot([PX + 0.08, PX + 0.68], [y_leg + 0.20, y_leg + 0.20],
        color=EC_FIELD, lw=0.8, linestyle="--", zorder=4)
label(PX + 0.78, y_leg + 0.09, "Plank gap — 1/8\" typ. between field planks", fs=6.8, bold=True, ha="left")
label(PX + 0.78, y_leg + 0.26, "No gap between PF and field (PF butts field edge)", fs=5.8, ha="left", color="#444444")

# Miter corner
y_leg = 11.45
ax.plot([PX + 0.08, PX + 0.68], [y_leg + 0.38, y_leg + 0.00],
        color=EC_PF_TREX, lw=2.5, zorder=4)
label(PX + 0.78, y_leg + 0.09, "45° miter joint — 2 OUTSIDE corners (far-left, far-right)", fs=6.8, bold=True, ha="left")
label(PX + 0.78, y_leg + 0.26, "2 INSIDE corners (against house wall) are butted — not mitered", fs=5.8, ha="left", color="#444444")

# Framing background swatches
y_leg = 12.35
rect(PX + 0.08, y_leg, 0.60, 0.40, C_GIRDER, EC_GIRDER, lw=2, zorder=3, alpha=FRAME_ALPHA)
label(PX + 0.78, y_leg + 0.09, "Framing (background, 40% opacity) — girders, ledger, joists", fs=6.8, bold=True, ha="left")
label(PX + 0.78, y_leg + 0.26, "Framing is unchanged from Page 1 — structural reference only", fs=5.8, ha="left", color="#444444")

# Deck thickness note
y_leg = 13.25
rect(PX + 0.08, y_leg, 0.60, 0.40, "#dddddd", "#888888", lw=1.0, zorder=3)
label(PX + 0.78, y_leg + 0.09, "Deck plank top = 12.0\" AG  (plank 1.0\" thick on 11.0\" AG framing)", fs=6.8, bold=True, ha="left")
label(PX + 0.78, y_leg + 0.26, "Trex Transcend nominal 1\" (actual ~0.94\"); shown as 1\" for clarity", fs=5.8, ha="left", color="#444444")

# ── Fastener / ordering notes ──────────────────────────────────────────────────
panel_box(17.5, 5.5, fc="#fdf9f0", ec="#a07a4a", lw=1.5)
order_notes = [
    "DECKING ORDERING NOTES (planning est. — v8)",
    "Field planks: 48 × 16-ft Trex Transcend 5.5\" (or equiv.)",
    "  each cut to 15'-7\" on site; ~5\" waste per board",
    "PF long sides: 2 × 24-ft preferred (house + far PF, 23'-6\" each)",
    "  If 24-ft unavailable: splice 2× 12-ft boards over a joist/girder",
    "PF short sides: 2 × 16-ft (left + right PF, 16'-6\" each, field-cut)",
    "Gap spacers: composite 1/8\" spacers (Trex or generic) recommended",
    "Hidden fasteners: Trex Hideaway or equivalent for field planks;",
    "  perimeter PF boards face-screwed w/ Trex composite screws",
    "All cuts: carbide-blade circular saw; cut from back face to avoid tear-out",
    "TOTAL ORDER (planning): ~57 boards (52 + 10% waste).",
    "Hollis will produce precise BOM with exact cut list.",
]
for i, note in enumerate(order_notes):
    fw = "bold" if i == 0 else "normal"
    fs_n = 6.5 if i == 0 else 5.8
    label(PX + 0.08, 17.72 + i * 0.29, note, fs=fs_n, bold=(i == 0), ha="left",
          color="#3a1a00" if i == 0 else "#333333")

# ══════════════════════════════════════════════════════════════════════════════
# SAVE
# ══════════════════════════════════════════════════════════════════════════════
out_path = "/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/owner_inbox/deck_blueprint/deck_plan.png"
fig.savefig(out_path, dpi=DPI, bbox_inches="tight", facecolor="white")
print(f"Saved: {out_path}")
print(f"Field plank count: {NUM_PLANKS}")
print(f"Field width: {FIELD_WIDTH_FT*12:.1f}\" = {FIELD_WIDTH_FT:.4f} ft")
print(f"Field plank length: {FIELD_LEN*12:.2f}\" = {FIELD_LEN:.4f} ft")
print(f"Plank step: {PLANK_STEP*12:.4f}\" (5.625\" target)")
print(f"Last plank right edge: {(FIELD_X0 + (NUM_PLANKS-1)*PLANK_STEP + PLANK_W)*12:.3f}\"  (field ends at {FIELD_X1*12:.3f}\")")
