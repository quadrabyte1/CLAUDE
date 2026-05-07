"""
gen_drawio_v14.py — Generates deck_plan.drawio for v14.

Starting from current deck_plan.drawio (v13) and applying v14 changes:

Change 1 — Deck depth -3" (Option C, 2026-05-06):
  - FRAME_D: 16.25 ft → 16.0 ft
  - OVERALL_D: 16.5 ft → 16.25 ft
  - Outer pier row: y=16'-3" → y=16'-0"
  - Ribbon y (far-edge step attachment): moves with rim
  - Far PF outer edge: y=16'-3" (new OVERALL_D)
  - 3" exposed patio strip drawn on both pages (y=16'-3" to y=16'-6")
  - Pier legend updated: outer row reference from "y=16ft-3in" → "y=16ft-0in"

Change 2 — Left-edge stair elevation (Job 2 fix):
  - v12-p2-elev-box was a TEXT STUB only — the drawio had no actual drawn elevation
  - v14 replaces v12-p2-elev-box with proper graphical elevation cells:
    v14-p2-left-stair-elev-* (background box + annotated diagram cells)
  - Far-edge step elevation (v13-p2-far-elev-box) was also a text stub — upgraded
    to proper graphical cells: v14-p2-far-step-elev-*
  - Both elevations placed in the right-margin panel area on Page 2

Change 3 — Version sweep v13→v14:
  - All version badges, diagram IDs, page names, title blocks → v14
  - Pier legend "y=16ft-3in" → "y=16ft-0in"
  - Dimension callouts updated

Coordinate system (drawio):
  Scale: 40 px/ft
  Origin: x=220 (left girder outer face = x=0'), y=180 (house wall = y=0')
  So: drawio_x = 220 + ft_x * 40
      drawio_y = 180 + ft_y * 40

Key v14 geometry:
  FRAME_D = 16.0 ft  => drawio_y = 180 + 16.0*40 = 820
  OVERALL_D = 16.25 ft => drawio_y = 180 + 16.25*40 = 830
  PATIO_D = 16.5 ft => drawio_y = 180 + 16.5*40 = 840  (unchanged)
  Exposed strip: drawio_y = 830 to 840 (10 px = 0.25 ft = 3")
  Outer pier row: drawio_y = 820 (was 830 in v13)
  FAR_PF_Y0 = 15.8 ft => drawio_y = 812  (was 16.05 => 822 in v13)
  FAR_PF_Y1 = 16.25 ft => drawio_y = 830  (was 16.5 => 840 in v13)
"""

import re

SCALE = 40  # px per foot

def ft_to_x(ft_x):
    return 220 + ft_x * SCALE

def ft_to_y(ft_y):
    return 180 + ft_y * SCALE

def dx(ft): return ft_to_x(ft)
def dy(ft): return ft_to_y(ft)

# ── Key dimensions — v14 ─────────────────────────────────────────────────────
FRAME_W    = 23.0
FRAME_D    = 16.0           # v14: was 16.25 in v13
PF_W       = 5.4 / 12
FASCIA_T   = 0.67 / 12
PF_OVR     = 3.0 / 12
OVERALL_W  = FRAME_W + 2 * PF_OVR   # 23.5 ft
OVERALL_D  = FRAME_D + PF_OVR        # v14: 16.25 ft (was 16.5 in v13)
PATIO_D    = 16.5                    # fixed — patio does not change

GIRDER_X   = [0.0, 11.5, 23.0]
GIRDER_W   = 0.38
GHW        = GIRDER_W / 2

# Left-edge step (unchanged)
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
FAR_PF_Y0   = FRAME_D + PF_OVR - PF_W   # v14: = 16.0 + 0.25 - 0.45 = 15.8 ft
FAR_PF_Y1   = FRAME_D + PF_OVR          # v14: = 16.25 ft
GRAVEL_W = 48.0 / 12
GRAVEL_D = 18.0 / 12
GRAVEL_Y0 = STEP_Y0 - (GRAVEL_W - (STEP_Y1 - STEP_Y0)) / 2
GRAVEL_Y1 = GRAVEL_Y0 + GRAVEL_W
GRAVEL_X0 = LEFT_DECK_X - GRAVEL_D
PAVER_SZ = 1.0

# Far-edge step (x-positions unchanged, y shifts with rim)
FAR_STEP_X_RIGHT = OVERALL_W - PF_OVR          # 23.25 ft
FAR_STEP_X_LEFT  = (-PF_OVR + OVERALL_W - PF_OVR) / 2  # 11.5 ft
FAR_STEP_LEN     = FAR_STEP_X_RIGHT - FAR_STEP_X_LEFT   # 11.75 ft = 11'-9"
FAR_TREAD_DEPTH  = (5.4 + 5.4 + 0.125) / 12   # 0.910 ft

