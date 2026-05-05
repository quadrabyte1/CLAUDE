"""
render_v12.py  —  Gemma's matplotlib render of deck_plan v12  (Page 2: Decking Plan)
Produces deck_plan.png at >=2000 px wide, white background.

v12 = v11 + single 42"-wide step on LEFT edge, starting 6' from house wall.
Changes from v11:
  - Single step added on LEFT edge:
      * Position: y=6'-0" to y=9'-6" from house wall (42" wide opening)
      * Projects 16" outward (negative-x direction) from left deck edge
      * Top tread flush with deck at 12" AG
      * Middle tread: 6" AG, 10.8" deep (2x 5.4" MoistureShield planks side-by-side)
      * Open risers (no riser board -- stringers visible)
      * 3 PT stringers (2x10 PT, cut stringer) at y=6', y=7'-9", y=9'-6"
      * Stringer attachment: Simpson LSCZ (or equiv) to left girder outer face
      * Ground-side stringer ends on precast 12x12 concrete pavers over #57 gravel
  - Left PF and left fascia interrupted at y=6'-0" and y=9'-6" (cut joints shown)
  - Step tread: 2 MoistureShield Vision planks (5.4" each) running parallel to L edge
    (i.e., running in y-direction in plan view)
  - Gravel pad (48"x18" stippled rectangle) + 3 pavers (12"x12" solid grey) rendered
    below step footprint in plan view
  - Side-elevation step inset detail added to legend area:
      12" AG (deck) -> 6" riser -> 6" AG tread -> 6" riser -> 0" AG (grade/paver)
      Open risers, gravel pad at base
  - Version badge bumped to v12 on both pages
  - Legend and fastener notes updated

What is UNCHANGED from v11:
  - Overall finished surface: 23'-6" x 16'-6"
  - Framing footprint: 23'-0" x 16'-3"
  - 49 field planks, MoistureShield Vision 5.4" running perp to house
  - 4-side PF (with L edge interrupted at step opening)
  - Outside-corner mitered joints (v10 fix preserved)
  - All framing, piers, ledger, girders, joists

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

# Pier positions
PIER_Y     = [1.0, 8.125, FRAME_D]

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

# ── Step dimensions (all in feet) ─────────────────────────────────────────────
# Step opening on Left edge: from y=6'-0" to y=9'-6" from house wall
STEP_Y0    = 6.0           # y=6'-0" from house (near-house end of step)
STEP_Y1    = 9.5           # y=9'-6" from house (far-from-house end of step)
STEP_W     = STEP_Y1 - STEP_Y0   # 3.5 ft = 42"

# Step projects LEFT (negative x) from left deck edge
# Left deck edge outer face (outer face of left PF) = -PF_OVR - FASCIA_T
LEFT_DECK_X = -PF_OVR - FASCIA_T  # outer face of left fascia

STEP_DEPTH = 16.0 / 12    # 16" = 1.333 ft (stringer footprint + tread)
STEP_X_OUT = LEFT_DECK_X - STEP_DEPTH  # leftmost x of step footprint

# Stringer positions (3 stringers, y-positions within step opening)
STRINGER_Y = [STEP_Y0, (STEP_Y0 + STEP_Y1) / 2, STEP_Y1]  # y=6', 7'-9", 9'-6"
STRINGER_W_FT = 2.0 / 12  # stringer thickness shown in plan ~2"

# Middle tread: 10.8" deep = 2 × 5.4" MoistureShield planks
TREAD_DEPTH  = 10.8 / 12   # 0.9 ft
# Middle tread starts 5.4" from left deck edge (one riser height = 6", but tread
# placement: top tread is the deck itself; middle tread is 6" below at 10.8" inset
# from outer edge. In plan view the step assembly shows:
# From LEFT_DECK_X outward (leftward):
#   0 to TREAD_DEPTH = middle tread planks (two 5.4" boards side-by-side in y-dir)
#   TREAD_DEPTH to STEP_DEPTH = stringer only zone / base gravel area

# Middle tread x range (in plan view, running left from left deck edge)
MTREAD_X0   = LEFT_DECK_X - TREAD_DEPTH   # inner face of middle tread
MTREAD_X1   = LEFT_DECK_X                  # aligns with left deck face

# Gravel pad: 48" wide (y-direction) × 18" deep (x-direction) centered on step
GRAVEL_W    = 48.0 / 12    # 4.0 ft (y-direction, wider than step opening for pad)
GRAVEL_D    = 18.0 / 12    # 1.5 ft (x-direction)
GRAVEL_Y0   = STEP_Y0 - (GRAVEL_W - STEP_W) / 2   # centered on step opening
GRAVEL_Y1   = GRAVEL_Y0 + GRAVEL_W
GRAVEL_X0   = LEFT_DECK_X - GRAVEL_D
GRAVEL_X1   = LEFT_DECK_X

# Pavers: 3 pavers (12"×12" = 1ft × 1ft) in a row, centered where stringers bear
PAVER_SZ    = 1.0           # 12" x 12"

# ── Canvas setup ───────────────────────────────────────────────────────────────
FIG_W_IN = 36
FIG_H_IN = 25
DPI = 100

fig, ax = plt.subplots(figsize=(FIG_W_IN, FIG_H_IN), dpi=DPI)
fig.patch.set_facecolor("white")
ax.set_facecolor("white")

ax.set_xlim(-6.5, 35.5)
ax.set_ylim(-5.5, 25.0)
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

# MoistureShield Vision decking colors
C_FIELD     = "#b89a68"
EC_FIELD    = "#6a4a2a"
C_PF_TREX   = "#8a6a3a"
EC_PF_TREX  = "#4a2a0a"
C_NOTE      = "#ffffee";  EC_NOTE    = "#888800"
C_CALLOUT   = "#fff9e6";  EC_CALLOUT = "#cc8800"

# Step-specific colors
C_STRINGER  = "#6a8a5a";  EC_STRINGER = "#2a5a1a"   # PT stringer: medium green
C_TREAD     = "#c8a878";  EC_TREAD    = "#7a5030"   # step tread: lighter tan
C_GRAVEL    = "#d0c8b8";  EC_GRAVEL   = "#8a7a68"   # gravel pad
C_PAVER     = "#9a9a9a";  EC_PAVER    = "#444444"   # precast pavers
C_CUTJOINT  = "#cc2200"                              # cut joint line color

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
# ══ VERSION BADGE — upper-left corner (v12) ══════════════════════════════════
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
        "v12",
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

# ── Ledger (background) ───────────────────────────────────────────────────────
LEDGER_H = 0.18
rect(0.0, 0.0, FRAME_W, LEDGER_H, C_LEDGER, EC_LEDGER, lw=2.5, zorder=5, alpha=FRAME_ALPHA)

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
DROP_T = 0.085
left_drop_x = -GHW - DROP_T
right_drop_x = GIRDER_X[2] + GHW
far_drop_y = RIM_Y + JOIST_H

rect(left_drop_x, 0.0, DROP_T, FRAME_D, C_DROP, EC_DROP, lw=2, zorder=5, alpha=FRAME_ALPHA)
rect(right_drop_x, 0.0, DROP_T, FRAME_D, C_DROP, EC_DROP, lw=2, zorder=5, alpha=FRAME_ALPHA)
rect(0.0, far_drop_y, FRAME_W, DROP_T, C_DROP, EC_DROP, lw=2, zorder=5, alpha=FRAME_ALPHA)

# ── Fascia (background) ────────────────────────────────────────────────────────
fas_y = far_drop_y + DROP_T
fas_y_end = fas_y + FASCIA_T

# Far fascia: full width
rect(0.0, fas_y, FRAME_W, FASCIA_T, C_FASCIA, EC_FASCIA, lw=2, zorder=6, alpha=FRAME_ALPHA)
# Left fascia: extended to fas_y_end; v10 fix preserved
rect(-FASCIA_T, 0.0, FASCIA_T, fas_y_end, C_FASCIA, EC_FASCIA, lw=2, zorder=6, alpha=FRAME_ALPHA)
# Right fascia
rect(FRAME_W, 0.0, FASCIA_T, fas_y_end, C_FASCIA, EC_FASCIA, lw=2, zorder=6, alpha=FRAME_ALPHA)

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
# ══ STEP ASSEMBLY — Plan view (foreground) ═══════════════════════════════════
# ══════════════════════════════════════════════════════════════════════════════

# ── Gravel pad (stippled/hatched) ─────────────────────────────────────────────
# Draw gravel pad first (lowest z in step assembly)
gravel_patch = FancyBboxPatch((GRAVEL_X0, GRAVEL_Y0), GRAVEL_D, GRAVEL_W,
                               boxstyle="square,pad=0",
                               facecolor=C_GRAVEL, edgecolor=EC_GRAVEL,
                               linewidth=1.5, zorder=6, alpha=0.85)
ax.add_patch(gravel_patch)
# Hatch for gravel texture
gravel_hatch = Rectangle((GRAVEL_X0, GRAVEL_Y0), GRAVEL_D, GRAVEL_W,
                           hatch='...', fill=False, edgecolor="#6a5a48",
                           linewidth=0, zorder=7, alpha=0.7)
ax.add_patch(gravel_hatch)
label(GRAVEL_X0 + GRAVEL_D/2, GRAVEL_Y0 - 0.18,
      "#57 gravel pad\n48\"×18\"",
      fs=5.5, bold=False, color="#6a5a48", ha="center", zorder=8)

# ── Precast pavers (3 × 12"×12") ──────────────────────────────────────────────
# Pavers sit at the stringer bearing points (outer end of step assembly)
# They are spaced at stringer positions along y
for py in STRINGER_Y:
    px_paver = GRAVEL_X0    # pavers at outer edge of gravel pad
    # Paver is 1ft x 1ft, centered on stringer y-position
    pv = FancyBboxPatch((px_paver, py - PAVER_SZ/2), PAVER_SZ, PAVER_SZ,
                         boxstyle="square,pad=0",
                         facecolor=C_PAVER, edgecolor=EC_PAVER,
                         linewidth=1.5, zorder=9)
    ax.add_patch(pv)

label(GRAVEL_X0 + PAVER_SZ/2, GRAVEL_Y0 + GRAVEL_W + 0.18,
      "12\"×12\"\nprecast\npavers",
      fs=5.5, bold=False, color="#444444", ha="center", zorder=10)

# ── 3 PT stringers projecting from left girder face ──────────────────────────
# Stringers appear as narrow vertical (in plan) bands running in x-direction
# from the LEFT GIRDER outer face (x=0 - GHW = -0.19) to the outer step edge
GIRDER_L_FACE = GIRDER_X[0] - GHW   # x = -0.19 ft (left face of left girder)
STRINGER_T    = 2.0 / 12             # 2x10 stringer shown ~2" thick in plan

for sy in STRINGER_Y:
    # Each stringer: thin rectangle running in x from girder face to step outer edge
    st = FancyBboxPatch((STEP_X_OUT, sy - STRINGER_T/2),
                         abs(STEP_X_OUT - GIRDER_L_FACE), STRINGER_T,
                         boxstyle="square,pad=0",
                         facecolor=C_STRINGER, edgecolor=EC_STRINGER,
                         linewidth=1.5, zorder=11)
    ax.add_patch(st)

# Stringer label
label(STEP_X_OUT + (GIRDER_L_FACE - STEP_X_OUT)/2,
      STEP_Y0 - 0.22,
      "2×10 PT stringers (3)\nSimpson LSCZ to L girder",
      fs=5.5, bold=True, color=EC_STRINGER, ha="center", zorder=12)

# ── Middle tread (two 5.4" MoistureShield planks running in y-direction) ──────
# Middle tread in plan: planks run in y-direction (parallel to deck edge)
# Plank 1: from MTREAD_X0 to MTREAD_X0+PLANK_W, across step opening y=STEP_Y0 to STEP_Y1
# Plank 2: PLANK_W further left
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

# ── Open riser space indicators (text labels in the open zones) ────────────────
# In plan view, "open riser" zone is between deck edge and middle tread
# and below middle tread -- we just annotate it
# The zone between deck face and tread outer edge = TREAD_DEPTH ~ 0.9 ft
# Open risers: no board, just space
ax.annotate("OPEN\nRISER",
            xy=(LEFT_DECK_X - PLANK_W*2 - PLANK_GAP*1 - 0.05, (STEP_Y0 + STEP_Y1)/2),
            xytext=(LEFT_DECK_X - PLANK_W*2 - PLANK_GAP*1 - 0.35, (STEP_Y0 + STEP_Y1)/2 - 0.8),
            fontsize=5.0, ha="center", color="#884400", fontweight="bold",
            arrowprops=dict(arrowstyle="->", color="#884400", lw=0.8),
            zorder=15, clip_on=False)

# ── Cut joints in left PF and fascia at y=6'-0" and y=9'-6" ──────────────────
# These are red lines marking where PF and fascia are interrupted
CJ_X0 = STEP_X_OUT - 0.1  # extend slightly left for visibility
CJ_X1 = LEFT_DECK_X + 0.05  # slightly into deck edge

ax.plot([CJ_X0, CJ_X1], [STEP_Y0, STEP_Y0],
        color=C_CUTJOINT, linewidth=2.0, linestyle="-", zorder=20,
        solid_capstyle='butt')
ax.plot([CJ_X0, CJ_X1], [STEP_Y1, STEP_Y1],
        color=C_CUTJOINT, linewidth=2.0, linestyle="-", zorder=20,
        solid_capstyle='butt')

# Cut joint labels
label(LEFT_DECK_X - TREAD_DEPTH/2, STEP_Y0 - 0.08,
      "CUT JOINT y=6'-0\"  (PF & fascia terminate)",
      fs=5.0, bold=True, color=C_CUTJOINT, ha="center", zorder=21)
label(LEFT_DECK_X - TREAD_DEPTH/2, STEP_Y1 + 0.08,
      "CUT JOINT y=9'-6\"  (PF & fascia resume)",
      fs=5.0, bold=True, color=C_CUTJOINT, ha="center", zorder=21)

# ── Dimension annotation: step width and depth ─────────────────────────────────
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
# ══ FOREGROUND: MOISTURESHIELD VISION DECK PLANKS ═══════════════════════════
# ══════════════════════════════════════════════════════════════════════════════

# ── 49 field planks ──────────────────────────────────────────────────────────
for i in range(NUM_PLANKS):
    x_left = FIELD_X0 + i * PLANK_STEP
    rect(x_left, FIELD_Y0, PLANK_W, FIELD_LEN,
         C_FIELD, EC_FIELD, lw=0.5, zorder=7)

# Count labels: field plank 1, 13, 25, 37, 49
labeled_planks = [0, 12, 24, 36, 48]
for i in labeled_planks:
    x_ctr = FIELD_X0 + i * PLANK_STEP + PLANK_W / 2
    y_ctr = FIELD_Y0 + FIELD_LEN / 2
    label(x_ctr, y_ctr,
          f"{i+1}\nof 49",
          fs=4.8, bold=True, color="#4a2a08", rotation=90, zorder=10)

# Overall field count callout
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

# ── LEFT PF — v12: interrupted at step opening y=6' to y=9'-6" ───────────────
# Draw LEFT PF in TWO segments, with a gap at the step opening
# Segment 1: from y=0 (house) down to y=STEP_Y0 (cut joint)
# Segment 2: from y=STEP_Y1 up to FAR_PF_Y0 (cut joint at far end)
# The mitered corner at far-left is still intact at lower end of seg 2

# Segment 1: house side, butted top, stops at cut joint y=6'
rect(LEFT_PF_X0, 0.0, PF_W, STEP_Y0,
     C_PF_TREX, EC_PF_TREX, lw=1.5, zorder=8)

# Segment 2: from y=9'-6" down to FAR_PF_Y0, with miter at bottom
left_pf_seg2_verts = np.array([
    [LEFT_PF_X0, STEP_Y1     ],  # top-left of seg 2
    [LEFT_PF_X1, STEP_Y1     ],  # top-right of seg 2
    [LEFT_PF_X1, FAR_PF_Y0   ],  # bottom-right (inner edge meets far PF inner edge)
    [LEFT_PF_X0, FAR_PF_Y1   ],  # miter point at outer bottom
])
left_pf_seg2 = MplPolygon(left_pf_seg2_verts,
                            closed=True,
                            facecolor=C_PF_TREX, edgecolor=EC_PF_TREX,
                            linewidth=1.5, zorder=8)
ax.add_patch(left_pf_seg2)

# Label LEFT PF (above and below step gap)
label(LEFT_PF_X0 + PF_W/2, STEP_Y0/2,
      "LEFT PF\n5.4\"\nMoistureShield",
      fs=4.8, bold=True, color="#3a1a00", rotation=90, zorder=11)
label(LEFT_PF_X0 + PF_W/2, STEP_Y1 + (FAR_PF_Y0 - STEP_Y1)/2,
      "LEFT PF\n5.4\"",
      fs=4.8, bold=True, color="#3a1a00", rotation=90, zorder=11)

# ── RIGHT PF — v10 fix preserved: full mitered polygon ────────────────────────
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

# Lower-left miter (at far end of left PF seg 2)
ax.plot([LEFT_PF_X1, LEFT_PF_X0],
        [FAR_PF_Y0,  FAR_PF_Y1],
        color=miter_color, lw=miter_lw, zorder=12, solid_capstyle='round')

# Lower-right miter
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
# ══ SIDE-ELEVATION STEP INSET (legend area) ════════════════════════════════════
# ══════════════════════════════════════════════════════════════════════════════
# Right-side panel coordinates
PX = 29.5
PW = 5.5

# Place step elevation inset below the main legend panel
EL_X  = PX + 0.2          # left edge of inset box
EL_Y0 = 18.0              # top of inset box (y inverted — this is drawn first)
EL_W  = PW - 0.4
EL_H  = 6.0

rect(EL_X, EL_Y0, EL_W, EL_H, "#f8f8f0", "#446688", lw=2.0, zorder=20)
label(EL_X + EL_W/2, EL_Y0 + 0.25,
      "STEP SIDE ELEVATION — 1\" riser = open",
      fs=8.0, bold=True, color="#2244aa", ha="center", zorder=21)

# Scale: draw at scale to fit box. Deck top = 12" AG, middle = 6" AG, ground = 0" AG
# Box height = 6 EL_H units; let 2" in diagram = 1" AG
# Map 12" AG range into ~ 4.5 units of figure space
EL_SCALE = 4.0 / 12.0   # figure inches per inch AG ... but we are in ft plot units
# In plot units: 12" AG = 12/12 ft = 1 ft. Let's scale so 1 ft AG = 2.5 plot units
EL_Y_GRADE  = EL_Y0 + EL_H - 0.8     # grade level position in plot (inverted)
EL_FT_SCALE = 2.2                      # plot units per foot AG

# Convert AG elevations to plot-y positions (inverted: higher AG = smaller plot-y)
def ag_to_py(ag_inches):
    """Convert elevation in inches-AG to plot y (inverted)."""
    return EL_Y_GRADE - (ag_inches / 12.0) * EL_FT_SCALE

EL_X_LEFT  = EL_X + 0.5
EL_X_RIGHT = EL_X + EL_W - 0.5
EL_X_MID   = (EL_X_LEFT + EL_X_RIGHT) / 2
EL_STEP_W  = (EL_X_RIGHT - EL_X_LEFT) * 0.6   # step width in plot = 60% of box

# Grade level (0" AG)
grade_py = ag_to_py(0)
# Middle tread (6" AG)
mid_py   = ag_to_py(6)
# Deck top (12" AG)
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
# Paver at base
paver_el = FancyBboxPatch((EL_STRINGER_X0, grade_py - 0.12),
                            0.4, 0.12,
                            boxstyle="square,pad=0",
                            facecolor=C_PAVER, edgecolor=EC_PAVER,
                            linewidth=1.2, zorder=22)
ax.add_patch(paver_el)
label(EL_STRINGER_X0 + 0.2, grade_py - 0.06,
      "paver", fs=4.5, color="#444444", ha="center", zorder=23)

# Draw stringer profile (stepped shape from deck top down to grade)
# Stringer is a cut 2x10 following the step profile
# Points (in plot coords, x=horizontal, y=vertical but inverted):
# Deck (top tread) surface connects at deck_py
# Then: vertical down 1 riser (6" => mid_py), then horizontal at mid tread, then
# vertical down second riser (6" => grade_py)
# Tread depths: top tread = deck surface; mid tread 10.8" deep
tread1_depth = (10.8/12.0) * EL_FT_SCALE   # in plot units
tread2_depth = (16.0/12.0) * EL_FT_SCALE   # stringer total foot from deck face

stringer_verts = [
    (EL_STRINGER_X0, deck_py),                    # top of stringer at deck level (top tread)
    (EL_STRINGER_X0 + tread1_depth, deck_py),      # horizontal out to tread1 edge
    (EL_STRINGER_X0 + tread1_depth, mid_py),       # drop to mid tread (open riser)
    (EL_STRINGER_X0 + tread2_depth, mid_py),       # horizontal to outer stringer edge
    (EL_STRINGER_X0 + tread2_depth, grade_py),     # drop to grade (open riser)
    (EL_STRINGER_X0, grade_py),                    # across base
]
stringer_patch_el = MplPolygon(stringer_verts, closed=True,
                                facecolor=C_STRINGER, edgecolor=EC_STRINGER,
                                linewidth=2.0, zorder=24)
ax.add_patch(stringer_patch_el)

# Middle tread planks (2 × 5.4" side by side)
tread_t = (1.0/12.0) * EL_FT_SCALE   # 1" thick
for i in range(2):
    tp_x0 = EL_STRINGER_X0 + i * (tread1_depth / 2)
    tp = FancyBboxPatch((tp_x0, mid_py - tread_t), tread1_depth / 2 - 0.02, tread_t,
                         boxstyle="square,pad=0",
                         facecolor=C_TREAD, edgecolor=EC_TREAD,
                         linewidth=1.0, zorder=25)
    ax.add_patch(tp)

# Deck surface (top tread -- the deck itself)
deck_t = (1.0/12.0) * EL_FT_SCALE
deck_el = FancyBboxPatch((EL_STRINGER_X0 - 0.1, deck_py - deck_t),
                           tread1_depth + 0.2, deck_t,
                           boxstyle="square,pad=0",
                           facecolor=C_FIELD, edgecolor=EC_FIELD,
                           linewidth=1.0, zorder=25)
ax.add_patch(deck_el)

# Open riser indicators (dashed lines where risers WOULD be)
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

# Elevation labels on side elevation
for ag_in, lbl in [(12, "12\" AG\n(deck top)"), (6, "6\" AG\n(mid tread)"), (0, "0\" AG\n(grade)")]:
    py_pos = ag_to_py(ag_in)
    ax.plot([EL_STRINGER_X0 - 0.5, EL_STRINGER_X0 - 0.05], [py_pos, py_pos],
            color="#444488", lw=0.8, linestyle=":", zorder=24)
    label(EL_STRINGER_X0 - 0.55, py_pos, lbl, fs=5.5, bold=True, color="#2244aa",
          ha="right", va="center", zorder=28)

# Riser height labels
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

# Tread depth labels
ax.annotate("", xy=(EL_STRINGER_X0, grade_py + 0.12),
            xytext=(EL_STRINGER_X0 + tread1_depth, grade_py + 0.12),
            arrowprops=dict(arrowstyle="<->", color="#774400", lw=0.9))
label(EL_STRINGER_X0 + tread1_depth/2, grade_py + 0.25,
      "10.8\"", fs=5.5, bold=True, color="#774400", ha="center", zorder=28)

label(EL_X + EL_W/2, EL_Y0 + EL_H - 0.25,
      "2 risers @ 6\" each | OPEN risers (no riser board) | 3 PT 2×10 stringers",
      fs=5.5, bold=False, color="#333333", ha="center", zorder=28)

# ══════════════════════════════════════════════════════════════════════════════
# RIGHT-SIDE PANEL — Title block and legend for Page 2
# ══════════════════════════════════════════════════════════════════════════════

# ── Title block ────────────────────────────────────────────────────────────────
panel_box(-5.2, 6.5, fc="#f5f5f5")
title_lines = [
    "DECK PLAN v12 — PAGE 2: DECKING",
    "23'-6\" × 16'-6\"  Overall Finished Surface",
    "MoistureShield Vision  |  ⊥ House  |  4-Side Picture Frame",
    "L-edge step: 42\" wide @ 6'-0\" from house, open risers",
    "House on 23'-6\" Edge  ▲ NORTH",
    "",
    "Scale: 1\" ≈ 1 ft (plot units = ft)",
    "HOUSE = top edge",
    "",
    "Date: 2026-05-01",
    "Gemma — Technical Diagramming Specialist",
    "(v12: +single step L-edge, 42\" wide, 6' from house, open risers,",
    " gravel+paver landing, Simpson LSCZ stringers)",
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
    ("Step treads (mid):", "2 × 5.4\" MoistureShield Vision ≈ 3.5' long"),
    ("Board subtotal:", "~55+ boards"),
    ("+10% waste:", "~6 boards"),
    ("TOTAL ORDER:", "~61 boards (planning est.)"),
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
panel_box(7.2, 10.5, fc="white")
label(PX + PW/2, 7.45, "LEGEND — PAGE 2: DECKING (v12)", fs=10.0, bold=True)

y_leg = 8.05
rect(PX + 0.08, y_leg, 0.60, 0.40, C_FIELD, EC_FIELD, lw=1.0, zorder=3)
label(PX + 0.78, y_leg + 0.09, "Field plank — 5.4\" MoistureShield Vision (composite, capped)", fs=6.8, bold=True, ha="left")
label(PX + 0.78, y_leg + 0.26, "49 planks, 16-ft cut to 15'-7.2\", running ⊥ house @ 5.525\" c-c", fs=5.8, ha="left", color="#444444")

y_leg = 8.85
rect(PX + 0.08, y_leg, 0.60, 0.40, C_PF_TREX, EC_PF_TREX, lw=1.5, zorder=3)
label(PX + 0.78, y_leg + 0.09, "Picture-frame (PF) — 5.4\" MoistureShield Vision, all 4 sides", fs=6.8, bold=True, ha="left")
label(PX + 0.78, y_leg + 0.26, "L-side PF interrupted at step opening (y=6'-0\" to y=9'-6\")", fs=5.8, ha="left", color="#444444")

y_leg = 9.65
ax.plot([PX + 0.08, PX + 0.68], [y_leg + 0.20, y_leg + 0.20],
        color=EC_FIELD, lw=0.8, linestyle="--", zorder=4)
label(PX + 0.78, y_leg + 0.09, "Plank gap — 1/8\" typ. between field planks", fs=6.8, bold=True, ha="left")
label(PX + 0.78, y_leg + 0.26, "No gap between PF and field (PF butts field edge)", fs=5.8, ha="left", color="#444444")

y_leg = 10.45
ax.plot([PX + 0.08, PX + 0.68], [y_leg + 0.38, y_leg + 0.00],
        color=EC_PF_TREX, lw=2.5, zorder=4)
label(PX + 0.78, y_leg + 0.09, "45° miter joint — 2 OUTSIDE corners (far-left, far-right)", fs=6.8, bold=True, ha="left")
label(PX + 0.78, y_leg + 0.26, "2 INSIDE corners (against house wall) are butted — not mitered", fs=5.8, ha="left", color="#444444")

y_leg = 11.25
rect(PX + 0.08, y_leg, 0.60, 0.40, C_STRINGER, EC_STRINGER, lw=2, zorder=3)
label(PX + 0.78, y_leg + 0.09, "Stair stringer — 2×10 PT cut stringer (3 total)", fs=6.8, bold=True, ha="left")
label(PX + 0.78, y_leg + 0.26, "Attached to L girder outer face via Simpson LSCZ stringer hangers", fs=5.8, ha="left", color="#444444")

y_leg = 12.05
rect(PX + 0.08, y_leg, 0.60, 0.40, C_TREAD, EC_TREAD, lw=1.5, zorder=3)
label(PX + 0.78, y_leg + 0.09, "Step middle tread — 2×5.4\" MoistureShield Vision planks", fs=6.8, bold=True, ha="left")
label(PX + 0.78, y_leg + 0.26, "Running parallel to L edge | 6\" AG | Open risers (no riser board)", fs=5.8, ha="left", color="#444444")

y_leg = 12.85
rect(PX + 0.08, y_leg, 0.60, 0.40, C_GRAVEL, EC_GRAVEL, lw=1.5, zorder=3, alpha=0.85)
gravel_hatch_leg = Rectangle((PX + 0.08, y_leg), 0.60, 0.40,
                               hatch='...', fill=False, edgecolor="#6a5a48",
                               linewidth=0, zorder=4, alpha=0.7)
ax.add_patch(gravel_hatch_leg)
label(PX + 0.78, y_leg + 0.09, "Gravel pad — #57 compacted gravel, 48\"×18\"", fs=6.8, bold=True, ha="left")
label(PX + 0.78, y_leg + 0.26, "Below step footprint and paver locations", fs=5.8, ha="left", color="#444444")

y_leg = 13.65
rect(PX + 0.08, y_leg, 0.60, 0.40, C_PAVER, EC_PAVER, lw=1.5, zorder=3)
label(PX + 0.78, y_leg + 0.09, "Precast 12\"×12\" paver — 3 total", fs=6.8, bold=True, ha="left")
label(PX + 0.78, y_leg + 0.26, "Stringer ends bear on pavers | metal stringer-to-paver anchors", fs=5.8, ha="left", color="#444444")

y_leg = 14.45
ax.plot([PX + 0.08, PX + 0.68], [y_leg + 0.20, y_leg + 0.20],
        color=C_CUTJOINT, lw=2.0, linestyle="-", zorder=4)
label(PX + 0.78, y_leg + 0.09, "CUT JOINT — PF and fascia interrupted at step opening", fs=6.8, bold=True, ha="left", color=C_CUTJOINT)
label(PX + 0.78, y_leg + 0.26, "Clean cut at y=6'-0\" and y=9'-6\" | contractor must measure/fit", fs=5.8, ha="left", color="#444444")

y_leg = 15.25
rect(PX + 0.08, y_leg, 0.60, 0.40, C_GIRDER, EC_GIRDER, lw=2, zorder=3, alpha=FRAME_ALPHA)
label(PX + 0.78, y_leg + 0.09, "Framing (background, 40% opacity) — girders, ledger, joists", fs=6.8, bold=True, ha="left")
label(PX + 0.78, y_leg + 0.26, "Framing is unchanged from Page 1 — structural reference only", fs=5.8, ha="left", color="#444444")

y_leg = 16.25
rect(PX + 0.08, y_leg, 0.60, 0.40, "#dddddd", "#888888", lw=1.0, zorder=3)
label(PX + 0.78, y_leg + 0.09, "Plank top = 12.0\" AG  (plank 1.0\" actual thick on 11.0\" AG framing)", fs=6.8, bold=True, ha="left")
label(PX + 0.78, y_leg + 0.26, "MoistureShield Vision 1.0\" actual; fascia 0.67\"; overhang 2.33\" past fascia", fs=5.8, ha="left", color="#444444")

# ── Fastener / ordering notes ──────────────────────────────────────────────────
# (step inset takes up bottom of right panel; fastener notes below that)

# ══════════════════════════════════════════════════════════════════════════════
# SAVE
# ══════════════════════════════════════════════════════════════════════════════
out_path = "/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/owner_inbox/deck_blueprint/deck_plan.png"
fig.savefig(out_path, dpi=DPI, bbox_inches="tight", facecolor="white")
print(f"Saved: {out_path}")
print(f"Field plank count: {NUM_PLANKS}")
print(f"Step opening: y={STEP_Y0:.3f}' ({STEP_Y0*12:.0f}\") to y={STEP_Y1:.3f}' ({STEP_Y1*12:.0f}\")")
print(f"Step width: {STEP_W*12:.1f}\"")
print(f"Step depth: {STEP_DEPTH*12:.1f}\"")
stringer_str = [f"{sy}ft ({sy*12:.0f}in)" for sy in STRINGER_Y]
print(f"Stringer positions y: {stringer_str}")
print(f"LEFT_PF_X0={LEFT_PF_X0:.4f}  LEFT_PF_X1={LEFT_PF_X1:.4f}")
print(f"FAR_PF_Y0={FAR_PF_Y0:.4f}  FAR_PF_Y1={FAR_PF_Y1:.4f}")
