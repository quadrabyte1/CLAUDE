"""Picture Perfect — Step 2: catch wire on pencils, read scale at frame top."""
from PIL import Image, ImageDraw, ImageFont
import math

ROOT  = '/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/owner_inbox/picture_perfect'
PARTS = f'{ROOT}/parts_alpha'

# Tool geometry
BODY_PIVOT_L = (85.1, 1077.8)
BODY_PIVOT_R = (254.2, 1077.8)
ARM_R_PIVOT  = (90, 91)
ARM_L_PIVOT  = (1090, 91)

# Scale geometry on body (source y for "0" mark and per-unit span)
SCALE_0_Y    = 900
SCALE_UNIT_Y = (900 - 220) / 4   # = 170 px per unit

# Pencil hole positions (right-arm source coords); left-arm mirrors
RIGHT_HOLES = {'A': (389, 87), 'B': (637, 87), 'C': (884, 87), 'D': (1132, 87)}
LEFT_HOLES  = {k: (1180 - v[0], v[1]) for k, v in RIGHT_HOLES.items()}

# Render params
RS = 4
CW, CH = 1600 * RS, 1020 * RS
TOOL_S = 0.27 * RS

HELV = '/System/Library/Fonts/Helvetica.ttc'
def font(sz, bold=False):
    return ImageFont.truetype(HELV, sz, index=(1 if bold else 0))

def scale_img(im, s):
    w, h = im.size
    return im.resize((max(1,int(round(w*s))), max(1,int(round(h*s)))), Image.LANCZOS)

def bezier(draw, p0, p1, p2, width, fill, n=60, ah_len=18*RS):
    pts = []
    for i in range(n+1):
        t = i/n
        pts.append((((1-t)**2*p0[0] + 2*(1-t)*t*p1[0] + t**2*p2[0]),
                    ((1-t)**2*p0[1] + 2*(1-t)*t*p1[1] + t**2*p2[1])))
    draw.line(pts, fill=fill, width=width, joint='curve')
    dx, dy = p2[0]-p1[0], p2[1]-p1[1]
    L = math.hypot(dx, dy) or 1.0
    tx, ty = dx/L, dy/L
    px, py = -ty, tx
    base = (p2[0]-tx*ah_len, p2[1]-ty*ah_len)
    a1 = (base[0]+px*ah_len*0.5, base[1]+py*ah_len*0.5)
    a2 = (base[0]-px*ah_len*0.5, base[1]-py*ah_len*0.5)
    draw.polygon([p2, a1, a2], fill=fill)

def dashed_line(draw, p0, p1, dash, gap, width, fill):
    dx, dy = p1[0]-p0[0], p1[1]-p0[1]
    L = math.hypot(dx, dy)
    if L == 0: return
    ux, uy = dx/L, dy/L
    s = 0
    while s < L:
        e = min(s + dash, L)
        draw.line([(p0[0]+ux*s, p0[1]+uy*s), (p0[0]+ux*e, p0[1]+uy*e)],
                  fill=fill, width=width)
        s += dash + gap

# ---------- Load parts ----------
body  = scale_img(Image.open(f'{PARTS}/body.png').convert('RGBA'),       TOOL_S)
arm_l = scale_img(Image.open(f'{PARTS}/arm_left.png').convert('RGBA'),   TOOL_S)
arm_r = scale_img(Image.open(f'{PARTS}/arm_right.png').convert('RGBA'),  TOOL_S)

bpl = (BODY_PIVOT_L[0]*TOOL_S, BODY_PIVOT_L[1]*TOOL_S)
bpr = (BODY_PIVOT_R[0]*TOOL_S, BODY_PIVOT_R[1]*TOOL_S)
apl = (ARM_L_PIVOT[0]*TOOL_S, ARM_L_PIVOT[1]*TOOL_S)
apr = (ARM_R_PIVOT[0]*TOOL_S, ARM_R_PIVOT[1]*TOOL_S)

canvas = Image.new('RGBA', (CW, CH), (255,255,255,255))
draw   = ImageDraw.Draw(canvas)

# ---------- Frame (back of artwork) ----------
art_cx     = 800 * RS
frame_w    = 940 * RS
frame_h    = 590 * RS
frame_top  = 320 * RS
frame_left = art_cx - frame_w//2
frame_right= art_cx + frame_w//2
frame_bot  = frame_top + frame_h

# Outer dark frame
draw.rectangle([frame_left, frame_top, frame_right, frame_bot],
               fill=(90, 62, 36), outline=(50, 30, 18), width=int(2.5*RS))

