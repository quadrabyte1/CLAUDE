"""
Patio Mockup Compositor — Cass, Architectural Visualization Specialist
======================================================================
Composites a proposed ground-level bluestone patio onto four "house_clean"
photos of Thomas's house.

Patio specification:
  - 20 feet deep x 20 feet wide, at grade level (no raised structure)
  - Picture frame border: ~1 ft real-world width, darker charcoal color
  - Field pavers: blue-gray bluestone color running one direction
  - Border pavers: darker charcoal/slate, running perpendicular
  - Contact shadow at house foundation
  - Does NOT encroach on the driveway (right side in patio/angle views)

Images are all 5712 x 4284 pixels.

Pipeline per photo:
  1. Load source photo
  2. Define perspective quad for the patio ground plane
  3. Draw field pavers with grid lines
  4. Draw picture frame border around perimeter
  5. Add contact shadow at house wall
  6. Blend edges and composite
  7. Label and save
"""

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
import os

# ─── CONFIGURATION ────────────────────────────────────────────────────

WORKING_DIR = "/Users/fourierflight/GIT/CLAUDE-GitHub/SHARED_WORK_FOLDER"
INPUT_DIR = os.path.join(WORKING_DIR, "owner_inbox")
OUTPUT_DIR = os.path.join(WORKING_DIR, "owner_inbox")

# Bluestone patio colors
FIELD_COLOR   = (140, 148, 155)   # blue-gray stone (field pavers)
BORDER_COLOR  = ( 85,  90,  95)   # darker charcoal/slate (picture frame border)
FIELD_JOINT   = (105, 110, 115)   # joint lines — darker for more contrast against field
BORDER_JOINT  = ( 65,  68,  72)   # joint lines between border pavers — dark for visibility
SHADOW_COLOR  = (  0,   0,   0)   # black, applied at low alpha

LABEL_TEXT = "Proposed 20'×20' Bluestone Patio"

# ─── GEOMETRY HELPERS ─────────────────────────────────────────────────

def lerp_point(p1, p2, t):
    """Linear interpolation between two 2-D points."""
    return (int(p1[0] + (p2[0] - p1[0]) * t),
            int(p1[1] + (p2[1] - p1[1]) * t))


def draw_filled_quad(draw, corners, color):
    """Draw a filled convex quadrilateral."""
    draw.polygon(corners, fill=color)


def draw_line_thick(draw, p1, p2, color, width=2):
    draw.line([p1, p2], fill=color, width=width)


def lerp4(tl, tr, br, bl, u, v):
    """
    Bilinear interpolation inside a quad.
    u in [0,1] = left→right, v in [0,1] = top→bottom (far→near).
    """
    top = lerp_point(tl, tr, u)
    bot = lerp_point(bl, br, u)
    return lerp_point(top, bot, v)


# ─── PATIO DRAWING ────────────────────────────────────────────────────

