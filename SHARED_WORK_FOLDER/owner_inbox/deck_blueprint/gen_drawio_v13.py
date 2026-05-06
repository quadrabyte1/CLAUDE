"""
gen_drawio_v13.py — Generates deck_plan.drawio for v13.

Reads the current deck_plan.drawio (v12) and applies v13 changes:

Change 1 — Drop house-side pier row (9 → 6 piers):
  - Hides/removes the 3 pier cells at y=12" row (P1, P4, P7) and their hole circles (h01, h04, h07)
  - Adds Simpson HU210-3 hanger symbols at x=0', 11'-6", 23'-0" on the ledger
  - Updates ledger label to include IRC R507.9.1.3 back-bolt spec
  - Updates pier legend entry from "9 total" to "6 total"
  - Adds point-load hanger callout box

Change 2 — Far-edge step (v13 new):
  - Adds far-edge step ribbon, tread planks, 5 precast blocks, gravel pad
  - Adds seasonal heave callout
  - Adds far-edge step side-elevation annotation
  - Updates title cells and version badges on both pages

Coordinate system (drawio):
  Scale: 40 px/ft
  Origin: x=220 (left girder outer face = x=0'), y=180 (house wall = y=0')
  So: drawio_x = 220 + ft_x * 40
      drawio_y = 180 + ft_y * 40

Key geometry for far-edge step:
  FAR_STEP_X_RIGHT = OVERALL_W - PF_OVR = 23.25 ft => drawio_x = 220 + 23.25*40 = 1150
  FAR_STEP_X_LEFT  = 11.5 ft => drawio_x = 220 + 11.5*40 = 680
  Step length = 11.75 ft = 11'-9" = 470 px
  OVERALL_D = FRAME_D + PF_OVR = 16.25 + 0.25 = 16.5 ft => drawio_y = 180 + 16.5*40 = 840
  FAR_PF_Y0 = 16.05 ft => drawio_y = 180 + 16.05*40 = 822
  FAR_PF_Y1 = 16.5 ft => drawio_y = 840
  Tread depth: 10.93" ≈ 10.9" => 0.908 ft => 36.3 px
  Ribbon: 3" = 0.25 ft => 10 px depth past far PF
"""

import re

SCALE = 40  # px per foot

def ft_to_x(ft_x):
    return 220 + ft_x * SCALE

def ft_to_y(ft_y):
    return 180 + ft_y * SCALE

# Key dimensions (must match render_v13.py exactly)
FRAME_W    = 23.0
FRAME_D    = 16.25
PF_W       = 5.4 / 12
FASCIA_T   = 0.67 / 12
PF_OVR     = 3.0 / 12
OVERALL_W  = FRAME_W + 2 * PF_OVR   # 23.5 ft
OVERALL_D  = FRAME_D + PF_OVR        # 16.5 ft

GIRDER_X   = [0.0, 11.5, 23.0]
GIRDER_W   = 0.38
GHW        = GIRDER_W / 2

# Left-edge step (unchanged from v12)
STEP_Y0    = 6.0
STEP_Y1    = 9.5
STEP_DEPTH = 16.0 / 12
LEFT_DECK_X = -PF_OVR - FASCIA_T
STEP_X_OUT  = LEFT_DECK_X - STEP_DEPTH
STRINGER_T  = 2.0 / 12
TREAD_DEPTH  = 10.8 / 12
PLANK_W      = 5.4 / 12
PLANK_GAP    = (1.0/8) / 12
LEFT_PF_X0 = -(PF_OVR + FASCIA_T + PF_W)
LEFT_PF_X1 = -(PF_OVR + FASCIA_T)
STRINGER_Y  = [STEP_Y0, (STEP_Y0 + STEP_Y1)/2, STEP_Y1]
FAR_PF_Y0   = FRAME_D + PF_OVR - PF_W
GRAVEL_W = 48.0 / 12
GRAVEL_D = 18.0 / 12
GRAVEL_Y0 = STEP_Y0 - (GRAVEL_W - (STEP_Y1 - STEP_Y0)) / 2
GRAVEL_Y1 = GRAVEL_Y0 + GRAVEL_W
GRAVEL_X0 = LEFT_DECK_X - GRAVEL_D
PAVER_SZ = 1.0

