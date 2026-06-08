"""Picture Perfect — Step 3: pencil mark at top of frame."""
from PIL import Image, ImageDraw, ImageFont
import math

ROOT = '/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/owner_inbox/picture_perfect'
RS = 4
CW, CH = 1600 * RS, 880 * RS
HELV = '/System/Library/Fonts/Helvetica.ttc'

def font(sz, bold=False):
    return ImageFont.truetype(HELV, sz, index=(1 if bold else 0))

def bezier(draw, p0, p1, p2, width, fill, n=60):
    """Quadratic bezier as a smooth polyline."""
    pts = []
    for i in range(n+1):
        t = i / n
        x = (1-t)**2 * p0[0] + 2*(1-t)*t * p1[0] + t**2 * p2[0]
        y = (1-t)**2 * p0[1] + 2*(1-t)*t * p1[1] + t**2 * p2[1]
        pts.append((x, y))
    draw.line(pts, fill=fill, width=width, joint='curve')
    # Arrowhead at p2, tangent toward (p2 - p1 direction)
    dx, dy = p2[0]-p1[0], p2[1]-p1[1]
    L = math.hypot(dx, dy) or 1.0
    tx, ty = dx/L, dy/L
    px, py = -ty, tx
    ah = 18 * RS
    base = (p2[0] - tx*ah, p2[1] - ty*ah)
    a1 = (base[0] + px*ah*0.5, base[1] + py*ah*0.5)
    a2 = (base[0] - px*ah*0.5, base[1] - py*ah*0.5)
    draw.polygon([p2, a1, a2], fill=fill)

canvas = Image.new('RGBA', (CW, CH), (255,255,255,255))
draw = ImageDraw.Draw(canvas)

# Wall surface — soft warm off-white
wall_color = (243, 238, 228)
wall_outline = (170, 160, 142)
wall_left, wall_top = 280*RS, 150*RS
wall_right, wall_bot = 1320*RS, 730*RS
draw.rectangle([wall_left, wall_top, wall_right, wall_bot], fill=wall_color,
               outline=wall_outline, width=int(2.5*RS))

# Subtle baseboard suggesting "wall"
baseboard_h = 18*RS
draw.rectangle([wall_left, wall_bot - baseboard_h, wall_right, wall_bot],
               fill=(225, 218, 205), outline=wall_outline, width=int(2.5*RS))

# ===== Framed artwork =====
pic_cx = 800 * RS
pic_top = 240 * RS
pic_w, pic_h = 340*RS, 260*RS
pic_left = pic_cx - pic_w//2
pic_right = pic_cx + pic_w//2
pic_bot = pic_top + pic_h

# Outer frame (dark wood)
frame_thickness = 20*RS
frame_color = (105, 72, 45)
draw.rectangle([pic_left, pic_top, pic_right, pic_bot],
               fill=frame_color, outline=(55, 35, 20), width=int(2*RS))

# Inner art area
art_left = pic_left + frame_thickness
art_top  = pic_top  + frame_thickness
art_right = pic_right - frame_thickness
art_bot   = pic_bot   - frame_thickness
draw.rectangle([art_left, art_top, art_right, art_bot],
               fill=(252, 248, 238), outline=(55,35,20), width=int(1.5*RS))

# Simple landscape inside the art
horizon_y = art_top + int((art_bot - art_top) * 0.62)
# Sky band
draw.rectangle([art_left, art_top, art_right, horizon_y], fill=(214, 232, 244))
# Ground band
draw.rectangle([art_left, horizon_y, art_right, art_bot], fill=(192, 213, 173))
# Sun
sun_r = 18*RS
sun_cx = art_right - 42*RS
sun_cy = art_top + 50*RS
draw.ellipse([sun_cx-sun_r, sun_cy-sun_r, sun_cx+sun_r, sun_cy+sun_r],
             fill=(255, 218, 135), outline=(220, 175, 95), width=int(1.5*RS))
# Mountains
mt_w = art_right - art_left
m1 = [(art_left + 40*RS, horizon_y),
      (art_left + int(mt_w*0.35), horizon_y - 70*RS),
      (art_left + int(mt_w*0.55), horizon_y)]
m2 = [(art_left + int(mt_w*0.45), horizon_y),
      (art_left + int(mt_w*0.68), horizon_y - 95*RS),
      (art_left + int(mt_w*0.92), horizon_y)]