def draw_patio(draw, patio_quad, border_frac=0.05, field_rows=18, field_cols=18):
    """
    Draw the full patio surface on `draw`.

    patio_quad: [far_left, far_right, near_right, near_left]
                (the four corners of the patio ground plane in perspective)
    border_frac: fraction of the patio width/depth that the border occupies
                 (1 ft out of 20 ft = 0.05)
    field_rows, field_cols: number of paver grid lines in the field
    """
    tl, tr, br, bl = patio_quad

    # ── 1. Fill entire patio with field color (base) ──
    draw_filled_quad(draw, [tl, tr, br, bl], FIELD_COLOR)

    # ── 2. Draw picture frame border ──
    # Border is defined by four inner corners offset inward by border_frac
    bf = border_frac
    # Inner quad corners (bilinear interpolation)
    inner_tl = lerp4(tl, tr, br, bl, bf,      bf)
    inner_tr = lerp4(tl, tr, br, bl, 1 - bf,  bf)
    inner_br = lerp4(tl, tr, br, bl, 1 - bf,  1 - bf)
    inner_bl = lerp4(tl, tr, br, bl, bf,       1 - bf)

    # Draw border as four trapezoids (top, right, bottom, left strips)
    # Top strip  (far edge, at house wall)
    draw_filled_quad(draw, [tl, tr, inner_tr, inner_tl], BORDER_COLOR)
    # Bottom strip (near edge, toward yard)
    draw_filled_quad(draw, [inner_bl, inner_br, br, bl], BORDER_COLOR)
    # Left strip
    draw_filled_quad(draw, [tl, inner_tl, inner_bl, bl], BORDER_COLOR)
    # Right strip
    draw_filled_quad(draw, [inner_tr, tr, br, inner_br], BORDER_COLOR)

    # ── 3. Border joint lines ──
    # Top border — vertical joints running perpendicular (picture-frame direction)
    n_border_horiz = 8
    for i in range(1, n_border_horiz):
        t = i / n_border_horiz
        p1 = lerp_point(tl, tr, t)
        p2 = lerp_point(inner_tl, inner_tr, t)
        draw_line_thick(draw, p1, p2, BORDER_JOINT, width=4)
    # Bottom border — vertical joints perpendicular
    for i in range(1, n_border_horiz):
        t = i / n_border_horiz
        p1 = lerp_point(inner_bl, inner_br, t)
        p2 = lerp_point(bl, br, t)
        draw_line_thick(draw, p1, p2, BORDER_JOINT, width=4)
    # Left border — horizontal joints running across the strip
    n_border_vert = 6
    for i in range(1, n_border_vert):
        t = i / n_border_vert
        p1 = lerp4(tl, tr, br, bl, 0,  t)   # left edge at this depth
        p2 = lerp4(tl, tr, br, bl, bf, t)   # inner-left edge at this depth
        draw_line_thick(draw, p1, p2, BORDER_JOINT, width=4)
    # Right border — horizontal joints
    for i in range(1, n_border_vert):
        t = i / n_border_vert
        p1 = lerp4(tl, tr, br, bl, 1 - bf, t)
        p2 = lerp4(tl, tr, br, bl, 1,       t)
        draw_line_thick(draw, p1, p2, BORDER_JOINT, width=4)

    # Corner joints — diagonal lines at corners to close the border miters
    # (just draw the outline edges of each border strip at corners)

    # ── 4. Field paver grid (inside the inner quad) ──
    # Horizontal running bond lines (parallel to house, running left-right)
    for i in range(1, field_rows):
        t = i / field_rows
        p1 = lerp_point(inner_tl, inner_bl, t)
        p2 = lerp_point(inner_tr, inner_br, t)
        draw_line_thick(draw, p1, p2, FIELD_JOINT, width=4)

    # Vertical lines (running far-to-near, perpendicular to house)
    for i in range(1, field_cols):
        t = i / field_cols
        p1 = lerp_point(inner_tl, inner_tr, t)
        p2 = lerp_point(inner_bl, inner_br, t)
        draw_line_thick(draw, p1, p2, FIELD_JOINT, width=4)

    # ── 5. Border outline strokes (crisp edges between field and border) ──
    line_w = 5
    draw_line_thick(draw, inner_tl, inner_tr, BORDER_JOINT, width=line_w)
    draw_line_thick(draw, inner_tr, inner_br, BORDER_JOINT, width=line_w)
    draw_line_thick(draw, inner_br, inner_bl, BORDER_JOINT, width=line_w)
    draw_line_thick(draw, inner_bl, inner_tl, BORDER_JOINT, width=line_w)

    # ── 6. Outer patio edge highlight/shadow (slight brightening on outer face) ──
    # A thin light line along near edge to suggest a slight thickness edge
    edge_color = (160, 165, 170)
    draw_line_thick(draw, bl, br, edge_color, width=4)

    return inner_tl, inner_tr, inner_br, inner_bl