# Far-edge step (v13 new)
FAR_STEP_X_RIGHT = OVERALL_W - PF_OVR          # 23.25 ft framing
FAR_STEP_X_LEFT  = (-PF_OVR + OVERALL_W - PF_OVR) / 2  # 11.5 ft framing
FAR_STEP_LEN     = FAR_STEP_X_RIGHT - FAR_STEP_X_LEFT   # 11.75 ft = 11'-9"
FAR_TREAD_DEPTH  = (5.4 + 5.4 + 0.125) / 12   # ≈ 0.910 ft

DROP_T = 0.085
JOIST_H = 0.085
RIM_Y = FRAME_D
far_drop_y = RIM_Y + JOIST_H
fas_y = far_drop_y + DROP_T
RIBBON_T = 2 * (1.5/12)   # 3" doubled 2x6

# FAR PF outer face y position in ft (= FAR_STEP_Y_ATTACH)
FAR_STEP_Y_ATTACH = OVERALL_D  # = 16.5 ft => drawio_y = 840

# Ribbon starts at fas_y (the far fascia outer face, approximate)
RIBBON_Y0 = fas_y   # ≈ 16.34 ft from house
RIBBON_Y1 = RIBBON_Y0 + RIBBON_T  # ≈ 16.59 ft

# Tread planks start after ribbon
TREAD_Y0 = RIBBON_Y1   # inboard face of first tread plank
TREAD_Y1 = TREAD_Y0 + 2 * PLANK_W + PLANK_GAP  # outer face of second plank

# Block y position (just beyond tread outer face)
BLOCK_Y0 = TREAD_Y1 + 0.05
FAR_BLOCK_ABS = [23.0, 20.167, 17.333, 14.5, 11.75]  # absolute from left outer PF corner
FAR_BLOCK_X   = [a - PF_OVR for a in FAR_BLOCK_ABS]   # in framing coords

FAR_BLOCK_SZ = 1.0  # 12"×12" = 1 ft

# Gravel pad for far-edge step
FAR_GRAVEL_Y0 = OVERALL_D   # starts at outer PF face
FAR_GRAVEL_Y1 = BLOCK_Y0 + FAR_BLOCK_SZ + 0.2  # extends past blocks

# Convert
def dx(ft): return ft_to_x(ft)
def dy(ft): return ft_to_y(ft)


