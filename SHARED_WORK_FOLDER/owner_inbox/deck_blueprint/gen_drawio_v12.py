"""
gen_drawio_v12.py — Generates deck_plan.drawio for v12.

Coordinate system (drawio):
  Scale: 40 px/ft
  Origin: x=220 (left girder outer face = x=0'), y=180 (house wall = y=0')
  So: drawio_x = 220 + ft_x * 40
      drawio_y = 180 + ft_y * 40

Step dimensions:
  STEP_Y0 = 6.0' => drawio_y = 180 + 240 = 420
  STEP_Y1 = 9.5' => drawio_y = 180 + 380 = 560
  Step width = 42" = 3.5' = 140 px
  Step depth = 16" = 1.333' = 53.3 px (from left deck outer edge leftward)

Left deck outer edge (outer face of fascia):
  left fascia x = 205 (from existing file: fascia id=151 at x=205)
  Left PF inner edge: x=189.2 (from existing: p2-2109)
  Left PF outer edge: x=189.2 - 18.3 = 170.9 (left edge of PF band)

  In ft: FASCIA_T = 0.67" = 0.0558 ft => 2.23 px
         PF_OVR = 3" = 0.25 ft => 10 px
  Left fascia outer face = 220 - PF_OVR * 40 - FASCIA_T * 40
                         = 220 - 10 - 2.23 = 207.77 => ~205 (matches existing!)

  LEFT_DECK_X (outer face of fascia, ft) = -PF_OVR - FASCIA_T = -0.25 - 0.0558 = -0.3058 ft
  In drawio px: 220 + (-0.3058)*40 = 220 - 12.23 = 207.77 => 208 px

  STEP_X_OUT (leftmost edge of step) = LEFT_DECK_X - STEP_DEPTH = -0.3058 - 16/12 = -0.3058 - 1.333 = -1.639 ft
  In drawio px: 220 + (-1.639)*40 = 220 - 65.56 = 154.4 => 154 px

LEFT_PF_X0 = -0.7558 ft => 220 + (-0.7558)*40 = 220 - 30.23 = 189.77 => 190 px
LEFT_PF_X1 = -0.3058 ft => 220 + (-0.3058)*40 = 220 - 12.23 = 207.77 => 208 px

Stringer positions in drawio_y:
  y=6.0' => 180 + 6.0*40 = 420
  y=7.75' => 180 + 7.75*40 = 490
  y=9.5' => 180 + 9.5*40 = 560
"""

SCALE = 40  # px per foot

def ft_to_x(ft_x):
    """Convert feet from left girder outer face to drawio x."""
    return 220 + ft_x * SCALE

def ft_to_y(ft_y):
    """Convert feet from house wall to drawio y."""
    return 180 + ft_y * SCALE

import re

# Key dimensions from render_v12.py
FRAME_W    = 23.0
FRAME_D    = 16.25
PF_W       = 5.4 / 12
FASCIA_T   = 0.67 / 12
PF_OVR     = 3.0 / 12
OVERALL_W  = FRAME_W + 2 * PF_OVR
OVERALL_D  = FRAME_D + PF_OVR

STEP_Y0    = 6.0
STEP_Y1    = 9.5
STEP_DEPTH = 16.0 / 12

GIRDER_W   = 0.38
GHW        = GIRDER_W / 2
GIRDER_L_FACE = 0.0 - GHW  # = -0.19 ft

LEFT_DECK_X = -PF_OVR - FASCIA_T
STEP_X_OUT  = LEFT_DECK_X - STEP_DEPTH
STRINGER_T  = 2.0 / 12

LEFT_PF_X0 = -(PF_OVR + FASCIA_T + PF_W)  # outer left edge of PF band
LEFT_PF_X1 = -(PF_OVR + FASCIA_T)          # inner left edge of PF band (= LEFT_DECK_X)

TREAD_DEPTH  = 10.8 / 12  # 2 x 5.4" planks depth
PLANK_W      = 5.4 / 12
PLANK_GAP    = (1.0/8) / 12

