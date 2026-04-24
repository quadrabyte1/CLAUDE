"""
Deck Mockup Compositor — Cass, Architectural Visualization Specialist
=====================================================================
Composites a proposed raised deck onto photos of Thomas's house.

Design spec (code-compliant, sensible for the house):
  - 12' deep x 16' wide raised composite deck
  - Deck surface at existing door threshold height (~42" above grade)
  - 36" railing with 4" max baluster spacing (IRC compliant)
  - 5 risers down to grade at 7.5" each, 11" treads
  - Composite decking in warm gray/brown tone
  - White painted railing to match existing trim
  - Shadow underneath for realism

Pipeline:
  1. Load source photo
  2. Define perspective-matched deck polygon geometry
  3. Draw deck surface with board lines
  4. Draw railing posts, top rail, and balusters
  5. Draw stairs
  6. Add shadow under deck
  7. Composite onto original with edge blending
  8. Output to owner_inbox/
"""

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
import os

# ─── CONFIGURATION ────────────────────────────────────────────────────

WORKING_DIR = "/Users/fourierflight/GIT/CLAUDE-GitHub/SHARED_WORK_FOLDER"
OUTPUT_DIR = os.path.join(WORKING_DIR, "owner_inbox")

# Deck material colors (composite decking, warm gray-brown)
DECK_SURFACE_COLOR = (158, 132, 105)       # warm gray-brown composite
DECK_BOARD_LINE = (138, 112, 88)           # darker line between boards
DECK_FASCIA_COLOR = (145, 120, 98)         # fascia board, slightly darker
RAILING_COLOR = (240, 238, 232)            # white painted railing
RAILING_SHADOW = (210, 208, 202)           # shadow side of railing
POST_COLOR = (235, 233, 227)              # white posts
SHADOW_COLOR = (0, 0, 0)                   # black, applied at low opacity
STAIR_TREAD_COLOR = (155, 130, 103)        # slightly different from deck
STAIR_RISER_COLOR = (175, 165, 152)        # lighter riser face

# ─── GEOMETRY HELPERS ─────────────────────────────────────────────────

def lerp_point(p1, p2, t):
    """Linear interpolation between two points."""
    return (int(p1[0] + (p2[0] - p1[0]) * t),
            int(p1[1] + (p2[1] - p1[1]) * t))


def subdivide_quad(corners, n_divisions, axis='horizontal'):
    """
    Subdivide a perspective quad into strips.
    corners: [top_left, top_right, bottom_right, bottom_left]
    Returns list of sub-quads.
    """
    tl, tr, br, bl = corners
    strips = []
    for i in range(n_divisions):
        t0 = i / n_divisions
        t1 = (i + 1) / n_divisions
        if axis == 'horizontal':
            # Strips running left to right (board lines)
            s_tl = lerp_point(tl, bl, t0)
            s_tr = lerp_point(tr, br, t0)
            s_bl = lerp_point(tl, bl, t1)
            s_br = lerp_point(tr, br, t1)
        else:
            # Strips running top to bottom
            s_tl = lerp_point(tl, tr, t0)
            s_tr = lerp_point(tl, tr, t1)
            s_bl = lerp_point(bl, br, t0)
            s_br = lerp_point(bl, br, t1)
        strips.append([s_tl, s_tr, s_br, s_bl])
    return strips


def draw_filled_quad(draw, corners, color):
    """Draw a filled quadrilateral."""
    draw.polygon(corners, fill=color)


def draw_line_thick(draw, p1, p2, color, width=2):
    """Draw a thick line."""
    draw.line([p1, p2], fill=color, width=width)


# ─── DECK DRAWING FUNCTIONS ──────────────────────────────────────────

