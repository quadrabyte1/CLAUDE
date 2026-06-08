"""Compose Picture Perfect — Step 1 diagram from real CAD parts (v3)."""
from PIL import Image, ImageDraw, ImageFont
import math

ROOT  = '/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/owner_inbox/picture_perfect'
PARTS = f'{ROOT}/parts_alpha'

# Pivot positions in source images (auto-detected, unscaled px)
BODY_PIVOT_L = (85.1, 1077.8)
BODY_PIVOT_R = (254.2, 1077.8)
ARM_R_PIVOT  = (90, 91)    # right arm: pivot disk center (near LEFT end)
ARM_L_PIVOT  = (1090, 91)  # left arm:  pivot disk center (near RIGHT end)

# Render super-sampled, then downsample for crisp anti-aliased lines/arcs.
RS = 4                 # render scale (super-sampling factor)
S  = 0.32 * RS         # scale applied to source PNGs
CW, CH = 1600 * RS, 880 * RS

HELV = '/System/Library/Fonts/Helvetica.ttc'
def font(sz, bold=False):
    return ImageFont.truetype(HELV, sz, index=(1 if bold else 0))

def scale_img(im, s):
    w, h = im.size
    return im.resize((max(1, int(round(w*s))), max(1, int(round(h*s)))), Image.LANCZOS)

def rotated_pivot(pivot, size, angle_deg):
    """Where does `pivot` land in PIL rotate(angle, expand=True)?"""
    W, H = size
    px, py = pivot
    dx, dy = px - W/2.0, py - H/2.0
    a = math.radians(angle_deg)
    new_dx = math.cos(a)*dx + math.sin(a)*dy
    new_dy = -math.sin(a)*dx + math.cos(a)*dy
    new_W = abs(W*math.cos(a)) + abs(H*math.sin(a))
    new_H = abs(W*math.sin(a)) + abs(H*math.cos(a))
    return (new_W/2.0 + new_dx, new_H/2.0 + new_dy)

def polyline_arc(draw, cx, cy, r, start_deg, end_deg, width, fill):
    """Draw arc as polyline (smoother than PIL.arc). Sweep is from start to end as given."""
    n = 80
    pts = []
    for i in range(n+1):
        t = start_deg + (end_deg - start_deg) * (i / n)
        a = math.radians(t)
        pts.append((cx + r*math.cos(a), cy + r*math.sin(a)))
    draw.line(pts, fill=fill, width=width, joint='curve')

def motion_arrow(draw, cx, cy, r, head_deg, sweep_from_deg, width, fill, ah_len):
    """Curved arrow whose arc spans [sweep_from_deg → head_deg],
       with the arrowhead at head_deg pointing in the direction of motion."""
    polyline_arc(draw, cx, cy, r, sweep_from_deg, head_deg, width, fill)
    a = math.radians(head_deg)
    tip = (cx + r*math.cos(a), cy + r*math.sin(a))
    # Motion tangent points from sweep_from → head (the way we just drew the arc)
    # Tangent direction at the head, projected from the previous point on the arc:
    prev_a = math.radians(head_deg - (head_deg - sweep_from_deg)/80)
    prev   = (cx + r*math.cos(prev_a), cy + r*math.sin(prev_a))
    dx, dy = tip[0]-prev[0], tip[1]-prev[1]
    norm = math.hypot(dx, dy) or 1.0
    tx, ty = dx/norm, dy/norm
    px, py = -ty, tx
    base = (tip[0] - tx*ah_len, tip[1] - ty*ah_len)
    p1 = (base[0] + px*ah_len*0.55, base[1] + py*ah_len*0.55)
    p2 = (base[0] - px*ah_len*0.55, base[1] - py*ah_len*0.55)
    draw.polygon([tip, p1, p2], fill=fill)

# ---------- Load + scale parts ----------
body  = scale_img(Image.open(f'{PARTS}/body.png').convert('RGBA'),       S)
arm_l = scale_img(Image.open(f'{PARTS}/arm_left.png').convert('RGBA'),   S)
arm_r = scale_img(Image.open(f'{PARTS}/arm_right.png').convert('RGBA'),  S)

bpl = (BODY_PIVOT_L[0]*S, BODY_PIVOT_L[1]*S)
bpr = (BODY_PIVOT_R[0]*S, BODY_PIVOT_R[1]*S)
apl = (ARM_L_PIVOT[0]*S, ARM_L_PIVOT[1]*S)
apr = (ARM_R_PIVOT[0]*S, ARM_R_PIVOT[1]*S)

canvas = Image.new('RGBA', (CW, CH), (255,255,255,255))

# ---------- PANEL A: FOLDED ----------
panel_a_cx = 320 * RS
body_top   = 180 * RS
body_left_a = panel_a_cx - body.size[0] // 2
canvas.alpha_composite(body, (body_left_a, body_top))

body_pl_a = (body_left_a + bpl[0], body_top + bpl[1])
body_pr_a = (body_left_a + bpr[0], body_top + bpr[1])