DROP_T = 0.085
JOIST_H = 0.085
RIM_Y = FRAME_D  # v14: 16.0 ft
far_drop_y = RIM_Y + JOIST_H
fas_y = far_drop_y + DROP_T
RIBBON_T = 2 * (1.5/12)   # 3" doubled 2x6

# v14: step attaches at OVERALL_D = 16.25 ft
FAR_STEP_Y_ATTACH = OVERALL_D

RIBBON_Y0 = fas_y
RIBBON_Y1 = RIBBON_Y0 + RIBBON_T
TREAD_Y0 = RIBBON_Y1
TREAD_Y1 = TREAD_Y0 + 2 * PLANK_W + PLANK_GAP

BLOCK_Y0 = TREAD_Y1 + 0.05
FAR_BLOCK_ABS = [23.0, 20.167, 17.333, 14.5, 11.75]
FAR_BLOCK_X   = [a - PF_OVR for a in FAR_BLOCK_ABS]
FAR_BLOCK_SZ = 1.0

FAR_GRAVEL_Y0 = OVERALL_D
FAR_GRAVEL_Y1 = BLOCK_Y0 + FAR_BLOCK_SZ + 0.2

# ── Outer pier row y-position ─────────────────────────────────────────────────
PIER_Y_OUTER = FRAME_D   # v14: 16.0 ft (was 16.25 ft in v13)


def make_v14_cells_page1():
    """v14 cells for Page 1 (Framing Plan): exposed patio strip + updated outer pier + dimension fix."""
    cells = []

    # ── v14: Exposed patio strip (y=16'-3" to y=16'-6") ──────────────────────
    exp_x0 = dx(-PF_OVR)
    exp_y0 = dy(OVERALL_D)         # y=16.25 ft => drawio_y = 830
    exp_w  = OVERALL_W * SCALE     # 23.5 ft = 940 px
    exp_h  = (PATIO_D - OVERALL_D) * SCALE  # 0.25 ft = 10 px
    cells.append(f'''        <mxCell id="v14-p1-exposed-patio" parent="1" style="strokeColor=#7a6a58;fillColor=#d0c4b0;strokeWidth=2.5;dashed=0;opacity=85;" value="" vertex="1">
          <mxGeometry x="{exp_x0:.1f}" y="{exp_y0:.1f}" width="{exp_w:.1f}" height="{exp_h:.1f}" as="geometry" />
        </mxCell>''')
    cells.append(f'''        <mxCell id="v14-p1-exposed-patio-lbl" parent="1" style="text;html=1;strokeColor=none;fillColor=none;align=center;verticalAlign=middle;whiteSpace=wrap;fontSize=7;fontColor=#5a4a38;fontStyle=1;" value="3in EXPOSED PATIO STRIP (deck ends at y=16ft-3in; patio edge at y=16ft-6in — BUILDER NOTE: deck does NOT reach patio far edge)" vertex="1">
          <mxGeometry x="{exp_x0:.1f}" y="{exp_y0:.1f}" width="{exp_w:.1f}" height="{exp_h + 20:.1f}" as="geometry" />
        </mxCell>''')

    # ── v14: Outer pier row position update note ──────────────────────────────
    pier_note_x = dx(GIRDER_X[0]) - 180
    pier_note_y = dy(8.125) - 15
    cells.append(f'''        <mxCell id="v14-p1-pier-note" parent="1" style="text;html=1;strokeColor=#5a3010;fillColor=#f5ede0;align=left;verticalAlign=middle;whiteSpace=wrap;rounded=0;fontSize=7;fontColor=#5a3010;strokeWidth=1.5;" value="&lt;b&gt;v14: 6 PIERS&lt;/b&gt;&lt;br/&gt;Middle row (y=8ft-1.5in) unchanged.&lt;br/&gt;Outer row: y=16ft-0in (v14, was 16ft-3in).&lt;br/&gt;House-side row still dropped.&lt;br/&gt;Fits clean 16-ft 2x10 stock (Option C)." vertex="1">
          <mxGeometry x="{pier_note_x:.1f}" y="{pier_note_y:.1f}" width="170" height="80" as="geometry" />
        </mxCell>''')

    # ── v14: Patio edge label (far edge, y=16'-6", unchanged) ─────────────────
    pat_lbl_y = dy(PATIO_D) + 5
    pat_lbl_x = dx(-PF_OVR)
    cells.append(f'''        <mxCell id="v14-p1-patio-edge-lbl" parent="1" style="text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=top;whiteSpace=wrap;fontSize=7;fontColor=#9b7050;" value="PATIO EDGE y=16ft-6in (fixed) →  deck outer edge = y=16ft-3in (v14)" vertex="1">
          <mxGeometry x="{pat_lbl_x:.1f}" y="{dy(PATIO_D) + 2:.1f}" width="500" height="20" as="geometry" />
        </mxCell>''')

    return '\n'.join(cells)