STRINGER_Y  = [STEP_Y0, (STEP_Y0 + STEP_Y1)/2, STEP_Y1]

FAR_PF_Y0   = FRAME_D + PF_OVR - PF_W

# Gravel pad
GRAVEL_W = 48.0 / 12
GRAVEL_D = 18.0 / 12
GRAVEL_Y0 = STEP_Y0 - (GRAVEL_W - (STEP_Y1 - STEP_Y0)) / 2
GRAVEL_Y1 = GRAVEL_Y0 + GRAVEL_W
GRAVEL_X0 = LEFT_DECK_X - GRAVEL_D
PAVER_SZ = 1.0

# Convert to drawio pixel coordinates
def dx(ft):  return ft_to_x(ft)
def dy(ft):  return ft_to_y(ft)

# All the new step cells to add to Page 1 (framing) and Page 2 (decking)

def make_step_cells_page1():
    """Returns XML cells to add to Page 1 (Framing Plan) for step."""
    cells = []

    # Gravel pad (background, muted)
    gx0 = dx(GRAVEL_X0); gy0 = dy(GRAVEL_Y0)
    gw = GRAVEL_D * SCALE; gh = GRAVEL_W * SCALE
    cells.append(f'''        <mxCell id="v12-p1-gravel" parent="1" style="strokeColor=#8a7a68;fillColor=#d0c8b8;strokeWidth=1.5;opacity=70;" value="" vertex="1">
          <mxGeometry x="{gx0:.1f}" y="{gy0:.1f}" width="{gw:.1f}" height="{gh:.1f}" as="geometry" />
        </mxCell>''')

    # Gravel label
    cells.append(f'''        <mxCell id="v12-p1-gravel-lbl" parent="1" style="text;html=1;strokeColor=none;fillColor=none;align=center;verticalAlign=middle;whiteSpace=wrap;fontSize=6;fontColor=#6a5a48;" value="gravel pad #57&lt;br/&gt;48in x 18in" vertex="1">
          <mxGeometry x="{gx0:.1f}" y="{gy0:.1f}" width="{gw:.1f}" height="{gh:.1f}" as="geometry" />
        </mxCell>''')

    # Pavers (3 x 12"x12")
    paver_w = PAVER_SZ * SCALE
    for idx, sy in enumerate(STRINGER_Y):
        px0 = dx(GRAVEL_X0); py0 = dy(sy - PAVER_SZ/2)
        cells.append(f'''        <mxCell id="v12-p1-paver-{idx}" parent="1" style="strokeColor=#444444;fillColor=#9a9a9a;strokeWidth=1.5;" value="" vertex="1">
          <mxGeometry x="{px0:.1f}" y="{py0:.1f}" width="{paver_w:.1f}" height="{paver_w:.1f}" as="geometry" />
        </mxCell>''')

    # 3 Stringers projecting from left girder face
    st_x0 = dx(STEP_X_OUT)
    st_x1 = dx(GIRDER_L_FACE)
    st_len = st_x1 - st_x0   # positive width
    st_h   = STRINGER_T * SCALE
    for idx, sy in enumerate(STRINGER_Y):
        sty0 = dy(sy - STRINGER_T/2)
        cells.append(f'''        <mxCell id="v12-p1-stringer-{idx}" parent="1" style="strokeColor=#2a5a1a;fillColor=#6a8a5a;strokeWidth=2;" value="" vertex="1">
          <mxGeometry x="{st_x0:.1f}" y="{sty0:.1f}" width="{st_len:.1f}" height="{st_h:.1f}" as="geometry" />
        </mxCell>''')

    # Stringer label
    mid_sy = dy(STRINGER_Y[1])
    cells.append(f'''        <mxCell id="v12-p1-stringer-lbl" parent="1" style="text;html=1;strokeColor=none;fillColor=none;align=center;verticalAlign=middle;whiteSpace=wrap;fontSize=6;fontColor=#2a5a1a;fontStyle=1;" value="3× 2x10 PT stringer&lt;br/&gt;Simpson LSCZ to L girder" vertex="1">
          <mxGeometry x="{st_x0:.1f}" y="{mid_sy - 20:.1f}" width="{st_len:.1f}" height="25" as="geometry" />
        </mxCell>''')

    # Cut joints — Page 1: lines at y=STEP_Y0 and y=STEP_Y1 on left edge
    cj_x0 = dx(STEP_X_OUT - 0.1)
    cj_x1 = dx(LEFT_DECK_X + 0.1)
    cj_len = cj_x1 - cj_x0
    for idx, cy in [(0, STEP_Y0), (1, STEP_Y1)]:
        cjy = dy(cy)
        cells.append(f'''        <mxCell id="v12-p1-cutjoint-{idx}" parent="1" style="endArrow=none;startArrow=none;strokeColor=#cc2200;strokeWidth=2.5;" value="" edge="1">
          <mxGeometry relative="1" as="geometry">
            <mxPoint as="sourcePoint" x="{cj_x0:.1f}" y="{cjy:.1f}" />
            <mxPoint as="targetPoint" x="{cj_x1:.1f}" y="{cjy:.1f}" />
          </mxGeometry>
        </mxCell>''')

    # Middle tread area (blocking / platform) — in framing view shown as a rectangle
    # The middle tread blocking in framing plan: 10.8" deep from LEFT_DECK_X leftward
    # between y=STEP_Y0 and y=STEP_Y1
    mt_x0 = dx(LEFT_DECK_X - TREAD_DEPTH)
    mt_y0 = dy(STEP_Y0)
    mt_w  = TREAD_DEPTH * SCALE
    mt_h  = (STEP_Y1 - STEP_Y0) * SCALE
    cells.append(f'''        <mxCell id="v12-p1-mtread-block" parent="1" style="strokeColor=#7a5030;fillColor=#c8a878;strokeWidth=1;opacity=60;" value="&lt;b&gt;mid tread blocking&lt;br/&gt;2x 5.4in MoistureShield&lt;br/&gt;6in AG&lt;/b&gt;" vertex="1">
          <mxGeometry x="{mt_x0:.1f}" y="{mt_y0:.1f}" width="{mt_w:.1f}" height="{mt_h:.1f}" as="geometry" />
        </mxCell>''')

    # Cut joint labels
    labels_y = [(STEP_Y0, "CUT JOINT y=6ft-0in", -15), (STEP_Y1, "CUT JOINT y=9ft-6in", 5)]
    for idx, (yft, ltxt, yoff) in enumerate(labels_y):
        lbx = dx(STEP_X_OUT - 0.1); lby = dy(yft) + yoff
        cells.append(f'''        <mxCell id="v12-p1-cj-lbl-{idx}" parent="1" style="text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;whiteSpace=wrap;fontSize=6;fontColor=#cc2200;fontStyle=1;" value="{ltxt} — PF &amp; fascia interrupted" vertex="1">
          <mxGeometry x="{lbx:.1f}" y="{lby:.1f}" width="140" height="14" as="geometry" />
        </mxCell>''')

    # Annotation: step location callout box
    ann_x = dx(STEP_X_OUT - 0.2) - 160
    ann_y = dy(STEP_Y0)
    cells.append(f'''        <mxCell id="v12-p1-step-callout" parent="1" style="text;html=1;strokeColor=#2244aa;fillColor=#e8eeff;align=left;verticalAlign=top;whiteSpace=wrap;rounded=0;fontSize=7;fontColor=#1a2a88;strokeWidth=1.5;" value="&lt;b&gt;SINGLE STEP v12 -- L EDGE&lt;/b&gt;&lt;br/&gt;y=6ft to 9ft-6in from house wall&lt;br/&gt;42in wide | 16in projection&lt;br/&gt;3x 2x10 PT cut stringers via LSCZ hangers&lt;br/&gt;Mid tread: 2x 5.4in MoistureShield @ 6in AG&lt;br/&gt;OPEN risers | pavers on #57 gravel" vertex="1">
          <mxGeometry x="{ann_x:.1f}" y="{ann_y:.1f}" width="155" height="100" as="geometry" />
        </mxCell>''')

    return '\n'.join(cells)