def make_v13_cells_page1():
    """v13 cells for Page 1 (Framing Plan): hangers + far-edge step outline + callouts."""
    cells = []

    # ── Hanger symbols at 3 girder-to-ledger connections ─────────────────────
    HANGER_SZ = 9  # px (≈ 0.22 ft * 40 = 8.8)
    for i, gx in enumerate(GIRDER_X):
        hx = dx(gx) - HANGER_SZ
        hy = dy(0) - HANGER_SZ / 2
        cells.append(f'''        <mxCell id="v13-p1-hanger-{i}" parent="1" style="text;html=1;strokeColor=#882200;fillColor=#cc4400;align=center;verticalAlign=middle;whiteSpace=wrap;rounded=0;fontSize=5;fontColor=#ffffff;fontStyle=1;strokeWidth=2;" value="&lt;b&gt;HU&lt;br/&gt;210-3&lt;/b&gt;" vertex="1">
          <mxGeometry x="{hx:.1f}" y="{hy:.1f}" width="{HANGER_SZ*2}" height="{HANGER_SZ*2}" as="geometry" />
        </mxCell>''')

    # Hanger callout box
    callout_x = dx(GIRDER_X[1]) - 120
    callout_y = dy(0) - 85
    cells.append(f'''        <mxCell id="v13-p1-hanger-callout" parent="1" style="text;html=1;strokeColor=#882200;fillColor=#fff0e0;align=center;verticalAlign=top;whiteSpace=wrap;rounded=1;fontSize=7;fontColor=#882200;strokeWidth=1.5;" value="&lt;b&gt;Simpson HU210-3 (or eq.)&lt;br/&gt;at each girder-ledger connection&lt;br/&gt;— typ. 3 places&lt;/b&gt;" vertex="1">
          <mxGeometry x="{callout_x:.1f}" y="{callout_y:.1f}" width="240" height="55" as="geometry" />
        </mxCell>''')

    # ── Updated ledger fastener note ──────────────────────────────────────────
    ledger_note_x = dx(FRAME_W) + 20
    ledger_note_y = dy(0) - 10
    cells.append(f'''        <mxCell id="v13-p1-ledger-note" parent="1" style="text;html=1;strokeColor=#cc8800;fillColor=#fff9e6;align=left;verticalAlign=top;whiteSpace=wrap;rounded=0;fontSize=6.5;fontColor=#663300;strokeWidth=1.5;" value="&lt;b&gt;v13 LEDGER: ½in HDG carriage bolts back-blocked from basement,&lt;br/&gt;clustered at girder connections; ½in HDG lag @ 18in OC two-row&lt;br/&gt;staggered between connections (IRC R507.9.1.3).&lt;br/&gt;Wall = wood-frame. Peel-and-stick + Z-flashing retained.&lt;/b&gt;" vertex="1">
          <mxGeometry x="{ledger_note_x:.1f}" y="{ledger_note_y:.1f}" width="380" height="65" as="geometry" />
        </mxCell>''')

    # ── Far-edge step outline (plan view, Page 1) ──────────────────────────────
    # Gravel pad
    fgx0 = dx(FAR_STEP_X_LEFT - 0.2); fgy0 = dy(FAR_GRAVEL_Y0)
    fgw  = (FAR_STEP_X_RIGHT - FAR_STEP_X_LEFT + 0.4) * SCALE
    fgh  = (FAR_GRAVEL_Y1 - FAR_GRAVEL_Y0) * SCALE
    cells.append(f'''        <mxCell id="v13-p1-far-gravel" parent="1" style="strokeColor=#8a7a68;fillColor=#d0c8b8;strokeWidth=1.5;opacity=70;dashed=1;" value="" vertex="1">
          <mxGeometry x="{fgx0:.1f}" y="{fgy0:.1f}" width="{fgw:.1f}" height="{fgh:.1f}" as="geometry" />
        </mxCell>''')
    cells.append(f'''        <mxCell id="v13-p1-far-gravel-lbl" parent="1" style="text;html=1;strokeColor=none;fillColor=none;align=center;verticalAlign=middle;whiteSpace=wrap;fontSize=6;fontColor=#6a5a48;" value="4in #57 gravel pad&lt;br/&gt;(outside deck footprint)" vertex="1">
          <mxGeometry x="{fgx0:.1f}" y="{fgy0:.1f}" width="{fgw:.1f}" height="30" as="geometry" />
        </mxCell>''')

    # Ribbon outline on Page 1 (framing plan shows ribbon attachment)
    ribbon_x0 = dx(FAR_STEP_X_LEFT)
    ribbon_y0 = dy(RIBBON_Y0)
    ribbon_w  = FAR_STEP_LEN * SCALE
    ribbon_h  = RIBBON_T * SCALE
    cells.append(f'''        <mxCell id="v13-p1-far-ribbon" parent="1" style="strokeColor=#2a5a2a;fillColor=#5a8a5a;strokeWidth=2;opacity=85;" value="&lt;b&gt;Dbl 2x6 PT ribbon&lt;/b&gt;" vertex="1">
          <mxGeometry x="{ribbon_x0:.1f}" y="{ribbon_y0:.1f}" width="{ribbon_w:.1f}" height="{ribbon_h:.1f}" as="geometry" />
        </mxCell>''')

    # 5 precast deck blocks
    bsz = FAR_BLOCK_SZ * SCALE
    for idx, bx in enumerate(FAR_BLOCK_X):
        bx0 = dx(bx - FAR_BLOCK_SZ/2)
        by0 = dy(BLOCK_Y0)
        cells.append(f'''        <mxCell id="v13-p1-far-block-{idx}" parent="1" style="strokeColor=#444444;fillColor=#9a9a9a;strokeWidth=1.5;" value="" vertex="1">
          <mxGeometry x="{bx0:.1f}" y="{by0:.1f}" width="{bsz:.1f}" height="{bsz:.1f}" as="geometry" />
        </mxCell>''')

    # Far-edge step callout
    fsc_x = dx(FAR_STEP_X_LEFT) - 160
    fsc_y = dy(FAR_STEP_Y_ATTACH) - 5
    cells.append(f'''        <mxCell id="v13-p1-far-step-callout" parent="1" style="text;html=1;strokeColor=#2244aa;fillColor=#e8eeff;align=left;verticalAlign=top;whiteSpace=wrap;rounded=0;fontSize=7;fontColor=#1a2a88;strokeWidth=1.5;" value="&lt;b&gt;FAR-EDGE STEP — v13 NEW&lt;/b&gt;&lt;br/&gt;11ft-9in long | right corner to midpoint&lt;br/&gt;Single 6in rise | 10.9in tread depth&lt;br/&gt;Doubled 2x6 PT ribbon to outer rim&lt;br/&gt;5x precast blocks @ ~28in OC&lt;br/&gt;4in #57 gravel pad (outside footprint)&lt;br/&gt;HEAVE: ¼-½in seasonal (accepted)" vertex="1">
          <mxGeometry x="{fsc_x:.1f}" y="{fsc_y:.1f}" width="155" height="120" as="geometry" />
        </mxCell>''')

    # Pier count note — updated for v13 (6 piers)
    pier_note_x = dx(GIRDER_X[0]) - 180
    pier_note_y = dy(8.125) - 15
    cells.append(f'''        <mxCell id="v13-p1-pier-note" parent="1" style="text;html=1;strokeColor=#5a3010;fillColor=#f5ede0;align=left;verticalAlign=middle;whiteSpace=wrap;rounded=0;fontSize=7;fontColor=#5a3010;strokeWidth=1.5;" value="&lt;b&gt;v13: 6 PIERS (was 9)&lt;/b&gt;&lt;br/&gt;House-side row (P1,P4,P7) removed.&lt;br/&gt;Ledger carries those reactions&lt;br/&gt;via HU210-3 hangers (3 places).&lt;br/&gt;Middle row (y=8ft-1.5in) +&lt;br/&gt;Outer row (y=16ft-3in) remain." vertex="1">
          <mxGeometry x="{pier_note_x:.1f}" y="{pier_note_y:.1f}" width="170" height="90" as="geometry" />
        </mxCell>''')

    return '\n'.join(cells)