def draw_contact_shadow(overlay, house_edge_left, house_edge_right, depth_px=40):
    """
    Draw a contact shadow along the house wall where the patio meets the foundation.
    Gradient from dark at the wall to transparent outward.
    """
    shadow_draw = ImageDraw.Draw(overlay)
    steps = 12
    for i in range(steps):
        t0 = i / steps
        t1 = (i + 1) / steps
        alpha = int(120 * (1 - t0))  # dark near wall, fades out
        # Shadow strip in perspective: parallel to house wall
        # house_edge_left and house_edge_right are the top-left and top-right of the patio
        # (where it meets the house), patio extends downward
        tl = lerp_point(house_edge_left,  (house_edge_left[0],  house_edge_left[1]  + depth_px), t0)
        tr = lerp_point(house_edge_right, (house_edge_right[0], house_edge_right[1] + depth_px), t0)
        bl = lerp_point(house_edge_left,  (house_edge_left[0],  house_edge_left[1]  + depth_px), t1)
        br = lerp_point(house_edge_right, (house_edge_right[0], house_edge_right[1] + depth_px), t1)
        shadow_draw.polygon([tl, tr, br, bl], fill=(0, 0, 0, alpha))


def add_label(draw, position, text, font_size=60):
    """Add a text label with a white semi-transparent background."""
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", font_size)
    except Exception:
        font = ImageFont.load_default()
    bbox = draw.textbbox(position, text, font=font)
    pad = 14
    draw.rectangle(
        [bbox[0] - pad, bbox[1] - pad, bbox[2] + pad, bbox[3] + pad],
        fill=(255, 255, 255, 210)
    )
    draw.text(position, text, fill=(30, 35, 40), font=font)


# ─── PHOTO-SPECIFIC GEOMETRY ──────────────────────────────────────────
# All images are 5712 × 4284 pixels.
# Quads are defined as [far_left, far_right, near_right, near_left]
# "far" = at the house wall (top of the patio in image)
# "near" = front edge of patio (toward yard / camera)
#
# Ground plane analysis:
#   rear:  Straight-on. House base/foundation visible center.
#          Grade level runs roughly y=2850-3100 across the frame center.
#          Patio will span from x≈1600 to x≈3900 (house width), extending
#          ~480px downward from the foundation line (representing 20ft depth).
#          No perspective skew needed — nearly orthographic.
#
#   patio: Right-side angle view. Camera is low, to the right of the house.
#          Existing flagstone runs from house out toward camera-left.
#          Driveway/road visible at far left (curb at x≈150, y≈3800).
#          Patio must NOT extend left of x≈700 at bottom of frame.
#          The patio right edge aligns with where the fence/yard ends before
#          the driveway.
#
#   angle: Back-left corner. Camera looking right-ish.
#          House left corner is at roughly x=2200, porch visible at center-left.
#          Patio runs from the house foundation rightward into the yard.
#          Right side stops well before the far right of frame.
#
#   porch: Side view. House/porch on left side of frame.
#          Patio would be visible in the foreground/midground.
#          Ground level is near y=3200-3500 across the frame.

def get_geometry_rear():
    """
    house_clean_rear.jpg — straight-on rear view.
    Image 5712 x 4284.
    House back wall spans roughly x=1550 to x=4050.
    Foundation/grade line at roughly y=2650 (base of the foundation brick/siding).
    Patio extends outward (downward in image) from there.
    At grade level the perspective compression is slight — nearly ortho.
    The existing furniture/clutter sits ON the patio; patio top edge meets foundation.
    """
    # Rear view — nearly orthographic, camera straight on.
    # The foundation/grade line where siding meets ground is at approx y=3100.
    # The items (chairs, bucket) on the ground sit at y=3200-3600.
    # The patio top edge must be at the foundation/grade line, not up the wall.
    # Near edge at y=3900 (representing ~20ft depth from house).
    # Left/right: house wall spans roughly x=1700 to x=4100.
    # Very slight perspective taper (wider near than far) for straight-on view.
    # Rear view — straight-on. The house foundation visibly meets the ground
    # at around y=3250 (below the porch deck underside, at the base of the
    # brick foundation wall). The yard/clutter sits at y=3300-3800.
    # Near edge at y=4100 to show full 20ft depth.
    patio_quad = [
        (1720, 3250),   # far_left   (house foundation meets grade, left)
        (4080, 3250),   # far_right  (house foundation meets grade, right)
        (4350, 4100),   # near_right (front edge, right — 20ft depth)
        (1450, 4100),   # near_left  (front edge, left — 20ft depth)
    ]
    contact_shadow_depth = 60   # pixels for shadow gradient

    return {
        'patio_quad': patio_quad,
        'contact_shadow_depth': contact_shadow_depth,
        'border_frac': 0.05,   # 1ft / 20ft = 0.05
        'field_rows': 17,
        'field_cols': 17,
        'label_pos': (120, 110),
        'foreground_masks': [],
    }