def make_step_cells_page2():
    """Returns XML cells to add to Page 2 (Decking Plan) for step."""
    cells = []

    # Gravel pad
    gx0 = dx(GRAVEL_X0); gy0 = dy(GRAVEL_Y0)
    gw = GRAVEL_D * SCALE; gh = GRAVEL_W * SCALE
    cells.append(f'''        <mxCell id="v12-p2-gravel" parent="p2-1" style="strokeColor=#8a7a68;fillColor=#d0c8b8;strokeWidth=1.5;" value="" vertex="1">
          <mxGeometry x="{gx0:.1f}" y="{gy0:.1f}" width="{gw:.1f}" height="{gh:.1f}" as="geometry" />
        </mxCell>''')
    cells.append(f'''        <mxCell id="v12-p2-gravel-lbl" parent="p2-1" style="text;html=1;strokeColor=none;fillColor=none;align=center;verticalAlign=middle;whiteSpace=wrap;fontSize=6;fontColor=#6a5a48;" value="#57 gravel pad 48in x 18in" vertex="1">
          <mxGeometry x="{gx0:.1f}" y="{gy0:.1f}" width="{gw:.1f}" height="25" as="geometry" />
        </mxCell>''')

    # Pavers (3)
    paver_w = PAVER_SZ * SCALE
    for idx, sy in enumerate(STRINGER_Y):
        px0 = dx(GRAVEL_X0); py0 = dy(sy - PAVER_SZ/2)
        cells.append(f'''        <mxCell id="v12-p2-paver-{idx}" parent="p2-1" style="strokeColor=#444444;fillColor=#9a9a9a;strokeWidth=1.5;" value="" vertex="1">
          <mxGeometry x="{px0:.1f}" y="{py0:.1f}" width="{paver_w:.1f}" height="{paver_w:.1f}" as="geometry" />
        </mxCell>''')

    # Stringers (plan view, 3 horizontal bands)
    st_x0 = dx(STEP_X_OUT)
    st_x1 = dx(GIRDER_L_FACE)
    st_len = st_x1 - st_x0
    st_h   = STRINGER_T * SCALE
    for idx, sy in enumerate(STRINGER_Y):
        sty0 = dy(sy - STRINGER_T/2)
        cells.append(f'''        <mxCell id="v12-p2-stringer-{idx}" parent="p2-1" style="strokeColor=#2a5a1a;fillColor=#6a8a5a;strokeWidth=2;" value="" vertex="1">
          <mxGeometry x="{st_x0:.1f}" y="{sty0:.1f}" width="{st_len:.1f}" height="{st_h:.1f}" as="geometry" />
        </mxCell>''')

    # Middle tread planks (2 × 5.4" MoistureShield, running in y-direction)
    mt_y0 = dy(STEP_Y0)
    mt_h  = (STEP_Y1 - STEP_Y0) * SCALE
    for i in range(2):
        tp_x0 = dx(LEFT_DECK_X - TREAD_DEPTH + i * PLANK_W)
        tp_w  = PLANK_W * SCALE
        cells.append(f'''        <mxCell id="v12-p2-tread-plank-{i}" parent="p2-1" style="strokeColor=#7a5030;fillColor=#c8a878;strokeWidth=1;" value="" vertex="1">
          <mxGeometry x="{tp_x0:.1f}" y="{mt_y0:.1f}" width="{tp_w:.1f}" height="{mt_h:.1f}" as="geometry" />
        </mxCell>''')

    # Middle tread label
    mt_cx = dx(LEFT_DECK_X - TREAD_DEPTH/2)
    mt_cy = dy((STEP_Y0 + STEP_Y1)/2)
    cells.append(f'''        <mxCell id="v12-p2-tread-lbl" parent="p2-1" style="text;html=1;strokeColor=none;fillColor=none;align=center;verticalAlign=middle;whiteSpace=wrap;fontSize=5.5;fontColor=#7a5030;fontStyle=1;" value="Mid tread&lt;br/&gt;2x 5.4in MoistureShield&lt;br/&gt;6in AG | OPEN risers" vertex="1">
          <mxGeometry x="{mt_cx - 30:.1f}" y="{mt_cy - 25:.1f}" width="60" height="50" as="geometry" />
        </mxCell>''')

    # Cut joints (red lines at y=STEP_Y0 and y=STEP_Y1)
    cj_x0 = dx(STEP_X_OUT - 0.1)
    cj_x1 = dx(LEFT_DECK_X + 0.05)
    for idx, cy in [(0, STEP_Y0), (1, STEP_Y1)]:
        cjy = dy(cy)
        cells.append(f'''        <mxCell id="v12-p2-cutjoint-{idx}" parent="p2-1" style="endArrow=none;startArrow=none;strokeColor=#cc2200;strokeWidth=2.5;" value="" edge="1">
          <mxGeometry relative="1" as="geometry">
            <mxPoint as="sourcePoint" x="{cj_x0:.1f}" y="{cjy:.1f}" />
            <mxPoint as="targetPoint" x="{cj_x1:.1f}" y="{cjy:.1f}" />
          </mxGeometry>
        </mxCell>''')

    # Cut joint labels
    labels_y = [(STEP_Y0, "CUT JOINT y=6ft-0in", -16), (STEP_Y1, "CUT JOINT y=9ft-6in", 3)]
    for idx, (yft, ltxt, yoff) in enumerate(labels_y):
        lbx = dx(STEP_X_OUT - 0.1); lby = dy(yft) + yoff
        cells.append(f'''        <mxCell id="v12-p2-cj-lbl-{idx}" parent="p2-1" style="text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;whiteSpace=wrap;fontSize=6;fontColor=#cc2200;fontStyle=1;" value="{ltxt}" vertex="1">
          <mxGeometry x="{lbx:.1f}" y="{lby:.1f}" width="130" height="14" as="geometry" />
        </mxCell>''')

    # Step elevation inset (side view) — placed below main diagram
    # Inset box: to the left of the deck diagram
    EI_X   = dx(STEP_X_OUT - 0.6) - 160
    EI_Y   = dy(STEP_Y1) + 20
    EI_W   = 155
    EI_H   = 160
    cells.append(f'''        <mxCell id="v12-p2-elev-box" parent="p2-1" style="text;html=1;strokeColor=#446688;fillColor=#f8f8f0;align=center;verticalAlign=top;whiteSpace=wrap;rounded=0;fontSize=7;fontColor=#2244aa;strokeWidth=2;" value="&lt;b&gt;STEP SIDE ELEVATION&lt;/b&gt;&lt;br/&gt;Open risers -- no riser board&lt;br/&gt;&lt;br/&gt;12in AG --------- (deck top)&lt;br/&gt;OPEN RISER (no board)&lt;br/&gt;6in AG -- [tread 10.8in deep] --&lt;br/&gt;OPEN RISER (no board)&lt;br/&gt;0in AG ----------- (grade)&lt;br/&gt;[gravel pad + 12in x 12in pavers]&lt;br/&gt;&lt;br/&gt;2 risers @ 6in each&lt;br/&gt;3x 2x10 PT stringers" vertex="1">
          <mxGeometry x="{EI_X:.1f}" y="{EI_Y:.1f}" width="{EI_W}" height="{EI_H}" as="geometry" />
        </mxCell>''')

    # Left PF interrupted: modify existing left PF cell — instead we just add notes
    # and the cut joints serve as the interruption visual
    # Add "open step zone" rectangle between cut joints in the PF zone
    # (gap in PF shown as white/empty space at that y range)
    pf_gap_x = dx(LEFT_PF_X0)
    pf_gap_y = dy(STEP_Y0)
    pf_gap_w = (LEFT_PF_X1 - LEFT_PF_X0) * SCALE
    pf_gap_h = (STEP_Y1 - STEP_Y0) * SCALE
    # White-out rectangle to mask the existing continuous left PF band in the gap zone
    cells.append(f'''        <mxCell id="v12-p2-pf-gap" parent="p2-1" style="strokeColor=#cc2200;fillColor=white;strokeWidth=1.5;dashed=1;dashPattern=6 3;" value="STEP&lt;br/&gt;OPENING" vertex="1">
          <mxGeometry x="{pf_gap_x:.1f}" y="{pf_gap_y:.1f}" width="{pf_gap_w:.1f}" height="{pf_gap_h:.1f}" as="geometry" />
        </mxCell>''')

    # Step callout annotation (placed to left)
    ann_x = dx(STEP_X_OUT - 0.2) - 165
    ann_y = dy(STEP_Y0) - 10
    cells.append(f'''        <mxCell id="v12-p2-step-callout" parent="p2-1" style="text;html=1;strokeColor=#2244aa;fillColor=#e8eeff;align=left;verticalAlign=top;whiteSpace=wrap;rounded=0;fontSize=7;fontColor=#1a2a88;strokeWidth=1.5;" value="&lt;b&gt;SINGLE STEP — L EDGE (v12)&lt;/b&gt;&lt;br/&gt;y=6ft-0in to 9ft-6in from house wall&lt;br/&gt;42in wide | 16in projection&lt;br/&gt;3x 2x10 PT stringers (LSCZ)&lt;br/&gt;Mid tread: 2x5.4in MoistureShield @ 6in AG&lt;br/&gt;OPEN risers | pavers on #57 gravel" vertex="1">
          <mxGeometry x="{ann_x:.1f}" y="{ann_y:.1f}" width="162" height="95" as="geometry" />
        </mxCell>''')

    return '\n'.join(cells)


