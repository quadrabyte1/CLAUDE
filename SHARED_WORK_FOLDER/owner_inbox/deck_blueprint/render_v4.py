"""
render_v4.py  —  Gemma's matplotlib render of deck_plan v4
Produces deck_plan.png at ≥2000 px wide, white background.

v4 changes vs v3:
  - House-side member is now a TRUE LEDGER (single 2x10 PT, lag-bolted only)
    NOT the v3 doubled dual-purpose rim. Joists run parallel to ledger and
    do NOT hang from it.
  - Joists at 12" o.c. (was 16" o.c.) → 17 total members across 16 ft depth
    (1 ledger + 15 regular joists + 1 doubled far-side rim)
  - MTWDeck lateral-tie callout added near ledger

Coordinate system:
  - X axis = 23 ft direction (along house wall, left→right)
  - Y axis = 16 ft direction (out from house, top→bottom)
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

# ── Canvas setup ──────────────────────────────────────────────────────────────
FIG_W_IN = 28      # inches at 100 dpi → 2800 px
FIG_H_IN = 21
DPI = 100

fig, ax = plt.subplots(figsize=(FIG_W_IN, FIG_H_IN), dpi=DPI)
fig.patch.set_facecolor("white")
ax.set_facecolor("white")

# Plan area: x 0..23 ft (along house), y 0..16 ft (out from house, downward)
PLAN_X0, PLAN_X1 = 0.0, 23.0
PLAN_Y0, PLAN_Y1 = 0.0, 16.0

ax.set_xlim(-2.5, 29.5)
ax.set_ylim(-2.8, 20.0)
ax.invert_yaxis()   # house at top (y=0 plots at top)
ax.set_aspect("equal")
ax.axis("off")

# ── Color palette (same semantic meaning as v3) ────────────────────────────────
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
# HOUSE WALL
# ══════════════════════════════════════════════════════════════════════════════
rect(0, -1.0, 23.0, 1.0, C_HOUSE, "#444444", lw=2, zorder=3)
label(11.5, -0.5, "HOUSE WALL  ▲  NORTH  (attached 23 ft edge)",
      fs=11, bold=True)

# ══════════════════════════════════════════════════════════════════════════════
# GIRDERS — perpendicular to house, run in 16 ft direction (vertical in plan)
# 3 girders at x = 0, 11.5, 23 ft; each 16 ft long
# ══════════════════════════════════════════════════════════════════════════════
GIRDER_W = 0.35
GIRDER_POSITIONS = [0.0, 11.5, 23.0]
GIRDER_LABELS = ["LEFT GIRDER\n(3) 2×10 PT\n@ 0 ft", "MIDDLE GIRDER\n(3) 2×10 PT\n@ 11'-6\"", "RIGHT GIRDER\n(3) 2×10 PT\n@ 23 ft"]

for gx, glabel_txt in zip(GIRDER_POSITIONS, GIRDER_LABELS):
    x0 = gx - GIRDER_W / 2
    x0 = max(0.0, min(x0, 23.0 - GIRDER_W))
    rect(x0, 0.0, GIRDER_W, 16.0, C_GIRDER, EC_GIRDER, lw=3, zorder=4)
    ax.text(x0 + GIRDER_W/2, 8.0, glabel_txt,
            fontsize=6.0, ha="center", va="center", rotation=90,
            fontweight="bold", color="#1a3a6b", zorder=6,
            multialignment="center")

# ══════════════════════════════════════════════════════════════════════════════
# LEDGER (v4 — replaces v3 doubled house-side rim)
# Single 2x10 PT, 23 ft long, lag-bolted to house
# Visually: ledger color (red/pink), THICKER stroke, taller bar than regular joist
# Joists run PARALLEL to ledger — ledger is Member 1 of the joist field
# ══════════════════════════════════════════════════════════════════════════════
LEDGER_H = 0.18   # slightly taller than a regular joist to signal importance
rect(0.0, 0.0, 23.0, LEDGER_H, C_LEDGER, EC_LEDGER, lw=3.5, zorder=5)
label(11.5, LEDGER_H/2,
      "LEDGER — SINGLE 2×10 PT  |  ½\" hot-dip galv lag bolts (or LedgerLOK) @ 16\" o.c. staggered  |  Z-flashing above  |  Rests on 3 girders (belt+suspenders)",
      fs=6.5, bold=True, color="#5a0000")

# MTWDeck lateral-tie callout (just right of ledger label, attached-edge zone)
rect(14.5, 0.22, 8.2, 0.55, C_CALLOUT, EC_CALLOUT, lw=1.5, zorder=6)
label(18.6, 0.50,
      "⚠ MTWDeck LATERAL TIE REQ'D — min. 2× Simpson MTWDeck (or equiv.) along ledger\n"
      "per IRC R507.9 / DCA-6: 2× band joist + 2× interior blocking bearing on sill plate",
      fs=6.0, ha="center", va="center", color="#663300", zorder=7)

# Ledger note in left margin
label(-1.8, 0.09,
      "LEDGER\n2×10 PT\n(lag-bolted\n+ Z-flash)",
      fs=6.5, ha="center", va="center", rotation=0)

# ══════════════════════════════════════════════════════════════════════════════
# FAR-SIDE DOUBLED RIM (Member 17) — doubled 2x10, yellow, at 16 ft
# ══════════════════════════════════════════════════════════════════════════════
FAR_RIM_H = 0.22   # doubled = visually thicker than regular joist
rect(0.0, 16.0 - FAR_RIM_H, 23.0, FAR_RIM_H, C_RIM, EC_RIM, lw=3, zorder=5)
label(11.5, 16.0 - FAR_RIM_H/2,
      "FAR-SIDE RIM — (2) 2×10 PT  |  Sits on 3 girders at 16 ft outer edge  |  Picture-frame board on top",
      fs=7.5, bold=True)

# ══════════════════════════════════════════════════════════════════════════════
# SHORT-EDGE RIM JOISTS — 16 ft long, at left (x=0) and right (x=23) edges
# ══════════════════════════════════════════════════════════════════════════════
RIM_SIDE_W = 0.22
rect(0.0, 0.0, RIM_SIDE_W, 16.0, C_RIM, EC_RIM, lw=2, zorder=3)
rect(23.0 - RIM_SIDE_W, 0.0, RIM_SIDE_W, 16.0, C_RIM, EC_RIM, lw=2, zorder=3)
label(-0.6, 8.0, "LEFT RIM\n2×10 PT\n16 ft\n(end-grain\nhangers)",
      fs=6.5, ha="center", va="center", rotation=0)
label(23.6, 8.0, "RIGHT RIM\n2×10 PT\n16 ft\n(end-grain\nhangers)",
      fs=6.5, ha="center", va="center", rotation=0)

# ══════════════════════════════════════════════════════════════════════════════
# JOISTS — Members 2–16 at 12" o.c. (1 ft spacing)
# y positions: 1 ft, 2 ft, ... 15 ft from house
# Total 15 regular joists, each 23 ft long, 2x10 PT
# ══════════════════════════════════════════════════════════════════════════════
JOIST_H = 0.09   # visual height for single 2x10 (slightly thinner to keep 17 readable)
JOIST_SPACING_FT = 1.0   # 12" = 1 ft

# Draw Members 2–16 (joists at 1 ft, 2 ft, ... 15 ft from house)
for i in range(1, 16):
    y_pos = i * JOIST_SPACING_FT
    rect(0.0, y_pos - JOIST_H/2, 23.0, JOIST_H, C_JOIST, EC_JOIST, lw=1, zorder=3)

# Splice callout on the 8th regular joist (middle of the field, y=8 ft)
splice_y = 8 * JOIST_SPACING_FT
ax.annotate("", xy=(11.5, splice_y), xytext=(12.3, splice_y - 0.7),
            arrowprops=dict(arrowstyle="->", color="#555555", lw=0.8))
label(13.5, splice_y - 0.85,
      "SPLICE over middle girder\n(lap joint + GRK RSS structural screws) — typ. all joists",
      fs=6, ha="left", va="center")

# Joist o.c. spacing labels — a few representative call-outs on the right side
# Show 3 representative spacing arrows to make 12" o.c. unmistakable
for arrow_i in [2, 7, 12]:
    y_a = (arrow_i - 0.5) * JOIST_SPACING_FT  # midpoint between two joists
    ax.annotate("", xy=(24.3, (arrow_i) * JOIST_SPACING_FT),
                xytext=(24.3, (arrow_i - 1) * JOIST_SPACING_FT if arrow_i > 1 else 0),
                arrowprops=dict(arrowstyle="<->", color="#333333", lw=0.9))
    label(24.75, y_a, '12"', fs=7.5, bold=True, ha="left")

label(25.4, 8.0, "12\" o.c.\ntypical", fs=9, bold=True, ha="left")

# ══════════════════════════════════════════════════════════════════════════════
# BLOCKING ROWS — dashed gray vertical lines at x = 5.75 ft and 17.25 ft
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
# ══════════════════════════════════════════════════════════════════════════════
POST_R = 0.38
POST_SQ = 0.22

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

for px, py, plabel_txt in posts:
    circ = plt.Circle((px, py), POST_R, fc=C_POST_F, ec=EC_POST, lw=2, zorder=6)
    ax.add_patch(circ)
    sq = mpatches.FancyBboxPatch((px - POST_SQ/2, py - POST_SQ/2),
                                 POST_SQ, POST_SQ,
                                 boxstyle="square,pad=0",
                                 fc=C_POST_F, ec=EC_POST, lw=1.5, zorder=7)
    ax.add_patch(sq)
    label(px, py, plabel_txt, fs=6.5, bold=True, zorder=8)

# ══════════════════════════════════════════════════════════════════════════════
# DIMENSION ANNOTATIONS
# ══════════════════════════════════════════════════════════════════════════════

# Overall 23 ft (horizontal, above house)
ax.annotate("", xy=(23.0, -1.9), xytext=(0.0, -1.9),
            arrowprops=dict(arrowstyle="<->", color="black", lw=1.2))
label(11.5, -2.25, "23'-0\"  (along house wall)", fs=9, bold=True)

# Overall 16 ft (vertical, left of plan)
ax.annotate("", xy=(-1.6, 16.0), xytext=(-1.6, 0.0),
            arrowprops=dict(arrowstyle="<->", color="black", lw=1.2))
label(-2.1, 8.0, "16'-0\"  (out from house)", fs=9, bold=True, rotation=90)

# Girder positions (tick marks along top)
for gx, gtxt in zip([0.0, 11.5, 23.0], ["0'", "11'-6\"", "23'"]):
    ax.plot([gx, gx], [-1.6, -0.9], color="#333333", lw=1, zorder=4)
    label(gx, -0.6, gtxt, fs=7.5, bold=True, va="bottom")

# Post spacing along girder (left margin)
for py, ptxt in zip([0.0, 8.0, 16.0], ["0'", "8'", "16'"]):
    ax.plot([-1.7, -1.3], [py, py], color="#555555", lw=0.8)
    label(-1.9, py, ptxt, fs=7.5, bold=False, ha="right")

# Joist span annotation (below plan)
ax.annotate("", xy=(11.5, 17.3), xytext=(0.0, 17.3),
            arrowprops=dict(arrowstyle="<->", color="#555577", lw=1.0))
label(5.75, 17.7, "11'-6\" joist span", fs=7.5, color="#333377")

ax.annotate("", xy=(23.0, 17.3), xytext=(11.5, 17.3),
            arrowprops=dict(arrowstyle="<->", color="#555577", lw=1.0))
label(17.25, 17.7, "11'-6\" joist span", fs=7.5, color="#333377")

# Blocking positions (tick below plan)
for bx in [5.75, 17.25]:
    ax.plot([bx, bx], [17.1, 17.5], color=C_BLOCK, lw=1, linestyle="--")

# ══════════════════════════════════════════════════════════════════════════════
# RIGHT-SIDE PANEL — Title block, framing callout, legend, section detail
# ══════════════════════════════════════════════════════════════════════════════
PX = 26.2   # left edge of right panel (pushed right to give room for o.c. arrows)
PW = 3.1    # panel width

def panel_box(y0, h, fc="#f5f5f5", ec="#444444", lw=1.5):
    rect(PX, y0, PW, h, fc, ec, lw=lw, zorder=2)

# ── Title block ───────────────────────────────────────────────────────────────
panel_box(-2.8, 5.2, fc="#f5f5f5")
title_lines = [
    'DECK PLAN v4',
    "23' × 16'  Attached Deck",
    '12" off grade',
    "House on 23' Edge",
    "Ledger + 12\" o.c. Joists",
    "Decking ⊥ House",
    "",
    "Scale: 1\" ≈ 1 ft (plot units = ft)",
    "HOUSE = top edge  ▲",
    "",
    "Date: 2026-05-01",
]
for i, line in enumerate(title_lines):
    fw = "bold" if i < 6 else "normal"
    fs = 8.5 if i == 0 else 7
    label(PX + PW/2, -2.6 + i * 0.42, line, fs=fs, bold=(fw == "bold"))

# ── Framing direction callout ─────────────────────────────────────────────────
panel_box(2.5, 2.5, fc="#fffde7", ec="#f57f17", lw=2)
label(PX + PW/2, 2.75, "FRAMING DIRECTION", fs=8, bold=True)
label(PX + 0.05, 3.05, "→ Girders: ⊥ to house (16 ft dir.)", fs=6.5, ha="left")
label(PX + 0.05, 3.3, "— Joists: ∥ to house (23 ft dir.), 12\" o.c.", fs=6.5, ha="left")
label(PX + 0.05, 3.55, "· Decking: ⊥ to joists (⊥ house, 16 ft)", fs=6.5, ha="left")
label(PX + 0.05, 3.8, "LEDGER lag-bolted to house. Joists run", fs=6.5, ha="left", color="#5a0000")
label(PX + 0.05, 4.0, "PARALLEL to ledger — do NOT hang from it.", fs=6.5, ha="left", color="#5a0000", bold=True)
label(PX + 0.05, 4.2, "Lag bolts + Z-flashing = house-attachment detail.", fs=6.5, ha="left", color="#5a0000")
label(PX + 0.05, 4.5, "Decking butts against wall (ledger edge, no PF board).", fs=6.0, ha="left", color="#555555")
label(PX + 0.05, 4.7, "PF boards on far side + both short edges only.", fs=6.0, ha="left", color="#555555")

# ── Legend ────────────────────────────────────────────────────────────────────
panel_box(5.1, 10.5, fc="white")
label(PX + PW/2, 5.3, "LEGEND", fs=10, bold=True)

legend_items = [
    (5.65, C_LEDGER, EC_LEDGER, 3.5,
     "Ledger — SINGLE 2×10 PT",
     "Lag bolts + Z-flashing; rests on 3 girders",
     "Ledger does NOT hang joists — joists run ∥ to it"),
    (6.65, C_GIRDER, EC_GIRDER, 3,
     "Girder — (3) 2×10 PT, ground-contact",
     "Runs ⊥ to house (16 ft); 3 @ 0', 11'-6\", 23'",
     None),
    (7.45, C_JOIST, EC_JOIST, 1,
     "Joist — 2×10 PT, 12\" o.c.",
     "Runs ∥ to house (23 ft); spliced over mid girder",
     "15 regular joists (Members 2–16) across 16 ft depth"),
    (8.4, C_RIM, EC_RIM, 2,
     "Picture-frame border",
     "Far rim: (2) 2×10 PT; short-edge rims: 2×10 PT",
     "PF composite board on far + two short edges only"),
    (9.35, C_POST_F, EC_POST, 2,
     "Post (P1–P9) + Footing",
     "6×6 PT on 12\" sonotube footings to frost depth",
     "9 posts; 3 per girder @ 0', 8', 16' along girder"),
]

for row in legend_items:
    yt, fc, ec, lw, main, sub1, sub2 = row
    rect(PX + 0.08, yt, 0.45, 0.35, fc, ec, lw=lw, zorder=3)
    label(PX + 0.6, yt + 0.10, main, fs=7, bold=True, ha="left")
    label(PX + 0.6, yt + 0.27, sub1, fs=6, ha="left", color="#444444")
    if sub2:
        label(PX + 0.6, yt + 0.42, sub2, fs=5.8, ha="left", color="#666666")

# Blocking legend
yt_block = 10.2
ax.plot([PX + 0.08, PX + 0.53], [yt_block + 0.17, yt_block + 0.17],
        color=C_BLOCK, lw=2.5, linestyle="--", zorder=4)
label(PX + 0.6, yt_block + 0.10, "Blocking — solid 2×10 PT between joists", fs=7, bold=True, ha="left")
label(PX + 0.6, yt_block + 0.27, "Rows at 5'-9\" and 17'-3\" from left edge", fs=6, ha="left", color="#444444")

# ── Fastener / material notes ─────────────────────────────────────────────────
panel_box(10.9, 5.0, fc=C_NOTE, ec=EC_NOTE)
notes = [
    "FASTENER / MATERIAL NOTES",
    "Ledger: ½\" hot-dip galv lag bolts or FastenMaster LedgerLOK,",
    "  16\" o.c. staggered top/bottom; metal Z-flashing above ledger",
    "Lateral ties: min. 2× Simpson MTWDeck (or equiv.) per IRC R507.9",
    "Joist-to-rim: Simpson LSU/LSC end-grain hangers (short edges)",
    "Joist tape: Zip System or equiv. on every joist top surface",
    "Joist splices: GRK RSS structural screws, lap joint over mid girder",
    "2-ply far-side rim: ½\" carriage bolts per AWC specs",
    "Framing: 2×10 PT UC4B throughout; posts: 6×6 PT UC4B",
    "Decking: Trex composite; boards run ⊥ to house (16 ft)",
    "Footings: 12\" dia. sonotube to frost depth, per local code",
    "Hardware: Simpson ZMAX or stainless throughout",
]
for i, note in enumerate(notes):
    fw = "bold" if i == 0 else "normal"
    label(PX + 0.07, 11.1 + i * 0.37, note, fs=6.2, bold=(i == 0), ha="left")

# ── Section detail ─────────────────────────────────────────────────────────────
panel_box(16.2, 3.7, fc="#f9f9f9")
label(PX + PW/2, 16.35, "SECTION DETAIL (typical bay)", fs=8, bold=True)
label(PX + PW/2, 16.6, "Vertical slice at any post, looking along joist", fs=6)

layers = [
    (16.8,  "PICTURE-FRAME BOARD",            C_RIM,    EC_RIM,    2, 0.18),
    (16.98, "TREX COMPOSITE DECKING (⊥ house)", C_DECK,  EC_DECK,   2, 0.22),
    (17.20, "JOIST TAPE",                      C_TAPE,   EC_TAPE,   2, 0.10),
    (17.30, "2×10 PT JOIST (∥ to house)",      C_JOIST,  EC_JOIST,  2, 0.26),
    (17.56, "(3) 2×10 PT GIRDER",              C_GIRDER, EC_GIRDER, 3, 0.30),
    (17.86, "POST CAP (Simpson BC/E or equiv.)", C_POST_F, EC_POST,  1, 0.10),
    (17.96, "6×6 PT POST (ground-contact)",    C_POST_F, EC_POST,   2, 0.50),
    (18.46, "12\" DIA. SONOTUBE FOOTING",       C_POST_F, EC_POST,   2, 0.35),
    (18.81, "GRADE (12\" below deck surface)",  "#aaaaaa","#555555", 2, 0.24),
]

for (y_pos, lbl, fc, ec, lw, h) in layers:
    rect(PX + 0.22, y_pos, PW - 0.44, h, fc, ec, lw=lw, zorder=3)
    label(PX + PW/2, y_pos + h/2, lbl, fs=6.5, bold=False, zorder=4)

label(PX + PW/2, 19.2, "▲ deck surface   ▼ below grade", fs=6.5, color="#555555")

# Inset note: ledger-to-house attachment
rect(PX + 0.05, 19.4, PW - 0.1, 0.5, "#fff0f0", "#b85450", lw=1.5, zorder=3)
label(PX + PW/2, 19.65,
      "Ledger detail: 2×10 PT lag-bolted to house rim joist\n"
      "Z-flashing tucked behind siding. Ledger rests on 3 girders.",
      fs=5.8, ha="center", va="center", color="#5a0000", zorder=4)

# ══════════════════════════════════════════════════════════════════════════════
# FIGURE title (top-left, outside plan)
# ══════════════════════════════════════════════════════════════════════════════
ax.text(-2.4, -2.5,
        'Deck Plan v4  —  23\'×16\' Attached, 12" off grade,\n'
        'House on 23\' Edge, Ledger + 12" o.c. Joists, Decking ⊥ House',
        fontsize=10, fontweight="bold", va="top", ha="left", color="#222222")

# ══════════════════════════════════════════════════════════════════════════════
# Save
# ══════════════════════════════════════════════════════════════════════════════
OUT = "/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/owner_inbox/deck_blueprint/deck_plan.png"
fig.savefig(OUT, dpi=DPI, bbox_inches="tight", facecolor="white")
print(f"Saved: {OUT}")

from PIL import Image
img = Image.open(OUT)
print(f"Size: {img.size[0]}×{img.size[1]} px")