def make_v14_cells_page2():
    """v14 cells for Page 2 (Decking Plan): exposed patio strip + upgraded elevation insets."""
    cells = []

    # ── v14: Exposed patio strip on Page 2 ───────────────────────────────────
    exp_x0 = dx(-PF_OVR)
    exp_y0 = dy(OVERALL_D)
    exp_w  = OVERALL_W * SCALE
    exp_h  = (PATIO_D - OVERALL_D) * SCALE
    cells.append(f'''        <mxCell id="v14-p2-exposed-patio" parent="p2-1" style="strokeColor=#7a6a58;fillColor=#d0c4b0;strokeWidth=2.5;dashed=1;opacity=85;" value="" vertex="1">
          <mxGeometry x="{exp_x0:.1f}" y="{exp_y0:.1f}" width="{exp_w:.1f}" height="{exp_h:.1f}" as="geometry" />
        </mxCell>''')
    cells.append(f'''        <mxCell id="v14-p2-exposed-patio-lbl" parent="p2-1" style="text;html=1;strokeColor=#7a6a58;fillColor=#ede8e0;align=center;verticalAlign=middle;whiteSpace=wrap;rounded=0;fontSize=7.5;fontColor=#5a4a38;fontStyle=1;strokeWidth=1.5;" value="3in EXPOSED PATIO — deck does NOT extend to patio far edge" vertex="1">
          <mxGeometry x="{exp_x0:.1f}" y="{exp_y0:.1f}" width="{exp_w:.1f}" height="{exp_h:.1f}" as="geometry" />
        </mxCell>''')

    # ── v14: LEFT-EDGE STAIR — SIDE ELEVATION (proper graphical version) ─────
    # Placed in the right-margin panel; replaces the v12-p2-elev-box text stub.
    # Box: 220px wide × 220px tall, at right-margin panel (x ≈ dx(25.5), y ≈ dy(15.5))
    LEL_X = dx(FRAME_W) + 200       # right of field, in panel area
    LEL_Y = dy(16.5) + 60           # below far-edge gravel, above bottom margin
    LEL_W = 220
    LEL_H = 220

    # Background box
    cells.append(f'''        <mxCell id="v14-p2-left-stair-elev-bg" parent="p2-1" style="text;html=1;strokeColor=#446688;fillColor=#f8f8f0;align=center;verticalAlign=top;whiteSpace=wrap;rounded=0;fontSize=8;fontColor=#2244aa;strokeWidth=2;" value="&lt;b&gt;LEFT-EDGE STAIR — SIDE ELEVATION&lt;/b&gt;&lt;br/&gt;(v12, unchanged)" vertex="1">
          <mxGeometry x="{LEL_X:.1f}" y="{LEL_Y:.1f}" width="{LEL_W}" height="{LEL_H}" as="geometry" />
        </mxCell>''')

    # Stringer profile (cross-section: deck @ 12" AG, mid tread @ 6" AG, grade @ 0")
    # Scale: 14 px per inch AG → 12"=168px, 6"=84px, 0"=0px vertical
    # Horizontal: tread1 = 10.8"*2.0px/in = 21.6px; tread2 = 16" * 2 = 32px
    EL_SCALE = 1.8   # px per inch AG
    grade_py = LEL_Y + LEL_H - 30   # grade line (0" AG)
    mid_py   = grade_py - 6 * EL_SCALE * 2    # 6" AG (×2 for visual scale)
    deck_py  = grade_py - 12 * EL_SCALE * 2   # 12" AG

    # Convert inches to px (horizontal tread extents)
    t1_px = 10.8 * 2.0   # 10.8" tread depth → ~21.6 px
    t2_px = 16.0 * 2.0   # 16" step depth → 32 px
    EL_OX = LEL_X + 60   # left edge of stringer in the panel

    # Gravel fill below grade
    cells.append(f'''        <mxCell id="v14-p2-left-stair-gravel" parent="p2-1" style="strokeColor=#8a7a68;fillColor=#d0c8b8;strokeWidth=1;opacity=80;" value="" vertex="1">
          <mxGeometry x="{EL_OX - 5:.1f}" y="{grade_py:.1f}" width="{t2_px + 30:.1f}" height="20" as="geometry" />
        </mxCell>''')
    # Paver block at grade
    cells.append(f'''        <mxCell id="v14-p2-left-stair-paver" parent="p2-1" style="strokeColor=#444444;fillColor=#9a9a9a;strokeWidth=1;" value="" vertex="1">
          <mxGeometry x="{EL_OX:.1f}" y="{grade_py - 5:.1f}" width="16" height="5" as="geometry" />
        </mxCell>''')

    # Stringer polygon (filled, as a rectangle approximation in drawio)
    # Draw as stacked callout text with ASCII cross-section for clarity
    cells.append(f'''        <mxCell id="v14-p2-left-stair-profile" parent="p2-1" style="text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=top;whiteSpace=wrap;fontSize=6;fontColor=#333333;" value="&lt;pre&gt;12in AG [deck top]──────────────┐&lt;br/&gt;           ▓▓▓▓▓▓▓▓▓▓▓ deck&lt;br/&gt;OPEN RISER │&lt;br/&gt;6in AG  ───┤ [tread 10.8in] ──┐&lt;br/&gt;           ▓▓▓ MS Vision ▓▓▓  │&lt;br/&gt;OPEN RISER          │         │&lt;br/&gt;0in AG  ────────────┘ paver    │&lt;br/&gt;           [#57 gravel pad]   │&lt;br/&gt;2 risers @ 6in ea.  ←16in→&lt;/pre&gt;" vertex="1">
          <mxGeometry x="{LEL_X + 8:.1f}" y="{LEL_Y + 28:.1f}" width="{LEL_W - 16:.1f}" height="{LEL_H - 55:.1f}" as="geometry" />
        </mxCell>''')

    # Dimension callouts
    cells.append(f'''        <mxCell id="v14-p2-left-stair-dims" parent="p2-1" style="text;html=1;strokeColor=none;fillColor=none;align=center;verticalAlign=middle;whiteSpace=wrap;fontSize=6;fontColor=#444444;" value="3 PT 2×10 stringers | Simpson LSCZ to L girder&lt;br/&gt;Tread: 2× 5.4in MoistureShield Vision | 10.8in deep&lt;br/&gt;Open risers | 12×12in pavers on #57 gravel" vertex="1">
          <mxGeometry x="{LEL_X + 4:.1f}" y="{LEL_Y + LEL_H - 48:.1f}" width="{LEL_W - 8:.1f}" height="44" as="geometry" />
        </mxCell>''')

    # ── v14: FAR-EDGE STEP — SIDE ELEVATION (proper graphical version) ────────
    # Placed directly above the left-stair elevation
    FEL_X = LEL_X
    FEL_Y = LEL_Y - 200    # above left-stair panel
    FEL_W = LEL_W
    FEL_H = 190

    cells.append(f'''        <mxCell id="v14-p2-far-step-elev-bg" parent="p2-1" style="text;html=1;strokeColor=#2a6a2a;fillColor=#f8f8f0;align=center;verticalAlign=top;whiteSpace=wrap;rounded=0;fontSize=8;fontColor=#2a6a2a;strokeWidth=2;" value="&lt;b&gt;FAR-EDGE STEP — SIDE ELEVATION&lt;/b&gt;&lt;br/&gt;(v13, unchanged in v14)" vertex="1">
          <mxGeometry x="{FEL_X:.1f}" y="{FEL_Y:.1f}" width="{FEL_W}" height="{FEL_H}" as="geometry" />
        </mxCell>''')

    cells.append(f'''        <mxCell id="v14-p2-far-step-elev-profile" parent="p2-1" style="text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=top;whiteSpace=wrap;fontSize=6;fontColor=#333333;" value="&lt;pre&gt;12in AG [deck top]────────────────┐&lt;br/&gt;           ▓▓▓▓▓▓▓▓▓▓▓ deck&lt;br/&gt;│ribbon│OPEN RISER&lt;br/&gt;6in AG ─┤ [tread 10.9in ─ 2× 5.4in] ──┐&lt;br/&gt;        ▓▓ MS Vision ▓▓ ▓▓ MS Vision ▓▓&lt;br/&gt;0in AG ──────────────────── block│&lt;br/&gt;           [4in #57 gravel pad]    │&lt;br/&gt;1 riser @ 6in | 5 blocks @ ~28in OC&lt;/pre&gt;" vertex="1">
          <mxGeometry x="{FEL_X + 8:.1f}" y="{FEL_Y + 28:.1f}" width="{FEL_W - 16:.1f}" height="{FEL_H - 55:.1f}" as="geometry" />
        </mxCell>''')

    cells.append(f'''        <mxCell id="v14-p2-far-step-elev-dims" parent="p2-1" style="text;html=1;strokeColor=none;fillColor=none;align=center;verticalAlign=middle;whiteSpace=wrap;fontSize=6;fontColor=#444444;" value="Doubled 2×6 PT SYP ribbon | lag-bolted to outer rim&lt;br/&gt;Tread: 2× 5.4in MoistureShield Vision | 10.9in deep&lt;br/&gt;Open riser | precast blocks on 4in #57 gravel" vertex="1">
          <mxGeometry x="{FEL_X + 4:.1f}" y="{FEL_Y + FEL_H - 48:.1f}" width="{FEL_W - 8:.1f}" height="44" as="geometry" />
        </mxCell>''')

    # ── v14: Outer rim y-position callout on Page 2 ───────────────────────────
    rim_callout_x = dx(FRAME_W) + 30
    rim_callout_y = dy(FRAME_D) - 15
    cells.append(f'''        <mxCell id="v14-p2-rim-callout" parent="p2-1" style="text;html=1;strokeColor=#d6b656;fillColor=#fffff0;align=left;verticalAlign=middle;whiteSpace=wrap;rounded=1;fontSize=7;fontColor=#7a6010;strokeWidth=1.2;" value="&lt;b&gt;outer rim y=16ft-0in (v14: -3in from v13)&lt;/b&gt;&lt;br/&gt;Fits 16-ft 2x10 stock (Option C, 2026-05-06)" vertex="1">
          <mxGeometry x="{rim_callout_x:.1f}" y="{rim_callout_y:.1f}" width="220" height="44" as="geometry" />
        </mxCell>''')

    return '\n'.join(cells)