def make_v13_cells_page2():
    """v13 cells for Page 2 (Decking Plan): far-edge step + hanger callout."""
    cells = []

    # ── Hanger symbols on Page 2 (background framing reference) ───────────────
    HANGER_SZ = 9
    for i, gx in enumerate(GIRDER_X):
        hx = dx(gx) - HANGER_SZ
        hy = dy(0) - HANGER_SZ / 2
        cells.append(f'''        <mxCell id="v13-p2-hanger-{i}" parent="p2-1" style="text;html=1;strokeColor=#882200;fillColor=#cc4400;align=center;verticalAlign=middle;whiteSpace=wrap;rounded=0;fontSize=5;fontColor=#ffffff;fontStyle=1;strokeWidth=2;opacity=60;" value="&lt;b&gt;HU210-3&lt;/b&gt;" vertex="1">
          <mxGeometry x="{hx:.1f}" y="{hy:.1f}" width="{HANGER_SZ*2}" height="{HANGER_SZ*2}" as="geometry" />
        </mxCell>''')

    # ── Far-edge step: gravel pad ──────────────────────────────────────────────
    fgx0 = dx(FAR_STEP_X_LEFT - 0.2); fgy0 = dy(FAR_GRAVEL_Y0)
    fgw  = (FAR_STEP_X_RIGHT - FAR_STEP_X_LEFT + 0.4) * SCALE
    fgh  = (FAR_GRAVEL_Y1 - FAR_GRAVEL_Y0) * SCALE
    cells.append(f'''        <mxCell id="v13-p2-far-gravel" parent="p2-1" style="strokeColor=#8a7a68;fillColor=#d0c8b8;strokeWidth=1.5;" value="" vertex="1">
          <mxGeometry x="{fgx0:.1f}" y="{fgy0:.1f}" width="{fgw:.1f}" height="{fgh:.1f}" as="geometry" />
        </mxCell>''')
    cells.append(f'''        <mxCell id="v13-p2-far-gravel-lbl" parent="p2-1" style="text;html=1;strokeColor=none;fillColor=none;align=center;verticalAlign=top;whiteSpace=wrap;fontSize=6;fontColor=#6a5a48;" value="4in compacted #57 gravel pad (outside deck footprint)" vertex="1">
          <mxGeometry x="{fgx0:.1f}" y="{fgy0 + fgh:.1f}" width="{fgw:.1f}" height="20" as="geometry" />
        </mxCell>''')

    # ── Doubled 2×6 PT ribbon ──────────────────────────────────────────────────
    ribbon_x0 = dx(FAR_STEP_X_LEFT)
    ribbon_y0 = dy(RIBBON_Y0)
    ribbon_w  = FAR_STEP_LEN * SCALE
    ribbon_h  = RIBBON_T * SCALE
    cells.append(f'''        <mxCell id="v13-p2-far-ribbon" parent="p2-1" style="text;html=1;strokeColor=#2a5a2a;fillColor=#5a8a5a;align=center;verticalAlign=middle;whiteSpace=wrap;rounded=0;fontSize=6.5;fontColor=#ffffff;fontStyle=1;strokeWidth=2;" value="Doubled 2x6 PT SYP ribbon — lag-bolted to outer rim" vertex="1">
          <mxGeometry x="{ribbon_x0:.1f}" y="{ribbon_y0:.1f}" width="{ribbon_w:.1f}" height="{ribbon_h:.1f}" as="geometry" />
        </mxCell>''')

    # ── Two MoistureShield tread planks ───────────────────────────────────────
    tp_w = FAR_STEP_LEN * SCALE
    tp_h = PLANK_W * SCALE
    for i in range(2):
        tp_y0 = dy(TREAD_Y0 + i * (PLANK_W + PLANK_GAP))
        cells.append(f'''        <mxCell id="v13-p2-far-tread-{i}" parent="p2-1" style="strokeColor=#7a5030;fillColor=#c8a878;strokeWidth=1;" value="" vertex="1">
          <mxGeometry x="{ribbon_x0:.1f}" y="{tp_y0:.1f}" width="{tp_w:.1f}" height="{tp_h:.1f}" as="geometry" />
        </mxCell>''')

    # Tread label
    tread_lbl_y = dy((TREAD_Y0 + TREAD_Y0 + 2*PLANK_W + PLANK_GAP) / 2)
    tread_lbl_x = ribbon_x0 + ribbon_w / 2
    cells.append(f'''        <mxCell id="v13-p2-far-tread-lbl" parent="p2-1" style="text;html=1;strokeColor=none;fillColor=none;align=center;verticalAlign=middle;whiteSpace=wrap;fontSize=6.5;fontColor=#7a5030;fontStyle=1;" value="2x 5.4in MoistureShield Vision | 10.9in tread | 6in AG | Open riser | Tiger Claw TC-G or Cortex" vertex="1">
          <mxGeometry x="{ribbon_x0:.1f}" y="{tread_lbl_y - 12:.1f}" width="{tp_w:.1f}" height="24" as="geometry" />
        </mxCell>''')

    # ── 5 Precast deck blocks ──────────────────────────────────────────────────
    bsz = FAR_BLOCK_SZ * SCALE
    block_y0_px = dy(BLOCK_Y0)
    for idx, bx in enumerate(FAR_BLOCK_X):
        bx0 = dx(bx - FAR_BLOCK_SZ/2)
        cells.append(f'''        <mxCell id="v13-p2-far-block-{idx}" parent="p2-1" style="strokeColor=#444444;fillColor=#9a9a9a;strokeWidth=1.5;" value="" vertex="1">
          <mxGeometry x="{bx0:.1f}" y="{block_y0_px:.1f}" width="{bsz:.1f}" height="{bsz:.1f}" as="geometry" />
        </mxCell>''')

    # Block label
    blocks_mid_x = (dx(FAR_STEP_X_LEFT) + dx(FAR_STEP_X_RIGHT)) / 2
    cells.append(f'''        <mxCell id="v13-p2-far-block-lbl" parent="p2-1" style="text;html=1;strokeColor=none;fillColor=none;align=center;verticalAlign=top;whiteSpace=wrap;fontSize=6.5;fontColor=#444444;fontStyle=1;" value="5x precast concrete deck blocks (12in x 12in) @ ≈28in OC" vertex="1">
          <mxGeometry x="{ribbon_x0:.1f}" y="{block_y0_px + bsz:.1f}" width="{tp_w:.1f}" height="20" as="geometry" />
        </mxCell>''')

    # ── Seasonal heave callout ────────────────────────────────────────────────
    heave_x = dx(FAR_STEP_X_LEFT) - 150
    heave_y = dy(FAR_STEP_Y_ATTACH) + 5
    cells.append(f'''        <mxCell id="v13-p2-heave-callout" parent="p2-1" style="text;html=1;strokeColor=#cc4400;fillColor=#fff0e0;align=left;verticalAlign=top;whiteSpace=wrap;rounded=1;fontSize=7;fontColor=#8B0000;strokeWidth=1.8;" value="&lt;b&gt;⚠ SEASONAL HEAVE (Hollis): shallow blocks WILL heave ¼-½in per cycle.&lt;/b&gt;&lt;br/&gt;Decorative convenience step — NOT frost-depth founded.&lt;br/&gt;Homeowner has accepted this trade-off.&lt;br/&gt;Separate from left-edge stair; does not affect deck structure." vertex="1">
          <mxGeometry x="{heave_x:.1f}" y="{heave_y:.1f}" width="330" height="75" as="geometry" />
        </mxCell>''')

    # ── Far-step step callout box ─────────────────────────────────────────────
    fsc_x = heave_x
    fsc_y = heave_y - 115
    cells.append(f'''        <mxCell id="v13-p2-far-step-callout" parent="p2-1" style="text;html=1;strokeColor=#2244aa;fillColor=#e8eeff;align=left;verticalAlign=top;whiteSpace=wrap;rounded=0;fontSize=7;fontColor=#1a2a88;strokeWidth=1.5;" value="&lt;b&gt;FAR-EDGE STEP — v13 NEW&lt;/b&gt;&lt;br/&gt;11ft-9in along outer 23ft-6in edge&lt;br/&gt;Right corner to midpoint (x=23ft-6in to x=11ft-9in)&lt;br/&gt;Single 6in rise | 10.9in tread (2x 5.4in MoistureShield)&lt;br/&gt;Doubled 2x6 PT ribbon to outer rim face&lt;br/&gt;5x precast blocks @ ~28in OC on 4in #57 gravel&lt;br/&gt;Open riser | TC-G or Cortex fasteners" vertex="1">
          <mxGeometry x="{fsc_x:.1f}" y="{fsc_y:.1f}" width="330" height="110" as="geometry" />
        </mxCell>''')

    # ── Far-step side elevation inset ────────────────────────────────────────
    # Placed in left margin area
    EI_X   = dx(FAR_STEP_X_LEFT) - 155
    EI_Y   = dy(STEP_Y1) + 30
    EI_W   = 150
    EI_H   = 150
    cells.append(f'''        <mxCell id="v13-p2-far-elev-box" parent="p2-1" style="text;html=1;strokeColor=#2a6a2a;fillColor=#f8f8f0;align=center;verticalAlign=top;whiteSpace=wrap;rounded=0;fontSize=7;fontColor=#2a6a2a;strokeWidth=2;" value="&lt;b&gt;FAR-EDGE STEP — SIDE ELEVATION (v13)&lt;/b&gt;&lt;br/&gt;&lt;br/&gt;12in AG -------- (deck top)&lt;br/&gt;OPEN RISER (6in drop, no board)&lt;br/&gt;6in AG ---- [tread 10.9in deep] ----&lt;br/&gt;(grade / block top)&lt;br/&gt;[4in #57 gravel pad + precast blocks]&lt;br/&gt;&lt;br/&gt;1 riser @ 6in&lt;br/&gt;Doubled 2x6 PT ribbon to deck rim&lt;br/&gt;5x blocks @ ~28in OC" vertex="1">
          <mxGeometry x="{EI_X:.1f}" y="{EI_Y:.1f}" width="{EI_W}" height="{EI_H}" as="geometry" />
        </mxCell>''')

    return '\n'.join(cells)


