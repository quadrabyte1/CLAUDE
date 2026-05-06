"""
render_v13.py  —  Gemma's matplotlib render of deck_plan v13  (Page 2: Decking Plan)
Produces deck_plan.png at >=2000 px wide, white background.

v13 = v12 + TWO structural changes only:

Change 1 — Drop house-side pier row (9 → 6 piers):
  - Piers at y=12" row (P1, P4, P7) removed.
  - Ledger carries those three girder-end reactions as point loads.
  - Simpson HU210-3 (or eq.) hangers shown at three girder-to-ledger intersections.
  - Ledger fastener callout updated: ½" HDG carriage bolts back-blocked from basement
    clustered at girder connections; ½" HDG lag at 18" OC two-row staggered between
    girder connections (IRC R507.9.1.3).
  - Peel-and-stick + Z-flashing detail callout preserved from v12.

Change 2 — Far-edge step (NEW):
  - 11'-9" long along outer 23'-6" edge.
  - Runs from right corner (x=23'-6") to midpoint (x=11'-9").
  - Single 6" rise; tread top at 6" AG. Open riser.
  - Tread depth = 10.9" (2× MoistureShield Vision 5.4" planks).
  - Doubled 2×6 PT ribbon lag-bolted to outer rim/drop-board face.
  - 5 precast concrete deck blocks at ~28" OC on 4" compacted #57 gravel pad.
  - Block x positions: 23'-0", 20'-2", 17'-4", 14'-6", 11'-9".
  - Gravel pad OUTSIDE deck footprint (beyond y=16'-6").
  - Seasonal heave callout (Hollis): ¼–½" heave accepted by homeowner.
  - Left-edge stair from v12 UNCHANGED.

What is UNCHANGED from v12:
  - Overall finished surface: 23'-6" x 16'-6"
  - Framing footprint: 23'-0" x 16'-3"
  - Joist orientation: parallel to house (along 23'-6" direction)
  - 49 field planks, MoistureShield Vision 5.4" running ⊥ house
  - 4-side PF (with L edge interrupted at left-edge step opening)
  - Outside-corner mitered joints (v10 fix preserved)
  - Middle girder at x=11'-6", outer piers at y=8'-1.5" and y=16'-3"
  - Left-edge stair (42" wide, y=6'-0" to y=9'-6") — UNCHANGED

Coordinate system (unchanged from v7):
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
from matplotlib.patches import Polygon as MplPolygon, FancyBboxPatch, Rectangle
from matplotlib.collections import PatchCollection

# ── Key dimensions ─────────────────────────────────────────────────────────────
FRAME_W    = 23.0           # framing width (along house), ft
FRAME_D    = 16.25          # framing depth (out from house) = 16'-3", ft
PF_W       = 5.4 / 12      # PF board width in ft = 0.45 ft
FASCIA_T   = 0.67 / 12     # fascia thickness, ft
PF_OVR     = 3.0 / 12      # PF overhang past rim outer face (3" = 0.25 ft)
OVERALL_W  = FRAME_W + 2 * PF_OVR    # 23.5 ft = 23'-6"
OVERALL_D  = FRAME_D + PF_OVR        # 16.5 ft = 16'-6"

# Girder positions
GIRDER_X   = [0.0, 11.5, 23.0]
GIRDER_W   = 0.38
GHW        = GIRDER_W / 2

# Joist rows
JOIST_SPACING = 1.0
RIM_Y         = FRAME_D
JOIST_H       = 0.085

# ── v13: PIER POSITIONS — house-side row DROPPED ──────────────────────────────
# v12 had PIER_Y = [1.0, 8.125, FRAME_D]  (12", 8'-1.5", 16'-3")
# v13: remove y=1.0 (12" row) — 6 piers remain: middle + outer rows only
PIER_Y     = [8.125, FRAME_D]   # was [1.0, 8.125, FRAME_D] in v12

# ── Plank dimensions (all in feet) ────────────────────────────────────────────
PLANK_W    = 5.4 / 12       # 0.45 ft
PLANK_GAP  = (1.0/8) / 12   # 0.01042 ft
PLANK_STEP = PLANK_W + PLANK_GAP  # 0.46042 ft

# PF inboard overlap on each side = 2.4" = 0.20 ft
PF_INBOARD = 2.4 / 12

# Field plank X range
FIELD_X0   = PF_INBOARD
FIELD_X1   = FRAME_W - PF_INBOARD
FIELD_WIDTH_FT = FIELD_X1 - FIELD_X0
NUM_PLANKS = 49

# Field plank Y range
FIELD_Y0   = PF_W
FIELD_Y1   = FRAME_D + PF_OVR - PF_W
FIELD_LEN  = FIELD_Y1 - FIELD_Y0

# ── LEFT-EDGE step dimensions — UNCHANGED from v12 ────────────────────────────
STEP_Y0    = 6.0           # y=6'-0" from house (near-house end of step)
STEP_Y1    = 9.5           # y=9'-6" from house (far-from-house end of step)
STEP_W     = STEP_Y1 - STEP_Y0   # 3.5 ft = 42"

# Step projects LEFT (negative x) from left deck edge
LEFT_DECK_X = -PF_OVR - FASCIA_T  # outer face of left fascia

STEP_DEPTH = 16.0 / 12    # 16" = 1.333 ft
STEP_X_OUT = LEFT_DECK_X - STEP_DEPTH

# Stringer positions (3 stringers, y-positions within step opening)
STRINGER_Y = [STEP_Y0, (STEP_Y0 + STEP_Y1) / 2, STEP_Y1]
STRINGER_W_FT = 2.0 / 12

# Middle tread: 10.8" deep = 2 × 5.4" MoistureShield planks
TREAD_DEPTH  = 10.8 / 12   # 0.9 ft

# Middle tread x range (in plan view, running left from left deck edge)
MTREAD_X0   = LEFT_DECK_X - TREAD_DEPTH
MTREAD_X1   = LEFT_DECK_X

# Gravel pad for left-edge step: 48" wide × 18" deep
GRAVEL_W    = 48.0 / 12    # 4.0 ft (y-direction)
GRAVEL_D    = 18.0 / 12    # 1.5 ft (x-direction)
GRAVEL_Y0   = STEP_Y0 - (GRAVEL_W - STEP_W) / 2
GRAVEL_Y1   = GRAVEL_Y0 + GRAVEL_W
GRAVEL_X0   = LEFT_DECK_X - GRAVEL_D
GRAVEL_X1   = LEFT_DECK_X
PAVER_SZ    = 1.0           # 12" x 12"

# ── FAR-EDGE STEP dimensions (v13 NEW) ────────────────────────────────────────
# Step runs along outer 23'-6" edge (far side, y = OVERALL_D = 16.5 ft)
# from RIGHT corner (x=23'-6" overall) to midpoint (x=11'-9" = 11.75 ft overall)
#
# The OVERALL 23.5 ft span is measured from outer far-side PF left edge to right edge:
#   Left PF outer face (along the outer edge) = -PF_OVR = -0.25 ft in framing coords
#   Right PF outer face (along the outer edge) = OVERALL_W - PF_OVR = 23.25 ft
# (This is confirmed by FAR_PF_X0 = -PF_OVR and FAR_PF_X1 = OVERALL_W - PF_OVR in render)
# Midpoint of 23.5 ft outer span = (-0.25 + 23.25) / 2 = 11.5 ft framing x
# Step length = 23.25 - 11.5 = 11.75 ft = 11'-9" ✓
FAR_STEP_X_RIGHT = OVERALL_W - PF_OVR         # = 23.25 ft (right outer PF face along far edge)
FAR_STEP_X_LEFT  = (-PF_OVR + OVERALL_W - PF_OVR) / 2   # = 11.5 ft (midpoint of outer span)

FAR_STEP_LEN = FAR_STEP_X_RIGHT - FAR_STEP_X_LEFT  # = 11.75 ft = 11'-9" ✓

# The step sits OUTSIDE the deck footprint (y > OVERALL_D)
# The outer rim/far PF outer edge sits at y = FRAME_D + PF_OVR = OVERALL_D = 16.5 ft
FAR_STEP_Y_ATTACH = OVERALL_D   # attachment line = outer face of far PF = y=16.5 ft

# Tread depth: 2× 5.4" MoistureShield planks perpendicular to house = 10.9" total
FAR_TREAD_DEPTH = (5.4 + 5.4 + 0.125) / 12   # 10.925"/12 ≈ 0.910 ft (with ~⅛" gap)
# Gravel pad: sits beyond y=16.5 ft
FAR_GRAVEL_Y0 = OVERALL_D  # starts right at outer PF face
FAR_GRAVEL_Y1 = FAR_GRAVEL_Y0 + FAR_TREAD_DEPTH + 4.0/12 + 0.2  # tread + 4" pad + margin
FAR_GRAVEL_DEPTH = FAR_GRAVEL_Y1 - FAR_GRAVEL_Y0  # ~1.25 ft

# 5 precast blocks, x positions (in framing coords from left girder face):
# Spec gives positions along the 23.5 ft outer edge measured from the LEFT outer PF corner.
# Left outer PF corner in framing coords = -PF_OVR = -0.25 ft
# So framing x = absolute_x_from_left_outer_PF + (-PF_OVR)
#             = absolute_x_from_left_outer_PF - PF_OVR
# Spec absolute positions: 23'-0", 20'-2", 17'-4", 14'-6", 11'-9"
# (measured along 23.5 ft outer edge from LEFT outer corner)
FAR_BLOCK_ABS  = [23.0, 20.167, 17.333, 14.5, 11.75]  # absolute from LEFT outer PF corner
FAR_BLOCK_X    = [a - PF_OVR for a in FAR_BLOCK_ABS]
# = [22.75, 19.917, 17.083, 14.25, 11.5]

# Far-step block size: precast deck block ~12"×12"
FAR_BLOCK_SZ   = 1.0   # 1 ft × 1 ft (12"×12")

# Drop-board y position (outer rim)
DROP_T = 0.085
far_drop_y = RIM_Y + JOIST_H
FAR_DROP_BOARD_FACE = far_drop_y + DROP_T + FASCIA_T  # outer face of fascia at far edge
# Ribbon attaches to this outer face

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

# ── Color palette ──────────────────────────────────────────────────────────────
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
C_HANGER    = "#cc4400";  EC_HANGER  = "#882200"   # hanger symbol

# MoistureShield Vision decking colors
C_FIELD     = "#b89a68"
EC_FIELD    = "#6a4a2a"
C_PF_TREX   = "#8a6a3a"
EC_PF_TREX  = "#4a2a0a"
C_NOTE      = "#ffffee";  EC_NOTE    = "#888800"
C_CALLOUT   = "#fff9e6";  EC_CALLOUT = "#cc8800"

# Left-edge step colors (unchanged from v12)
C_STRINGER  = "#6a8a5a";  EC_STRINGER = "#2a5a1a"
C_TREAD     = "#c8a878";  EC_TREAD    = "#7a5030"
C_GRAVEL    = "#d0c8b8";  EC_GRAVEL   = "#8a7a68"
C_PAVER     = "#9a9a9a";  EC_PAVER    = "#444444"
C_CUTJOINT  = "#cc2200"

# Far-edge step colors
C_FAR_RIBBON = "#5a8a5a"; EC_FAR_RIBBON = "#2a5a2a"  # doubled 2×6 PT ribbon (deep green)
C_FAR_TREAD  = "#c8a878"; EC_FAR_TREAD  = "#7a5030"  # same tan as left-edge tread
C_FAR_BLOCK  = "#9a9a9a"; EC_FAR_BLOCK  = "#444444"   # precast deck blocks
C_FAR_GRAVEL = "#d0c8b8"; EC_FAR_GRAVEL = "#8a7a68"   # gravel pad

# Framing background alpha
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
# ══ VERSION BADGE — upper-left corner (v13) ══════════════════════════════════
# ══════════════════════════════════════════════════════════════════════════════
BADGE_X = -6.4
BADGE_Y = -5.4
BADGE_W = 3.6
BADGE_H = 1.8

badge = FancyBboxPatch((BADGE_X, BADGE_Y), BADGE_W, BADGE_H,
                       boxstyle="round,pad=0.05",
                       facecolor="#1a1a1a", edgecolor="#1a1a1a",
                       linewidth=2, zorder=50)
ax.add_patch(badge)

ax.text(BADGE_X + BADGE_W / 2, BADGE_Y + BADGE_H * 0.38,
        "v13",
        fontsize=36, fontweight="bold",
        ha="center", va="center",
        color="white", zorder=51, clip_on=False)

ax.text(BADGE_X + BADGE_W / 2, BADGE_Y + BADGE_H * 0.78,
        "Page 2 of 2 — Decking",
        fontsize=8, fontweight="normal",
        ha="center", va="center",
        color="#cccccc", zorder=51, clip_on=False)

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
for gx in GIRDER_X:
    x0 = max(0.0, gx - GHW)
    x0 = min(x0, FRAME_W - GIRDER_W)
    rect(x0, 0.0, GIRDER_W, FRAME_D, C_GIRDER, EC_GIRDER, lw=2, zorder=4, alpha=FRAME_ALPHA)

# ── Ledger (background) — v13: now carries point loads at girder connections ──
LEDGER_H = 0.18
rect(0.0, 0.0, FRAME_W, LEDGER_H, C_LEDGER, EC_LEDGER, lw=2.5, zorder=5, alpha=FRAME_ALPHA)

# ── v13: Hanger symbols at girder-to-ledger connections (3 locations) ─────────
# Draw a bold colored "H" / hanger icon at each girder-ledger meeting point
HANGER_LOCATIONS = GIRDER_X  # x=0', 11'-6", 23'-0"
HANGER_SZ = 0.22  # half-size of hanger symbol square
for hx in HANGER_LOCATIONS:
    # Draw hanger as a small bold orange square at ledger level
    h_patch = FancyBboxPatch((hx - HANGER_SZ, -HANGER_SZ * 0.5), HANGER_SZ * 2, HANGER_SZ * 2,
                              boxstyle="square,pad=0",
                              facecolor=C_HANGER, edgecolor=EC_HANGER,
                              linewidth=2.5, zorder=18, alpha=0.92)
    ax.add_patch(h_patch)
    ax.text(hx, HANGER_SZ * 0.5, "HU\n210-3",
            fontsize=4.5, ha="center", va="center",
            color="white", fontweight="bold", zorder=19, clip_on=False)

# Hanger annotation callout (one leader to the left hanger)
ax.annotate("Simpson HU210-3 (or eq.)\nat each girder-ledger connection\n— typ. 3 places",
            xy=(GIRDER_X[0], HANGER_SZ * 0.5),
            xytext=(-2.5, -1.8),
            fontsize=6.5, ha="center", color=EC_HANGER, fontweight="bold",
            arrowprops=dict(arrowstyle="->", color=EC_HANGER, lw=1.2),
            zorder=20, clip_on=False,
            bbox=dict(boxstyle="round,pad=0.3", facecolor="#fff0e0", edgecolor=C_HANGER, lw=1.5))

# ── v13: Ledger fastener callout box ──────────────────────────────────────────
ledger_callout_x = FRAME_W + 0.6
ledger_callout_y = -0.15
ledger_callout_w = 10.0
ledger_callout_h = 1.6
rect(ledger_callout_x, ledger_callout_y, ledger_callout_w, ledger_callout_h,
     "#fff8ee", EC_CALLOUT, lw=1.5, zorder=16)
label(ledger_callout_x + ledger_callout_w/2, ledger_callout_y + 0.22,
      "v13 LEDGER UPGRADE: ½\" HDG carriage bolts, back-blocked from basement,",
      fs=6.2, bold=True, color="#663300", ha="center", zorder=17)
label(ledger_callout_x + ledger_callout_w/2, ledger_callout_y + 0.55,
      "clustered at girder connections; ½\" HDG lag at 18\" OC two-row staggered",
      fs=6.2, bold=False, color="#333300", ha="center", zorder=17)
label(ledger_callout_x + ledger_callout_w/2, ledger_callout_y + 0.88,
      "between girder connections (IRC R507.9.1.3). Wall = wood-frame, no masonry.",
      fs=6.2, bold=False, color="#333300", ha="center", zorder=17)
label(ledger_callout_x + ledger_callout_w/2, ledger_callout_y + 1.21,
      "Basement access confirmed for back-blocking. Peel-and-stick + Z-flashing retained.",
      fs=6.2, bold=False, color="#333300", ha="center", zorder=17)
# Leader arrow from callout to ledger
ax.annotate("", xy=(FRAME_W + 0.05, LEDGER_H/2),
            xytext=(ledger_callout_x, ledger_callout_y + ledger_callout_h/2),
            arrowprops=dict(arrowstyle="->", color=EC_CALLOUT, lw=1.0),
            zorder=17)

# ── Joist segments (background) ───────────────────────────────────────────────
SEG_A_X0 = GIRDER_X[0] + GHW
SEG_A_X1 = GIRDER_X[1] - GHW
SEG_B_X0 = GIRDER_X[1] + GHW
SEG_B_X1 = GIRDER_X[2] - GHW

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

# ── Drop-board sub-fascia (background) ────────────────────────────────────────
left_drop_x = -GHW - DROP_T
right_drop_x = GIRDER_X[2] + GHW

rect(left_drop_x, 0.0, DROP_T, FRAME_D, C_DROP, EC_DROP, lw=2, zorder=5, alpha=FRAME_ALPHA)
rect(right_drop_x, 0.0, DROP_T, FRAME_D, C_DROP, EC_DROP, lw=2, zorder=5, alpha=FRAME_ALPHA)
rect(0.0, far_drop_y, FRAME_W, DROP_T, C_DROP, EC_DROP, lw=2, zorder=5, alpha=FRAME_ALPHA)

# ── Fascia (background) ────────────────────────────────────────────────────────
fas_y = far_drop_y + DROP_T
fas_y_end = fas_y + FASCIA_T

# Far fascia: full width
rect(0.0, fas_y, FRAME_W, FASCIA_T, C_FASCIA, EC_FASCIA, lw=2, zorder=6, alpha=FRAME_ALPHA)
# Left fascia
rect(-FASCIA_T, 0.0, FASCIA_T, fas_y_end, C_FASCIA, EC_FASCIA, lw=2, zorder=6, alpha=FRAME_ALPHA)
# Right fascia
rect(FRAME_W, 0.0, FASCIA_T, fas_y_end, C_FASCIA, EC_FASCIA, lw=2, zorder=6, alpha=FRAME_ALPHA)

# ── Piers (background) — v13: only 6 piers (middle + outer rows) ──────────────
PIER_R  = 0.22
HOLE_R  = 0.35
for i, gx in enumerate(GIRDER_X):
    for j, py in enumerate(PIER_Y):   # PIER_Y now has only 2 rows
        hole = plt.Circle((gx, py), HOLE_R, fc=C_PIER_HOLE, ec=EC_HOLE,
                          lw=1.0, zorder=5, alpha=FRAME_ALPHA * 0.7)
        ax.add_patch(hole)
        pier = plt.Circle((gx, py), PIER_R, fc=C_PIER, ec=EC_PIER,
                          lw=1.5, zorder=8, alpha=FRAME_ALPHA)
        ax.add_patch(pier)

# Pier count callout
label(FRAME_W/2, PIER_Y[0] - 0.45,
      "6 PIERS (v13: house-side row dropped — ledger carries those reactions)",
      fs=6.5, bold=True, color="#5a3010", zorder=10, alpha=FRAME_ALPHA + 0.2)

# ── Field blocking dashed lines (background) ──────────────────────────────────
for bx in [5.75, 17.25]:
    ax.plot([bx, bx], [1.0, FRAME_D],
            color=C_BLOCK, linewidth=2.0, linestyle="--",
            zorder=3, alpha=FRAME_ALPHA * 0.8)

# ══════════════════════════════════════════════════════════════════════════════
# ══ LEFT-EDGE STEP ASSEMBLY — Plan view (UNCHANGED from v12) ═════════════════
# ══════════════════════════════════════════════════════════════════════════════

# ── Gravel pad (stippled/hatched) ─────────────────────────────────────────────
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

# ── Precast pavers (3 × 12"×12") ──────────────────────────────────────────────
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

# ── 3 PT stringers projecting from left girder face ──────────────────────────
GIRDER_L_FACE = GIRDER_X[0] - GHW
STRINGER_T    = 2.0 / 12

for sy in STRINGER_Y:
    st = FancyBboxPatch((STEP_X_OUT, sy - STRINGER_T/2),
                         abs(STEP_X_OUT - GIRDER_L_FACE), STRINGER_T,
                         boxstyle="square,pad=0",
                         facecolor=C_STRINGER, edgecolor=EC_STRINGER,
                         linewidth=1.5, zorder=11)
    ax.add_patch(st)

label(STEP_X_OUT + (GIRDER_L_FACE - STEP_X_OUT)/2,
      STEP_Y0 - 0.22,
      "2×10 PT stringers (3)\nSimpson LSCZ to L girder",
      fs=5.5, bold=True, color=EC_STRINGER, ha="center", zorder=12)

# ── Middle tread (two 5.4" MoistureShield planks running in y-direction) ──────
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

# ── Cut joints in left PF and fascia at y=6'-0" and y=9'-6" ──────────────────
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

# ── Dimension annotation: left-edge step width and depth ──────────────────────
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
# ══ FAR-EDGE STEP — Plan view (v13 NEW) ══════════════════════════════════════
# ══════════════════════════════════════════════════════════════════════════════

# The step sits below the far PF (y > OVERALL_D).
# In our inverted axis system, OVERALL_D is "top" of the step zone (visually at bottom
# of diagram since y increases downward on screen, but invert_yaxis means large y = low).

FAR_STEP_TREAD_Y0 = OVERALL_D                         # starts at outer PF face
FAR_STEP_TREAD_Y1 = OVERALL_D + FAR_TREAD_DEPTH       # tread outer edge
FAR_STEP_GRAVEL_Y1 = OVERALL_D + FAR_TREAD_DEPTH + 4.0/12 + 0.25   # gravel pad outer

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
      "4\" compacted #57 gravel pad\n(outside deck footprint — beyond y=16'-6\")",
      fs=5.5, bold=False, color="#6a5a48", ha="center", zorder=8)

# ── Doubled 2×6 PT ribbon (lag-bolted to outer rim/drop-board face) ───────────
# The ribbon runs along the face of the far fascia/rim, spanning the step length.
RIBBON_T   = 2 * (1.5/12)  # two 2×6 = 2 × 1.5" actual = 3" = 0.25 ft
RIBBON_Y0  = fas_y          # inboard face of ribbon (at the outer drop-board/fascia face)
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

# ── Two MoistureShield tread planks (running ⊥ house = in y-direction) ────────
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
far_tread_outer_y = RIBBON_Y1 + 2 * PLANK_W + PLANK_GAP  # outer face of 2nd tread plank
block_y0 = far_tread_outer_y + 0.05  # blocks sit just beyond tread outer edge

for bx in FAR_BLOCK_X:
    b = FancyBboxPatch(
        (bx - FAR_BLOCK_SZ/2, block_y0),
        FAR_BLOCK_SZ,
        FAR_BLOCK_SZ,
        boxstyle="square,pad=0",
        facecolor=C_FAR_BLOCK, edgecolor=EC_FAR_BLOCK,
        linewidth=1.5, zorder=14)
    ax.add_patch(b)

# Block labels and spacing annotation
label((FAR_STEP_X_LEFT + FAR_STEP_X_RIGHT)/2,
      block_y0 + FAR_BLOCK_SZ + 0.22,
      "5× precast concrete deck blocks (12\"×12\") @ ≈28\" OC on #57 gravel pad",
      fs=5.5, bold=True, color="#444444", ha="center", zorder=15)

# Spacing arrow between first two blocks
ax.annotate("", xy=(FAR_BLOCK_X[0], block_y0 + FAR_BLOCK_SZ + 0.10),
            xytext=(FAR_BLOCK_X[1], block_y0 + FAR_BLOCK_SZ + 0.10),
            arrowprops=dict(arrowstyle="<->", color="#555555", lw=0.9))
label((FAR_BLOCK_X[0] + FAR_BLOCK_X[1])/2, block_y0 + FAR_BLOCK_SZ + 0.35,
      "~28\" OC", fs=5.5, bold=False, color="#555555", ha="center")

# ── Dimension annotations: far-edge step length and depth ────────────────────
# Step length (along x) annotation below gravel pad
ann_y_far = FAR_STEP_GRAVEL_Y1 + 0.55
ax.annotate("", xy=(FAR_STEP_X_LEFT, ann_y_far), xytext=(FAR_STEP_X_RIGHT, ann_y_far),
            arrowprops=dict(arrowstyle="<->", color="#2244aa", lw=1.3))
label((FAR_STEP_X_LEFT + FAR_STEP_X_RIGHT)/2, ann_y_far + 0.30,
      "11'-9\" far-edge step (right corner → midpoint)",
      fs=7.0, bold=True, color="#2244aa", ha="center")

# Step depth (y-direction)
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
      "⚠  SEASONAL HEAVE NOTE (Hollis): shallow precast blocks WILL heave ¼–½\" per cycle.",
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
# ══ FOREGROUND: MOISTURESHIELD VISION DECK PLANKS ═══════════════════════════
# ══════════════════════════════════════════════════════════════════════════════

# ── 49 field planks ──────────────────────────────────────────────────────────
for i in range(NUM_PLANKS):
    x_left = FIELD_X0 + i * PLANK_STEP
    rect(x_left, FIELD_Y0, PLANK_W, FIELD_LEN,
         C_FIELD, EC_FIELD, lw=0.5, zorder=7)

# Count labels
labeled_planks = [0, 12, 24, 36, 48]
for i in labeled_planks:
    x_ctr = FIELD_X0 + i * PLANK_STEP + PLANK_W / 2
    y_ctr = FIELD_Y0 + FIELD_LEN / 2
    label(x_ctr, y_ctr,
          f"{i+1}\nof 49",
          fs=4.8, bold=True, color="#4a2a08", rotation=90, zorder=10)

label(FIELD_X0 - 0.35, FIELD_Y0 + FIELD_LEN/2,
      "← 49 field planks →\n5.4\" ea. + 1/8\" gap\n16-ft MoistureShield, cut 15'-7.2\"\nrunning ⊥ house",
      fs=6.5, ha="right", bold=True, color="#4a2a08", zorder=10)

# ── Picture-frame boards ──────────────────────────────────────────────────────
HOUSE_PF_X0 = -PF_OVR
HOUSE_PF_X1 = OVERALL_W - PF_OVR
HOUSE_PF_Y0 = 0.0
HOUSE_PF_Y1 = PF_W

FAR_PF_X0 = -PF_OVR
FAR_PF_X1 = OVERALL_W - PF_OVR
FAR_PF_Y0 = FRAME_D + PF_OVR - PF_W
FAR_PF_Y1 = FRAME_D + PF_OVR

lx = -PF_OVR - FASCIA_T
LEFT_PF_X0 = lx - PF_W
LEFT_PF_X1 = lx

rx = FRAME_W + FASCIA_T
RIGHT_PF_X0 = rx
RIGHT_PF_X1 = rx + PF_W

# ── House-side PF (full width) ────────────────────────────────────────────────
rect(HOUSE_PF_X0, HOUSE_PF_Y0, HOUSE_PF_X1 - HOUSE_PF_X0, PF_W,
     C_PF_TREX, EC_PF_TREX, lw=1.5, zorder=8)
label((HOUSE_PF_X0 + HOUSE_PF_X1)/2, HOUSE_PF_Y0 + PF_W/2,
      "HOUSE-SIDE PF — 5.4\" MoistureShield Vision  |  23'-6\" long  |  Butted at house wall  |  Butted corners (inside)",
      fs=5.8, bold=True, color="#3a1a00", zorder=11)

# ── Far-side PF (full width) ──────────────────────────────────────────────────
rect(FAR_PF_X0, FAR_PF_Y0, FAR_PF_X1 - FAR_PF_X0, PF_W,
     C_PF_TREX, EC_PF_TREX, lw=1.5, zorder=8)
label((FAR_PF_X0 + FAR_PF_X1)/2, FAR_PF_Y0 + PF_W/2,
      "FAR-SIDE PF — 5.4\" MoistureShield Vision  |  23'-6\" long  |  MITERED corners (outside) ← 45°",
      fs=5.8, bold=True, color="#3a1a00", zorder=11)

# ── LEFT PF — interrupted at step opening y=6' to y=9'-6" ────────────────────
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

# ── RIGHT PF — full mitered polygon ──────────────────────────────────────────
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
      "RIGHT PF\n5.4\" MoistureShield\n16'-6\" long",
      fs=5.3, bold=True, color="#3a1a00", rotation=90, zorder=11)

# ── Miter seam lines ──────────────────────────────────────────────────────────
miter_lw = 2.5
miter_color = EC_PF_TREX

ax.plot([LEFT_PF_X1, LEFT_PF_X0],
        [FAR_PF_Y0,  FAR_PF_Y1],
        color=miter_color, lw=miter_lw, zorder=12, solid_capstyle='round')

ax.plot([RIGHT_PF_X0, RIGHT_PF_X1],
        [FAR_PF_Y0,   FAR_PF_Y1],
        color=miter_color, lw=miter_lw, zorder=12, solid_capstyle='round')

# ── Miter corner label annotations ───────────────────────────────────────────
label(LEFT_PF_X0 - 0.25, FAR_PF_Y1 + 0.20,
      "Outside corner\n45° miter",
      fs=5.5, bold=True, color="#5a1a00", ha="center", zorder=12)
ax.annotate("", xy=(LEFT_PF_X0 + 0.05, FAR_PF_Y1 - 0.08),
            xytext=(LEFT_PF_X0 - 0.25, FAR_PF_Y1 + 0.12),
            arrowprops=dict(arrowstyle="->", color="#5a1a00", lw=0.9))

label(RIGHT_PF_X1 + 0.25, FAR_PF_Y1 + 0.20,
      "Outside corner\n45° miter",
      fs=5.5, bold=True, color="#5a1a00", ha="center", zorder=12)
ax.annotate("", xy=(RIGHT_PF_X1 - 0.05, FAR_PF_Y1 - 0.08),
            xytext=(RIGHT_PF_X1 + 0.25, FAR_PF_Y1 + 0.12),
            arrowprops=dict(arrowstyle="->", color="#5a1a00", lw=0.9))

# Inside corner labels
label(LEFT_PF_X1 - 0.05, HOUSE_PF_Y1 + 0.12,
      "Inside corner\n(butted)",
      fs=5.0, color="#777777", ha="center", zorder=10)
label(RIGHT_PF_X0 + 0.05, HOUSE_PF_Y1 + 0.12,
      "Inside corner\n(butted)",
      fs=5.0, color="#777777", ha="center", zorder=10)

# ── Mitered corner inset / zoom detail ────────────────────────────────────────
INSET_CX = -1.5
INSET_CY = 22.0
INSET_SCALE = 4.0
INSET_BOX_W = 3.8
INSET_BOX_H = 2.8

rect(INSET_CX - INSET_BOX_W/2, INSET_CY - 0.2,
     INSET_BOX_W, INSET_BOX_H, "#fdf8f0", "#5a3a1a", lw=2.0, zorder=15)

label(INSET_CX, INSET_CY + 0.12,
      "OUTSIDE CORNER DETAIL (bottom-left, approx. 4× scale)",
      fs=7.5, bold=True, color="#3a1a00", zorder=16)

INS_PFW = PF_W * INSET_SCALE
INS_X_LEFT = INSET_CX - INSET_BOX_W/2 + 0.15
INS_Y_TOP  = INSET_CY + 0.45

rect(INS_X_LEFT, INS_Y_TOP + INS_PFW, INSET_BOX_W - 0.3, INS_PFW,
     C_PF_TREX, EC_PF_TREX, lw=1.5, zorder=16)
label(INS_X_LEFT + (INSET_BOX_W - 0.3)/2, INS_Y_TOP + INS_PFW + INS_PFW/2,
      "Far-side PF (5.4\")", fs=6.0, bold=True, color="#3a1a00", zorder=17)

rect(INS_X_LEFT, INS_Y_TOP, INS_PFW, INS_PFW,
     C_PF_TREX, EC_PF_TREX, lw=1.5, zorder=16)
label(INS_X_LEFT + INS_PFW/2, INS_Y_TOP + INS_PFW/2,
      "Left\nPF\n(5.4\")", fs=6.0, bold=True, color="#3a1a00", rotation=0, zorder=17)

ax.plot([INS_X_LEFT, INS_X_LEFT + INS_PFW],
        [INS_Y_TOP + INS_PFW, INS_Y_TOP],
        color=EC_PF_TREX, lw=3.0, zorder=18)

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
# ══ DIMENSION ANNOTATIONS ═════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════════════════════════════

# Overall 23'-6" (top)
ax.annotate("", xy=(-PF_OVR, -3.2), xytext=(OVERALL_W - PF_OVR, -3.2),
            arrowprops=dict(arrowstyle="<->", color="#000099", lw=1.6))
label(FRAME_W/2, -3.55, "23'-6\"  OVERALL FINISHED SURFACE  (PF outer edge to outer edge)",
      fs=10, bold=True, color="#000099")

# Framing 23'-0"
ax.annotate("", xy=(0.0, -2.7), xytext=(FRAME_W, -2.7),
            arrowprops=dict(arrowstyle="<->", color="#444444", lw=1.2))
label(FRAME_W/2, -2.45, "23'-0\"  framing footprint (rim outer edge)  — UNCHANGED",
      fs=8, bold=False, color="#444444")

# Overall 16'-6" (right side)
right_ann = RIGHT_PF_X1 + 0.9
ax.annotate("", xy=(right_ann, 0.0), xytext=(right_ann, OVERALL_D),
            arrowprops=dict(arrowstyle="<->", color="#000099", lw=1.6))
label(right_ann + 0.6, OVERALL_D/2,
      "16'-6\"\nOVERALL\n(PF outer\nto wall)",
      fs=8.5, bold=True, color="#000099", rotation=90)

# Field width annotation
ax.annotate("", xy=(FIELD_X0, -2.1), xytext=(FIELD_X1, -2.1),
            arrowprops=dict(arrowstyle="<->", color="#7a3a00", lw=1.2))
label((FIELD_X0 + FIELD_X1)/2, -1.85,
      "22'-7.2\"  field plank area (271.2\")",
      fs=7.5, bold=True, color="#7a3a00")

# Field length annotation (right side)
field_ann_x = FIELD_X1 + 0.6
ax.annotate("", xy=(field_ann_x, FIELD_Y0), xytext=(field_ann_x, FIELD_Y1),
            arrowprops=dict(arrowstyle="<->", color="#7a3a00", lw=1.2))
label(field_ann_x + 0.7, (FIELD_Y0 + FIELD_Y1)/2,
      "15'-7.2\"\nfield\nplank\nlength\n(187.2\")",
      fs=7.5, bold=True, color="#7a3a00", rotation=90)

# Plank width callout
ax.annotate("", xy=(FIELD_X0, -1.6), xytext=(FIELD_X0 + PLANK_W, -1.6),
            arrowprops=dict(arrowstyle="<->", color="#5a3010", lw=1.0))
label(FIELD_X0 + PLANK_W/2, -1.35, "5.4\"", fs=6.5, bold=True, color="#5a3010")
ax.annotate("", xy=(FIELD_X0 + PLANK_W, -1.6),
            xytext=(FIELD_X0 + PLANK_STEP, -1.6),
            arrowprops=dict(arrowstyle="<->", color="#5a3010", lw=0.8))
label(FIELD_X0 + PLANK_W + PLANK_GAP/2, -1.35, "⅛\"", fs=6.0, color="#5a3010")

# PF width callout (far-side PF)
ax.annotate("", xy=(-PF_OVR, OVERALL_D + 0.25),
            xytext=(-PF_OVR + PF_W, OVERALL_D + 0.25),
            arrowprops=dict(arrowstyle="<->", color="#5a3a1a", lw=1.0))
label(-PF_OVR + PF_W/2, OVERALL_D + 0.55, "5.4\"\nPF", fs=6.5, bold=True, color="#5a3a1a")

# Step y-position annotations on left side
ax.annotate("", xy=(LEFT_PF_X0 - 0.7, 0.0), xytext=(LEFT_PF_X0 - 0.7, STEP_Y0),
            arrowprops=dict(arrowstyle="<->", color="#2244aa", lw=1.0))
label(LEFT_PF_X0 - 0.95, STEP_Y0/2,
      "6'-0\"", fs=6.0, bold=True, color="#2244aa", rotation=90)

ax.plot([LEFT_PF_X0 - 0.5, LEFT_PF_X0], [STEP_Y0, STEP_Y0],
        color="#2244aa", lw=0.8, linestyle="--", zorder=4)
ax.plot([LEFT_PF_X0 - 0.5, LEFT_PF_X0], [STEP_Y1, STEP_Y1],
        color="#2244aa", lw=0.8, linestyle="--", zorder=4)

# ══════════════════════════════════════════════════════════════════════════════
# ══ SIDE-ELEVATION STEP INSET (left-edge stair — unchanged from v12) ═════════
# ══════════════════════════════════════════════════════════════════════════════
PX = 29.5
PW = 5.5

EL_X  = PX + 0.2
EL_Y0 = 19.5
EL_W  = PW - 0.4
EL_H  = 5.5

rect(EL_X, EL_Y0, EL_W, EL_H, "#f8f8f0", "#446688", lw=2.0, zorder=20)
label(EL_X + EL_W/2, EL_Y0 + 0.25,
      "LEFT-EDGE STEP — SIDE ELEVATION (unchanged v12)",
      fs=8.0, bold=True, color="#2244aa", ha="center", zorder=21)

EL_Y_GRADE  = EL_Y0 + EL_H - 0.8
EL_FT_SCALE = 2.2

def ag_to_py(ag_inches):
    return EL_Y_GRADE - (ag_inches / 12.0) * EL_FT_SCALE

EL_X_LEFT  = EL_X + 0.5
EL_X_RIGHT = EL_X + EL_W - 0.5
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

for ag_in, lbl in [(12, "12\" AG\n(deck top)"), (6, "6\" AG\n(mid tread)"), (0, "0\" AG\n(grade)")]:
    py_pos = ag_to_py(ag_in)
    ax.plot([EL_STRINGER_X0 - 0.5, EL_STRINGER_X0 - 0.05], [py_pos, py_pos],
            color="#444488", lw=0.8, linestyle=":", zorder=24)
    label(EL_STRINGER_X0 - 0.55, py_pos, lbl, fs=5.5, bold=True, color="#2244aa",
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

label(EL_X + EL_W/2, EL_Y0 + EL_H - 0.25,
      "2 risers @ 6\" each | OPEN risers (no riser board) | 3 PT 2×10 stringers",
      fs=5.5, bold=False, color="#333333", ha="center", zorder=28)

# ══════════════════════════════════════════════════════════════════════════════
# ══ FAR-EDGE STEP — SIDE ELEVATION INSET (v13 NEW) ═══════════════════════════
# ══════════════════════════════════════════════════════════════════════════════
FAR_EL_X  = PX + 0.2
FAR_EL_Y0 = 14.5
FAR_EL_W  = PW - 0.4
FAR_EL_H  = 4.5

rect(FAR_EL_X, FAR_EL_Y0, FAR_EL_W, FAR_EL_H, "#f8f8f0", "#2a6a2a", lw=2.0, zorder=20)
label(FAR_EL_X + FAR_EL_W/2, FAR_EL_Y0 + 0.25,
      "FAR-EDGE STEP — SIDE ELEVATION (v13 NEW)",
      fs=8.0, bold=True, color="#2a6a2a", ha="center", zorder=21)

# Scale for far-edge step: deck @ 12" AG, tread @ 6" AG, grade @ 0"
FAR_EL_GRADE  = FAR_EL_Y0 + FAR_EL_H - 0.7
FAR_EL_SCALE  = 1.8  # plot units per foot AG

def far_ag_to_py(ag_inches):
    return FAR_EL_GRADE - (ag_inches / 12.0) * FAR_EL_SCALE

FAR_EL_X0 = FAR_EL_X + 0.6
FAR_EL_X1 = FAR_EL_X + FAR_EL_W - 0.3
FAR_TREAD_W_PLOT = (FAR_TREAD_DEPTH) * FAR_EL_SCALE   # horizontal extent of tread

far_deck_py  = far_ag_to_py(12)
far_tread_py = far_ag_to_py(6)
far_grade_py = far_ag_to_py(0)

# Grade / gravel
far_gravel_el = FancyBboxPatch(
    (FAR_EL_X0 - 0.1, far_grade_py),
    FAR_EL_X1 - FAR_EL_X0 + 0.2,
    FAR_EL_GRADE - far_grade_py + 0.2,
    boxstyle="square,pad=0",
    facecolor=C_FAR_GRAVEL, edgecolor=EC_FAR_GRAVEL,
    linewidth=1.2, zorder=21)
ax.add_patch(far_gravel_el)
# Precast block at grade
far_block_el = FancyBboxPatch(
    (FAR_EL_X0 + 0.1, far_grade_py - 0.12),
    0.45, 0.12,
    boxstyle="square,pad=0",
    facecolor=C_FAR_BLOCK, edgecolor=EC_FAR_BLOCK,
    linewidth=1.2, zorder=22)
ax.add_patch(far_block_el)
label(FAR_EL_X0 + 0.33, far_grade_py - 0.06,
      "precast\nblock", fs=4.2, color="#444444", ha="center", zorder=23)

# Ribbon at deck face
ribbon_py = far_deck_py
ribbon_h  = (3.0/12) * FAR_EL_SCALE   # 3" ribbon = 0.25 ft
ribbon_el = FancyBboxPatch(
    (FAR_EL_X0, ribbon_py - ribbon_h),
    (1.5/12) * FAR_EL_SCALE,   # ribbon shown in elevation: 1.5" thick
    ribbon_h,
    boxstyle="square,pad=0",
    facecolor=C_FAR_RIBBON, edgecolor=EC_FAR_RIBBON,
    linewidth=1.5, zorder=24)
ax.add_patch(ribbon_el)
label(FAR_EL_X0 + (1.5/12) * FAR_EL_SCALE / 2, ribbon_py - ribbon_h / 2,
      "ribbon", fs=4.2, color="white", ha="center", zorder=25)

# Tread planks in elevation: 2 planks each 1.0" thick, stacked
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

# Deck surface
deck_t_far = (1.0/12.0) * FAR_EL_SCALE
deck_el_far = FancyBboxPatch(
    (FAR_EL_X0 - 0.15, far_deck_py - deck_t_far),
    FAR_TREAD_W_PLOT + 0.3, deck_t_far,
    boxstyle="square,pad=0",
    facecolor=C_FIELD, edgecolor=EC_FIELD,
    linewidth=1.0, zorder=24)
ax.add_patch(deck_el_far)

# Open riser (dashed line between deck and tread top)
ax.plot([FAR_EL_X0 + (1.5/12) * FAR_EL_SCALE + FAR_TREAD_W_PLOT,
         FAR_EL_X0 + (1.5/12) * FAR_EL_SCALE + FAR_TREAD_W_PLOT],
        [far_deck_py, far_tread_py],
        color="#cc4400", lw=1.0, linestyle="--", zorder=26)
label(FAR_EL_X0 + (1.5/12) * FAR_EL_SCALE + FAR_TREAD_W_PLOT + 0.05,
      (far_deck_py + far_tread_py)/2,
      "OPEN\nRISER", fs=4.5, bold=True, color="#cc4400", ha="left", zorder=27)

# Elevation labels
for ag_in, lbl_txt in [(12, "12\" AG\n(deck)"), (6, "6\" AG\n(tread)"), (0, "0\" AG\n(grade)")]:
    py_pos = far_ag_to_py(ag_in)
    ax.plot([FAR_EL_X0 - 0.5, FAR_EL_X0 - 0.05], [py_pos, py_pos],
            color="#444488", lw=0.8, linestyle=":", zorder=24)
    label(FAR_EL_X0 - 0.55, py_pos, lbl_txt, fs=5.0, bold=True, color="#2a6a2a",
          ha="right", va="center", zorder=28)

# Riser height
ax.annotate("", xy=(FAR_EL_X0 - 0.2, far_deck_py),
            xytext=(FAR_EL_X0 - 0.2, far_tread_py),
            arrowprops=dict(arrowstyle="<->", color="#666666", lw=0.9))
label(FAR_EL_X0 - 0.2, (far_deck_py + far_tread_py)/2,
      "6\"", fs=5.0, bold=True, color="#444444", ha="right", zorder=28)

# Tread depth
ax.annotate("", xy=(FAR_EL_X0 + (1.5/12) * FAR_EL_SCALE, far_grade_py + 0.1),
            xytext=(FAR_EL_X0 + (1.5/12) * FAR_EL_SCALE + FAR_TREAD_W_PLOT, far_grade_py + 0.1),
            arrowprops=dict(arrowstyle="<->", color="#774400", lw=0.9))
label(FAR_EL_X0 + (1.5/12) * FAR_EL_SCALE + FAR_TREAD_W_PLOT/2,
      far_grade_py + 0.25,
      "10.9\"", fs=5.0, bold=True, color="#774400", ha="center", zorder=28)

label(FAR_EL_X + FAR_EL_W/2, FAR_EL_Y0 + FAR_EL_H - 0.22,
      "1 riser @ 6\" | OPEN riser | doubled 2×6 PT ribbon | 5 precast blocks @ 28\" OC",
      fs=5.3, bold=False, color="#333333", ha="center", zorder=28)

# ══════════════════════════════════════════════════════════════════════════════
# RIGHT-SIDE PANEL — Title block and legend for Page 2
# ══════════════════════════════════════════════════════════════════════════════

# ── Title block ────────────────────────────────────────────────────────────────
panel_box(-5.2, 6.5, fc="#f5f5f5")
title_lines = [
    "DECK PLAN v13 — PAGE 2: DECKING",
    "23'-6\" × 16'-6\"  Overall Finished Surface",
    "MoistureShield Vision  |  ⊥ House  |  4-Side Picture Frame",
    "L-edge step: 42\" wide @ 6'-0\" | Far-edge step: 11'-9\" @ right corner",
    "House on 23'-6\" Edge  ▲ NORTH",
    "",
    "Scale: 1\" ≈ 1 ft (plot units = ft)",
    "HOUSE = top edge",
    "",
    "Date: 2026-05-05",
    "Gemma — Technical Diagramming Specialist",
    "(v13: 9→6 piers; ledger+HU210-3 hangers; far-edge step 11'-9\"",
    " right corner to midpoint; precast blocks on gravel — heave accepted)",
]
for i, line in enumerate(title_lines):
    fw = "bold" if i < 5 else "normal"
    fs = 9.0 if i == 0 else 7.0
    label(PX + PW/2, -5.0 + i * 0.48, line, fs=fs, bold=(fw == "bold"))

# ── Plank count summary box ────────────────────────────────────────────────────
panel_box(1.5, 5.5, fc="#fdf5e8", ec="#8a6a3a", lw=2.5)
label(PX + PW/2, 1.75, "PLANK COUNT SUMMARY", fs=9.5, bold=True, color="#4a2a08")
count_lines = [
    ("Field planks:", "49 × 16-ft MoistureShield Vision"),
    ("", "  cut to 15'-7.2\" | waste ~4.8\"/board"),
    ("PF — house side:", "1 board, 23'-6\" length"),
    ("PF — far side:", "1 board, 23'-6\" length"),
    ("PF — left side:", "2 pcs: 0-6' + 9'-6\"-16'-6\" (interrupted)"),
    ("PF — right side:", "1 board, 16'-6\" length"),
    ("L-step treads:", "2 × 5.4\" MoistureShield ≈ 3.5' long"),
    ("Far-step treads:", "2 × 5.4\" × 11'-9\" MoistureShield"),
    ("Board subtotal:", "~57+ boards"),
    ("+10% waste:", "~6 boards"),
    ("TOTAL ORDER:", "~63 boards (planning est.)"),
    ("", "  Hollis will produce precise BOM."),
]
for i, (lbl_a, lbl_b) in enumerate(count_lines):
    y_row = 2.2 + i * 0.35
    bold_row = lbl_a in ("Board subtotal:", "+10% waste:", "TOTAL ORDER:")
    color_a = "#8B0000" if bold_row else "#333333"
    label(PX + 0.08, y_row, lbl_a, fs=6.0, bold=bold_row, ha="left", color=color_a)
    label(PX + 2.2, y_row, lbl_b, fs=6.0, bold=bold_row, ha="left",
          color="#4a2a08" if bold_row else "#444444")

# ── Legend ─────────────────────────────────────────────────────────────────────
panel_box(7.2, 7.2, fc="white")
label(PX + PW/2, 7.45, "LEGEND — PAGE 2: DECKING (v13)", fs=10.0, bold=True)

y_leg = 8.05
rect(PX + 0.08, y_leg, 0.60, 0.40, C_FIELD, EC_FIELD, lw=1.0, zorder=3)
label(PX + 0.78, y_leg + 0.09, "Field plank — 5.4\" MoistureShield Vision (composite, capped)", fs=6.8, bold=True, ha="left")
label(PX + 0.78, y_leg + 0.26, "49 planks, 16-ft cut to 15'-7.2\", running ⊥ house @ 5.525\" c-c", fs=5.8, ha="left", color="#444444")

y_leg = 8.85
rect(PX + 0.08, y_leg, 0.60, 0.40, C_PF_TREX, EC_PF_TREX, lw=1.5, zorder=3)
label(PX + 0.78, y_leg + 0.09, "Picture-frame (PF) — 5.4\" MoistureShield Vision, all 4 sides", fs=6.8, bold=True, ha="left")
label(PX + 0.78, y_leg + 0.26, "L-side PF interrupted at L-edge step opening (y=6'-0\" to y=9'-6\")", fs=5.8, ha="left", color="#444444")

y_leg = 9.65
rect(PX + 0.08, y_leg, 0.60, 0.40, C_STRINGER, EC_STRINGER, lw=2, zorder=3)
label(PX + 0.78, y_leg + 0.09, "L-edge stair stringer — 2×10 PT cut stringer (3 total)", fs=6.8, bold=True, ha="left")
label(PX + 0.78, y_leg + 0.26, "Attached to L girder outer face via Simpson LSCZ stringer hangers", fs=5.8, ha="left", color="#444444")

y_leg = 10.45
rect(PX + 0.08, y_leg, 0.60, 0.40, C_FAR_RIBBON, EC_FAR_RIBBON, lw=2, zorder=3)
label(PX + 0.78, y_leg + 0.09, "Far-edge step ribbon — doubled 2×6 PT SYP (v13 new)", fs=6.8, bold=True, ha="left")
label(PX + 0.78, y_leg + 0.26, "Lag-bolted to outer rim/drop-board face; 11'-9\" long, right corner to midpoint", fs=5.8, ha="left", color="#444444")

y_leg = 11.25
rect(PX + 0.08, y_leg, 0.60, 0.40, C_FAR_TREAD, EC_FAR_TREAD, lw=1.5, zorder=3)
label(PX + 0.78, y_leg + 0.09, "Far-edge tread planks — 2× MoistureShield Vision 5.4\" (v13 new)", fs=6.8, bold=True, ha="left")
label(PX + 0.78, y_leg + 0.26, "10.9\" depth | 6\" AG | Open riser | Tiger Claw TC-G or Cortex fasteners", fs=5.8, ha="left", color="#444444")

y_leg = 12.05
rect(PX + 0.08, y_leg, 0.60, 0.40, C_FAR_BLOCK, EC_FAR_BLOCK, lw=1.5, zorder=3)
label(PX + 0.78, y_leg + 0.09, "Far-step precast deck block (12\"×12\") — 5 total @ ≈28\" OC", fs=6.8, bold=True, ha="left")
label(PX + 0.78, y_leg + 0.26, "On 4\" compacted #57 gravel pad | ¼–½\" seasonal heave accepted", fs=5.8, ha="left", color="#cc4400")

y_leg = 12.85
rect(PX + 0.08, y_leg, 0.60, 0.40, C_HANGER, EC_HANGER, lw=2.5, zorder=3)
label(PX + 0.78, y_leg + 0.09, "Simpson HU210-3 (or eq.) — girder-to-ledger hanger (v13 new)", fs=6.8, bold=True, ha="left")
label(PX + 0.78, y_leg + 0.26, "3 places; ½\" HDG bolts back-blocked from basement at each + IRC R507.9.1.3 lags", fs=5.8, ha="left", color="#444444")

y_leg = 13.65
rect(PX + 0.08, y_leg, 0.60, 0.40, C_GIRDER, EC_GIRDER, lw=2, zorder=3, alpha=FRAME_ALPHA)
label(PX + 0.78, y_leg + 0.09, "Framing (background, 40% opacity) — 6 piers in v13 (was 9)", fs=6.8, bold=True, ha="left")
label(PX + 0.78, y_leg + 0.26, "House-side pier row dropped; middle (y=8'-1.5\") + outer (y=16'-3\") rows remain", fs=5.8, ha="left", color="#444444")

# ══════════════════════════════════════════════════════════════════════════════
# SAVE
# ══════════════════════════════════════════════════════════════════════════════
out_path = "/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/owner_inbox/deck_blueprint/deck_plan.png"
fig.savefig(out_path, dpi=DPI, bbox_inches="tight", facecolor="white")
print(f"Saved: {out_path}")
print(f"Field plank count: {NUM_PLANKS}")
print(f"Pier rows: {PIER_Y}  (6 piers total, house-side row dropped)")
print(f"Far-edge step X range: {FAR_STEP_X_LEFT:.3f} to {FAR_STEP_X_RIGHT:.3f} ft")
print(f"Far-edge step length: {FAR_STEP_LEN*12:.1f}\" = {FAR_STEP_LEN:.3f} ft")
print(f"Far-edge step tread depth: {FAR_TREAD_DEPTH*12:.2f}\"")
print(f"Far block positions (framing x): {[f'{bx:.2f}ft' for bx in FAR_BLOCK_X]}")
print(f"Far block positions (absolute from left): {[f'{a}ft' for a in FAR_BLOCK_ABS]}")
print(f"Hanger locations x: {HANGER_LOCATIONS}")
print(f"LEFT_PF_X0={LEFT_PF_X0:.4f}  LEFT_PF_X1={LEFT_PF_X1:.4f}")
print(f"FAR_PF_Y0={FAR_PF_Y0:.4f}  FAR_PF_Y1={FAR_PF_Y1:.4f}")