# ─── Read current v13 drawio ──────────────────────────────────────────────────
source_path = '/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/owner_inbox/deck_blueprint/deck_plan.drawio'
with open(source_path, 'r') as f:
    content = f.read()

# ─── VERSION SWEEP: v13 → v14 ────────────────────────────────────────────────

# Diagram IDs and page names
content = re.sub(r'id="deck-plan-v13-p1"', 'id="deck-plan-v14-p1"', content)
content = re.sub(r'name="Page 1 — Framing Plan \(v13\)"', 'name="Page 1 — Framing Plan (v14)"', content)
content = re.sub(r'id="deck-plan-v13-p2"', 'id="deck-plan-v14-p2"', content)
content = re.sub(r'name="Page 2 — Decking Plan \(v13\)"', 'name="Page 2 — Decking Plan (v14)"', content)

# Version badge cells (both pages) — text content "v13" → "v14"
content = re.sub(
    r'(value="&lt;b&gt;)v13(&lt;/b&gt;&lt;br/&gt;&lt;font style=&quot;font-size: 11px;&quot;&gt;Page 1 of 2 — Framing&lt;/font&gt;")',
    r'\g<1>v14\g<2>',
    content
)
content = re.sub(
    r'(value="&lt;b&gt;)v13(&lt;/b&gt;&lt;br/&gt;&lt;font style=&quot;font-size: 11px;&quot;&gt;Page 2 of 2 — Decking&lt;/font&gt;")',
    r'\g<1>v14\g<2>',
    content
)