def draw_deck_surface(draw, deck_top_quad, n_boards=12):
    """
    Draw the top surface of the deck with board lines.
    deck_top_quad: [far_left, far_right, near_right, near_left] in perspective
    """
    tl, tr, br, bl = deck_top_quad

    # Fill the deck surface
    draw_filled_quad(draw, [tl, tr, br, bl], DECK_SURFACE_COLOR)

    # Draw board lines (running left to right, parallel to the house)
    for i in range(1, n_boards):
        t = i / n_boards
        left_pt = lerp_point(tl, bl, t)
        right_pt = lerp_point(tr, br, t)
        draw_line_thick(draw, left_pt, right_pt, DECK_BOARD_LINE, width=3)


def draw_deck_fascia(draw, deck_top_quad, fascia_depth_px):
    """
    Draw the front fascia (vertical face) of the deck.
    """
    tl, tr, br, bl = deck_top_quad
    # Front fascia is the bottom edge of the top quad, extended down
    fascia_bl = (bl[0], bl[1] + fascia_depth_px)
    fascia_br = (br[0], br[1] + fascia_depth_px)
    draw_filled_quad(draw, [bl, br, fascia_br, fascia_bl], DECK_FASCIA_COLOR)

    # Draw a shadow line at the top of the fascia
    draw_line_thick(draw, bl, br, (120, 100, 80), width=4)

    return fascia_bl, fascia_br


def draw_railing(draw, deck_top_quad, railing_height_px, n_posts=5):
    """
    Draw railing along the front and sides of the deck.
    """
    tl, tr, br, bl = deck_top_quad

    # ── Front railing (along the near edge, bl to br) ──
    rail_top_bl = (bl[0], bl[1] - railing_height_px)
    rail_top_br = (br[0], br[1] - int(railing_height_px * 0.85))  # perspective

    # Top rail
    draw_line_thick(draw, rail_top_bl, rail_top_br, RAILING_COLOR, width=6)
    # Bottom rail (at deck surface)
    draw_line_thick(draw, bl, br, RAILING_COLOR, width=4)
    # Mid rail
    mid_bl = lerp_point(bl, rail_top_bl, 0.5)
    mid_br = lerp_point(br, rail_top_br, 0.5)
    draw_line_thick(draw, mid_bl, mid_br, RAILING_SHADOW, width=3)

    # Posts along front
    for i in range(n_posts + 1):
        t = i / n_posts
        base = lerp_point(bl, br, t)
        top = lerp_point(rail_top_bl, rail_top_br, t)
        draw_line_thick(draw, base, top, POST_COLOR, width=7)

    # Balusters between posts (4" spacing -> ~8-9 per section)
    for i in range(n_posts):
        t0 = i / n_posts
        t1 = (i + 1) / n_posts
        n_balusters = 8
        for j in range(1, n_balusters):
            t = t0 + (t1 - t0) * (j / n_balusters)
            base = lerp_point(bl, br, t)
            top = lerp_point(rail_top_bl, rail_top_br, t)
            # Balusters start a bit above deck surface
            bal_base = lerp_point(base, top, 0.08)
            bal_top = lerp_point(base, top, 0.95)
            draw_line_thick(draw, bal_base, bal_top, RAILING_SHADOW, width=2)

    # ── Left side railing (along the left edge, tl to bl) ──
    rail_top_tl = (tl[0], tl[1] - int(railing_height_px * 0.65))  # more perspective
    # Top rail
    draw_line_thick(draw, rail_top_tl, rail_top_bl, RAILING_COLOR, width=5)
    # Posts
    n_side_posts = 3
    for i in range(n_side_posts + 1):
        t = i / n_side_posts
        base = lerp_point(tl, bl, t)
        top = lerp_point(rail_top_tl, rail_top_bl, t)
        draw_line_thick(draw, base, top, POST_COLOR, width=6)

    # Side balusters
    for i in range(n_side_posts):
        t0 = i / n_side_posts
        t1 = (i + 1) / n_side_posts
        n_balusters = 6
        for j in range(1, n_balusters):
            t = t0 + (t1 - t0) * (j / n_balusters)
            base = lerp_point(tl, bl, t)
            top = lerp_point(rail_top_tl, rail_top_bl, t)
            bal_base = lerp_point(base, top, 0.08)
            bal_top = lerp_point(base, top, 0.95)
            draw_line_thick(draw, bal_base, bal_top, RAILING_SHADOW, width=2)

    # Mid rail on side
    side_mid_tl = lerp_point(tl, rail_top_tl, 0.5)
    side_mid_bl = lerp_point(bl, rail_top_bl, 0.5)
    draw_line_thick(draw, side_mid_tl, side_mid_bl, RAILING_SHADOW, width=3)

    # ── Right side railing (tr to br) ──
    rail_top_tr_side = (tr[0], tr[1] - int(railing_height_px * 0.65))
    draw_line_thick(draw, rail_top_tr_side, rail_top_br, RAILING_COLOR, width=5)
    n_side_posts_r = 3
    for i in range(n_side_posts_r + 1):
        t = i / n_side_posts_r
        base = lerp_point(tr, br, t)
        top = lerp_point(rail_top_tr_side, rail_top_br, t)
        draw_line_thick(draw, base, top, POST_COLOR, width=6)
    # Balusters
    for i in range(n_side_posts_r):
        t0 = i / n_side_posts_r
        t1 = (i + 1) / n_side_posts_r
        n_balusters = 6
        for j in range(1, n_balusters):
            t = t0 + (t1 - t0) * (j / n_balusters)
            base = lerp_point(tr, br, t)
            top = lerp_point(rail_top_tr_side, rail_top_br, t)
            bal_base = lerp_point(base, top, 0.08)
            bal_top = lerp_point(base, top, 0.95)
            draw_line_thick(draw, bal_base, bal_top, RAILING_SHADOW, width=2)
    # Mid rail right
    side_mid_tr = lerp_point(tr, rail_top_tr_side, 0.5)
    side_mid_br_r = lerp_point(br, rail_top_br, 0.5)
    draw_line_thick(draw, side_mid_tr, side_mid_br_r, RAILING_SHADOW, width=3)

    return rail_top_bl, rail_top_br


