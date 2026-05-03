"""
render_v5.py  —  Gemma's matplotlib render of deck_plan v5
Produces deck_plan.png at ≥2000 px wide, white background.

v5 changes vs v4:
  - Overall finished surface grows from 23' × 16' → 23'-6" × 16'-6"
  - Framing footprint = 23'-6" × 16'-6" (PF board flush with rim outer edge)
  - Ledger grows from 23'-0" → 23'-6"
  - Girder length grows from 16'-0" → 16'-6"
  - Girder positions: 0', 11'-9", 23'-6" (was 0/11'-6/23)
  - Joist count: 18 members total (was 17):
      Member 1  (0"):   ledger
      Members 2–17 (12"–192"):  16 regular joists
      Member 18 (198" / 16'-6"): doubled far-side rim
  - Final bay: 6" between last 12" o.c. joist (at 16'-0") and doubled far rim (at 16'-6")
  - Post positions along each girder: 0', 8'-3", 16'-6" (was 0/8/16)
  - Blocking rows: 5'-10.5" and 17'-7.5" from left edge (was 5'-9" and 17'-3")
  - Picture-frame on 3 exposed sides only (unchanged config)

Coordinate system:
  - X axis = 23.5 ft direction (along house wall, left→right)
  - Y axis = 16.5 ft direction (out from house, top→bottom)
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

# Plan area: x 0..23.5 ft (along house), y 0..16.5 ft (out from house, downward)
PLAN_X0, PLAN_X1 = 0.0, 23.5
PLAN_Y0, PLAN_Y1 = 0.0, 16.5

ax.set_xlim(-2.5, 30.5)
ax.set_ylim(-3.2, 21.0)
ax.invert_yaxis()   # house at top (y=0 plots at top)
ax.set_aspect("equal")
ax.axis("off")

# ── Color palette (identical semantic meaning as v4) ───────────────────────────
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
rect(0, -1.0, 23.5, 1.0, C_HOUSE, "#444444", lw=2, zorder=3)
label(11.75, -0.5, "HOUSE WALL  ▲  NORTH  (attached 23'-6\" edge)",
      fs=11, bold=True)

# ══════════════════════════════════════════════════════════════════════════════
# GIRDERS — perpendicular to house, run in 16.5 ft direction (vertical in plan)
# 3 girders at x = 0, 11.75, 23.5 ft; each 16.5 ft long
# ══════════════════════════════════════════════════════════════════════════════
GIRDER_W = 0.35
# 11'-9" = 11.75 ft
GIRDER_POSITIONS = [0.0, 11.75, 23.5]
GIRDER_LABELS = [
    "LEFT GIRDER\n(3) 2×10 PT\n@ 0 ft",
    "MIDDLE GIRDER\n(3) 2×10 PT\n@ 11'-9\"",
    "RIGHT GIRDER\n(3) 2×10 PT\n@ 23'-6\"",
]

for gx, glabel_txt in zip(GIRDER_POSITIONS, GIRDER_LABELS):
    x0 = gx - GIRDER_W / 2
    x0 = max(0.0, min(x0, 23.5 - GIRDER_W))
    rect(x0, 0.0, GIRDER_W, 16.5, C_GIRDER, EC_GIRDER, lw=3, zorder=4)
    ax.text(x0 + GIRDER_W/2, 8.25, glabel_txt,
            fontsize=6.0, ha="center", va="center", rotation=90,
            fontweight="bold", color="#1a3a6b", zorder=6,
            multialignment="center")

# ══════════════════════════════════════════════════════════════════════════════
# LEDGER (v5 — 23'-6" long)
# Single 2x10 PT, 23.5 ft long, lag-bolted to house
# Member 1 of the joist field (at y=0)
# ══════════════════════════════════════════════════════════════════════════════
LEDGER_H = 0.18
rect(0.0, 0.0, 23.5, LEDGER_H, C_LEDGER, EC_LEDGER, lw=3.5, zorder=5)
label(11.75, LEDGER_H/2,
      "LEDGER — SINGLE 2×10 PT, 23'-6\"  |  ½\" hot-dip galv lag bolts (or LedgerLOK) @ 16\" o.c. staggered  |  Z-flashing above  |  Rests on 3 girders",
      fs=6.5, bold=True, color="#5a0000")

# MTWDeck lateral-tie callout
rect(14.5, 0.22, 8.7, 0.55, C_CALLOUT, EC_CALLOUT, lw=1.5, zorder=6)
label(18.85, 0.50,
      "⚠ MTWDeck LATERAL TIE REQ'D — min. 2× Simpson MTWDeck (or equiv.) along ledger\n"
      "per IRC R507.9 / DCA-6: 2× band joist + 2× interior blocking bearing on sill plate",
      fs=6.0, ha="center", va="center", color="#663300", zorder=7)

# Ledger margin note
label(-1.8, 0.09,
      "LEDGER\n2×10 PT\n23'-6\"\n(lag-bolted\n+ Z-flash)",
      fs=6.5, ha="center", va="center", rotation=0)

# ══════════════════════════════════════════════════════════════════════════════
# FAR-SIDE DOUBLED RIM (Member 18) — at 16.5 ft (16'-6")
# Doubled 2x10 PT, yellow, sits on top of 3 girders
# ══════════════════════════════════════════════════════════════════════════════
FAR_RIM_H = 0.22
rect(0.0, 16.5 - FAR_RIM_H, 23.5, FAR_RIM_H, C_RIM, EC_RIM, lw=3, zorder=5)
label(11.75, 16.5 - FAR_RIM_H/2,
      "FAR-SIDE RIM — (2) 2×10 PT, 23'-6\"  |  Sits on 3 girders at 16'-6\" outer edge  |  Picture-frame board on top",
      fs=7.5, bold=True)

# Picture-frame board width label on far side
label(11.75, 16.5 + 0.25,
      "← 5.5\" PF board (Trex, flush with rim outer edge) →",
      fs=6.5, color="#5a4000")

# ══════════════════════════════════════════════════════════════════════════════
# SHORT-EDGE RIM JOISTS — 16.5 ft long, at left (x=0) and right (x=23.5) edges
# ══════════════════════════════════════════════════════════════════════════════
RIM_SIDE_W = 0.22
rect(0.0, 0.0, RIM_SIDE_W, 16.5, C_RIM, EC_RIM, lw=2, zorder=3)
rect(23.5 - RIM_SIDE_W, 0.0, RIM_SIDE_W, 16.5, C_RIM, EC_RIM, lw=2, zorder=3)

# PF board width labels on short edges
label(-0.22, 8.25, "5.5\"\nPF", fs=6, ha="center", va="center", color="#5a4000", rotation=90)
label(23.72, 8.25, "5.5\"\nPF", fs=6, ha="center", va="center", color="#5a4000", rotation=90)

label(-0.75, 8.25, "LEFT RIM\n2×10 PT\n16'-6\"\n(end-grain\nhangers)",
      fs=6.5, ha="center", va="center", rotation=0)
label(24.25, 8.25, "RIGHT RIM\n2×10 PT\n16'-6\"\n(end-grain\nhangers)",
      fs=6.5, ha="center", va="center", rotation=0)

# ══════════════════════════════════════════════════════════════════════════════
# JOISTS — Members 2–17: 16 regular joists at 12" o.c.
# y positions in feet: 1/12*12 = 1 ft, 2 ft, … 16 ft
# Member 18 is the far-side doubled rim at 16.5 ft (drawn above)
#
# NOTE on the 6" final bay:
#   Last 12" o.c. joist is at 16.0 ft (192").
#   Doubled far rim is at 16.5 ft (198").
#   Gap = 6" — intentional, keeps standard spacing through the field.
# ══════════════════════════════════════════════════════════════════════════════
JOIST_H = 0.09
JOIST_SPACING_FT = 1.0   # 12" = 1 ft

# Members 2–17: joists at 1 ft through 16 ft
for i in range(1, 17):
    y_pos = i * JOIST_SPACING_FT
    rect(0.0, y_pos - JOIST_H/2, 23.5, JOIST_H, C_JOIST, EC_JOIST, lw=1, zorder=3)

# Highlight the 6" final bay with a subtle shaded band
# From y=16.0 (last joist top) to y=16.5 (far rim bottom) minus the rim thickness
y_last_joist = 16.0
y_far_rim_bottom = 16.5 - FAR_RIM_H
rect(0.0, y_last_joist + JOIST_H/2, 23.5, y_far_rim_bottom - (y_last_joist + JOIST_H/2),
     "#fffbe6", "#d4a800", lw=0.5, zorder=2, alpha=0.6)
label(11.75, (y_last_joist + y_far_rim_bottom) / 2,
      "← 6\" final bay (normal — std. 12\" o.c. holds through field) →",
      fs=6.0, color="#7a5800", bold=False)

# Splice callout on the 8th regular joist
splice_y = 8 * JOIST_SPACING_FT
ax.annotate("", xy=(11.75, splice_y), xytext=(12.5, splice_y - 0.7),
            arrowprops=dict(arrowstyle="->", color="#555555", lw=0.8))
label(13.7, splice_y - 0.85,
      "SPLICE over middle girder\n(lap joint + GRK RSS structural screws) — typ. all joists",
      fs=6, ha="left", va="center")

# Joist o.c. spacing arrows — 3 representative call-outs on the right side
for arrow_i in [2, 7, 12]:
    y_a = (arrow_i - 0.5) * JOIST_SPACING_FT
    ax.annotate("", xy=(25.1, arrow_i * JOIST_SPACING_FT),
                xytext=(25.1, (arrow_i - 1) * JOIST_SPACING_FT if arrow_i > 1 else 0),
                arrowprops=dict(arrowstyle="<->", color="#333333", lw=0.9))
    label(25.55, y_a, '12"', fs=7.5, bold=True, ha="left")

label(26.2, 8.0, "12\" o.c.\ntypical", fs=9, bold=True, ha="left")

# 6" final bay arrow
ax.annotate("", xy=(25.1, 16.5 - FAR_RIM_H/2),
            xytext=(25.1, 16.0),
            arrowprops=dict(arrowstyle="<->", color="#d4a800", lw=0.9))
label(25.55, 16.25, '6"', fs=7.5, bold=True, ha="left", color="#7a5800")

# ══════════════════════════════════════════════════════════════════════════════
# BLOCKING ROWS — dashed gray vertical lines
# Row 1: midspan of left bay = midpoint between 0 and 11.75 = 5.875 ft ≈ 5'-10.5"
# Row 2: midspan of right bay = midpoint between 11.75 and 23.5 = 17.625 ft ≈ 17'-7.5"
# ══════════════════════════════════════════════════════════════════════════════
BLOCKING_X = [5.875, 17.625]
BLOCKING_LABELS = ["BLOCKING\n@ 5'-10½\"", "BLOCKING\n@ 17'-7½\""]
for bx, blbl in zip(BLOCKING_X, BLOCKING_LABELS):
    ax.plot([bx, bx], [0.0, 16.5],
            color=C_BLOCK, linewidth=2.5, linestyle="--", zorder=3, alpha=0.85)
    label(bx, -1.0, blbl, fs=7, bold=True, color="#555555")

# ══════════════════════════════════════════════════════════════════════════════
# POSTS — 9 total, labeled P1–P9
# Each girder: posts at 0', 8'-3", 16'-6" along girder (out from house)
# 8'-3" = 8.25 ft
# ══════════════════════════════════════════════════════════════════════════════
POST_R = 0.38
POST_SQ = 0.22

posts = [
    (0.0,   0.0,   "P1"),
    (0.0,   8.25,  "P2"),
    (0.0,   16.5,  "P3"),
    (11.75, 0.0,   "P4"),
    (11.75, 8.25,  "P5"),
    (11.75, 16.5,  "P6"),
    (23.5,  0.0,   "P7"),
    (23.5,  8.25,  "P8"),
    (23.5,  16.5,  "P9"),
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

# Overall 23'-6" (horizontal, above house)
ax.annotate("", xy=(23.5, -1.9), xytext=(0.0, -1.9),
            arrowprops=dict(arrowstyle="<->", color="black", lw=1.5))
label(11.75, -2.1, "23'-6\"  overall (along house wall) = framing dimension", fs=9, bold=True)
label(11.75, -2.4, "(PF board flush with rim outer edge — no cantilever)", fs=7.5, color="#555555")

# Framing dimension = overall (same, note PF flush)
# Show a second annotation for the framing footprint clarity
ax.annotate("", xy=(23.5, -1.5), xytext=(0.0, -1.5),
            arrowprops=dict(arrowstyle="<->", color="#1a3a6b", lw=0.8))
label(11.75, -1.3, "Framing: 23'-6\"  (= overall, PF is flush)", fs=7.5, color="#1a3a6b")

# Overall 16'-6" (vertical, left of plan)
ax.annotate("", xy=(-1.6, 16.5), xytext=(-1.6, 0.0),
            arrowprops=dict(arrowstyle="<->", color="black", lw=1.5))
label(-2.2, 8.25, "16'-6\"  overall (out from house) = framing dimension", fs=9, bold=True, rotation=90)

ax.annotate("", xy=(-1.2, 16.5), xytext=(-1.2, 0.0),
            arrowprops=dict(arrowstyle="<->", color="#1a3a6b", lw=0.8))
label(-0.95, 8.25, "Framing: 16'-6\"", fs=7.5, color="#1a3a6b", rotation=90)

# Girder positions (tick marks along top)
for gx, gtxt in zip([0.0, 11.75, 23.5], ["0'", "11'-9\"", "23'-6\""]):
    ax.plot([gx, gx], [-1.6, -0.9], color="#333333", lw=1, zorder=4)
    label(gx, -0.65, gtxt, fs=7.5, bold=True, va="bottom")

# Post spacing along girder (left margin)
for py, ptxt in zip([0.0, 8.25, 16.5], ["0'", "8'-3\"", "16'-6\""]):
    ax.plot([-1.7, -1.3], [py, py], color="#555555", lw=0.8)
    label(-1.9, py, ptxt, fs=7.5, bold=False, ha="right")

# Joist span annotations (below plan)
ax.annotate("", xy=(11.75, 17.8), xytext=(0.0, 17.8),
            arrowprops=dict(arrowstyle="<->", color="#555577", lw=1.0))
label(5.875, 18.2, "11'-9\" joist span", fs=7.5, color="#333377")

ax.annotate("", xy=(23.5, 17.8), xytext=(11.75, 17.8),
            arrowprops=dict(arrowstyle="<->", color="#555577", lw=1.0))
label(17.625, 18.2, "11'-9\" joist span", fs=7.5, color="#333377")

# Blocking position ticks below plan
for bx in BLOCKING_X:
    ax.plot([bx, bx], [17.6, 18.0], color=C_BLOCK, lw=1, linestyle="--")

# ══════════════════════════════════════════════════════════════════════════════
# RIGHT-SIDE PANEL — Title block, framing callout, legend, section detail
# ══════════════════════════════════════════════════════════════════════════════
PX = 27.4   # left edge of right panel
PW = 3.0    # panel width

def panel_box(y0, h, fc="#f5f5f5", ec="#444444", lw=1.5):
    rect(PX, y0, PW, h, fc, ec, lw=lw, zorder=2)

# ── Title block ───────────────────────────────────────────────────────────────
panel_box(-3.2, 5.5, fc="#f5f5f5")
title_lines = [
    "DECK PLAN v5",
    "23'-6\" × 16'-6\"  Overall (incl. PF)",
    "12\" off grade",
    "House on 23'-6\" Edge",
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
    label(PX + PW/2, -3.0 + i * 0.42, line, fs=fs, bold=(fw == "bold"))

# ── Framing direction callout ─────────────────────────────────────────────────
panel_box(2.5, 3.0, fc="#fffde7", ec="#f57f17", lw=2)
label(PX + PW/2, 2.75, "FRAMING DIRECTION", fs=8, bold=True)
label(PX + 0.05, 3.05, "→ Girders: ⊥ to house (16'-6\" dir.)", fs=6.5, ha="left")
label(PX + 0.05, 3.3,  "— Joists: ∥ to house (23'-6\" dir.), 12\" o.c.", fs=6.5, ha="left")
label(PX + 0.05, 3.55, "· Decking: ⊥ to joists (⊥ house, 16'-6\")", fs=6.5, ha="left")
label(PX + 0.05, 3.80, "Framing 23'-6\" × 16'-6\" = overall finished", fs=6.5, ha="left", color="#5a0000", bold=True)
label(PX + 0.05, 4.00, "  surface (PF board flush with rim).", fs=6.5, ha="left", color="#5a0000")
label(PX + 0.05, 4.22, "LEDGER lag-bolted to house. Joists run", fs=6.5, ha="left", color="#333333")
label(PX + 0.05, 4.42, "PARALLEL — do NOT hang from ledger.", fs=6.5, ha="left", color="#333333", bold=True)
label(PX + 0.05, 4.65, "Decking butts wall (ledger edge, no PF board).", fs=6.0, ha="left", color="#555555")
label(PX + 0.05, 4.85, "PF boards on far side + both short edges only.", fs=6.0, ha="left", color="#555555")

# ── Legend ────────────────────────────────────────────────────────────────────
panel_box(5.6, 10.8, fc="white")
label(PX + PW/2, 5.8, "LEGEND", fs=10, bold=True)

legend_items = [
    (6.15, C_LEDGER, EC_LEDGER, 3.5,
     "Ledger — SINGLE 2×10 PT, 23'-6\"",
     "Lag bolts + Z-flashing; rests on 3 girders",
     "Does NOT hang joists — joists run ∥ to it"),
    (7.15, C_GIRDER, EC_GIRDER, 3,
     "Girder — (3) 2×10 PT, 16'-6\" long",
     "Runs ⊥ to house; 3 @ 0', 11'-9\", 23'-6\"",
     None),
    (7.95, C_JOIST, EC_JOIST, 1,
     "Joist — 2×10 PT, 12\" o.c., 23'-6\" long",
     "16 regular joists (Members 2–17), ∥ to house",
     "Spliced over middle girder (~11'-9\" each span)"),
    (8.90, C_RIM, EC_RIM, 2,
     "Picture-frame border (3 exposed sides)",
     "Far rim: (2) 2×10 PT; short-edge rims: 2×10 PT",
     "5.5\" Trex PF board on top, flush with rim outer edge"),
    (9.90, C_POST_F, EC_POST, 2,
     "Post (P1–P9) + Footing",
     "6×6 PT on 12\" sonotube footings to frost depth",
     "9 posts; 3 per girder @ 0', 8'-3\", 16'-6\" along girder"),
]

for row in legend_items:
    yt, fc, ec, lw, main, sub1, sub2 = row
    rect(PX + 0.08, yt, 0.45, 0.35, fc, ec, lw=lw, zorder=3)
    label(PX + 0.6, yt + 0.10, main, fs=7, bold=True, ha="left")
    label(PX + 0.6, yt + 0.27, sub1, fs=6, ha="left", color="#444444")
    if sub2:
        label(PX + 0.6, yt + 0.42, sub2, fs=5.8, ha="left", color="#666666")

# Blocking legend
yt_block = 10.7
ax.plot([PX + 0.08, PX + 0.53], [yt_block + 0.17, yt_block + 0.17],
        color=C_BLOCK, lw=2.5, linestyle="--", zorder=4)
label(PX + 0.6, yt_block + 0.10, "Blocking — solid 2×10 PT between joists", fs=7, bold=True, ha="left")
label(PX + 0.6, yt_block + 0.27, "Rows at 5'-10½\" and 17'-7½\" from left edge", fs=6, ha="left", color="#444444")

# 6" final bay legend
yt_bay = 11.4
rect(PX + 0.08, yt_bay, 0.45, 0.35, "#fffbe6", "#d4a800", lw=1, zorder=3, alpha=0.7)
label(PX + 0.6, yt_bay + 0.10, "6\" final bay (at 16'-0\" to 16'-6\")", fs=7, bold=True, ha="left", color="#7a5800")
label(PX + 0.6, yt_bay + 0.27, "Normal — keeps 12\" o.c. standard through field.", fs=5.8, ha="left", color="#666666")

# ── Fastener / material notes ─────────────────────────────────────────────────
panel_box(12.0, 5.2, fc=C_NOTE, ec=EC_NOTE)
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
    "Decking: Trex composite; boards run ⊥ to house (16'-6\")",
    "Footings: 12\" dia. sonotube to frost depth, per local code",
    "Hardware: Simpson ZMAX or stainless throughout",
]
for i, note in enumerate(notes):
    fw = "bold" if i == 0 else "normal"
    label(PX + 0.07, 12.2 + i * 0.37, note, fs=6.2, bold=(i == 0), ha="left")

# ── Section detail ─────────────────────────────────────────────────────────────
panel_box(17.4, 3.5, fc="#f9f9f9")
label(PX + PW/2, 17.55, "SECTION DETAIL (typical bay)", fs=8, bold=True)
label(PX + PW/2, 17.80, "Vertical slice at any post, looking along joist", fs=6)

layers = [
    (18.00, "PICTURE-FRAME BOARD (5.5\" Trex, flush w/ rim outer edge)", C_RIM,    EC_RIM,    2, 0.18),
    (18.18, "TREX COMPOSITE DECKING (⊥ house)",                          C_DECK,   EC_DECK,   2, 0.22),
    (18.40, "JOIST TAPE",                                                  C_TAPE,   EC_TAPE,   2, 0.10),
    (18.50, "2×10 PT JOIST (∥ to house, 23'-6\" long)",                  C_JOIST,  EC_JOIST,  2, 0.26),
    (18.76, "(3) 2×10 PT GIRDER (16'-6\" long)",                         C_GIRDER, EC_GIRDER, 3, 0.30),
    (19.06, "POST CAP (Simpson BC/E or equiv.)",                           C_POST_F, EC_POST,   1, 0.10),
    (19.16, "6×6 PT POST (ground-contact)",                               C_POST_F, EC_POST,   2, 0.50),
    (19.66, "12\" DIA. SONOTUBE FOOTING",                                 C_POST_F, EC_POST,   2, 0.35),
    (20.01, "GRADE (12\" below deck surface)",                             "#aaaaaa","#555555", 2, 0.24),
]

for (y_pos, lbl, fc, ec, lw, h) in layers:
    rect(PX + 0.22, y_pos, PW - 0.44, h, fc, ec, lw=lw, zorder=3)
    label(PX + PW/2, y_pos + h/2, lbl, fs=6.0, bold=False, zorder=4)

label(PX + PW/2, 20.3, "▲ deck surface   ▼ below grade", fs=6.5, color="#555555")

# Inset note: ledger-to-house attachment
rect(PX + 0.05, 20.55, PW - 0.1, 0.45, "#fff0f0", "#b85450", lw=1.5, zorder=3)
label(PX + PW/2, 20.78,
      "Ledger: 2×10 PT lag-bolted to house rim joist\n"
      "Z-flashing tucked behind siding. Rests on 3 girders.",
      fs=5.8, ha="center", va="center", color="#5a0000", zorder=4)

# ══════════════════════════════════════════════════════════════════════════════
# FIGURE title (top-left, outside plan)
# ══════════════════════════════════════════════════════════════════════════════
ax.text(-2.4, -3.0,
        "Deck Plan v5  —  23'-6\" × 16'-6\" Overall (incl. PF board), 12\" off grade,\n"
        "House on 23'-6\" Edge, Ledger + 12\" o.c. Joists, Decking ⊥ House",
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