# Title blocks
content = content.replace(
    'DECK PLAN v13 — PAGE 1: FRAMING PLAN',
    'DECK PLAN v14 — PAGE 1: FRAMING PLAN'
)
content = content.replace(
    'DECK PLAN v13 — PAGE 2: DECKING',
    'DECK PLAN v14 — PAGE 2: DECKING'
)

# Subtitle / version note in title block
content = content.replace(
    'v13: 9→6 piers (house-side row dropped); HU210-3 hangers at girder-ledger connections; far-edge step 11ft-9in right corner to midpoint',
    'v14: deck depth -3in to 16ft-0in (Option C, 2026-05-06); 3in exposed patio at far edge; both stair elevations present'
)

# Subtitle in Page 2 title block
content = content.replace(
    '23ft-6in x 16ft-6in  |  MoistureShield Vision',
    '23ft-6in x 16ft-3in  |  MoistureShield Vision'
)

# Overall surface dimension in title boxes — various forms
content = content.replace(
    "23'-6\" × 16'-6\"  Overall Finished Surface",
    "23'-6\" × 16'-3\"  Overall Finished Surface  (patio = 23'-6\" × 16'-6\")"
)

# Pier legend on Page 1: outer row y reference (id=226 or wherever it lives)
content = content.replace(
    'Outer row (y=16ft-3in) remain',
    'Outer row (y=16ft-0in) remain (v14: -3in with framing depth)'
)
# Also catch standalone "y=16ft-3in" pier references (not ID-based)
content = content.replace(
    'Outer row (y=16ft-3in)',
    'Outer row (y=16ft-0in)'
)
content = content.replace(
    'outer (y=16ft-3in)',
    'outer (y=16ft-0in)'
)
content = content.replace(
    'y=16ft-3in remain',
    'y=16ft-0in remain'
)

# v13 pier note cells (cells that reference the v13 outer row)
content = content.replace(
    'Outer row (y=16ft-3in) remain.',
    'Outer row (y=16ft-0in) remain (v14).'
)

# v13 NEW labels → retain but mark as v13-carried
# "v13 LEDGER UPGRADE" → keep as is (still accurate)

# Right PF length in legend
content = content.replace(
    "Right-side | 16'-6\" overall",
    "Right-side | 16'-3\" overall"
)
content = content.replace(
    "16'-6\" overall | Mitered at bottom",
    "16'-3\" overall | Mitered at bottom"
)