def draw_stairs(draw, stair_top_left, stair_top_right, n_steps, step_height_px, step_depth_px):
    """
    Draw stairs descending from the deck to grade.
    Stairs go down from stair_top_left/right toward the viewer.
    """
    for i in range(n_steps):
        # Each step: tread (horizontal) then riser (vertical)
        y_offset = i * step_height_px
        depth_offset = i * step_depth_px

        # Tread top-left / top-right (the "back" of this tread, near side of prev riser)
        tl = (stair_top_left[0] + depth_offset // 3,
              stair_top_left[1] + y_offset)
        tr = (stair_top_right[0] + depth_offset // 5,
              stair_top_right[1] + y_offset)

        # Tread bottom-left / bottom-right (front edge of this tread)
        bl = (tl[0] + step_depth_px // 2,
              tl[1] + step_depth_px // 3)
        br = (tr[0] + step_depth_px // 2,
              tr[1] + step_depth_px // 3)

        # Draw tread
        draw_filled_quad(draw, [tl, tr, br, bl], STAIR_TREAD_COLOR)
        # Board line on tread
        draw_line_thick(draw, tl, tr, DECK_BOARD_LINE, width=2)

        # Riser (vertical face below this tread)
        riser_bl = (bl[0], bl[1] + step_height_px)
        riser_br = (br[0], br[1] + step_height_px)
        draw_filled_quad(draw, [bl, br, riser_br, riser_bl], STAIR_RISER_COLOR)
        # Shadow at top of riser
        draw_line_thick(draw, bl, br, (130, 110, 90), width=2)


def draw_shadow_under_deck(overlay, deck_top_quad, fascia_depth_px, shadow_extend=60):
    """
    Draw a ground shadow under and in front of the deck.
    Uses a semi-transparent dark layer.
    """
    tl, tr, br, bl = deck_top_quad
    shadow_draw = ImageDraw.Draw(overlay)

    # Shadow polygon: extends below fascia and slightly forward
    s_tl = (bl[0] - 10, bl[1] + fascia_depth_px + 5)
    s_tr = (br[0] + 10, br[1] + fascia_depth_px + 5)
    s_bl = (bl[0] + shadow_extend, bl[1] + fascia_depth_px + shadow_extend)
    s_br = (br[0] + shadow_extend // 2, br[1] + fascia_depth_px + shadow_extend)

    shadow_draw.polygon([s_tl, s_tr, s_br, s_bl], fill=(0, 0, 0, 80))

    # Under-deck shadow (darker, between deck surface and fascia bottom)
    under_tl = (tl[0], tl[1] + 5)
    under_tr = (tr[0], tr[1] + 5)
    under_bl = (bl[0], bl[1] + fascia_depth_px)
    under_br = (br[0], br[1] + fascia_depth_px)
    shadow_draw.polygon([under_tl, under_tr, under_br, under_bl], fill=(0, 0, 0, 100))


def add_label(draw, position, text, font_size=48):
    """Add a text label with background."""
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", font_size)
    except Exception:
        font = ImageFont.load_default()

    bbox = draw.textbbox(position, text, font=font)
    padding = 10
    draw.rectangle(
        [bbox[0] - padding, bbox[1] - padding, bbox[2] + padding, bbox[3] + padding],
        fill=(255, 255, 255, 200)
    )
    draw.text(position, text, fill=(40, 40, 40), font=font)


# ─── PHOTO-SPECIFIC GEOMETRY ─────────────────────────────────────────
# These coordinates are hand-calibrated to each photo's perspective.

def get_geometry_1076():
    """
    Perspective geometry for IMG_1076 2.JPG
    This is the most straight-on rear view.
    The existing porch/door is roughly centered.

    Coordinate system: (x, y) in pixels, origin top-left.
    Image is 5712 x 4284.

    Key reference points from the photo:
    - Back door is approximately at x=2700, y=1650
    - Existing porch deck surface is at about y=2150
    - Grade level (bottom of steps) is at about y=2700
    - House left edge at about x=1700
    - House right edge at about x=3950
    """
    # Deck top surface quad - perspective matched
    # The deck attaches at the house wall and extends outward toward camera
    # far_left, far_right = where deck meets house (smaller, further away)
    # near_left, near_right = front edge of deck (larger, closer to camera)
    deck_top = [
        (1850, 2200),   # far left (at house wall)
        (3600, 2200),   # far right (at house wall)
        (3950, 2850),   # near right (front edge, closer to camera)
        (1500, 2850),   # near left (front edge, closer to camera)
    ]
    fascia_depth = 160     # pixels for the vertical fascia face
    railing_height = 260   # pixels for 36" railing
    n_boards = 14          # number of deck boards visible

    # Stair location: centered on front edge
    stair_left = lerp_point(deck_top[3], deck_top[2], 0.35)
    stair_right = lerp_point(deck_top[3], deck_top[2], 0.65)
    stair_left = (stair_left[0], stair_left[1] + fascia_depth)
    stair_right = (stair_right[0], stair_right[1] + fascia_depth)
    n_steps = 5
    step_h = 60
    step_d = 70

    return {
        'deck_top': deck_top,
        'fascia_depth': fascia_depth,
        'railing_height': railing_height,
        'n_boards': n_boards,
        'stair_left': stair_left,
        'stair_right': stair_right,
        'n_steps': n_steps,
        'step_h': step_h,
        'step_d': step_d,
    }


def get_geometry_1077():
    """
    Perspective geometry for IMG_1077 2.JPG
    Slightly more to the right, showing left side of house more.
    The view is from the right side of the yard looking left.
    """
    deck_top = [
        (1700, 2100),   # far left (at house wall, further away)
        (3650, 1950),   # far right (at house wall, closer due to angle)
        (4100, 2650),   # near right (front edge)
        (1650, 2850),   # near left (front edge)
    ]
    fascia_depth = 150
    railing_height = 250
    n_boards = 14

    stair_left = lerp_point(deck_top[3], deck_top[2], 0.30)
    stair_right = lerp_point(deck_top[3], deck_top[2], 0.60)
    stair_left = (stair_left[0], stair_left[1] + fascia_depth)
    stair_right = (stair_right[0], stair_right[1] + fascia_depth)
    n_steps = 5
    step_h = 55
    step_d = 65

    return {
        'deck_top': deck_top,
        'fascia_depth': fascia_depth,
        'railing_height': railing_height,
        'n_boards': n_boards,
        'stair_left': stair_left,
        'stair_right': stair_right,
        'n_steps': n_steps,
        'step_h': step_h,
        'step_d': step_d,
    }


# ─── MAIN COMPOSITOR ─────────────────────────────────────────────────

def composite_deck(photo_path, geometry, output_path, label_text=""):
    """
    Full pipeline: load photo, draw deck, composite, save.
    """
    print(f"Loading {os.path.basename(photo_path)}...")
    img = Image.open(photo_path).convert("RGBA")
    w, h = img.size
    print(f"  Image size: {w}x{h}")

    # Create deck layer (transparent)
    deck_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    deck_draw = ImageDraw.Draw(deck_layer)

    g = geometry

    # 1. Draw shadow under deck first (on a separate layer for alpha)
    shadow_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw_shadow_under_deck(shadow_layer, g['deck_top'], g['fascia_depth'])
    # Blur the shadow for softness
    shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(radius=15))

    # 2. Draw support posts under the deck (before fascia so fascia covers them)
    tl, tr, br, bl = g['deck_top']
    post_color_dark = (180, 175, 168)
    n_support_posts = 4
    for i in range(n_support_posts):
        t = (i + 0.5) / n_support_posts
        top_pt = lerp_point(bl, br, t)
        bottom_pt = (top_pt[0] + 5, top_pt[1] + g['fascia_depth'] + 200)
        draw_line_thick(deck_draw, top_pt, bottom_pt, post_color_dark, width=12)

    # 2b. Draw fascia (front face of deck)
    fascia_bl, fascia_br = draw_deck_fascia(deck_draw, g['deck_top'], g['fascia_depth'])

    # 3. Draw stairs
    draw_stairs(deck_draw, g['stair_left'], g['stair_right'],
                g['n_steps'], g['step_h'], g['step_d'])

    # 4. Draw deck surface (on top of fascia)
    draw_deck_surface(deck_draw, g['deck_top'], g['n_boards'])

    # 5. Draw railing (on top of everything)
    draw_railing(deck_draw, g['deck_top'], g['railing_height'])

    # ── Composite layers ──
    # Start with original
    result = img.copy()

    # Apply shadow layer
    result = Image.alpha_composite(result, shadow_layer)

    # Apply deck layer with slight transparency for blending
    # Make deck 92% opaque so it doesn't look pasted on
    deck_array = np.array(deck_layer)
    mask = deck_array[:, :, 3] > 0
    deck_array[mask, 3] = (deck_array[mask, 3].astype(float) * 0.92).astype(np.uint8)
    deck_layer = Image.fromarray(deck_array)

    result = Image.alpha_composite(result, deck_layer)

    # Add label
    if label_text:
        label_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        label_draw = ImageDraw.Draw(label_layer)
        add_label(label_draw, (100, 100), label_text, font_size=72)
        result = Image.alpha_composite(result, label_layer)

    # Convert to RGB for JPEG output
    result_rgb = result.convert("RGB")

    # Apply very slight blur to the deck region to match photo's depth of field
    # (phone photos are slightly soft compared to vector graphics)
    # We do this by blurring a copy and pasting just the deck region
    blurred = result_rgb.filter(ImageFilter.GaussianBlur(radius=1.2))

    # Create mask for deck region
    deck_mask = Image.new("L", (w, h), 0)
    mask_draw = ImageDraw.Draw(deck_mask)
    # Expand the deck region slightly for the mask
    tl, tr, br, bl = g['deck_top']
    expanded = [
        (tl[0] - 20, tl[1] - g['railing_height'] - 20),
        (tr[0] + 20, tr[1] - g['railing_height'] - 20),
        (br[0] + 80, br[1] + g['fascia_depth'] + g['n_steps'] * g['step_h'] + 80),
        (bl[0] - 80, bl[1] + g['fascia_depth'] + g['n_steps'] * g['step_h'] + 80),
    ]
    mask_draw.polygon(expanded, fill=255)
    deck_mask = deck_mask.filter(ImageFilter.GaussianBlur(radius=5))

    result_rgb.paste(blurred, mask=deck_mask)

    # Save
    result_rgb.save(output_path, "JPEG", quality=92)
    print(f"  Saved: {output_path}")
    return output_path


def create_before_after(photo_path, mockup_path, output_path):
    """Create a side-by-side before/after comparison."""
    original = Image.open(photo_path).convert("RGB")
    mockup = Image.open(mockup_path).convert("RGB")

    w, h = original.size
    # Scale both to half width for side-by-side
    half_w = w // 2
    orig_small = original.resize((half_w, h // 2), Image.LANCZOS)
    mock_small = mockup.resize((half_w, h // 2), Image.LANCZOS)

    combined = Image.new("RGB", (half_w * 2, h // 2 + 100), (255, 255, 255))

    # Add labels
    draw = ImageDraw.Draw(combined)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 48)
    except Exception:
        font = ImageFont.load_default()

    draw.text((half_w // 2 - 80, 20), "BEFORE", fill=(80, 80, 80), font=font)
    draw.text((half_w + half_w // 2 - 80, 20), "AFTER", fill=(80, 80, 80), font=font)

    combined.paste(orig_small, (0, 90))
    combined.paste(mock_small, (half_w, 90))

    # Divider line
    draw.line([(half_w, 0), (half_w, h // 2 + 100)], fill=(200, 200, 200), width=4)

    combined.save(output_path, "JPEG", quality=90)
    print(f"  Saved comparison: {output_path}")


# ─── RUN ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # ── Mockup 1: IMG_1076 (straight-on rear view) ──
    photo1 = os.path.join(WORKING_DIR, "team_inbox", "IMG_1076 2.JPG")
    out1 = os.path.join(OUTPUT_DIR, "deck_mockup_1_rear_view.jpg")
    composite_deck(
        photo1,
        get_geometry_1076(),
        out1,
        label_text="Proposed 12'x16' Composite Deck — Rear View"
    )

    # ── Mockup 2: IMG_1077 (angled view from right) ──
    photo2 = os.path.join(WORKING_DIR, "team_inbox", "IMG_1077 2.JPG")
    out2 = os.path.join(OUTPUT_DIR, "deck_mockup_2_angle_view.jpg")
    composite_deck(
        photo2,
        get_geometry_1077(),
        out2,
        label_text="Proposed 12'x16' Composite Deck — Angle View"
    )

    # ── Before/After comparisons ──
    ba1 = os.path.join(OUTPUT_DIR, "deck_before_after_rear.jpg")
    create_before_after(photo1, out1, ba1)

    ba2 = os.path.join(OUTPUT_DIR, "deck_before_after_angle.jpg")
    create_before_after(photo2, out2, ba2)

    print("\nDone! All mockups saved to owner_inbox/")
    print("Files:")
    print(f"  1. {out1}")
    print(f"  2. {out2}")
    print(f"  3. {ba1}")
    print(f"  4. {ba2}")