# Read clean v11 drawio (from git backup at /tmp/deck_plan_v11.drawio)
# This ensures we always start from a clean v11 base, not a previously-patched file
import os
v11_source = '/tmp/deck_plan_v11.drawio'
if not os.path.exists(v11_source):
    # Fallback: extract from current file if /tmp version missing
    v11_source = '/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/owner_inbox/deck_blueprint/deck_plan.drawio'
with open(v11_source, 'r') as f:
    content = f.read()

# ── Bump version badges ────────────────────────────────────────────────────────
# Update all v11 references to v12 in critical locations

# Page 1 diagram id/name — handle any prior version (v10, v11, etc.)
content = re.sub(r'id="deck-plan-v\d+-p1"', 'id="deck-plan-v12-p1"', content)
content = re.sub(r'name="Page 1 — Framing Plan \(v\d+\)"', 'name="Page 1 — Framing Plan (v12)"', content)

# Page 2 diagram id/name
content = re.sub(r'id="deck-plan-v\d+-p2"', 'id="deck-plan-v12-p2"', content)
content = re.sub(r'name="Page 2 — Decking Plan \(v\d+\)"', 'name="Page 2 — Decking Plan (v12)"', content)

# Version badge cells — the v11 drawio still has v10 in badge values (known v11 regression).
# Replace whatever version is there with v12 for both pages.
content = re.sub(
    r'(value="&lt;b&gt;)v\d+(&lt;/b&gt;&lt;br/&gt;&lt;font style=&quot;font-size: 11px;&quot;&gt;Page 1 of 2 — Framing&lt;/font&gt;")',
    r'\g<1>v12\g<2>',
    content
)
content = re.sub(
    r'(value="&lt;b&gt;)v\d+(&lt;/b&gt;&lt;br/&gt;&lt;font style=&quot;font-size: 11px;&quot;&gt;Page 2 of 2 — Decking&lt;/font&gt;")',
    r'\g<1>v12\g<2>',
    content
)