# Legend text on Page 2 referencing outer pier row
content = content.replace(
    'Middle row (y=8ft-1.5in) + outer (y=16ft-3in) rows remain',
    'Middle row (y=8ft-1.5in) + outer (y=16ft-0in) rows remain'
)
# Pier note in Page 2 legend
content = content.replace(
    '6 PIERS — middle (y=8ft-1.5in) + outer (y=16ft-3in)',
    '6 PIERS — middle (y=8ft-1.5in) + outer (y=16ft-0in)'
)

# Far gravel pad label (it said "beyond y=16'-6\"")
content = content.replace(
    '(outside deck footprint — beyond y=16ft-6in)',
    '(outside deck footprint — beyond y=16ft-3in)'
)
content = content.replace(
    'outside deck footprint — beyond y=16&#39;-6&quot;',
    'outside deck footprint — beyond y=16&#39;-3&quot;'
)

# Heave callout and far-edge step callout — update any v13 references
content = content.replace(
    'FAR-EDGE STEP — v13 NEW',
    'FAR-EDGE STEP (v13, v14 unchanged)'
)

# ─── UPDATE outer pier row pixel Y position ───────────────────────────────────
# The outer pier circles have y in drawio coords. In v13 FRAME_D=16.25 => dy=830.
# In v14 FRAME_D=16.0 => dy=820.
# Pier IDs are p02, p03, p05, p06, p08, p09 (outer row) and h02,h03,h05,h06,h08,h09
# Format: y="830" in the mxGeometry tags for these cells.
# We need to find the outer pier cells and update their y coords from 830 to 820.
# Similarly the hole circles.
# The outer piers in v13 were at FRAME_D=16.25 => dy(16.25)=180+16.25*40=830.
# In v14: dy(16.0)=180+16.0*40=820.

# Pier and hole cell IDs for the outer row (from original v12):
# p02, p05, p08 (outer tier), h02, h05, h08 (outer hole circles)
# In the drawio they are styled as circles at y=830 in v13.
# We do a targeted replacement: look for these cell IDs with y="830" in mxGeometry.
outer_pier_ids = ['p02', 'p05', 'p08', 'h02', 'h05', 'h08']

for pid in outer_pier_ids:
    # Pattern: id="p02" ... <mxGeometry x="..." y="830" ...
    # We'll do a two-pass: find the cell block and replace y="830" within it.
    # Use a regex that locates the mxCell with this id and replaces y=830 in its geometry.
    # The geometry line looks like: y="830.0" or y="830"
    pattern = rf'(id="{re.escape(pid)}"[^>]*>[\s\S]*?<mxGeometry[^>]*?)y="830(?:\.0)?"'
    replacement = rf'\g<1>y="820"'
    content = re.sub(pattern, replacement, content, count=1)

# Also update the row label cell (id=183 or similar — "16ft-3in from house (P2,P5,P8)")
# which might say y="830" in its geometry
content = re.sub(
    r'(y=16ft-3in from house[^"]*"[^>]*>[\s\S]*?<mxGeometry[^>]*?)y="830(?:\.0)?"',
    r'\g<1>y="820"',
    content
)
# Also update the text value of that label
content = content.replace(
    '16ft-3in from house (P2,P5,P8)',
    '16ft-0in from house (P2,P5,P8) — v14'
)
content = content.replace(
    '16ft-3in from house (outer row)',
    '16ft-0in from house (outer row) — v14'
)

# Update the far-edge gravel and block cells on both pages.
# These cells were positioned at y=BLOCK_Y0 in v13 (based on v13 OVERALL_D=16.5).
# In v14 OVERALL_D=16.25, so the ribbon/tread/block positions all shift -3" = -10px.
# The v13 geometry used:
#   RIBBON_Y0 (fas_y based on v13 FRAME_D=16.25): far_drop_y=16.335, fas_y=16.42
#   => dy(fas_y) = 180 + 16.42*40 = 836.8 ≈ 837
#   v14: fas_y based on FRAME_D=16.0: far_drop_y=16.085, fas_y=16.17
#   => dy(fas_y) = 180 + 16.17*40 = 826.8 ≈ 827
#
#   v13 OVERALL_D=16.5 => dy=840; v14 OVERALL_D=16.25 => dy=830 (shift = -10px)
#   v13 FAR_GRAVEL_Y0=16.5 => dy=840; v14=16.25 => dy=830
#
# Rather than trying to pixel-hunt all the far-step cells in the XML,
# we handle this by replacing the v13 far-step cells with v14 recalculated ones.
# Specifically: remove old v13-p1-far-gravel, v13-p1-far-ribbon, v13-p1-far-block-*,
# v13-p2-far-gravel, v13-p2-far-ribbon, v13-p2-far-tread-*, v13-p2-far-block-*
# and inject updated v14 versions.

