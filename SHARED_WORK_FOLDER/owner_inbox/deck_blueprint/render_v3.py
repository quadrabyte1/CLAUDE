"""
render_v3.py  —  Gemma's matplotlib render of deck_plan v3
Produces deck_plan.png at ≥2000 px wide, white background.

Coordinate system matches the drawio file:
  - X axis = 23 ft direction (along house wall, left→right)
  - Y axis = 16 ft direction (out from house, top→bottom)
  - House wall along the TOP of the drawing.

All measurements in feet unless noted.
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyArrowPatch
import matplotlib.lines as mlines
import numpy as np

# ── Canvas setup ──────────────────────────────────────────────────────────────
FIG_W_IN = 28      # inches at 100 dpi → 2800 px
FIG_H_IN = 21
DPI = 100

fig, ax = plt.subplots(figsize=(FIG_W_IN, FIG_H_IN), dpi=DPI)
fig.patch.set_facecolor("white")
ax.set_facecolor("white")

# ── Coordinate helpers ─────────────────────────────────────────────────────────
# Plan area: x 0..23 ft (along house), y 0..16 ft (out from house, downward)
# We'll work in feet and flip y so house is at the TOP.
# matplotlib default: y increases upward. We'll invert the y axis.

PLAN_X0, PLAN_X1 = 0.0, 23.0   # feet
PLAN_Y0, PLAN_Y1 = 0.0, 16.0   # feet (0 = at house, 16 = far edge)

# Reserves: left margin 1.5 ft, right panel 5 ft, top margin 2 ft, bottom 1 ft
# We'll set axis limits slightly beyond the plan.
ax.set_xlim(-2.0, 29.0)
ax.set_ylim(-2.5, 19.5)
ax.invert_yaxis()   # house at top (y=0 plots at top)
ax.set_aspect("equal")
ax.axis("off")

# ── Color palette (same as drawio) ────────────────────────────────────────────
C_HOUSE    = "#cccccc"
C_LEDGER   = "#f8cecc";  EC_LEDGER  = "#b85450"
C_GIRDER   = "#dae8fc";  EC_GIRDER  = "#6c8ebf"
C_JOIST    = "#d5e8d4";  EC_JOIST   = "#82b366"
C_RIM      = "#fff2cc";  EC_RIM     = "#d6b656"
C_POST_F   = "#e1d5e7";  EC_POST    = "#9673a6"
C_BLOCK    = "#888888"
C_TAPE     = "#ffff99";  EC_TAPE    = "#cccc00"
C_DECK     = "#dddddd";  EC_DECK    = "#888888"
C_NOTE     = "#ffffee";  EC_NOTE    = "#888800"

def rect(x, y, w, h, fc, ec, lw=1.0, zorder=2, alpha=1.0):
    """Draw a filled rectangle (x,y = top-left corner in plan coords)."""
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
            color=color, rotation=rotation, zorder=zorder,
            clip_on=False)

# ══════════════════════════════════════════════════════════════════════════════
# HOUSE WALL
# ══════════════════════════════════════════════════════════════════════════════
rect(0, -1.0, 23.0, 1.0, C_HOUSE, "#444444", lw=2, zorder=3)
label(11.5, -0.5, "HOUSE WALL  ▲  NORTH  (attached 23 ft edge)",
      fs=11, bold=True)

# ══════════════════════════════════════════════════════════════════════════════
# GIRDERS — perpendicular to house, run in 16 ft direction (vertical in plan)
# 3 girders at x = 0, 11.5, 23 ft; each 16 ft long; width = 0.33 ft (~4 in)
# Rendered as thick blue vertical bands
# ══════════════════════════════════════════════════════════════════════════════
GIRDER_W = 0.35   # ft (visual width in plan for tripled 2x10 — not to structural scale)
GIRDER_POSITIONS = [0.0, 11.5, 23.0]
GIRDER_LABELS = ["LEFT GIRDER\n0 ft", "MIDDLE GIRDER\n11'-6\"", "RIGHT GIRDER\n23 ft"]

for gx, glabel in zip(GIRDER_POSITIONS, GIRDER_LABELS):
    # Center the girder band on its nominal position
    x0 = gx - GIRDER_W / 2
    # Clamp to plan edge
    x0 = max(0.0, min(x0, 23.0 - GIRDER_W))
    rect(x0, 0.0, GIRDER_W, 16.0, C_GIRDER, EC_GIRDER, lw=3, zorder=4)
    # Label inside band (rotated)
    ax.text(x0 + GIRDER_W/2, 8.0, glabel,
            fontsize=6.5, ha="center", va="center", rotation=90,
            fontweight="bold", color="#1a3a6b", zorder=6,
            multialignment="center")

# ══════════════════════════════════════════════════════════════════════════════
# HOUSE-SIDE RIM (Joist #1) — doubled 2x10, red/pink, full 23 ft
# ══════════════════════════════════════════════════════════════════════════════
RIM_H = 0.22   # visual height (ft) for doubled 2x10
rect(0.0, 0.0, 23.0, RIM_H, C_LEDGER, EC_LEDGER, lw=3, zorder=5)
label(11.5, RIM_H/2,
      "HOUSE-SIDE RIM / LEDGER — (2) 2×10 PT  |  Lag-bolted w/ LedgerLOK + Z-flashing  |  Rests on 3 girders",
      fs=7.5, bold=True)

# FAR-SIDE RIM (Joist #13) — doubled 2x10, yellow, at 16 ft
rect(0.0, 16.0 - RIM_H, 23.0, RIM_H, C_RIM, EC_RIM, lw=3, zorder=5)
label(11.5, 16.0 - RIM_H/2,
      "FAR-SIDE RIM — (2) 2×10 PT  |  Sits on 3 girders at 16 ft outer edge",
      fs=7.5, bold=True)

# ══════════════════════════════════════════════════════════════════════════════
# SHORT-EDGE RIM JOISTS — 16 ft long, at left (x=0) and right (x=23) edges
# ══════════════════════════════════════════════════════════════════════════════
RIM_SIDE_W = 0.22
rect(0.0, 0.0, RIM_SIDE_W, 16.0, C_RIM, EC_RIM, lw=2, zorder=3)
rect(23.0 - RIM_SIDE_W, 0.0, RIM_SIDE_W, 16.0, C_RIM, EC_RIM, lw=2, zorder=3)
label(-0.7, 8.0, "LEFT RIM\n2×10 PT\n16 ft\n(end-grain\nhangers)",
      fs=6.5, ha="center", va="center", rotation=0)
label(23.7, 8.0, "RIGHT RIM\n2×10 PT\n16 ft\n(end-grain\nhangers)",
      fs=6.5, ha="center", va="center", rotation=0)

# ══════════════════════════════════════════════════════════════════════════════
# JOISTS — parallel to house (horizontal in plan), 23 ft long, 16" o.c.
# Joist #1 = house-side rim (already drawn)
# Joist #13 = far-side rim (already drawn)
# Interior joists #2..#12 at 16", 32"... 176" from house
# ══════════════════════════════════════════════════════════════════════════════
JOIST_H = 0.10   # visual height for single 2x10
JOIST_SPACING = 16/12  # ft = 1.333...

for i in range(1, 12):   # joists 2..12 (index 1..11, position 16"..176")
    y_pos = i * JOIST_SPACING  # ft from house
    rect(0.0, y_pos - JOIST_H/2, 23.0, JOIST_H, C_JOIST, EC_JOIST, lw=1, zorder=3)

# Splice indicator on joist #7 (center joist, y=6*JOIST_SPACING)
splice_y = 6 * JOIST_SPACING
ax.annotate("", xy=(11.5, splice_y), xytext=(11.5 + 0.8, splice_y - 0.5),
            arrowprops=dict(arrowstyle="->", color="#555555", lw=0.8))
label(12.5, splice_y - 0.65,
      "SPLICE over middle girder\n(lap joint + GRK RSS structural screws) — typ.",
      fs=6, ha="left", va="center")

# Joist o.c. spacing label (right side)
label(24.4, 3.0, "16\" o.c.\ntypical", fs=8, bold=True, ha="left")

# ══════════════════════════════════════════════════════════════════════════════
# BLOCKING ROWS — dashed vertical lines at x = 5.75 ft and 17.25 ft
# (midspan of each girder bay, running 16 ft in Y direction)
# ══════════════════════════════════════════════════════════════════════════════
BLOCKING_X = [5.75, 17.25]
for bx in BLOCKING_X:
    ax.plot([bx, bx], [0.0, 16.0],
            color=C_BLOCK, linewidth=2.5, linestyle="--", zorder=3, alpha=0.85)

label(5.75, -1.0, "BLOCKING\n@ 5'-9\"", fs=7, bold=True, color="#555555")
label(17.25, -1.0, "BLOCKING\n@ 17'-3\"", fs=7, bold=True, color="#555555")

# ══════════════════════════════════════════════════════════════════════════════
# POSTS — 9 total, labeled P1–P9
# 3 girders × 3 posts at 0 ft, 8 ft, 16 ft along girder (in Y direction)
# Layout:
#   Left girder (x=0):   P1@y=0, P2@y=8, P3@y=16
#   Middle girder(x=11.5): P4@y=0, P5@y=8, P6@y=16
#   Right girder(x=23): P7@y=0, P8@y=8, P9@y=16
# ══════════════════════════════════════════════════════════════════════════════
POST_R = 0.38   # footing circle radius
POST_SQ = 0.22  # post square half-size

posts = [
    (0.0,  0.0,  "P1"),
    (0.0,  8.0,  "P2"),
    (0.0,  16.0, "P3"),
    (11.5, 0.0,  "P4"),
    (11.5, 8.0,  "P5"),
    (11.5, 16.0, "P6"),
    (23.0, 0.0,  "P7"),
    (23.0, 8.0,  "P8"),
    (23.0, 16.0, "P9"),
]

for px, py, plabel in posts:
    # Footing (circle)
    circ = plt.Circle((px, py), POST_R, fc=C_POST_F, ec=EC_POST, lw=2, zorder=6)
    ax.add_patch(circ)
    # Post (square, slightly smaller)
    sq = mpatches.FancyBboxPatch((px - POST_SQ/2, py - POST_SQ/2),
                                 POST_SQ, POST_SQ,
                                 boxstyle="square,pad=0",
                                 fc=C_POST_F, ec=EC_POST, lw=1.5, zorder=7)
    ax.add_patch(sq)
    label(px, py, plabel, fs=6.5, bold=True, zorder=8)

# ══════════════════════════════════════════════════════════════════════════════
# DIMENSION ANNOTATIONS
# ══════════════════════════════════════════════════════════════════════════════

# Overall 23 ft (horizontal, above house)
ax.annotate("", xy=(23.0, -1.8), xytext=(0.0, -1.8),
            arrowprops=dict(arrowstyle="<->", color="black", lw=1.2))
label(11.5, -2.1, "23'-0\"  (along house wall)", fs=9, bold=True)

# Overall 16 ft (vertical, left of plan)
ax.annotate("", xy=(-1.5, 16.0), xytext=(-1.5, 0.0),
            arrowprops=dict(arrowstyle="<->", color="black", lw=1.2))
label(-1.9, 8.0, "16'-0\"  (out from house)", fs=9, bold=True, rotation=90)

# Girder positions (tick marks along top)
for gx, gtxt in zip([0.0, 11.5, 23.0], ["0'", "11'-6\"", "23'"]):
    ax.plot([gx, gx], [-1.5, -0.8], color="#333333", lw=1, zorder=4)
    label(gx, -0.5, gtxt, fs=7.5, bold=True, va="bottom")

# Post spacing along girder (left margin)
for py, ptxt in zip([0.0, 8.0, 16.0], ["0'", "8'", "16'"]):
    ax.plot([-1.6, -1.2], [py, py], color="#555555", lw=0.8)
    label(-1.8, py, ptxt, fs=7.5, bold=False, ha="right")

# Joist span annotation (between left and middle girder)
ax.annotate("", xy=(11.5, 17.2), xytext=(0.0, 17.2),
            arrowprops=dict(arrowstyle="<->", color="#555577", lw=1.0))
label(5.75, 17.6, "11'-6\" joist span", fs=7.5, color="#333377")

ax.annotate("", xy=(23.0, 17.2), xytext=(11.5, 17.2),
            arrowprops=dict(arrowstyle="<->", color="#555577", lw=1.0))
label(17.25, 17.6, "11'-6\" joist span", fs=7.5, color="#333377")

# Blocking x-positions (tick below plan)
for bx, btxt in zip([5.75, 17.25], ["5'-9\"", "17'-3\""]):
    ax.plot([bx, bx], [17.0, 17.4], color=C_BLOCK, lw=1, linestyle="--")

# ══════════════════════════════════════════════════════════════════════════════
# RIGHT-SIDE PANEL — Title block, framing callout, legend, section detail
# Panel starts at x = 24.5
# ══════════════════════════════════════════════════════════════════════════════
PX = 24.5   # left edge of right panel (ft units)
PW = 4.3    # panel width

def panel_box(y0, h, fc="#f5f5f5", ec="#444444", lw=1.5):
    rect(PX, y0, PW, h, fc, ec, lw=lw, zorder=2)

# ── Title block ───────────────────────────────────────────────────────────────
panel_box(-2.5, 4.4, fc="#f5f5f5")
title_lines = [
    "DECK PLAN v3",
    "23' × 16'  Attached Deck",
    "12\" off grade",
    "House on 23' Edge",
    "Decking ⊥ House",
    "",
    "Scale: 1\" ≈ 1 ft (plot units = ft)",
    "HOUSE = top edge  ▲",
    "",
    "Date: 2026-05-01",
]
for i, line in enumerate(title_lines):
    fw = "bold" if i < 5 else "normal"
    fs = 9 if i == 0 else 7.5
    label(PX + PW/2, -2.3 + i * 0.4, line, fs=fs, bold=(fw=="bold"))

# ── Framing direction callout ─────────────────────────────────────────────────
panel_box(2.2, 2.0, fc="#fffde7", ec="#f57f17", lw=2)
label(PX + PW/2, 2.5, "FRAMING DIRECTION", fs=8, bold=True)
label(PX + 0.1, 2.9, "→ Girders: perpendicular to house (16 ft dir.)", fs=7, ha="left")
label(PX + 0.1, 3.2, "— Joists: parallel to house (23 ft dir.)", fs=7, ha="left")
label(PX + 0.1, 3.5, "· Decking: perpendicular to joists (⊥ house)", fs=7, ha="left")
label(PX + 0.1, 3.9, "  Boards run 16 ft long across the 23 ft width", fs=7, ha="left", color="#555555")

# ── Legend ────────────────────────────────────────────────────────────────────
panel_box(4.5, 9.2, fc="white")
label(PX + PW/2, 4.7, "LEGEND", fs=10, bold=True)

legend_items = [
    # (y_top, fc, ec, lw, label_text, sublabel)
    (5.1, C_LEDGER, EC_LEDGER, 3,
     "House-side rim / ledger — (2) 2×10 PT",
     "Lag-bolted w/ LedgerLOK + Z-flashing; rests on 3 girders"),
    (5.9, C_GIRDER, EC_GIRDER, 3,
     "Girder — (3) 2×10 PT, ground-contact",
     "Runs ⊥ to house (16 ft); 3 girders @ 0', 11'-6\", 23'"),
    (6.7, C_JOIST, EC_JOIST, 1,
     "Joist — 2×10 PT, 16\" o.c.",
     "Runs ∥ to house (23 ft); spliced over mid girder; joist tape"),
    (7.5, C_RIM, EC_RIM, 2,
     "Picture-frame border / far-side rim",
     "Far rim (2) 2×10 PT; short-edge rims 2×10 PT w/ end hangers"),
    (8.3, C_POST_F, EC_POST, 2,
     "Post (P1–P9) — 6×6 PT ground-contact",
     "9 total; 3 per girder @ 0', 8', 16' along girder"),
    (9.1, C_POST_F, EC_POST, 2,
     "Footing — 12\" dia. sonotube to frost depth",
     "One per post; each post in its own footing"),
]

for (yt, fc, ec, lw, main, sub) in legend_items:
    rect(PX + 0.1, yt, 0.5, 0.38, fc, ec, lw=lw, zorder=3)
    label(PX + 0.7, yt + 0.13, main, fs=7.5, bold=True, ha="left")
    label(PX + 0.7, yt + 0.32, sub, fs=6.5, ha="left", color="#444444")

# Blocking legend item (dashed line style)
yt_block = 9.9
ax.plot([PX + 0.1, PX + 0.6], [yt_block + 0.19, yt_block + 0.19],
        color=C_BLOCK, lw=2.5, linestyle="--", zorder=4)
label(PX + 0.7, yt_block + 0.13, "Blocking — solid 2×10 PT between joists", fs=7.5, bold=True, ha="left")
label(PX + 0.7, yt_block + 0.32, "Rows at 5'-9\" and 17'-3\" from left edge", fs=6.5, ha="left", color="#444444")

# ── Fastener / material notes ─────────────────────────────────────────────────
panel_box(10.6, 4.0, fc=C_NOTE, ec=EC_NOTE)
notes = [
    "FASTENER / MATERIAL NOTES",
    "Ledger: FastenMaster LedgerLOK, 16\" o.c. staggered",
    "Z-flashing at ledger (hot-dip galv metal)",
    "Joist-to-rim: Simpson LSU/LSC end-grain hangers",
    "Joist splices: GRK RSS screws, lap joint over mid girder",
    "2-ply rims: ½\" carriage bolts per AWC specs",
    "Framing: 2×10 PT UC4B throughout; posts: 6×6 PT UC4B",
    "Decking: Trex composite, boards run ⊥ to house (16 ft)",
    "Footings: 12\" dia. sonotube to frost depth, per local code",
    "Hardware: Simpson ZMAX or stainless throughout",
]
for i, note in enumerate(notes):
    fw = "bold" if i == 0 else "normal"
    label(PX + 0.1, 10.75 + i * 0.37, note, fs=7, bold=(i==0), ha="left")

# ── Section detail (vertical assembly stack) ──────────────────────────────────
panel_box(15.0, 4.4, fc="#f9f9f9")
label(PX + PW/2, 15.15, "SECTION DETAIL (typical bay)", fs=9, bold=True)
label(PX + PW/2, 15.45, "Vertical slice at any post, looking along joist", fs=6.5)

# Draw stacked layers top → bottom (surface is at the top of the section panel)
layers = [
    # (y_in_panel, label, fc, ec, lw, h)
    (15.65, "PICTURE-FRAME BOARD", C_RIM,    EC_RIM,   2, 0.22),
    (15.87, "TREX COMPOSITE DECKING (⊥ house)", C_DECK, EC_DECK, 2, 0.25),
    (16.12, "JOIST TAPE", C_TAPE, EC_TAPE,  2, 0.13),
    (16.25, "2×10 PT JOIST (∥ to house)", C_JOIST, EC_JOIST, 2, 0.30),
    (16.55, "(3) 2×10 PT GIRDER", C_GIRDER, EC_GIRDER, 3, 0.35),
    (16.90, "POST CAP (Simpson BC/E or equiv.)", C_POST_F, EC_POST, 1, 0.12),
    (17.02, "6×6 PT POST (ground-contact)", C_POST_F, EC_POST, 2, 0.60),
    (17.62, "12\" DIA. SONOTUBE FOOTING", C_POST_F, EC_POST, 2, 0.40),
    (18.02, "GRADE (12\" below deck surface)", "#aaaaaa", "#555555", 2, 0.28),
]

for (y_pos, lbl, fc, ec, lw, h) in layers:
    rect(PX + 0.3, y_pos, PW - 0.6, h, fc, ec, lw=lw, zorder=3)
    label(PX + PW/2, y_pos + h/2, lbl, fs=7, bold=False, zorder=4)

label(PX + PW/2, 18.55, "▲ = top of deck surface   ▼ = below grade", fs=7, color="#555555")

# ══════════════════════════════════════════════════════════════════════════════
# FIGURE title (top-left corner, outside plan)
# ══════════════════════════════════════════════════════════════════════════════
ax.text(-1.9, -2.2,
        "Deck Plan v3  —  23'×16' Attached, 12\" off grade,\nHouse on 23' Edge, Decking ⊥ House",
        fontsize=11, fontweight="bold", va="top", ha="left", color="#222222")

# ══════════════════════════════════════════════════════════════════════════════
# Save
# ══════════════════════════════════════════════════════════════════════════════
OUT = "/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/owner_inbox/deck_blueprint/deck_plan.png"
fig.savefig(OUT, dpi=DPI, bbox_inches="tight", facecolor="white")
print(f"Saved: {OUT}")

from PIL import Image
img = Image.open(OUT)
print(f"Size: {img.size[0]}×{img.size[1]} px")
