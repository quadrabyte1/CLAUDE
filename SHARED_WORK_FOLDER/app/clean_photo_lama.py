"""
House photo cleanup using LaMa inpainting.
Processes at 512px (LaMa's native training resolution) for best quality.
Multi-pass: isolated objects first, large areas second.
"""
import os
os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'

from simple_lama_inpainting import SimpleLama
from PIL import Image, ImageDraw

lama = SimpleLama()

# LaMa native resolution — best quality at this size
PROC_W, PROC_H = 512, 384

def p(fx, fy):
    return (int(fx * PROC_W), int(fy * PROC_H))

def make_mask(polygons):
    mask = Image.new("L", (PROC_W, PROC_H), 0)
    draw = ImageDraw.Draw(mask)
    for poly in polygons:
        draw.polygon(poly, fill=255)
    return mask

def run_pass(image_proc, polygons):
    mask = make_mask(polygons)
    return lama(image_proc, mask)

def process(src_path, out_path, *passes):
    """Process image through one or more inpainting passes."""
    print(f"\nProcessing {src_path} ...")
    image = Image.open(src_path).convert("RGB")
    orig_w, orig_h = image.size
    current = image.resize((PROC_W, PROC_H), Image.LANCZOS)

    for i, polys in enumerate(passes, 1):
        print(f"  Pass {i} ({len(polys)} masks)...")
        current = run_pass(current, polys)

    result = current.resize((orig_w, orig_h), Image.LANCZOS)
    result.save(out_path, quality=92)
    print(f"  -> {out_path}")


BASE = "/Users/fourierflight/GIT/CLAUDE-GitHub/SHARED_WORK_FOLDER"


# ═══════════════════════════════════════════════════════════════════
# IMG_1075 — PATIO SIDE VIEW
# At 512x384:
#   Dog:         x=31-51%, y=76-100%
#   Debris pile: x=40-90%, y=50-98%   (storm window, chairs, boards)
#   Grill:       x=83-100%, y=42-84%
#   Blue tarp:   x=2-17%, y=44-68%   (porch left)
#   Lumber:      x=13-37%, y=40-66%  (porch steps)
#   White hoop:  x=0-7%, y=60-72%
#   Porch clutter visible through railing: x=10-35%, y=44-62%
# ═══════════════════════════════════════════════════════════════════
polys_1075 = [
    # Dog
    [p(.31,.77), p(.51,.76), p(.53,.88), p(.48,1.0), p(.28,1.0), p(.26,.87)],
    # Main debris pile (storm window, chairs, boards, cardboard)
    [p(.40,.50), p(.88,.48), p(.90,.62), p(.86,.96),
     p(.52,.98), p(.38,.92), p(.37,.68)],
    # Grill far right
    [p(.83,.42), p(.99,.42), p(1.0,.56), p(1.0,.84),
     p(.85,.86), p(.81,.62)],
    # Blue tarp/bag on porch
    [p(.02,.44), p(.17,.43), p(.18,.61), p(.14,.69), p(.01,.69)],
    # Lumber on porch steps
    [p(.13,.40), p(.37,.38), p(.38,.58), p(.33,.66), p(.11,.65)],
    # White hoop far left
    [p(0,.60), p(.07,.58), p(.08,.72), p(0,.73)],
    # Bottom-right stone/debris remnant
    [p(.72,.88), p(1.0,.88), p(1.0,1.0), p(.70,1.0)],
]


# ═══════════════════════════════════════════════════════════════════
# IMG_1076 — STRAIGHT-ON REAR VIEW
# Pass 1: dog, ladder, porch items, far-right clutter
# Pass 2: grill + bucket, right foreground
# Pass 3: large left pile, diagonal board, tarp bundle
# ═══════════════════════════════════════════════════════════════════
p1076_pass1 = [
    # Dog on porch steps
    [p(.25,.51), p(.39,.49), p(.40,.63), p(.37,.70),
     p(.23,.70), p(.22,.57)],
    # Orange ladder on porch railing
    [p(.35,.37), p(.46,.35), p(.48,.54), p(.44,.61),
     p(.33,.59), p(.32,.44)],
    # Items behind porch railing center-right
    [p(.43,.39), p(.65,.37), p(.67,.55), p(.62,.59),
     p(.41,.58), p(.40,.45)],
    # Far-right misc items
    [p(.85,.61), p(1.0,.59), p(1.0,.85), p(.83,.87), p(.81,.73)],
]