def get_geometry_patio():
    """
    house_clean_patio.jpg — angle view from right, showing existing stone area.
    Image 5712 x 4284.
    Camera is positioned to the right of the house, looking left-ish.
    House porch is on the left side of the image.
    Existing flagstone runs across the foreground.
    Driveway/road is at the BOTTOM-LEFT (curb at roughly x=250, y=4000+).

    Looking at the image:
    - House left edge of patio: x≈650, y≈2500 (far left)
    - House right edge (where patio ends near fence): x≈2200, y≈2200 (far right)
    - Near right (front, no driveway): x≈3200, y≈3400
    - Near left MUST stop before driveway: x≈1000, y≈3600

    The driveway is at the very bottom-left; keeping near_left at x≈900
    ensures we clear it well.
    """
    # patio (side angle) view: camera is to the right-front, looking left-back.
    # The existing flagstone is the ground plane — it runs from near the porch
    # column base (far-left at low angle) across to the right.
    # The flagstone surface in the image:
    #   - At the house/porch column: x≈530, y≈2900 (full res)
    #   - Along house wall going right: rises to x≈2200, y≈2650
    #   - Near-right (front of flagstone area): x≈3300, y≈3500
    #   - Near-left (front, near driveway): x≈1400, y≈3650
    # The driveway curb is at bottom-left; keep near_left x > 1300.
    # Critically: far_left y must be at the flagstone surface, NOT up the wall.
    # Patio (side angle) view: camera right-front, looking left-back at house.
    # The existing flagstone surface in the photo:
    #   far-left corner (where house meets flagstone): x≈480, y≈3050
    #   far-right corner (right end along house): x≈2100, y≈2800
    #   near-right (front of flagstone, right): x≈3200, y≈3650
    #   near-left (front left, driveway is bottom-left): x≈1300, y≈3850
    patio_quad = [
        ( 480, 3050),   # far_left   (porch column base at flagstone grade)
        (2100, 2800),   # far_right  (right end along house wall at grade)
        (3200, 3650),   # near_right (front edge right)
        (1300, 3850),   # near_left  (front edge left — clear of driveway)
    ]
    contact_shadow_depth = 80

    return {
        'patio_quad': patio_quad,
        'contact_shadow_depth': contact_shadow_depth,
        'border_frac': 0.05,
        'field_rows': 16,
        'field_cols': 16,
        'label_pos': (200, 140),
        'foreground_masks': [],
    }


def get_geometry_angle():
    """
    house_clean_angle.jpg — back-left corner view.
    Image 5712 x 4284.
    Camera is positioned to the back-left, looking at the right side of the house.
    House left corner is roughly at x=2100, the back-right corner goes off right edge.
    Porch/door area is visible in the center.

    Ground plane:
    - far_left (house wall, left side): x≈2100, y≈2700
    - far_right (house wall, right extent): x≈5000, y≈2500
    - near_right: x≈5200, y≈3400
    - near_left: x≈1800, y≈3500

    The patio must not extend past the fence on the left.
    """
    # angle (back-left corner) view: camera looking right toward house.
    # House left corner is at x≈2200. Porch/door area visible center-left.
    # Grass/ground is clearly visible on the right at y≈3400+.
    # The base of the house foundation meets grade at approx y=3300 on left,
    # y=3100 on right (perspective). Bushes/shrubs are FOREGROUND objects
    # that will partially cover the left side of the patio — we place the
    # patio behind them.
    # Far edge: where house foundation meets grade (not up the wall).
    # Near edge: toward camera, across the grass.
    # Angle (back-left corner) view: camera looks right.
    # The grass/ground on the right is at y≈3500+. The bushes/shrubs occupy
    # the middle of the frame as foreground. The house foundation meets grade
    # at approx y=3500 on the left side (due to perspective/slope), y=3350
    # on the right. The patio must sit flat on this ground plane below the
    # bushes — bushes will naturally overlap the top portion of the patio.
    patio_quad = [
        (2500, 3550),   # far_left   (house foundation, left — below bushes)
        (5150, 3300),   # far_right  (house wall right, at grade)
        (5500, 4100),   # near_right (front edge right, on grass)
        (2100, 4200),   # near_left  (front edge left)
    ]
    contact_shadow_depth = 70

    return {
        'patio_quad': patio_quad,
        'contact_shadow_depth': contact_shadow_depth,
        'border_frac': 0.05,
        'field_rows': 15,
        'field_cols': 15,
        'label_pos': (150, 120),
        'foreground_masks': [],
    }