# ─── Read current v12 drawio ──────────────────────────────────────────────────
import os
source_path = '/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/owner_inbox/deck_blueprint/deck_plan.drawio'
with open(source_path, 'r') as f:
    content = f.read()

# ─── VERSION SWEEP: v12 → v13 ────────────────────────────────────────────────

# Diagram IDs and names
content = re.sub(r'id="deck-plan-v12-p1"', 'id="deck-plan-v13-p1"', content)
content = re.sub(r'name="Page 1 — Framing Plan \(v12\)"', 'name="Page 1 — Framing Plan (v13)"', content)
content = re.sub(r'id="deck-plan-v12-p2"', 'id="deck-plan-v13-p2"', content)
content = re.sub(r'name="Page 2 — Decking Plan \(v12\)"', 'name="Page 2 — Decking Plan (v13)"', content)

# Version badge cells (both pages)
content = re.sub(
    r'(value="&lt;b&gt;)v12(&lt;/b&gt;&lt;br/&gt;&lt;font style=&quot;font-size: 11px;&quot;&gt;Page 1 of 2 — Framing&lt;/font&gt;")',
    r'\g<1>v13\g<2>',
    content
)
content = re.sub(
    r'(value="&lt;b&gt;)v12(&lt;/b&gt;&lt;br/&gt;&lt;font style=&quot;font-size: 11px;&quot;&gt;Page 2 of 2 — Decking&lt;/font&gt;")',
    r'\g<1>v13\g<2>',
    content
)