draw.polygon(m1, fill=(132, 110, 92))
draw.polygon(m2, fill=(95, 80, 68))
# Tiny snow caps
sc1_top = (art_left + int(mt_w*0.35), horizon_y - 70*RS)
sc1 = [(sc1_top[0]-18*RS, sc1_top[1]+18*RS), sc1_top, (sc1_top[0]+18*RS, sc1_top[1]+18*RS)]
draw.polygon(sc1, fill=(245, 245, 245))
sc2_top = (art_left + int(mt_w*0.68), horizon_y - 95*RS)
sc2 = [(sc2_top[0]-22*RS, sc2_top[1]+22*RS), sc2_top, (sc2_top[0]+22*RS, sc2_top[1]+22*RS)]
draw.polygon(sc2, fill=(250, 250, 250))

# ===== Pencil mark on wall (bottom edge exactly at the frame's top) =====
mark_w = 36*RS
mark_h = 3*RS
mark_y_top = pic_top - mark_h
mark_y_bot = pic_top  # bottom edge sits exactly on the frame's top line
draw.rectangle([pic_cx - mark_w/2, mark_y_top, pic_cx + mark_w/2, mark_y_bot],
               fill=(70, 70, 70))
# Tiny downward "alignment tick" at each end of the mark, crossing into the frame's top outline,
# to visually anchor the mark to the frame top edge.
tick_h = 6*RS
for tx in (pic_cx - mark_w/2, pic_cx + mark_w/2):
    draw.line([(tx, mark_y_top - 2*RS), (tx, pic_top + 4*RS)],
              fill=(70, 70, 70), width=int(2*RS))

# ===== Pencil graphic above the mark =====
def draw_pencil(draw, tip, length, angle_deg, body_color=(240, 195, 70), eraser_color=(220, 100, 90),
                tip_color=(40, 30, 20), wood_color=(225, 200, 150)):
    """Pencil pointing toward `tip`, body extends `length` away at `angle_deg` from tip."""
    a = math.radians(angle_deg)
    dx, dy = math.cos(a), math.sin(a)
    # Width perpendicular to length
    px, py = -dy, dx
    width = 18*RS
    half_w = width/2
    # Tip cone: from tip back by tip_len along axis
    tip_len = 28*RS
    cone_base = (tip[0] - dx*tip_len, tip[1] - dy*tip_len)
    cone_l = (cone_base[0] + px*half_w, cone_base[1] + py*half_w)
    cone_r = (cone_base[0] - px*half_w, cone_base[1] - py*half_w)
    # Wood section (lighter ring) between cone and body
    wood_len = 14*RS
    wood_base = (cone_base[0] - dx*wood_len, cone_base[1] - dy*wood_len)
    wood_tl = (cone_base[0] + px*half_w, cone_base[1] + py*half_w)
    wood_tr = (cone_base[0] - px*half_w, cone_base[1] - py*half_w)
    wood_bl = (wood_base[0] + px*half_w, wood_base[1] + py*half_w)
    wood_br = (wood_base[0] - px*half_w, wood_base[1] - py*half_w)
    # Body section (the main yellow part)
    body_len = length - tip_len - wood_len - 18*RS  # reserve last 18 for ferrule + eraser
    body_end = (wood_base[0] - dx*body_len, wood_base[1] - dy*body_len)
    body_tl = wood_bl
    body_tr = wood_br
    body_bl = (body_end[0] + px*half_w, body_end[1] + py*half_w)
    body_br = (body_end[0] - px*half_w, body_end[1] - py*half_w)
    # Ferrule (metal band)
    ferrule_len = 10*RS
    ferrule_end = (body_end[0] - dx*ferrule_len, body_end[1] - dy*ferrule_len)
    f_tl = body_bl
    f_tr = body_br
    f_bl = (ferrule_end[0] + px*half_w, ferrule_end[1] + py*half_w)
    f_br = (ferrule_end[0] - px*half_w, ferrule_end[1] - py*half_w)
    # Eraser
    eraser_len = 16*RS
    eraser_end = (ferrule_end[0] - dx*eraser_len, ferrule_end[1] - dy*eraser_len)
    e_tl = f_bl
    e_tr = f_br
    e_bl = (eraser_end[0] + px*half_w, eraser_end[1] + py*half_w)
    e_br = (eraser_end[0] - px*half_w, eraser_end[1] - py*half_w)

    # Draw layers (back to front)
    # Tip (cone)
    draw.polygon([tip, cone_l, cone_r], fill=tip_color, outline=(20,15,10))
    # Wood ring
    draw.polygon([wood_tl, wood_tr, wood_br, wood_bl], fill=wood_color, outline=(120,100,70))
    # Body
    draw.polygon([body_tl, body_tr, body_br, body_bl], fill=body_color, outline=(150,120,40))
    # Ferrule
    draw.polygon([f_tl, f_tr, f_br, f_bl], fill=(180,180,185), outline=(110,110,115))
    # Eraser
    draw.polygon([e_tl, e_tr, e_br, e_bl], fill=eraser_color, outline=(140,60,60))
    # Outline whole pencil
    outline_poly = [tip, cone_l, wood_tl, body_tl, f_tl, e_tl, e_bl, f_bl, body_bl, wood_bl, cone_r]
    draw.line(outline_poly + [tip], fill=(40,30,20), width=int(1.5*RS), joint='curve')