def get_geometry_porch():
    """
    house_clean_porch.jpg — side view of covered porch, looking at house from yard.
    Image 5712 x 4284.
    House/porch is on the RIGHT side of the frame (the porch columns are visible).
    Camera is at roughly yard level, looking across toward the porch.

    Ground plane for patio (foreground):
    - This is a side/oblique view. The patio would appear in the midground-foreground
      running across the bottom of the frame.
    - far edge (near house foundation): roughly y=3000, runs across x=1400 to x=5200
    - near edge (toward camera): y≈3800, x=1000 to x=5500

    The porch steps are on the right side; patio would connect to the porch area.
    """
    # porch view: camera looking at the porch from the yard (left side of frame
    # is yard, right side is porch). The fence runs across the midground at
    # approx y=2900-3100 full res. The patio is ON THE GROUND, behind the fence.
    # Ground level (where patio surface sits) is at y≈3300+ on right,
    # y≈3400+ on left. The fence/bushes at y=2900-3200 are foreground and
    # must occlude the patio (handled by foreground_mask in geometry).
    # Far edge of patio: at porch foundation/base, y≈3300 right, y≈3400 left.
    # Near edge: toward camera, y≈4000+.
    # The patio only appears in the lower portion of the frame below the fence.
    # Porch view: camera looks at the porch from the yard (left = yard, right = porch).
    # The fence top rail is at about y=2900. The patio ground is BEHIND the fence.
    # Porch column base/grade on right is at y≈3500. Ground on left at y≈3600.
    # The patio far edge (at porch wall) is around y=3450-3550.
    # Near edge (toward camera) extends to y=4200+.
    patio_quad = [
        (1000, 3600),   # far_left   (left extent, at grade behind fence)
        (5400, 3350),   # far_right  (porch column base at grade, right)
        (5712, 4200),   # near_right (front right edge, toward camera)
        (600,  4200),   # near_left  (front left edge)
    ]
    contact_shadow_depth = 60
    # Foreground mask: the fence and bushes (y < 3300 range) should occlude
    # the patio. We pass a foreground_cutoff_y to blank patio above this line.
    # In the compositor, any patio pixel above this Y will be masked out,
    # restoring the original photo (fence/bushes remain visible).
    # The fence bottom rail sits at approx y=3100-3200, so we mask patio
    # pixels that fall in the fence/bush zone by preserving original pixels
    # there. This is handled via foreground_mask polygon in composite_patio.

    # Foreground mask polygons: regions where original photo should show THROUGH
    # the patio (fence, bushes, and plants that are in front of the patio).
    # Coordinates in full-res 5712x4284 pixels.
    # The fence runs from the left edge to ~x=4800 at y≈2900-3300.
    # Bushes fill the midground left side from x=0 to ~x=3000 at y=2800-3400.
    # We define a broad polygon covering the fence+bush zone to mask out patio.
    foreground_masks = [
        # Fence and bush zone: this region spans the fence rail and shrub mass.
        # Runs across the image from left to right, following the bottom of
        # the fence/bush silhouette. The bottom of the mask follows the
        # fence bottom / bush bottom which slopes slightly.
        # This restores original photo pixels (fence, bushes) on top of patio.
        [
            (0,    2500),   # top-left (sky/above fence)
            (5712, 2500),   # top-right
            (5712, 3500),   # right side — fence meets grade on porch side
            (4000, 3500),   # porch side, bottom of rail area
            (2500, 3600),   # center, bottom of bush mass
            (1000, 3650),   # left-center, bush bottom
            (0,    3700),   # far left, bush bottom
        ],
    ]

    return {
        'patio_quad': patio_quad,
        'contact_shadow_depth': contact_shadow_depth,
        'border_frac': 0.05,
        'field_rows': 15,
        'field_cols': 15,
        'label_pos': (120, 110),
        'foreground_masks': foreground_masks,
    }