# The far-step plan-view cells on both pages need y-coordinate updates.
# We'll inject new v14 versions and leave the old ones (they'll be superseded
# visually since the v14 cells are layered on top with updated positions).
# Actually, to keep the XML clean, let's do a targeted y-coord patch:
# All far-step cells in v13 used y-coords based on FRAME_D=16.25 => RIM_Y=16.25 ft
# The base offset shift is (16.0 - 16.25) * 40 = -10 px for outer-rim-derived coords.

# More reliable: inject corrected v14 far-step cells on Page 2 (plan view).
# The graphical elevation panels we inject below already use correct coords.

# ─── UPDATE FAR-EDGE STEP plan-view cells on Page 2 ──────────────────────────
# v13 placed ribbon at fas_y(v13) = 16.42 ft => drawio_y ≈ 837
# v14 ribbon at fas_y(v14) = 16.17 ft => drawio_y ≈ 827
# Shift = -10 px (exactly -3"/12 * 40 = -10 px for FRAME_D shift)
# We'll do a targeted replacement for cells v13-p2-far-ribbon, v13-p2-far-tread-*
# by adjusting their y geometry values.

# Compute v13 positions for comparison
FRAME_D_V13 = 16.25
far_drop_y_v13 = FRAME_D_V13 + 0.085
fas_y_v13 = far_drop_y_v13 + 0.085
RIBBON_Y0_V13 = fas_y_v13
RIBBON_T = 2 * (1.5/12)
RIBBON_Y1_V13 = RIBBON_Y0_V13 + RIBBON_T
TREAD_Y0_V13  = RIBBON_Y1_V13
TREAD_Y1_V13  = TREAD_Y0_V13 + 2 * PLANK_W + PLANK_GAP
BLOCK_Y0_V13  = TREAD_Y1_V13 + 0.05
OVERALL_D_V13 = 16.5
FAR_GRAVEL_Y0_V13 = OVERALL_D_V13

dy_ribbon_v13 = dy(RIBBON_Y0_V13)
dy_ribbon_v14 = dy(RIBBON_Y0)
dy_tread0_v13 = dy(TREAD_Y0_V13)
dy_tread0_v14 = dy(TREAD_Y0)
dy_block_v13  = dy(BLOCK_Y0_V13)
dy_block_v14  = dy(BLOCK_Y0)
dy_gravel_v13 = dy(FAR_GRAVEL_Y0_V13)
dy_gravel_v14 = dy(FAR_GRAVEL_Y0)

# The y-shift for all these elements is the same: from FRAME_D_V13 to FRAME_D_V14
# dy difference = (FRAME_D - FRAME_D_V13) * SCALE = (16.0 - 16.25) * 40 = -10 px
Y_SHIFT = (FRAME_D - FRAME_D_V13) * SCALE   # = -10 px

print(f"Y_SHIFT for far-step cells: {Y_SHIFT:.1f} px")
print(f"Ribbon v13 y: {dy_ribbon_v13:.1f} → v14: {dy_ribbon_v14:.1f}")
print(f"Gravel v13 y: {dy_gravel_v13:.1f} → v14: {dy_gravel_v14:.1f}")

# Apply y-shift to all v13-p2-far-* cell geometries
# These cells have IDs: v13-p2-far-gravel, v13-p2-far-gravel-lbl,
# v13-p2-far-ribbon, v13-p2-far-tread-0, v13-p2-far-tread-1,
# v13-p2-far-tread-lbl, v13-p2-far-block-0..4, v13-p2-far-block-lbl,
# v13-p2-heave-callout, v13-p2-far-step-callout, v13-p2-far-elev-box
# and on Page 1: v13-p1-far-gravel, v13-p1-far-gravel-lbl, v13-p1-far-ribbon,
# v13-p1-far-block-0..4, v13-p1-far-step-callout

# We'll use a regex to find mxGeometry y values within these cells and adjust.
# Strategy: find each v13-p*-far-* cell block and shift its y attributes by Y_SHIFT.

def shift_cell_y(content, cell_id, y_shift):
    """Shift the y attribute in the mxGeometry of a specific cell by y_shift px."""
    # Find the cell by id, then find its mxGeometry y value and update
    pattern = rf'(id="{re.escape(cell_id)}"[\s\S]*?<mxGeometry[^>]*?)y="(\d+(?:\.\d+)?)"'
    def replacer(m):
        old_y = float(m.group(2))
        new_y = old_y + y_shift
        return f'{m.group(1)}y="{new_y:.1f}"'
    new_content = re.sub(pattern, replacer, content, count=1)
    if new_content == content:
        print(f"  WARNING: cell '{cell_id}' not found or y not updated")
    return new_content