# Title blocks
content = re.sub(
    r'DECK PLAN v12 — PAGE 1: FRAMING PLAN',
    'DECK PLAN v13 — PAGE 1: FRAMING PLAN',
    content
)
content = re.sub(
    r'DECK PLAN v12 — PAGE 2: DECKING',
    'DECK PLAN v13 — PAGE 2: DECKING',
    content
)

# Callout references to v12 in step cells
content = re.sub(r'SINGLE STEP v12', 'SINGLE STEP v12 (unchanged)', content)
content = re.sub(r'SINGLE STEP — L EDGE \(v12\)', 'SINGLE STEP — L EDGE (v12, unchanged in v13)', content)

# Version notes in subtitle
content = content.replace(
    'v12: +single step L-edge 42in wide @ 6ft from house; open risers; gravel+paver landing',
    'v13: 9→6 piers (house-side row dropped); HU210-3 hangers at girder-ledger connections; far-edge step 11ft-9in right corner to midpoint'
)

# Update Page 1 pier legend entry (id=226): "9 total" → "6 total"
content = content.replace(
    '&lt;b&gt;Pylex 50 spiral pier (P1-P9) — 9 total (3 per girder)&lt;/b&gt;',
    '&lt;b&gt;Pylex 50 spiral pier (P2,P3,P5,P6,P8,P9) — 6 total in v13 (house-side row P1,P4,P7 dropped)&lt;/b&gt;'
)