# ─── MAIN COMPOSITOR ──────────────────────────────────────────────────

def composite_patio(photo_path, geometry, output_path, label_text=""):
    """
    Full pipeline: load photo → draw patio → composite → save.
    """
    print(f"Loading {os.path.basename(photo_path)}...")
    img = Image.open(photo_path).convert("RGBA")
    w, h = img.size
    print(f"  Image: {w}x{h}")

    g = geometry
    patio_quad = g['patio_quad']
    tl, tr, br, bl = patio_quad  # far_left, far_right, near_right, near_left

    # ── Layer 1: Contact shadow at house wall ──
    shadow_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw_contact_shadow(shadow_layer, tl, tr, depth_px=g['contact_shadow_depth'])
    shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(radius=18))

    # ── Layer 2: Patio surface ──
    patio_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    patio_draw = ImageDraw.Draw(patio_layer)

    draw_patio(
        patio_draw,
        patio_quad,
        border_frac=g['border_frac'],
        field_rows=g['field_rows'],
        field_cols=g['field_cols'],
    )

    # ── Layer 3: Subtle forward shadow (patio casts slight shadow into yard) ──
    # A very faint dark strip just beyond the near edge (toward camera)
    fwd_shadow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    fwd_draw = ImageDraw.Draw(fwd_shadow)
    # Near edge of patio
    shadow_extend = 30
    fwd_near_l = (bl[0] - shadow_extend, bl[1] + shadow_extend)
    fwd_near_r = (br[0] + shadow_extend, br[1] + shadow_extend)
    fwd_draw.polygon([bl, br, fwd_near_r, fwd_near_l], fill=(0, 0, 0, 35))
    fwd_shadow = fwd_shadow.filter(ImageFilter.GaussianBlur(radius=20))

    # ── Composite all layers ──
    result = img.copy()

    # Apply forward shadow first (under patio)
    result = Image.alpha_composite(result, fwd_shadow)

    # Apply patio at ~90% opacity for slight realism/blending
    patio_arr = np.array(patio_layer)
    mask = patio_arr[:, :, 3] > 0
    patio_arr[mask, 3] = (patio_arr[mask, 3].astype(float) * 0.90).astype(np.uint8)
    patio_layer = Image.fromarray(patio_arr)
    result = Image.alpha_composite(result, patio_layer)

    # Apply contact shadow on top of patio (so it's visible on the patio surface)
    result = Image.alpha_composite(result, shadow_layer)

    # ── Foreground mask: restore original photo pixels where foreground objects
    #    (fences, bushes) should appear IN FRONT of the patio ──
    foreground_masks = g.get('foreground_masks', [])
    if foreground_masks:
        # Build a combined mask of all foreground regions
        fg_mask = Image.new("L", (w, h), 0)
        fg_mask_draw = ImageDraw.Draw(fg_mask)
        for poly in foreground_masks:
            fg_mask_draw.polygon(poly, fill=255)
        # Feather the mask edges slightly for natural blending
        fg_mask = fg_mask.filter(ImageFilter.GaussianBlur(radius=6))
        # Composite: where mask is white, use original photo; where black, keep result
        result_arr = np.array(result)
        orig_arr = np.array(img)
        mask_arr = np.array(fg_mask).astype(float) / 255.0
        for c in range(4):
            result_arr[:, :, c] = (
                orig_arr[:, :, c] * mask_arr +
                result_arr[:, :, c] * (1.0 - mask_arr)
            ).astype(np.uint8)
        result = Image.fromarray(result_arr)

    # ── Label ──
    if label_text:
        label_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        label_draw = ImageDraw.Draw(label_layer)
        add_label(label_draw, g['label_pos'], label_text, font_size=72)
        result = Image.alpha_composite(result, label_layer)

    # ── Slight blur on patio region to match photo DOF ──
    result_rgb = result.convert("RGB")
    blurred = result_rgb.filter(ImageFilter.GaussianBlur(radius=1.0))

    patio_mask = Image.new("L", (w, h), 0)
    mask_draw = ImageDraw.Draw(patio_mask)
    # Expand patio region slightly for mask
    expanded = [
        (tl[0] - 30, tl[1] - 30),
        (tr[0] + 30, tr[1] - 30),
        (br[0] + 30, br[1] + 30),
        (bl[0] - 30, bl[1] + 30),
    ]
    mask_draw.polygon(expanded, fill=180)
    patio_mask = patio_mask.filter(ImageFilter.GaussianBlur(radius=12))
    result_rgb.paste(blurred, mask=patio_mask)

    result_rgb.save(output_path, "JPEG", quality=93)
    print(f"  Saved: {output_path}")
    return output_path