# Place pencil with tip touching the mark on the wall (angled up-right)
pencil_tip = (pic_cx + mark_w/2 - 2*RS, mark_y_top + mark_h/2)
draw_pencil(draw, pencil_tip, length=210*RS, angle_deg=-32)  # -32° = pointing up-right slightly

# ===== Annotations =====
# Label: "Light pencil mark at top of frame" — pointing to the mark
note_x1 = 1180*RS
note_y1 = 280*RS
draw.text((note_x1, note_y1), 'Light pencil mark',
          font=font(int(22*RS), bold=True), fill='black', anchor='lm')
draw.text((note_x1, note_y1 + 32*RS), 'at the very top of the frame',
          font=font(int(17*RS)), fill='black', anchor='lm')
# Bezier arrow from text to mark
bezier(draw,
       p0=(note_x1 - 8*RS, note_y1 + 18*RS),
       p1=(note_x1 - 140*RS, note_y1 - 50*RS),
       p2=(pic_cx + mark_w/2 + 10*RS, mark_y_top - 6*RS),
       width=int(3*RS), fill=(50,50,50))

# Label: "Hold the artwork in the desired position" — pointing to the picture
note_x2 = 420*RS
note_y2 = 460*RS
draw.text((note_x2, note_y2), 'Hold the artwork',
          font=font(int(22*RS), bold=True), fill='black', anchor='rm')
draw.text((note_x2, note_y2 + 32*RS), 'in your desired position',
          font=font(int(17*RS)), fill='black', anchor='rm')
# Curved arrow to the picture
bezier(draw,
       p0=(note_x2 + 8*RS, note_y2 + 18*RS),
       p1=(note_x2 + 120*RS, note_y2 + 70*RS),
       p2=(pic_left - 8*RS, pic_top + pic_h//2),
       width=int(3*RS), fill=(50,50,50))

# ===== Title / subtitle / caption / version badge =====
bx, by, bw, bh = 24*RS, 24*RS, 96*RS, 36*RS
draw.rectangle([bx, by, bx+bw, by+bh], outline='black', width=int(2.5*RS))
draw.text((bx+bw/2, by+bh/2), 'v2', font=font(int(19*RS), bold=True),
          fill='black', anchor='mm')

draw.text((CW/2, 35*RS), 'Picture Perfect — Step 3',
          font=font(int(32*RS), bold=True), fill='black', anchor='mm')
draw.text((CW/2, 75*RS),
          'Hold the artwork in position. Make a light pencil mark at the very top of the frame.',
          font=font(int(20*RS)), fill='black', anchor='mm')

draw.text((CW/2, 780*RS),
          'The mark records the desired top edge of the frame on the wall.',
          font=font(int(17*RS)), fill='black', anchor='mm')
draw.text((CW/2, CH - 25*RS), 'Picture Perfect · Step 3 of N · v2',
          font=font(int(13*RS)), fill=(85,85,85), anchor='mm')

# ===== Save (downsample) =====
fw, fh = CW // RS, CH // RS
final = canvas.resize((fw, fh), Image.LANCZOS)
final.convert('RGB').save(f'{ROOT}/step_03_pencil_mark.png', 'PNG', optimize=True)
print(f'Saved step_03_pencil_mark.png ({fw}x{fh})')

hi = canvas.resize((fw*2, fh*2), Image.LANCZOS)
hi.convert('RGB').save(f'{ROOT}/step_03_pencil_mark@2x.png', 'PNG', optimize=True)
print(f'Saved step_03_pencil_mark@2x.png ({fw*2}x{fh*2})')