# Title block on Page 1 (cell id=2) -- replace vN with v12 in title
content = re.sub(
    r'DECK PLAN v\d+ — PAGE 1: FRAMING PLAN',
    'DECK PLAN v12 — PAGE 1: FRAMING PLAN',
    content
)

# Title block on Page 2 (cell p2-2111) -- replace vN with v12 in title
content = re.sub(
    r'DECK PLAN v\d+ — PAGE 2: DECKING',
    'DECK PLAN v12 — PAGE 2: DECKING',
    content
)

# Update Page 2 subtitle/version note -- replace any prior version note string
for old_ver_note in [
    'v10: outside-corner miter fixed at lower-left and lower-right',
    'v11: MoistureShield Vision brand swap; 49 field planks; 5.4&quot; board width',
    'v11: MoistureShield Vision brand swap; 49 field planks; 5.4" board width',
]:
    content = content.replace(old_ver_note,
        'v12: +single step L-edge 42in wide @ 6ft from house; open risers; gravel+paver landing'
    )

# Fastener notes on Page 1 (cell id=500): add LSCZ and paver anchors
old_fastener_note = ('MoistureShield Vision Fascia: 0.67in, stainless trim screws to rim outer face&lt;br/&gt;'
                     'Piers: Pylex 50 helical pier, 50in galvanized shaft, screwed to refusal through punched patio holes&lt;br/&gt;'
                     'Hardware: hot-dip galvanized or stainless throughout (ACQ-compatible)')