def create_before_after(photo_path, mockup_path, output_path):
    """Create a side-by-side before/after comparison at half resolution."""
    original = Image.open(photo_path).convert("RGB")
    mockup   = Image.open(mockup_path).convert("RGB")

    w, h = original.size
    half_w = w // 2
    target_h = h // 2

    orig_small = original.resize((half_w, target_h), Image.LANCZOS)
    mock_small = mockup.resize((half_w, target_h), Image.LANCZOS)

    bar_h = 100
    combined = Image.new("RGB", (half_w * 2, target_h + bar_h), (245, 245, 245))
    draw = ImageDraw.Draw(combined)

    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 52)
        font_small = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 36)
    except Exception:
        font = ImageFont.load_default()
        font_small = font

    draw.text((half_w // 2 - 90, 18), "BEFORE", fill=(80, 80, 80), font=font)
    draw.text((half_w + half_w // 2 - 80, 18), "AFTER",  fill=(40, 80, 40), font=font)

    combined.paste(orig_small, (0, bar_h))
    combined.paste(mock_small, (half_w, bar_h))

    # Divider
    draw.line([(half_w, 0), (half_w, target_h + bar_h)], fill=(180, 180, 180), width=6)

    combined.save(output_path, "JPEG", quality=91)
    print(f"  Comparison: {output_path}")


# ─── RUN ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    photos = [
        {
            'src':    os.path.join(INPUT_DIR, "house_clean_rear.jpg"),
            'out':    os.path.join(OUTPUT_DIR, "patio_mockup_rear.jpg"),
            'ba':     os.path.join(OUTPUT_DIR, "patio_before_after_rear.jpg"),
            'geo':    get_geometry_rear(),
            'suffix': "Rear View",
        },
        {
            'src':    os.path.join(INPUT_DIR, "house_clean_patio.jpg"),
            'out':    os.path.join(OUTPUT_DIR, "patio_mockup_patio.jpg"),
            'ba':     os.path.join(OUTPUT_DIR, "patio_before_after_patio.jpg"),
            'geo':    get_geometry_patio(),
            'suffix': "Side Angle View",
        },
        {
            'src':    os.path.join(INPUT_DIR, "house_clean_angle.jpg"),
            'out':    os.path.join(OUTPUT_DIR, "patio_mockup_angle.jpg"),
            'ba':     os.path.join(OUTPUT_DIR, "patio_before_after_angle.jpg"),
            'geo':    get_geometry_angle(),
            'suffix': "Back-Left Corner View",
        },
        {
            'src':    os.path.join(INPUT_DIR, "house_clean_porch.jpg"),
            'out':    os.path.join(OUTPUT_DIR, "patio_mockup_porch.jpg"),
            'ba':     os.path.join(OUTPUT_DIR, "patio_before_after_porch.jpg"),
            'geo':    get_geometry_porch(),
            'suffix': "Porch View",
        },
    ]

    for p in photos:
        label = f"{LABEL_TEXT} — {p['suffix']}"
        composite_patio(p['src'], p['geo'], p['out'], label_text=label)
        create_before_after(p['src'], p['out'], p['ba'])
        print()

    print("Done! All mockups saved to owner_inbox/")
    print("Mockup files:")
    for p in photos:
        print(f"  {p['out']}")
    print("Before/after comparisons:")
    for p in photos:
        print(f"  {p['ba']}")