# Right arm rotated +90 CCW → pivot at bottom, arm extends up
arr = arm_r.rotate(90, resample=Image.BICUBIC, expand=True)
arr_pivot = rotated_pivot(apr, arm_r.size, 90)
canvas.alpha_composite(arr,
    (int(round(body_pr_a[0]-arr_pivot[0])), int(round(body_pr_a[1]-arr_pivot[1]))))

# Left arm rotated -90 CW → pivot at bottom, arm extends up
alr = arm_l.rotate(-90, resample=Image.BICUBIC, expand=True)
alr_pivot = rotated_pivot(apl, arm_l.size, -90)
canvas.alpha_composite(alr,
    (int(round(body_pl_a[0]-alr_pivot[0])), int(round(body_pl_a[1]-alr_pivot[1]))))

# ---------- PANEL B: DEPLOYED (arms BEHIND body so disks show only through pivot holes) ----------
panel_b_cx = 1200 * RS
body_left_b = panel_b_cx - body.size[0] // 2

body_pl_b = (body_left_b + bpl[0], body_top + bpl[1])
body_pr_b = (body_left_b + bpr[0], body_top + bpr[1])

# Arms FIRST, with corrected pivot positions
canvas.alpha_composite(arm_l,
    (int(round(body_pl_b[0]-apl[0])), int(round(body_pl_b[1]-apl[1]))))
canvas.alpha_composite(arm_r,
    (int(round(body_pr_b[0]-apr[0])), int(round(body_pr_b[1]-apr[1]))))

# Body ON TOP — pivot tabs of arms show through the body's transparent pivot holes
canvas.alpha_composite(body, (body_left_b, body_top))

# ---------- ANNOTATIONS ----------
draw = ImageDraw.Draw(canvas)

# Version badge
bx, by, bw, bh = 24*RS, 24*RS, 96*RS, 36*RS
draw.rectangle([bx, by, bx+bw, by+bh], outline='black', width=int(2.5*RS))
draw.text((bx+bw/2, by+bh/2), 'v4', font=font(int(19*RS), bold=True),
          fill='black', anchor='mm')

# Title + subtitle
draw.text((CW/2, 35*RS), 'Picture Perfect — Step 1',
          font=font(int(32*RS), bold=True), fill='black', anchor='mm')
draw.text((CW/2, 75*RS),
          'Take the tool from the box and fold both arms down to form an inverted T.',
          font=font(int(20*RS)), fill='black', anchor='mm')

# Panel labels
draw.text((panel_a_cx, 130*RS), 'As packaged',
          font=font(int(22*RS), bold=True), fill='black', anchor='mm')
draw.text((panel_b_cx, 130*RS), 'Ready to use',
          font=font(int(22*RS), bold=True), fill='black', anchor='mm')

# Captions
draw.text((panel_a_cx, 770*RS), 'Arms folded up alongside the body',
          font=font(int(17*RS)), fill='black', anchor='mm')
draw.text((panel_b_cx, 770*RS),
          'Arms swung down — body + arms form an inverted T',
          font=font(int(17*RS)), fill='black', anchor='mm')

# Linear arrow between panels
ax1, ax2, ay = 720*RS, 820*RS, 460*RS
draw.line([(ax1, ay), (ax2 - 18*RS, ay)], fill='black', width=int(5*RS))
ah = 16*RS
draw.polygon([(ax2, ay), (ax2-ah, ay-ah*0.75), (ax2-ah, ay+ah*0.75)], fill='black')

# Curved motion arrows — both heads point DOWN to indicate arms fold DOWN.
arc_r = 175 * RS
line_w = int(5 * RS)
ah_len = 22 * RS

# RIGHT arm: motion is CW (top → right). Arc sweep 280° → 355°.
motion_arrow(draw,
    body_pr_a[0], body_pr_a[1], arc_r,
    head_deg=355, sweep_from_deg=280,
    width=line_w, fill='black', ah_len=ah_len)

# LEFT arm: motion is CCW (top → left). Sweep 260° → 185° (decreasing angle).
motion_arrow(draw,
    body_pl_a[0], body_pl_a[1], arc_r,
    head_deg=185, sweep_from_deg=260,
    width=line_w, fill='black', ah_len=ah_len)

# Footer
draw.text((CW/2, CH - 25*RS), 'Picture Perfect · Step 1 of N · v4',
          font=font(int(13*RS)), fill=(85,85,85), anchor='mm')

# ---------- Save (downsample 4× → final 1×) ----------
final_w, final_h = CW // RS, CH // RS
final = canvas.resize((final_w, final_h), Image.LANCZOS)
final.convert('RGB').save(f'{ROOT}/step_01_unfold.png', 'PNG', optimize=True)
print(f'Saved step_01_unfold.png ({final_w}x{final_h})')

# 2× version for retina viewing (downsample 4× to 2×)
hi = canvas.resize((final_w*2, final_h*2), Image.LANCZOS)
hi.convert('RGB').save(f'{ROOT}/step_01_unfold@2x.png', 'PNG', optimize=True)
print(f'Saved step_01_unfold@2x.png ({final_w*2}x{final_h*2})')
