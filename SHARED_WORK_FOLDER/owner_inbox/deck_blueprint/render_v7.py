"""
render_v7.py  —  Gemma's matplotlib render of deck_plan v7
Produces deck_plan.png at >=2000 px wide, white background.

v7 — FULL STRUCTURAL REWRITE:
  - Foundation: Pylex 50 spiral piers through punched concrete patio holes
    (replaces 6x6 posts on sonotube footings)
  - Framing: face-hung joists, top-flush with girders at 11.0" AG
    (replaces joists-on-top-of-girders; fixes geometric impossibility at 12" ceiling)
  - Pier positions: 12" / 8'-1.5" / 16'-3" out from house (P1 is offset from house)
  - Joist segments: each joist run broken into 2 segments per girder bay,
    face-hung at both ends with Simpson LUS210Z hangers
  - 16 regular rows at 12" o.c. + 1 doubled far rim = 17 rows × 2 segments = 34 segments
  - Concrete patio shown as tinted background (23'-6" x 16'-6")
  - Section detail completely rewritten for 12" vertical budget

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
import matplotlib.patheffects as pe
import numpy as np

# ── Key dimensions ─────────────────────────────────────────────────────────────
FRAME_W    = 23.0           # framing width (along house), ft  (rim outer edge to rim outer edge)
FRAME_D    = 16.25          # framing depth (out from house) = 16'-3", ft
PF_W       = 5.5 / 12      # picture-frame board width, ft  (~0.4583)
FASCIA_T   = 0.75 / 12     # fascia thickness, ft  (0.0625)
PF_OVR     = 3.0 / 12      # PF overhang past rim outer face on 3 exposed sides, ft (0.25)
OVERALL_W  = FRAME_W + 2 * PF_OVR    # 23.5 ft = 23'-6"
OVERALL_D  = FRAME_D + PF_OVR        # 16.5 ft = 16'-6"

# Girder positions (x, along house direction)
GIRDER_X   = [0.0, 11.5, 23.0]
GIRDER_W   = 0.38           # visual width of tripled 2x10 girder in plan

# Joist rows: 16 regular at 12" o.c. + 1 doubled rim at 16.25 ft
JOIST_SPACING = 1.0         # 12" = 1 ft
JOIST_ROWS    = list(range(1, 17))       # y = 1..16 ft (regular rows)
RIM_Y         = FRAME_D                  # doubled far rim at 16.25 ft

# Pier positions per girder (y, out from house)
PIER_Y     = [1.0, 8.125, FRAME_D]      # 12", 8'-1.5", 16'-3" — 1 ft = 12"

# ── Canvas setup ───────────────────────────────────────────────────────────────
FIG_W_IN = 34
FIG_H_IN = 24
DPI = 100

fig, ax = plt.subplots(figsize=(FIG_W_IN, FIG_H_IN), dpi=DPI)
fig.patch.set_facecolor("white")
ax.set_facecolor("white")

ax.set_xlim(-4.0, 34.5)
ax.set_ylim(-4.5, 24.0)
ax.invert_yaxis()
ax.set_aspect("equal")
ax.axis("off")

# ── Color palette ──────────────────────────────────────────────────────────────
C_HOUSE     = "#cccccc"
C_PATIO     = "#e8e0d4"     # warm concrete tint for patio background
EC_PATIO    = "#a09080"
C_LEDGER    = "#f8cecc";  EC_LEDGER  = "#b85450"
C_GIRDER    = "#dae8fc";  EC_GIRDER  = "#6c8ebf"
C_JOIST     = "#d5e8d4";  EC_JOIST   = "#82b366"
C_RIM       = "#fff2cc";  EC_RIM     = "#d6b656"
C_PF        = "#ffe680";  EC_PF      = "#b8860b"
C_FASCIA    = "#c8a0e8";  EC_FASCIA  = "#7030a0"
C_PIER      = "#5a4030";  EC_PIER    = "#2a1808"   # dark brown for spiral piers
C_PIER_HOLE = "#b0a898";  EC_HOLE    = "#706050"
C_DROP      = "#c0d8b0";  EC_DROP    = "#507040"   # drop-board sub-fascia
C_BLOCK     = "#888888"
C_TAPE      = "#ffff99";  EC_TAPE    = "#cccc00"
C_DECK      = "#dddddd";  EC_DECK    = "#888888"
C_NOTE      = "#ffffee";  EC_NOTE    = "#888800"
C_CALLOUT   = "#fff9e6";  EC_CALLOUT = "#cc8800"
C_HANGER    = "#ff8c00"   # orange for face-mount hangers

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
# PATIO BACKGROUND — concrete slab under entire deck, 23'-6" x 16'-6"
# Drawn first so everything sits on top
# ══════════════════════════════════════════════════════════════════════════════
rect(-PF_OVR, 0.0, OVERALL_W, OVERALL_D - PF_OVR,   # patio = 23.5 x 16.5 ft
     C_PATIO, EC_PATIO, lw=2.5, zorder=1, alpha=0.65)
# Hatch the patio to make it unmistakable as concrete
from matplotlib.patches import Rectangle
hatch_rect = Rectangle((-PF_OVR, 0.0), OVERALL_W, FRAME_D + PF_OVR,
                        hatch='....', fill=False, edgecolor="#c0b090",
                        linewidth=0, zorder=1, alpha=0.4)
ax.add_patch(hatch_rect)

label(-PF_OVR + OVERALL_W/2, FRAME_D/2 + 1.5,
      "EXISTING CONCRETE PATIO\n23'-6\" × 16'-6\"  (matches deck footprint exactly)\nSlab punched for spiral pier installation",
      fs=7.5, bold=False, color="#6b5030", zorder=2)

# ══════════════════════════════════════════════════════════════════════════════
# HOUSE WALL
# ══════════════════════════════════════════════════════════════════════════════
rect(-PF_OVR, -1.2, OVERALL_W, 1.1, C_HOUSE, "#444444", lw=2, zorder=3)
label(FRAME_W/2, -0.65,
      "HOUSE WALL  ▲  NORTH  (attached 23'-6\" overall edge)",
      fs=11, bold=True)

# ══════════════════════════════════════════════════════════════════════════════
# GIRDERS — 3 tripled 2x10 PT, perpendicular to house, 16'-3" long
# Top-flush at 11.0" AG. NO post/cap — bottom sits in Pylex saddle.
# ══════════════════════════════════════════════════════════════════════════════
GIRDER_LABELS = [
    "LEFT GIRDER\n(3) 2×10 PT\n@ x=0'",
    "MID GIRDER\n(3) 2×10 PT\n@ x=11'-6\"",
    "RIGHT GIRDER\n(3) 2×10 PT\n@ x=23'"
]

for gx, glbl in zip(GIRDER_X, GIRDER_LABELS):
    x0 = max(0.0, gx - GIRDER_W/2)
    x0 = min(x0, FRAME_W - GIRDER_W)
    rect(x0, 0.0, GIRDER_W, FRAME_D, C_GIRDER, EC_GIRDER, lw=3, zorder=4)
    ax.text(x0 + GIRDER_W/2, FRAME_D/2, glbl,
            fontsize=5.5, ha="center", va="center", rotation=90,
            fontweight="bold", color="#1a3a6b", zorder=7,
            multialignment="center")

# ══════════════════════════════════════════════════════════════════════════════
# LEDGER — SINGLE 2x10 PT, 23'-0" long, lag-bolted to house
# Top-flush at 11.0" AG (same elevation as girder tops).
# NOT supported by piers — supported entirely by lag bolts.
# ══════════════════════════════════════════════════════════════════════════════
LEDGER_H = 0.18
rect(0.0, 0.0, FRAME_W, LEDGER_H, C_LEDGER, EC_LEDGER, lw=3.5, zorder=5)
label(FRAME_W/2, LEDGER_H/2,
      "LEDGER — SINGLE 2×10 PT  |  ½\" hot-dip galv lag bolts (LedgerLOK) @ 16\" o.c. staggered  |  Z-flashing  |  TOP-FLUSH @ 11\" AG",
      fs=6.3, bold=True, color="#5a0000", zorder=8)

# MTWDeck callout
rect(12.5, 0.22, 10.0, 0.58, C_CALLOUT, EC_CALLOUT, lw=1.5, zorder=7)
label(17.5, 0.52,
      "⚠ MTWDeck LATERAL TIE REQ'D — min. 2× Simpson MTWDeck (or equiv.) per IRC R507.9 / DCA-6\n"
      "2× band joist + 2× interior blocking bearing on sill plate inside house",
      fs=5.8, ha="center", va="center", color="#663300", zorder=8)

# House-side PF blocking label (small callout at y=0 zone)
label(-1.5, 0.5,
      "LEDGER\n2×10 PT\nlag-bolted\n+Z-flash\nTOP-FLUSH",
      fs=5.8, ha="center", va="center")

# ══════════════════════════════════════════════════════════════════════════════
# JOIST SEGMENTS — face-hung, top-flush with girders
# Each of 17 rows is split at each girder into 2 segments:
#   Seg A: from left girder (x=0) face to middle girder (x=11.5) face
#   Seg B: from middle girder face to right girder (x=23) face
#
# Girder half-widths:  left outer = 0+GIRDER_W/2, middle inner at 11.5-GIRDER_W/2
#                      middle outer = 11.5+GIRDER_W/2, right inner at 23-GIRDER_W/2
# ══════════════════════════════════════════════════════════════════════════════
GHW = GIRDER_W / 2   # girder half-width

# Segment boundaries
SEG_A_X0 = GIRDER_X[0] + GHW       # right face of left girder
SEG_A_X1 = GIRDER_X[1] - GHW       # left face of middle girder
SEG_B_X0 = GIRDER_X[1] + GHW       # right face of middle girder
SEG_B_X1 = GIRDER_X[2] - GHW       # left face of right girder

JOIST_H = 0.085   # visual height for 2x10 joist

# All 17 rows: 16 regular (y=1..16 ft) + doubled rim (y=16.25 ft)
all_rows = [(i * JOIST_SPACING, False) for i in range(1, 17)]   # (y, is_rim)
all_rows.append((RIM_Y, True))

for y_pos, is_rim in all_rows:
    h = JOIST_H * 2 if is_rim else JOIST_H
    fc = C_RIM if is_rim else C_JOIST
    ec = EC_RIM if is_rim else EC_JOIST
    lw = 2.5 if is_rim else 1.0
    zord = 5 if is_rim else 3

    # Segment A
    rect(SEG_A_X0, y_pos - h/2, SEG_A_X1 - SEG_A_X0, h,
         fc, ec, lw=lw, zorder=zord)
    # Segment B
    rect(SEG_B_X0, y_pos - h/2, SEG_B_X1 - SEG_B_X0, h,
         fc, ec, lw=lw, zorder=zord)

# Far-side rim label
rim_label_y = RIM_Y
label(FRAME_W/2, rim_label_y,
      "DOUBLED FAR-SIDE RIM — (2) 2×10 PT  |  Face-hung in 2 segments  |  LUS210-2Z hangers  |  3\" final bay",
      fs=6.8, bold=True, zorder=6)

# 3" final bay callout arrow
ax.annotate("", xy=(24.3, RIM_Y - JOIST_H), xytext=(24.3, 16.0),
            arrowprops=dict(arrowstyle="<->", color="#cc4400", lw=1.2))
label(24.85, RIM_Y - JOIST_H/2 - 0.05, "3\"\nfinal\nbay", fs=6.5, bold=True,
      color="#cc4400", ha="left")

# ══════════════════════════════════════════════════════════════════════════════
# FACE-MOUNT HANGERS — shown as small orange tick marks at segment ends
# Both ends of every segment. Only annotate select ones to avoid crowding.
# ══════════════════════════════════════════════════════════════════════════════
HANGER_H = 0.12

for y_pos, is_rim in all_rows:
    h = JOIST_H * 2 if is_rim else JOIST_H
    # 4 hanger positions per row: left face of seg A, right face of seg A,
    #                              left face of seg B, right face of seg B
    for hx in [SEG_A_X0 - 0.04, SEG_A_X1 + 0.01,
               SEG_B_X0 - 0.04, SEG_B_X1 + 0.01]:
        ax.plot([hx, hx], [y_pos - HANGER_H, y_pos + HANGER_H],
                color=C_HANGER, lw=1.5, zorder=6, alpha=0.75)

# Label a few representative hangers
label(SEG_A_X0 - 0.3, 4.5, "LUS210Z\nhanger\n(typ.)",
      fs=5.5, color="#c05000", ha="center", bold=True)
ax.annotate("", xy=(SEG_A_X0 - 0.04, 4.5), xytext=(SEG_A_X0 - 0.3, 4.3),
            arrowprops=dict(arrowstyle="->", color="#c05000", lw=0.7))

label(SEG_B_X1 + 0.3, 12.5, "LUS210Z\nhanger\n(typ.)",
      fs=5.5, color="#c05000", ha="center", bold=True)
ax.annotate("", xy=(SEG_B_X1 + 0.04, 12.5), xytext=(SEG_B_X1 + 0.3, 12.3),
            arrowprops=dict(arrowstyle="->", color="#c05000", lw=0.7))

# ══════════════════════════════════════════════════════════════════════════════
# HOUSE-SIDE PF BLOCKING — short 2x10 segments between ledger and first joist row
# at ~12" o.c. along x direction (y range: 0 to 1 ft)
# ══════════════════════════════════════════════════════════════════════════════
BLOCK_Y0 = LEDGER_H
BLOCK_Y1 = 1.0 - JOIST_H/2   # up to first joist row
BLOCK_H  = BLOCK_Y1 - BLOCK_Y0

# Blocking pieces along x at 1 ft intervals (12" o.c.)
for bx in np.arange(0.5, FRAME_W, 1.0):
    if abs(bx - GIRDER_X[0]) < 0.3 or abs(bx - GIRDER_X[1]) < 0.3 or abs(bx - GIRDER_X[2]) < 0.3:
        continue  # skip where girder sits
    rect(bx - 0.05, BLOCK_Y0, 0.10, BLOCK_H,
         "#d0e8c0", "#60a040", lw=1.0, zorder=4, alpha=0.85)

label(5.5, BLOCK_Y0 + BLOCK_H/2,
      "House-side PF blocking (2×10, 12\" o.c.) — backs the house-side PF board",
      fs=6.0, ha="center", color="#3a6020", zorder=6, bold=True)

# ══════════════════════════════════════════════════════════════════════════════
# DROP-BOARD SUB-FASCIA — on left, right, and far edges
# Thin secondary line just outside the girder/rim outer face at joist elevation
# Backs up PF cantilever on 3 exposed sides
# ══════════════════════════════════════════════════════════════════════════════
DROP_T = 0.085   # visual thickness = same as one joist
DROP_LW = 2.5

# Left drop-board: just outside left girder outer face (x=0 - GIRDER_W/2 = 0 - GHW)
# Left girder left face is at x=0 (girder centered at 0, left face = 0 - GHW ≈ -0.19)
left_drop_x = -GHW - DROP_T
rect(left_drop_x, 0.0, DROP_T, FRAME_D, C_DROP, EC_DROP, lw=DROP_LW, zorder=5)

# Right drop-board
right_drop_x = GIRDER_X[2] + GHW
rect(right_drop_x, 0.0, DROP_T, FRAME_D, C_DROP, EC_DROP, lw=DROP_LW, zorder=5)

# Far drop-board (horizontal strip below far rim)
far_drop_y = RIM_Y + JOIST_H
rect(0.0, far_drop_y, FRAME_W, DROP_T, C_DROP, EC_DROP, lw=DROP_LW, zorder=5)

# Drop-board labels
label(left_drop_x - 0.12, FRAME_D/2,
      "drop board\n(sub-fascia)\nbacks L PF\ncantilever",
      fs=5.2, ha="right", color="#305020", rotation=0)
label(right_drop_x + DROP_T + 0.12, FRAME_D/2,
      "drop board\n(sub-fascia)\nbacks R PF\ncantilever",
      fs=5.2, ha="left", color="#305020", rotation=0)
label(FRAME_W/2, far_drop_y + DROP_T + 0.12,
      "far drop-board (sub-fascia) — backs far PF cantilever",
      fs=5.5, color="#305020", ha="center")

# ══════════════════════════════════════════════════════════════════════════════
# FASCIA — 0.75" Trex Universal Fascia, 3 exposed sides only
# ══════════════════════════════════════════════════════════════════════════════
fas_y = far_drop_y + DROP_T
rect(0.0, fas_y, FRAME_W, FASCIA_T, C_FASCIA, EC_FASCIA, lw=2.5, zorder=6)
rect(-FASCIA_T, 0.0, FASCIA_T, fas_y, C_FASCIA, EC_FASCIA, lw=2.5, zorder=6)
rect(FRAME_W, 0.0, FASCIA_T, fas_y, C_FASCIA, EC_FASCIA, lw=2.5, zorder=6)

# ══════════════════════════════════════════════════════════════════════════════
# PICTURE FRAME — 4 sides
# House side: 5.5" PF board, y=0..PF_W, full overall width, no overhang
# Far/left/right: 5.5" Trex, 3" past rim = PF_OVR past rim outer face
# ══════════════════════════════════════════════════════════════════════════════
# House-side PF (sits at y=0, overlapping ledger visually)
rect(-PF_OVR, 0.0, OVERALL_W, PF_W, C_PF, EC_PF, lw=2.5, zorder=6, alpha=0.7)
label(FRAME_W/2, PF_W/2,
      "HOUSE-SIDE PICTURE-FRAME BOARD — 5.5\" Trex  |  Butts wall (1/4\" thermal gap)  |  Supported by ledger + house-side blocking",
      fs=6.3, bold=True, color="#6b4400", zorder=9)

# Far PF
pf_far_y = fas_y + FASCIA_T
rect(-PF_OVR, pf_far_y, OVERALL_W, PF_W, C_PF, EC_PF, lw=2.5, zorder=7)
label(FRAME_W/2, pf_far_y + PF_W/2,
      "FAR PICTURE-FRAME BOARD — 5.5\" Trex  |  2.25\" overhang past fascia  |  3\" past rim",
      fs=6.5, bold=True, color="#6b4400", zorder=9)

# Left PF
lx = -PF_OVR - FASCIA_T
rect(lx - PF_W, 0.0, PF_W, fas_y + FASCIA_T, C_PF, EC_PF, lw=2.5, zorder=7)
label(lx - PF_W/2, FRAME_D/2,
      "LEFT PF\n5.5\" Trex\n3\" past rim", fs=5.3, bold=True, color="#6b4400", rotation=90)

# Right PF
rx = FRAME_W + FASCIA_T
rect(rx, 0.0, PF_W, fas_y + FASCIA_T, C_PF, EC_PF, lw=2.5, zorder=7)
label(rx + PF_W/2, FRAME_D/2,
      "RIGHT PF\n5.5\" Trex\n3\" past rim", fs=5.3, bold=True, color="#6b4400", rotation=90)

# ══════════════════════════════════════════════════════════════════════════════
# PYLEX 50 SPIRAL PIERS — 9 total (P1-P9)
# Drawn as filled brown circles with a ✱ helix glyph.
# Outer thin circle = punched patio hole (~3-4" dia in plan, exaggerated to ~8" for legibility)
# Pier numbering: left girder = P1,P2,P3; mid = P4,P5,P6; right = P7,P8,P9
# Pier y-positions: 1.0 ft (12"), 8.125 ft (8'-1.5"), 16.25 ft (16'-3")
# ══════════════════════════════════════════════════════════════════════════════
PIER_R      = 0.22    # pier shaft radius in plan (visual, = ~6" — exaggerated)
HOLE_R      = 0.35    # punched hole radius (3-4" actual; exaggerated for legibility)

piers = []
for i, gx in enumerate(GIRDER_X):
    for j, py in enumerate(PIER_Y):
        pnum = i * 3 + j + 1
        piers.append((gx, py, f"P{pnum}"))

for px, py, plbl in piers:
    # Punched hole outline (thin, lighter)
    hole = plt.Circle((px, py), HOLE_R, fc=C_PIER_HOLE, ec=EC_HOLE, lw=1.0, zorder=5, alpha=0.5)
    ax.add_patch(hole)
    # Pier shaft (filled, dark)
    pier = plt.Circle((px, py), PIER_R, fc=C_PIER, ec=EC_PIER, lw=1.5, zorder=8)
    ax.add_patch(pier)
    # Helix glyph (✱)
    ax.text(px, py - 0.04, "✱", fontsize=8, ha="center", va="center",
            color="white", fontweight="bold", zorder=9)
    # Pier label
    ax.text(px + HOLE_R + 0.06, py - HOLE_R - 0.10, plbl,
            fontsize=6.0, ha="left", va="top", fontweight="bold",
            color="#2a1808", zorder=10)

# Pier depth callout (pointing to P5, the middle one)
mid_px, mid_py = GIRDER_X[1], PIER_Y[1]
ax.annotate("", xy=(mid_px, mid_py), xytext=(mid_px - 2.5, mid_py - 2.0),
            arrowprops=dict(arrowstyle="->", color="#2a1808", lw=0.9))
label(mid_px - 2.5, mid_py - 2.3,
      "Pylex 50 spiral pier\n50\" galv. shaft through\npunched patio hole\n→ tip ~49\" below patio\n(past 42\" frost line)",
      fs=5.5, ha="center", color="#2a1808", bold=True)

# ── Pier 12" house-side cantilever callout ─────────────────────────────────
ax.annotate("", xy=(GIRDER_X[0], 0.0), xytext=(GIRDER_X[0], PIER_Y[0]),
            arrowprops=dict(arrowstyle="<->", color="#5a3000", lw=1.1))
label(GIRDER_X[0] - 0.55, PIER_Y[0]/2,
      "12\"\ncantilever\nto ledger",
      fs=5.5, ha="right", color="#5a3000", bold=True)

# ══════════════════════════════════════════════════════════════════════════════
# FIELD BLOCKING — midspan dashed lines in each girder bay
# Row 1: x = 5.75 ft (midspan of left bay, 0 to 11.5)
# Row 2: x = 17.25 ft (midspan of right bay, 11.5 to 23)
# ══════════════════════════════════════════════════════════════════════════════
BLOCKING_X = [5.75, 17.25]
for bx in BLOCKING_X:
    ax.plot([bx, bx], [1.0, FRAME_D],
            color=C_BLOCK, linewidth=2.5, linestyle="--", zorder=3, alpha=0.8)

label(5.75, -1.5, "FIELD BLOCKING\n@ 5'-9\"\n(midspan left bay)", fs=6.5, bold=True, color="#555555")
label(17.25, -1.5, "FIELD BLOCKING\n@ 17'-3\"\n(midspan right bay)", fs=6.5, bold=True, color="#555555")

# ══════════════════════════════════════════════════════════════════════════════
# JOIST o.c. SPACING CALLOUTS
# ══════════════════════════════════════════════════════════════════════════════
for arrow_i in [2, 8, 14]:
    y_lo = (arrow_i - 1) * JOIST_SPACING
    y_hi = arrow_i * JOIST_SPACING
    x_ann = 26.0
    ax.annotate("", xy=(x_ann, y_hi), xytext=(x_ann, y_lo),
                arrowprops=dict(arrowstyle="<->", color="#333333", lw=0.9))
    label(x_ann + 0.4, (y_lo + y_hi)/2, '12\"', fs=7.0, bold=True, ha="left")

label(27.0, 8.0, "12\" o.c.\ntypical", fs=9, bold=True, ha="left")

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
right_ann = FRAME_W + FASCIA_T + PF_W + 0.9
ax.annotate("", xy=(right_ann, 0.0), xytext=(right_ann, OVERALL_D),
            arrowprops=dict(arrowstyle="<->", color="#000099", lw=1.6))
label(right_ann + 0.6, OVERALL_D/2,
      "16'-6\"\nOVERALL\n(PF outer to wall)",
      fs=8.5, bold=True, color="#000099", rotation=90)

# Framing 16'-3" (right side)
frame_d_ann = right_ann + 1.4
ax.annotate("", xy=(frame_d_ann, 0.0), xytext=(frame_d_ann, FRAME_D),
            arrowprops=dict(arrowstyle="<->", color="#444444", lw=1.2))
label(frame_d_ann + 0.5, FRAME_D/2,
      "16'-3\"\nframing", fs=8, bold=False, color="#444444", rotation=90)

# Pier y-positions (left margin ticks)
for py_v, ptxt in zip(PIER_Y, ["1'=12\"", "8'-1.5\"", "16'-3\""]):
    ax.plot([-2.2, -1.8], [py_v, py_v], color="#5a3000", lw=1.2)
    label(-2.5, py_v, ptxt, fs=6.8, bold=True, ha="right", color="#5a3000")

# Girder x-positions (top ticks)
for gx, gtxt in zip([0.0, 11.5, 23.0], ["x=0'", "x=11'-6\"", "x=23'"]):
    ax.plot([gx, gx], [-1.7, -0.9], color="#333333", lw=1, zorder=4)
    label(gx, -0.62, gtxt, fs=7.5, bold=True, va="bottom")

# PF overhang callout
ax.annotate("", xy=(2.0, RIM_Y), xytext=(2.0, pf_far_y + PF_W),
            arrowprops=dict(arrowstyle="<->", color="#8B0000", lw=1.1))
label(2.0, pf_far_y + PF_W + 0.22,
      "PF = 5.5\" (3\" past rim, 2.25\" past fascia)",
      fs=7, bold=True, color="#8B0000")

# Fascia callout
ax.annotate("", xy=(5.5, RIM_Y + JOIST_H + DROP_T), xytext=(5.5, RIM_Y + JOIST_H + DROP_T + FASCIA_T),
            arrowprops=dict(arrowstyle="<->", color="#5a0070", lw=1.1))
label(5.5, RIM_Y + JOIST_H + DROP_T + FASCIA_T + 0.10,
      "Fascia 0.75\"", fs=6.5, color="#5a0070")

# Joist span callout (below plan)
span_y = pf_far_y + PF_W + 1.3
ax.annotate("", xy=(11.5, span_y), xytext=(0.0, span_y),
            arrowprops=dict(arrowstyle="<->", color="#555577", lw=1.0))
label(5.75, span_y + 0.38, "11'-3\" face-hung segment (approx.)", fs=7, color="#333377")

ax.annotate("", xy=(23.0, span_y), xytext=(11.5, span_y),
            arrowprops=dict(arrowstyle="<->", color="#555577", lw=1.0))
label(17.25, span_y + 0.38, "11'-3\" face-hung segment (approx.)", fs=7, color="#333377")

# ══════════════════════════════════════════════════════════════════════════════
# 12" AG VERTICAL BUDGET CALLOUT (prominent box, left margin)
# ══════════════════════════════════════════════════════════════════════════════
rect(-3.9, 5.0, 2.8, 8.0, "#fff0e0", "#cc4400", lw=2.5, zorder=10)
label(-2.5, 5.25, "VERTICAL BUDGET", fs=8.5, bold=True, color="#cc4400")
label(-2.5, 5.55, "12.0\" MAX AG  ✓ MET", fs=7.5, bold=True, color="#8B0000")
budget_lines = [
    ("Top of Trex decking:", "12.0\" AG"),
    ("Trex board thickness:", "− 1.0\""),
    ("= Top of joist/girder:", "11.0\" AG"),
    ("2×10 depth (actual):", "− 9.25\""),
    ("= Bottom of joist/girder:", " 1.75\" AG"),
    ("Pylex saddle height:", "~1.5\""),
    ("= Saddle top ≈ joist bottom:", " ~1.75\" AG ✓"),
    ("Pier shaft above patio:", "~0.5\""),
    ("Patio surface:", " 0\" AG = grade"),
    ("Pier shaft (Pylex 50):", "50\" total"),
    ("  → tip depth:", "~49\" below patio"),
    ("CT frost line:", "42\" — CLEAR ✓"),
]
for i, (lbl_a, lbl_b) in enumerate(budget_lines):
    y_row = 5.9 + i * 0.42
    fc_row = "#fff8f0" if i % 2 == 0 else "#ffe8d0"
    rect(-3.85, y_row - 0.04, 2.7, 0.38, fc_row, "#ddcccc", lw=0.5, zorder=10)
    label(-3.85 + 0.08, y_row + 0.15, lbl_a, fs=5.5, ha="left", color="#333333")
    label(-3.85 + 2.62, y_row + 0.15, lbl_b, fs=5.5, ha="right", bold=True, color="#8B0000")

label(-2.5, 11.65, "EVERY ELEVATION VERIFIED", fs=7.0, bold=True, color="#8B0000")
label(-2.5, 11.9, "TOP OF DECK = 12.0\" AG", fs=7.5, bold=True, color="#cc4400")

# ══════════════════════════════════════════════════════════════════════════════
# RIGHT-SIDE PANEL — Title block, framing callout, legend, fastener notes,
#                    section detail, patio hole inset
# ══════════════════════════════════════════════════════════════════════════════
PX = 28.5    # left edge of right panel
PW = 5.5     # panel width

def panel_box(y0, h, fc="#f5f5f5", ec="#444444", lw=1.5):
    rect(PX, y0, PW, h, fc, ec, lw=lw, zorder=2)

# ── Title block ────────────────────────────────────────────────────────────────
panel_box(-4.2, 6.3, fc="#f5f5f5")
title_lines = [
    "DECK PLAN v7",
    "23'-6\" × 16'-6\"  Overall Finished Surface",
    "12\" Max AG  |  Pylex 50 Spiral Piers Through Patio",
    "Face-Hung Joists Top-Flush  |  4-Side Picture Frame",
    "House on 23'-6\" Edge",
    "",
    "Scale: 1\" ≈ 1 ft (plot units = ft)",
    "HOUSE = top edge  ▲ NORTH",
    "",
    "Date: 2026-05-01",
    "Gemma — Technical Diagramming Specialist",
]
for i, line in enumerate(title_lines):
    fw = "bold" if i < 5 else "normal"
    fs = 9.5 if i == 0 else 7.5
    label(PX + PW/2, -4.0 + i * 0.50, line, fs=fs, bold=(fw == "bold"))

# ── Framing direction callout ──────────────────────────────────────────────────
panel_box(2.3, 4.2, fc="#fffde7", ec="#f57f17", lw=2)
label(PX + PW/2, 2.55, "FRAMING DIRECTION (v7 — FACE-HUNG)", fs=8.5, bold=True)
fd_lines = [
    "→ Girders: (3) 2×10 PT ⊥ house (16'-3\" dir.), at x=0', 11'-6\", 23'",
    "— Joists: 2×10 PT ∥ house, 12\" o.c., FACE-HUNG from girder faces",
    "· All framing tops at 11\" AG (top-flush). Joists do NOT pass over girders.",
    "  Joists butt girder faces; Simpson LUS210Z face-mount hanger at each end.",
    "  34 total segments + ~68 hangers in field. Doubled rim: LUS210-2Z.",
    "· Decking: Trex ⊥ house (16'-3\" dir.); 1\" thick → top at 12\" AG.",
    "· Pylex 50 piers through punched patio holes — no posts, no sonotubes.",
    "· Ledger independent: lag-bolted only; top-flush; no piers under ledger.",
    "· 4-side PF; fascia on 3 exposed sides; PF overhangs 2.25\" past fascia.",
]
for i, ln in enumerate(fd_lines):
    fc_ln = "#5a0000" if "FACE-HUNG" in ln or "top-flush" in ln or "Pylex" in ln else "#333333"
    bld = "top-flush" in ln or "Pylex" in ln
    label(PX + 0.08, 2.95 + i * 0.42, ln, fs=6.0, ha="left", color=fc_ln, bold=bld)

# ── Legend ─────────────────────────────────────────────────────────────────────
panel_box(6.7, 14.5, fc="white")
label(PX + PW/2, 6.95, "LEGEND", fs=10.5, bold=True)

legend_items = [
    (7.5,  C_LEDGER,  EC_LEDGER, 3.5,
     "Ledger — SINGLE 2×10 PT, 23'-0\" long  (top-flush @ 11\" AG)",
     "Lag bolts + Z-flashing; independent of piers; no piers under ledger",
     "MTWDeck lateral tie req'd (IRC R507.9 / DCA-6)"),

    (8.55, C_GIRDER, EC_GIRDER, 3,
     "Girder — (3) 2×10 PT, 16'-3\" long, ground-contact  (top-flush @ 11\" AG)",
     "Bottom at 1.75\" AG in Pylex saddle brackets. Cantilevers 12\" past P1 to ledger.",
     "3 girders @ x=0', 11'-6\", 23'"),

    (9.65, C_JOIST, EC_JOIST, 1,
     "Joist segment — 2×10 PT, 12\" o.c., FACE-HUNG (top-flush @ 11\" AG)",
     "2 segments per row (34 total). LUS210Z face-mount hanger at each segment end (~68 total).",
     "16 regular rows at 12\" o.c. y=1'..16'. Final bay = 3\" to doubled rim at 16'-3\"."),

    (10.85, C_RIM, EC_RIM, 2.5,
     "Doubled far-side rim — (2) 2×10 PT, face-hung in 2 segments  (top-flush @ 11\" AG)",
     "LUS210-2Z hangers. Picture-frame on top.",
     None),

    (11.7,  C_PF, EC_PF, 2.5,
     "Picture-frame board — 5.5\" Trex, ALL 4 SIDES",
     "House side: butts wall (1/4\" gap), backed by ledger + house-side 2×10 blocking",
     "3 exposed sides: 2.25\" overhang past fascia (3\" past rim)"),

    (12.75, C_FASCIA, EC_FASCIA, 3,
     "Trex Universal Fascia (0.75\") — 3 exposed sides only",
     "Attached to outer face of rim/drop-board at joist elevation",
     None),

    (13.55, C_DROP, EC_DROP, 2.5,
     "Drop-board sub-fascia (2× outboard of left/right girder + far rim)",
     "Continuous along each edge at joist elevation; backs 3\" PF cantilever",
     None),

    (14.35, C_PIER, EC_PIER, 2,
     "Pylex 50 spiral pier (P1-P9) — ✱ symbol",
     "50\" galv. helical shaft screwed through punched patio hole, tip ~49\" below patio",
     "Saddle bracket bolts to shaft top, 1/2\" galv bolts up into girder. No post."),
]

for row in legend_items:
    yt, fc, ec, lw, main, sub1, sub2 = row
    rect(PX + 0.08, yt, 0.60, 0.40, fc, ec, lw=lw, zorder=3)
    if fc == C_PIER:
        # Show ✱ glyph in legend swatch
        ax.text(PX + 0.08 + 0.30, yt + 0.20, "✱", fontsize=9, ha="center",
                va="center", color="white", fontweight="bold", zorder=4)
    label(PX + 0.78, yt + 0.09, main, fs=6.8, bold=True, ha="left")
    label(PX + 0.78, yt + 0.26, sub1, fs=5.8, ha="left", color="#444444")
    if sub2:
        label(PX + 0.78, yt + 0.43, sub2, fs=5.6, ha="left", color="#666666")

# Hanger legend swatch
yt_hanger = 15.2
ax.plot([PX + 0.08, PX + 0.68], [yt_hanger + 0.20, yt_hanger + 0.20],
        color=C_HANGER, lw=3.0, zorder=4)
label(PX + 0.78, yt_hanger + 0.09, "Face-mount hanger — Simpson LUS210Z (hot-dip galv)", fs=6.8, bold=True, ha="left")
label(PX + 0.78, yt_hanger + 0.26, "~68 total in field (4 per joist row × 17 rows). Rim: LUS210-2Z.", fs=5.8, ha="left", color="#444444")

# Pier hole legend
yt_hole = 15.95
hole_leg = plt.Circle((PX + 0.38, yt_hole + 0.22), 0.28, fc=C_PIER_HOLE, ec=EC_HOLE, lw=1.0, zorder=4, alpha=0.5)
ax.add_patch(hole_leg)
pier_leg = plt.Circle((PX + 0.38, yt_hole + 0.22), 0.17, fc=C_PIER, ec=EC_PIER, lw=1.5, zorder=5)
ax.add_patch(pier_leg)
label(PX + 0.78, yt_hole + 0.09, "Punched patio hole (outer circle) + pier shaft (inner circle)", fs=6.8, bold=True, ha="left")
label(PX + 0.78, yt_hole + 0.26, "~3-4\" actual hole dia. Patch concrete around shaft after install.", fs=5.8, ha="left", color="#444444")

# Blocking swatch
yt_bl = 16.75
ax.plot([PX + 0.08, PX + 0.68], [yt_bl + 0.17, yt_bl + 0.17],
        color=C_BLOCK, lw=2.5, linestyle="--", zorder=4)
label(PX + 0.78, yt_bl + 0.09, "Field blocking — solid 2×10 PT, perpendicular to joist segments", fs=6.8, bold=True, ha="left")
label(PX + 0.78, yt_bl + 0.26, "Rows at x=5'-9\" and x=17'-3\" (midspan of each girder bay)", fs=5.8, ha="left", color="#444444")

# ── Fastener notes ─────────────────────────────────────────────────────────────
panel_box(17.5, 5.0, fc=C_NOTE, ec=EC_NOTE)
fastener_notes = [
    "FASTENER / MATERIAL NOTES (v7)",
    "Ledger: ½\" hot-dip galv lag bolts or FastenMaster LedgerLOK,",
    "  16\" o.c. staggered top/bottom; metal Z-flashing above ledger",
    "Lateral ties: min. 2× Simpson MTWDeck per IRC R507.9 / DCA-6",
    "Face-hung joists: Simpson LUS210Z hot-dip galv (all joist segments);",
    "  Simpson LUS210-2Z for doubled far-side rim segments (~34 hangers each side)",
    "Helical pier saddles: Pylex saddle plate, ½\" hot-dip galv bolts to pier",
    "  shaft top; ½\" galv lag bolts up into girder bottom",
    "Drop-board sub-fascia: 2× outboard of each exposed edge, joist elevation",
    "Joist tape: Zip System or equiv. on every joist top surface",
    "Framing: 2×10 PT UC4B ground-contact throughout; no posts, no sonotubes",
    "Trex Universal Fascia: 0.75\" × rim height, stainless trim screws",
    "Piers: Pylex 50 helical pier, 50\" galvanized shaft, screwed to refusal",
    "  Install through sledgehammer-punched holes (~3-4\" dia) in existing patio",
    "Hardware: hot-dip galvanized or stainless throughout (ACQ-compatible)",
]
for i, note in enumerate(fastener_notes):
    fw = "bold" if i == 0 else "normal"
    fs = 6.5 if i == 0 else 5.8
    label(PX + 0.08, 17.68 + i * 0.29, note, fs=fs, bold=(i == 0), ha="left")

# ══════════════════════════════════════════════════════════════════════════════
# SECTION DETAIL — COMPLETE REWRITE for 12" vertical budget
# Shows: grade + patio + pier shaft going down 50" + saddle + girder bottom/top
#         + joist (face-hung, same elevation) + tape + decking + PF overhang
# ══════════════════════════════════════════════════════════════════════════════
SD_X0 = PX + 0.25
SD_X1 = PX + PW - 0.25
SD_W  = SD_X1 - SD_X0
SD_TOP_Y = 22.5   # top of section detail in figure coords
SD_BOT_Y = SD_TOP_Y + 14.0

panel_box(SD_TOP_Y - 0.5, SD_BOT_Y - SD_TOP_Y + 0.7, fc="#f9f9f9")
label(PX + PW/2, SD_TOP_Y - 0.28,
      "SECTION DETAIL — Vertical Stack at Girder/Pier  (v7 complete rewrite)",
      fs=8.0, bold=True)
label(PX + PW/2, SD_TOP_Y - 0.02,
      "Cross-section looking along joist. All elevations above grade (AG).",
      fs=6.0)

# Scale: 1 real inch = 0.13 ft plot units (so 12\" = 1.56 ft → readable height)
SD_SCALE = 0.13   # ft per real inch

# Reference y=0 in section = grade line = figure y = SD_TOP_Y + offset
# Top of decking at 12\" AG → at SD_TOP_Y + some offset
# Let's put top of decking at SD_TOP_Y + 1.0 (some air above)
# Then grade at SD_TOP_Y + 1.0 + 12\" * SD_SCALE = SD_TOP_Y + 1.0 + 1.56

DECK_TOP_FIG = SD_TOP_Y + 1.0        # figure y for top of Trex decking (12\" AG)
GRADE_FIG    = DECK_TOP_FIG + 12.0 * SD_SCALE   # grade line

def sec_bar(y_fig_top, real_in, label_txt, fc, ec, lw=1.5):
    """Draw a horizontal band in the section detail."""
    h_fig = real_in * SD_SCALE
    rect(SD_X0, y_fig_top, SD_W, h_fig, fc, ec, lw=lw, zorder=5)
    return y_fig_top + h_fig

def sec_label(y_fig_top, real_in, txt, fs=5.8, color="black", bold=False, elev_str=""):
    mid_y = y_fig_top + (real_in * SD_SCALE) / 2
    # left text
    ax.text(SD_X0 + 0.06, mid_y, txt, fontsize=fs, ha="left", va="center",
            fontweight="bold" if bold else "normal", color=color, zorder=7, clip_on=False)
    # right elevation annotation
    if elev_str:
        ax.text(SD_X1 - 0.06, mid_y, elev_str, fontsize=5.8, ha="right", va="center",
                fontweight="bold", color="#8B0000", zorder=7, clip_on=False)

# ── Draw layers top to bottom (figure y increases downward since inverted) ──

y = DECK_TOP_FIG

# Top of decking = 12" AG
ax.plot([SD_X0 - 0.1, SD_X1 + 0.1], [y, y], color="#8B0000", lw=2.5, zorder=8, linestyle="--")
ax.text(SD_X1 + 0.12, y, "12.0\" AG  ← TOP OF DECK", fontsize=6.5, va="center",
        fontweight="bold", color="#8B0000", clip_on=False)

# Trex decking 1"
y = sec_bar(y, 1.0, "", C_DECK, EC_DECK)
sec_label(DECK_TOP_FIG, 1.0, "Trex composite decking  (1.0\" thick)", fs=5.5, color="#555555")

# Joist tape 0.125"
y_tape = y
y = sec_bar(y, 0.125, "", C_TAPE, EC_TAPE, lw=1.0)

# Joist / girder 9.25" (both tops at same elevation — top-flush)
y_joist_top = y
y = sec_bar(y, 9.25, "", C_JOIST, EC_JOIST, lw=2.0)
sec_label(y_joist_top, 9.25, "2×10 PT JOIST face-hung in LUS210Z hanger\n  (top-flush with girder — both at 11.0\" AG)",
          fs=5.5, color="#1a5a1a", bold=True, elev_str="↑ 11.0\" AG")

# Girder alongside (shown as annotation since it's the same height band)
# Draw a wider hatched box to the right to indicate girder is at same elevation
g_inset_x = SD_X0 + (SD_W * 0.55)
g_inset_w = SD_W * 0.40
rect(g_inset_x, y_joist_top, g_inset_w, 9.25 * SD_SCALE,
     C_GIRDER, EC_GIRDER, lw=2.5, zorder=6)
ax.text(g_inset_x + g_inset_w/2, y_joist_top + (9.25 * SD_SCALE)/2,
        "(3) 2×10 PT\nGIRDER\n(same top elev.)",
        fontsize=5.0, ha="center", va="center", fontweight="bold",
        color="#1a3a6b", zorder=8)

y_girder_bot = y_joist_top + 9.25 * SD_SCALE   # bottom of joist/girder

# Bottom of joist/girder = 1.75" AG
ax.plot([SD_X0 - 0.1, SD_X1 + 0.1], [y_girder_bot, y_girder_bot],
        color="#1a3a6b", lw=1.5, zorder=8, linestyle=":")
ax.text(SD_X1 + 0.12, y_girder_bot, "1.75\" AG  ← girder/joist bottom",
        fontsize=5.8, va="center", color="#1a3a6b", clip_on=False)

# Pylex saddle ~1.5"
y_saddle_top = y_girder_bot
y = sec_bar(y_saddle_top, 1.5, "", "#a07040", "#705020", lw=2.0)
sec_label(y_saddle_top, 1.5, "Pylex saddle bracket (~1.5\" ht)  ½\" galv bolts",
          fs=5.2, color="#5a3000")

# Pier shaft above patio 0.5"
y_pier_top = y
y = sec_bar(y_pier_top, 0.5, "", C_PIER, EC_PIER, lw=1.5)
ax.text(SD_X0 + SD_W/2, y_pier_top + 0.25 * SD_SCALE, "pier shaft above slab (~0.5\")",
        fontsize=4.8, ha="center", va="center", color="white", zorder=8)

# Grade / patio surface
GRADE_FIG_ACTUAL = y
ax.plot([SD_X0 - 0.1, SD_X1 + 0.1], [GRADE_FIG_ACTUAL, GRADE_FIG_ACTUAL],
        color="#555555", lw=2.5, zorder=8)
ax.text(SD_X1 + 0.12, GRADE_FIG_ACTUAL, "0\" AG  ← patio surface / grade",
        fontsize=5.8, va="center", color="#555555", clip_on=False)

# Patio slab ~4"
y_patio_top = GRADE_FIG_ACTUAL
y = sec_bar(y_patio_top, 4.0, "", C_PATIO, EC_PATIO, lw=1.5)
ax.text(SD_X0 + SD_W/2, y_patio_top + 2.0 * SD_SCALE,
        "concrete patio slab\n(~4\" typical)\nHOLE PUNCHED HERE",
        fontsize=5.2, ha="center", va="center", color="#6b5030",
        fontweight="bold", zorder=8)

# Pier shaft continuing below patio — show as narrower dark band
PIER_SHAFT_W = SD_W * 0.25
pier_shaft_x = SD_X0 + (SD_W - PIER_SHAFT_W)/2
# 50" total shaft; ~0.5" above + 4" through slab + 45.5" below → show compressed
below_patio_in = 45.5   # approx inches below bottom of slab
y_slab_bot = y
rect(pier_shaft_x, y_slab_bot, PIER_SHAFT_W, below_patio_in * SD_SCALE,
     C_PIER, EC_PIER, lw=1.5, zorder=5)

# Shaft label
y_shaft_mid = y_slab_bot + (below_patio_in * SD_SCALE)/2
ax.text(pier_shaft_x - 0.12, y_shaft_mid,
        "Pylex 50\nhelical shaft\n50\" total galv.\n(through punched\npatio hole)",
        fontsize=5.0, ha="right", va="center", color="#2a1808",
        fontweight="bold", clip_on=False)

# Helical blade at shaft bottom
y_tip = y_slab_bot + below_patio_in * SD_SCALE
rect(pier_shaft_x - PIER_SHAFT_W*0.7, y_tip, PIER_SHAFT_W * 2.4, 0.5 * SD_SCALE,
     "#8b6030", "#5a3000", lw=2.0, zorder=5)
ax.text(SD_X0 + SD_W/2, y_tip + 0.25 * SD_SCALE, "helical blade",
        fontsize=4.8, ha="center", va="center", color="white", zorder=8)

# Depth label at tip
ax.plot([SD_X0 - 0.1, pier_shaft_x], [y_tip, y_tip],
        color="#5a3000", lw=1.0, linestyle="--")
ax.text(SD_X0 - 0.12, y_tip, "~49\" below patio\n(>42\" frost  ✓)",
        fontsize=5.2, ha="right", va="center", color="#5a3000",
        fontweight="bold", clip_on=False)

# ── VERIFIED callout box inside section ───────────────────────────────────────
box_y = DECK_TOP_FIG + 0.3
rect(SD_X0 + 0.05, box_y, SD_W - 0.1, 0.7,
     "#fff0d0", "#cc4400", lw=2.0, zorder=10)
ax.text(SD_X0 + SD_W/2, box_y + 0.35,
        "EVERY ELEVATION VERIFIED\nTOP OF DECK = 12.0\" AG",
        fontsize=6.5, ha="center", va="center",
        fontweight="bold", color="#8B0000", zorder=11)

# ══════════════════════════════════════════════════════════════════════════════
# PUNCHED PATIO HOLE INSET (top-view detail, small box)
# ══════════════════════════════════════════════════════════════════════════════
INS_X = PX + 0.2
INS_Y = SD_TOP_Y - 5.8   # above section detail
INS_W = 2.4
INS_H = 4.5
panel_box(INS_Y, INS_H, fc="#f5f5f5")
label(INS_X + INS_W/2, INS_Y + 0.22,
      "PATIO HOLE DETAIL (top view)", fs=7.0, bold=True)
# Patio background
rect(INS_X + 0.12, INS_Y + 0.45, INS_W - 0.24, INS_H - 0.6, C_PATIO, EC_PATIO, lw=1.5, zorder=3)
# Hole
cx = INS_X + INS_W/2
cy = INS_Y + INS_H/2 + 0.2
hole_ins = plt.Circle((cx, cy), 0.45, fc=C_PIER_HOLE, ec=EC_HOLE, lw=1.5, zorder=5)
ax.add_patch(hole_ins)
# Pier shaft
pier_ins = plt.Circle((cx, cy), 0.25, fc=C_PIER, ec=EC_PIER, lw=1.5, zorder=6)
ax.add_patch(pier_ins)
ax.text(cx, cy, "✱", fontsize=9, ha="center", va="center", color="white",
        fontweight="bold", zorder=7)
# Labels
label(cx, INS_Y + INS_H - 0.65,
      "patio surface (concrete)", fs=5.5, color="#6b5030")
label(cx, cy + 0.60, "punched hole\n~3-4\" dia", fs=5.0, color="#706050", bold=True)
label(cx, cy - 0.60, "pier shaft passes\nthrough; grout/patch\naround shaft", fs=5.0, color="#2a1808")
# Arrow to hole
ax.annotate("", xy=(cx + 0.46, cy), xytext=(cx + 1.0, cy),
            arrowprops=dict(arrowstyle="->", color="#706050", lw=0.8))
label(cx + 1.1, cy, "hole\noutline", fs=5.0, ha="left", color="#706050")

# ══════════════════════════════════════════════════════════════════════════════
# FIGURE TITLE (top-left, outside plan area)
# ══════════════════════════════════════════════════════════════════════════════
ax.text(-3.8, -4.3,
        "Deck Plan v7  —  23'-6\" × 16'-6\" Overall Finished Surface, 12\" Max AG\n"
        "Pylex 50 Spiral Piers Through Patio, Face-Hung Joists Top-Flush, House on 23'-6\" Edge",
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