# ─── HIDE house-side pier row (P1, P4, P7) and their hole circles ─────────────
# These cells have ids: p01, p04, p07, h01, h04, h07
# We hide them by setting visibility=0 or replacing their style with invisible
for cell_id in ['p01', 'p04', 'p07', 'h01', 'h04', 'h07']:
    # Add visible="0" attribute to the mxCell tag with this id
    # Pattern: <mxCell id="p01" parent="..." style="..." value="..." vertex="1">
    old_pattern = f'id="{cell_id}"'
    new_pattern = f'id="{cell_id}" visible="0"'
    content = content.replace(old_pattern, new_pattern)

# Also hide the row label at id=185 ("12in from house (P1,P4,P7)")
content = content.replace(
    'id="185" style=',
    'id="185" visible="0" style='
)

# ─── Update Page 2 pier note ──────────────────────────────────────────────────
# The "6 PIERS" callout text in render doesn't exist in drawio as a separate cell,
# but the pier legend on Page 1 (id=226) is already updated above.

# ─── Update FASTENER note on Page 1 (cell id=500) with v13 ledger spec ────────
old_fastener = ('Stair stringers: Simpson LSCZ stair stringer hangers (or equiv.) to outer face of L girder&lt;br/&gt;'
                'Stringer base: metal stringer-to-paver anchors; stringers bear on 12in x 12in precast pavers over #57 gravel&lt;br/&gt;'
                'Hardware: hot-dip galvanized or stainless throughout (ACQ-compatible)')
new_fastener = ('Stair stringers: Simpson LSCZ stair stringer hangers (or equiv.) to outer face of L girder&lt;br/&gt;'
                'Stringer base: metal stringer-to-paver anchors; stringers bear on 12in x 12in precast pavers over #57 gravel&lt;br/&gt;'
                'v13 Ledger: Simpson HU210-3 (or eq.) at each girder-ledger connection (3 places)&lt;br/&gt;'
                '½in HDG carriage bolts back-blocked from basement clustered at girder connections; '
                '½in HDG lag @ 18in OC two-row staggered between connections (IRC R507.9.1.3)&lt;br/&gt;'
                'Hardware: hot-dip galvanized or stainless throughout (ACQ-compatible)')