# Inner back panel
back_t     = 28 * RS
back_left  = frame_left + back_t
back_top   = frame_top  + back_t
back_right = frame_right - back_t
back_bot   = frame_bot   - back_t
draw.rectangle([back_left, back_top, back_right, back_bot],
               fill=(206, 184, 152), outline=(140, 115, 85), width=int(1.5*RS))

# Wire attachment points
wire_y      = back_top + int((back_bot - back_top) * 0.34)
wire_left_x = back_left + int((back_right - back_left) * 0.16)
wire_right_x= back_right - int((back_right - back_left) * 0.16)

def draw_dring(draw, cx, cy):
    r1, r2 = 9*RS, 4*RS
    draw.ellipse([cx-r1, cy-r1, cx+r1, cy+r1], fill=(135, 110, 85),
                 outline=(45, 30, 18), width=int(1.8*RS))
    draw.ellipse([cx-r2, cy-r2, cx+r2, cy+r2], fill=(170, 145, 115),
                 outline=(45, 30, 18), width=int(1*RS))

draw_dring(draw, wire_left_x, wire_y)
draw_dring(draw, wire_right_x, wire_y)

# ---------- Place the tool: position so target scale value = frame_top ----------
chosen = 'B'
target_value = 1.25     # frame top reads 1¼

body_target_y = SCALE_0_Y - target_value * SCALE_UNIT_Y   # source y for 1¼ on scale
body_top_canvas = frame_top - int(body_target_y * TOOL_S)
body_left_canvas = art_cx - body.size[0] // 2

body_pl_canvas = (body_left_canvas + bpl[0], body_top_canvas + bpl[1])
body_pr_canvas = (body_left_canvas + bpr[0], body_top_canvas + bpr[1])

# Compute arm top-lefts for hole lookup
left_arm_tl  = (int(round(body_pl_canvas[0]-apl[0])), int(round(body_pl_canvas[1]-apl[1])))
right_arm_tl = (int(round(body_pr_canvas[0]-apr[0])), int(round(body_pr_canvas[1]-apr[1])))

# Composite arms (behind body), body on top
canvas.alpha_composite(arm_l,  left_arm_tl)
canvas.alpha_composite(arm_r,  right_arm_tl)
canvas.alpha_composite(body,   (body_left_canvas, body_top_canvas))

# Pencil-hole canvas coordinates for chosen letter
lh = LEFT_HOLES[chosen]
rh = RIGHT_HOLES[chosen]
left_p  = (left_arm_tl[0]  + int(lh[0]*TOOL_S), left_arm_tl[1]  + int(lh[1]*TOOL_S))
right_p = (right_arm_tl[0] + int(rh[0]*TOOL_S), right_arm_tl[1] + int(rh[1]*TOOL_S))

# ---------- Wire ----------
wire_color = (45, 35, 25)
wire_w = int(3 * RS)

# Slants (visible on the wall outside the tool)
draw.line([(wire_left_x, wire_y), left_p],  fill=wire_color, width=wire_w)
draw.line([right_p, (wire_right_x, wire_y)], fill=wire_color, width=wire_w)
# Horizontal "top" of trapezoid (hidden behind tool) — dashed
dashed_line(draw, left_p, right_p, dash=10*RS, gap=6*RS, width=wire_w, fill=wire_color)

# ---------- Pencils (yellow circles, with dark graphite dot) ----------
pencil_r = 13 * RS
for p in (left_p, right_p):
    draw.ellipse([p[0]-pencil_r, p[1]-pencil_r, p[0]+pencil_r, p[1]+pencil_r],
                 fill=(248, 198, 70), outline=(140, 100, 30), width=int(2*RS))
    dr = 3 * RS
    draw.ellipse([p[0]-dr, p[1]-dr, p[0]+dr, p[1]+dr], fill=(30, 22, 12))

# ---------- Reading indicator: arrow + "1¼" at frame_top, right side of body ----------
body_right_canvas = body_left_canvas + body.size[0]
arrow_start_x = body_right_canvas + 4*RS
arrow_end_x   = arrow_start_x + 70*RS
arrow_y       = frame_top

# Red arrow pointing LEFT into the scale
draw.line([(arrow_start_x, arrow_y), (arrow_end_x, arrow_y)],
          fill=(190, 30, 30), width=int(3.5*RS))
ah = 14 * RS
draw.polygon([(arrow_start_x, arrow_y),
              (arrow_start_x + ah, arrow_y - ah*0.55),
              (arrow_start_x + ah, arrow_y + ah*0.55)], fill=(190, 30, 30))