new_fastener_note = ('MoistureShield Vision Fascia: 0.67in, stainless trim screws to rim outer face&lt;br/&gt;'
                     'Piers: Pylex 50 helical pier, 50in galvanized shaft, screwed to refusal through punched patio holes&lt;br/&gt;'
                     'Stair stringers: Simpson LSCZ stair stringer hangers (or equiv.) to outer face of L girder&lt;br/&gt;'
                     'Stringer base: metal stringer-to-paver anchors; stringers bear on 12in x 12in precast pavers over #57 gravel&lt;br/&gt;'
                     'Hardware: hot-dip galvanized or stainless throughout (ACQ-compatible)')
content = content.replace(old_fastener_note, new_fastener_note)

# Legend on Page 2 (cell p2-2113): add step entries
old_legend_end = ('Available: Home Depot, Lowe&#39;s, Richards Building Supply (Hartford metro)')
new_legend_end = ('Available: Home Depot, Lowe&#39;s, Richards Building Supply (Hartford metro)&lt;br/&gt;'
                  '&lt;br/&gt;&lt;b&gt;STEP (v12 NEW):&lt;/b&gt;&lt;br/&gt;'
                  'Stair stringers (#6a8a5a green): 3x 2x10 PT cut stringer; Simpson LSCZ to L girder face&lt;br/&gt;'
                  'Middle tread (#c8a878): 2x5.4in MoistureShield Vision planks, parallel to L edge, 6in AG&lt;br/&gt;'
                  'Gravel pad (#d0c8b8 stippled): #57 compacted gravel, 48in x 18in under step footprint&lt;br/&gt;'
                  'Pavers (#9a9a9a): 3x precast 12in x 12in concrete pavers; metal stringer-to-paver anchors&lt;br/&gt;'
                  'Cut joints (red lines): PF and fascia terminate/resume at y=6ft-0in and y=9ft-6in&lt;br/&gt;'
                  'Open risers: no riser board; stringers visible; see side elevation inset')
content = content.replace(old_legend_end, new_legend_end)

# ── Inject step cells into Page 1 (before closing </root>) ────────────────────
page1_root_close = '      </root>\n    </mxGraphModel>\n  </diagram>\n  <diagram id="deck-plan-v12-p2"'
step1_cells = make_step_cells_page1()
content = content.replace(
    page1_root_close,
    f'{step1_cells}\n{page1_root_close}'
)

# ── Inject step cells into Page 2 (before closing </root>) ────────────────────
page2_root_close = '      </root>\n    </mxGraphModel>\n  </diagram>\n</mxfile>'
step2_cells = make_step_cells_page2()
content = content.replace(
    page2_root_close,
    f'{step2_cells}\n{page2_root_close}'
)

# Write updated file
out_path = '/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/owner_inbox/deck_blueprint/deck_plan.drawio'
with open(out_path, 'w') as f:
    f.write(content)

print(f"Written: {out_path}")
print(f"File size: {len(content)} bytes")