p1076_pass2 = [
    # Grill center
    [p(.46,.57), p(.63,.55), p(.65,.68), p(.63,.83),
     p(.47,.85), p(.43,.71)],
    # Bucket + bags center patio
    [p(.41,.70), p(.59,.68), p(.61,.83), p(.57,.91),
     p(.39,.91), p(.37,.78)],
    # Right foreground clutter
    [p(.69,.59), p(.89,.57), p(.91,.75), p(.87,.91),
     p(.67,.91), p(.65,.74)],
]

p1076_pass3 = [
    # Diagonal plank across patio (shorter — only actual board)
    [p(.03,.69), p(.36,.63), p(.38,.71), p(.05,.77)],
    # Green tarp bundle center-left
    [p(.24,.59), p(.48,.57), p(.50,.70), p(.45,.87),
     p(.26,.89), p(.22,.76)],
    # Stacked wood/deck boards — far left foreground
    [p(0,.60), p(.32,.58), p(.34,.72), p(.29,.92), p(0,.94)],
]


# ═══════════════════════════════════════════════════════════════════
# IMG_1077 — ANGLED REAR VIEW
# Pass 1: dog, wood pile on porch, metal arch, watering can
# Pass 2: scattered debris, tarp bundle
# Pass 3: trash cans left
# ═══════════════════════════════════════════════════════════════════
p1077_pass1 = [
    # Dog on porch steps
    [p(.43,.52), p(.56,.50), p(.58,.64), p(.54,.70),
     p(.41,.68), p(.41,.58)],
    # Wood pile / items on porch
    [p(.50,.36), p(.63,.32), p(.65,.48), p(.61,.57),
     p(.47,.57), p(.45,.44)],
    # Metal garden arch (center)
    [p(.34,.40), p(.48,.37), p(.51,.52), p(.49,.64),
     p(.43,.68), p(.36,.64), p(.32,.50)],
    # Green watering can + misc items right side
    [p(.77,.53), p(.89,.51), p(.91,.64), p(.87,.74),
     p(.75,.74), p(.73,.62)],
]

p1077_pass2 = [
    # Scattered debris on patio center
    [p(.25,.70), p(.51,.66), p(.53,.78), p(.49,.89),
     p(.23,.91), p(.21,.80)],
    # Green tarp bundle left-center
    [p(.05,.64), p(.31,.60), p(.35,.72), p(.31,.85),
     p(.07,.87), p(.03,.74)],
]

p1077_pass3 = [
    # Trash cans far left
    [p(0,.55), p(.15,.53), p(.17,.70), p(.13,.83), p(0,.85)],
]


# ═══════════════════════════════════════════════════════════════════
# IMG_1078 — PORCH CLOSE-UP (angled)
# Pass 1: dog, trash can, storm window, porch clutter, step base items
# Pass 2: large lumber pile
# ═══════════════════════════════════════════════════════════════════
p1078_pass1 = [
    # Dog — lower center
    [p(.31,.66), p(.50,.64), p(.54,.78), p(.50,.93),
     p(.29,.95), p(.27,.80)],
    # Blue trash can left
    [p(.09,.54), p(.22,.52), p(.24,.68), p(.20,.75),
     p(.07,.75), p(.06,.60)],
    # Storm window right of porch steps
    [p(.57,.28), p(.74,.26), p(.77,.43), p(.75,.63),
     p(.60,.65), p(.53,.49), p(.53,.34)],
    # Porch clutter above railing (chairs/items — left of column)
    [p(.55,.33), p(.83,.29), p(.85,.51), p(.80,.63),
     p(.55,.65), p(.51,.48)],
    # Items at porch steps base
    [p(.45,.60), p(.63,.58), p(.65,.72), p(.60,.81),
     p(.43,.81), p(.41,.70)],
]

p1078_pass2 = [
    # Large lumber/debris pile bottom-left foreground
    [p(0,.57), p(.47,.55), p(.51,.70), p(.44,.89), p(0,.93)],
]


# ─── Run all 4 ───────────────────────────────────────────────────
process(
    f"{BASE}/team_inbox/IMG_1075 2.JPG",
    f"{BASE}/owner_inbox/house_clean_patio.jpg",
    polys_1075,            # single pass — all objects at 512px
)

process(
    f"{BASE}/team_inbox/IMG_1076 2.JPG",
    f"{BASE}/owner_inbox/house_clean_rear.jpg",
    p1076_pass1,
    p1076_pass2,
    p1076_pass3,
)

process(
    f"{BASE}/team_inbox/IMG_1077 2.JPG",
    f"{BASE}/owner_inbox/house_clean_angle.jpg",
    p1077_pass1,
    p1077_pass2,
    p1077_pass3,
)

process(
    f"{BASE}/team_inbox/IMG_1078.JPG",
    f"{BASE}/owner_inbox/house_clean_porch.jpg",
    p1078_pass1,
    p1078_pass2,
)

print("\nAll 4 images complete.")