draw.text((arrow_end_x + 10*RS, arrow_y - 4*RS), '1¼',
          font=font(int(30*RS), bold=True), fill=(190, 30, 30), anchor='lm')
draw.text((arrow_end_x + 10*RS, arrow_y + 32*RS), 'on scale = frame top',
          font=font(int(14*RS)), fill=(140, 80, 80), anchor='lm')

# ---------- Annotations ----------
# (1) pencils in matching letter holes
ann1_x, ann1_y = 90*RS, 640*RS
draw.text((ann1_x, ann1_y), 'Insert pencils in',
          font=font(int(22*RS), bold=True), fill='black', anchor='lm')
draw.text((ann1_x, ann1_y + 30*RS),
          f'matching {chosen} holes',
          font=font(int(20*RS), bold=True), fill='black', anchor='lm')
draw.text((ann1_x, ann1_y + 58*RS),
          '(A=narrow art · D=wide art)',
          font=font(int(15*RS)), fill=(80, 80, 80), anchor='lm')
bezier(draw,
       p0=(ann1_x + 250*RS, ann1_y + 8*RS),
       p1=(ann1_x + 380*RS, ann1_y + 100*RS),
       p2=(left_p[0] - 20*RS, left_p[1] + 0*RS),
       width=int(3*RS), fill=(50,50,50))

# (2) lift tool until wire taut
ann2_x, ann2_y = 1510*RS, 800*RS
draw.text((ann2_x, ann2_y), 'Lift tool until',
          font=font(int(22*RS), bold=True), fill='black', anchor='rm')
draw.text((ann2_x, ann2_y + 30*RS),
          'wire is taut',
          font=font(int(20*RS), bold=True), fill='black', anchor='rm')
draw.text((ann2_x, ann2_y + 58*RS),
          '(forms a trapezoid)',
          font=font(int(15*RS)), fill=(80, 80, 80), anchor='rm')
bezier(draw,
       p0=(ann2_x - 220*RS, ann2_y + 8*RS),
       p1=(ann2_x - 460*RS, ann2_y - 110*RS),
       p2=(right_p[0] + 22*RS, right_p[1] + 0*RS),
       width=int(3*RS), fill=(50,50,50))

# (3) frame top on scale = remember this
ann3_x, ann3_y = 1510*RS, 360*RS
draw.text((ann3_x, ann3_y), 'Read scale at',
          font=font(int(22*RS), bold=True), fill='black', anchor='rm')
draw.text((ann3_x, ann3_y + 30*RS),
          'the frame top',
          font=font(int(20*RS), bold=True), fill='black', anchor='rm')
draw.text((ann3_x, ann3_y + 58*RS),
          '— remember this number',
          font=font(int(15*RS)), fill=(80, 80, 80), anchor='rm')

# ---------- Title / footer / version badge ----------
bx, by, bw, bh = 24*RS, 24*RS, 96*RS, 36*RS
draw.rectangle([bx, by, bx+bw, by+bh], outline='black', width=int(2.5*RS))
draw.text((bx+bw/2, by+bh/2), 'v2', font=font(int(19*RS), bold=True),
          fill='black', anchor='mm')

draw.text((CW/2, 35*RS), 'Picture Perfect — Step 2',
          font=font(int(32*RS), bold=True), fill='black', anchor='mm')
draw.text((CW/2, 75*RS),
          'With artwork facing the wall, catch the wire on two pencils and read the frame-top mark.',
          font=font(int(20*RS)), fill='black', anchor='mm')

draw.text((CW/2, 955*RS),
          'Example: moderately wide art uses B holes. Frame top reads 1¼ — remember this number for Step 5.',
          font=font(int(17*RS)), fill='black', anchor='mm')
draw.text((CW/2, CH - 25*RS), 'Picture Perfect · Step 2 of N · v1',
          font=font(int(13*RS)), fill=(85,85,85), anchor='mm')

# ---------- Save ----------
fw, fh = CW // RS, CH // RS
canvas.resize((fw, fh), Image.LANCZOS).convert('RGB').save(
    f'{ROOT}/step_02_catch_wire.png', 'PNG', optimize=True)
print(f'Saved step_02_catch_wire.png ({fw}x{fh})')

canvas.resize((fw*2, fh*2), Image.LANCZOS).convert('RGB').save(
    f'{ROOT}/step_02_catch_wire@2x.png', 'PNG', optimize=True)
print(f'Saved step_02_catch_wire@2x.png ({fw*2}x{fh*2})')