content = content.replace(old_fastener, new_fastener)

# If the v12 step callout still has old fastener text, use fallback replacement
old_fastener_fallback = 'Hardware: hot-dip galvanized or stainless throughout (ACQ-compatible)'
if old_fastener_fallback in content and 'v13 Ledger' not in content:
    content = content.replace(
        old_fastener_fallback,
        ('v13 Ledger: Simpson HU210-3 (or eq.) at each girder-ledger connection (3 places)&lt;br/&gt;'
         '½in HDG carriage bolts back-blocked from basement clustered at girder connections; '
         '½in HDG lag @ 18in OC two-row staggered between connections (IRC R507.9.1.3)&lt;br/&gt;'
         'Hardware: hot-dip galvanized or stainless throughout (ACQ-compatible)'),
        1  # replace only first occurrence
    )

# ─── Update legend on Page 2 (append far-edge step entries) ──────────────────
old_legend_step_end = ('Cut joints (red lines): PF and fascia terminate/resume at y=6ft-0in and y=9ft-6in&lt;br/&gt;'
                       'Open risers: no riser board; stringers visible; see side elevation inset')
new_legend_step_end = ('Cut joints (red lines): PF and fascia terminate/resume at y=6ft-0in and y=9ft-6in&lt;br/&gt;'
                       'Open risers: no riser board; stringers visible; see side elevation inset&lt;br/&gt;'
                       '&lt;br/&gt;&lt;b&gt;FAR-EDGE STEP (v13 NEW):&lt;/b&gt;&lt;br/&gt;'
                       'Ribbon (#5a8a5a green): doubled 2x6 PT SYP, lag-bolted to outer rim face&lt;br/&gt;'
                       'Tread (#c8a878): 2x 5.4in MoistureShield Vision, running ⊥ house, 10.9in depth, 6in AG&lt;br/&gt;'
                       'Blocks (#9a9a9a): 5x precast concrete deck blocks 12in x 12in @ ~28in OC&lt;br/&gt;'
                       'Gravel (#d0c8b8): 4in compacted #57 gravel pad (outside deck footprint)&lt;br/&gt;'
                       'Heave warning: ¼-½in seasonal heave expected and accepted by homeowner&lt;br/&gt;'
                       'Hangers (orange HU210-3): Simpson HU210-3 at 3 girder-ledger connections; '
                       '½in HDG bolts back-blocked from basement + IRC R507.9.1.3 lags between')
content = content.replace(old_legend_step_end, new_legend_step_end)

# ─── Inject v13 cells into Page 1 (before </root>) ───────────────────────────
page1_close = '      </root>\n    </mxGraphModel>\n  </diagram>\n  <diagram id="deck-plan-v13-p2"'
v13_cells_p1 = make_v13_cells_page1()
content = content.replace(
    page1_close,
    f'{v13_cells_p1}\n{page1_close}'
)

# ─── Inject v13 cells into Page 2 (before </root>) ───────────────────────────
page2_close = '      </root>\n    </mxGraphModel>\n  </diagram>\n</mxfile>'
v13_cells_p2 = make_v13_cells_page2()
content = content.replace(
    page2_close,
    f'{v13_cells_p2}\n{page2_close}'
)

# ─── Write output ─────────────────────────────────────────────────────────────
out_path = '/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/owner_inbox/deck_blueprint/deck_plan.drawio'
with open(out_path, 'w') as f:
    f.write(content)

print(f"Written: {out_path}")
print(f"File size: {len(content)} bytes")
print(f"v12→v13 sweep complete. Checking for stray 'v12' tokens...")

# Verify no stray v12 tokens remain
import re as re2
# Exclude the "SINGLE STEP v12 (unchanged)" intentional references and v12 render filename refs
stray = [line.strip() for line in content.split('\n')
         if 'v12' in line.lower()
         and 'unchanged' not in line.lower()
         and 'render_v12' not in line.lower()
         and 'gen_drawio_v12' not in line.lower()]
if stray:
    print(f"WARNING: {len(stray)} lines still contain 'v12':")
    for s in stray[:10]:
        print(f"  {s[:120]}")
else:
    print("OK: No stray v12 tokens found.")