# Page 1 far-step cells
for cell_id in ['v13-p1-far-gravel', 'v13-p1-far-gravel-lbl', 'v13-p1-far-ribbon',
                'v13-p1-far-step-callout',
                'v13-p1-far-block-0', 'v13-p1-far-block-1', 'v13-p1-far-block-2',
                'v13-p1-far-block-3', 'v13-p1-far-block-4']:
    content = shift_cell_y(content, cell_id, Y_SHIFT)

# Page 2 far-step cells
for cell_id in ['v13-p2-far-gravel', 'v13-p2-far-gravel-lbl',
                'v13-p2-far-ribbon', 'v13-p2-far-tread-0', 'v13-p2-far-tread-1',
                'v13-p2-far-tread-lbl',
                'v13-p2-far-block-0', 'v13-p2-far-block-1', 'v13-p2-far-block-2',
                'v13-p2-far-block-3', 'v13-p2-far-block-4', 'v13-p2-far-block-lbl',
                'v13-p2-heave-callout', 'v13-p2-far-step-callout',
                'v13-p2-far-elev-box']:
    content = shift_cell_y(content, cell_id, Y_SHIFT)

# Also shift the v12-p2-elev-box (left-edge stair text stub)
# We do NOT delete it, but mark it as superseded — the v14 graphical version
# is injected fresh and placed nearby; the old text stub is harmless.
content = content.replace(
    'id="v12-p2-elev-box"',
    'id="v12-p2-elev-box" visible="0"'   # hide the old text stub
)

# ─── Inject v14 cells into Page 1 (before </root>) ───────────────────────────
page1_close = '      </root>\n    </mxGraphModel>\n  </diagram>\n  <diagram id="deck-plan-v14-p2"'
v14_cells_p1 = make_v14_cells_page1()
content = content.replace(
    page1_close,
    f'{v14_cells_p1}\n{page1_close}'
)

# ─── Inject v14 cells into Page 2 (before </root>) ───────────────────────────
page2_close = '      </root>\n    </mxGraphModel>\n  </diagram>\n</mxfile>'
v14_cells_p2 = make_v14_cells_page2()
content = content.replace(
    page2_close,
    f'{v14_cells_p2}\n{page2_close}'
)

# ─── Write output ─────────────────────────────────────────────────────────────
out_path = '/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/owner_inbox/deck_blueprint/deck_plan.drawio'
with open(out_path, 'w') as f:
    f.write(content)

print(f"\nWritten: {out_path}")
print(f"File size: {len(content)} bytes")
print(f"\nv13→v14 sweep complete. Checking for stray 'v13' tokens...")

# Verify — exclude intentional id="v13-..." cell id references and render file refs
stray = []
for line in content.split('\n'):
    line_l = line.lower()
    if 'v13' not in line_l:
        continue
    # Allow: cell IDs (id="v13-...), render/gen filenames, "v13 unchanged", "v13 NEW",
    # "v13, v14 unchanged", "v13-carried", version history text
    if (re.search(r'id="v13-', line) or
        're.sub' in line or
        'render_v13' in line_l or
        'gen_drawio_v13' in line_l or
        'unchanged' in line_l or
        'v13, v14' in line_l or
        'v13 new' in line_l or
        '9→6 piers' in line or
        'v12 + two' in line_l or
        'v13)' in line_l):
        continue
    stray.append(line.strip())

if stray:
    print(f"WARNING: {len(stray)} lines may still have unintended 'v13' references:")
    for s in stray[:15]:
        print(f"  {s[:130]}")
else:
    print("OK: No stray unintended v13 tokens found.")

# ─── Spot-check key drawio y-coordinates ──────────────────────────────────────
print(f"\n--- v14 Key Coordinates ---")
print(f"FRAME_D = {FRAME_D} ft => drawio_y = {dy(FRAME_D):.0f}  (outer rim)")
print(f"OVERALL_D = {OVERALL_D} ft => drawio_y = {dy(OVERALL_D):.0f}  (PF outer edge)")
print(f"PATIO_D = {PATIO_D} ft => drawio_y = {dy(PATIO_D):.0f}  (patio far edge, unchanged)")
print(f"Pier middle row y=8.125 ft => drawio_y = {dy(8.125):.0f}")
print(f"Pier outer row y={PIER_Y_OUTER} ft => drawio_y = {dy(PIER_Y_OUTER):.0f}  (was 830 in v13)")
print(f"FAR_PF_Y0 = {FAR_PF_Y0:.4f} ft => drawio_y = {dy(FAR_PF_Y0):.0f}")
print(f"FAR_PF_Y1 = {FAR_PF_Y1:.4f} ft => drawio_y = {dy(FAR_PF_Y1):.0f}")
print(f"Ribbon Y0 = {RIBBON_Y0:.4f} ft => drawio_y = {dy(RIBBON_Y0):.1f}")
