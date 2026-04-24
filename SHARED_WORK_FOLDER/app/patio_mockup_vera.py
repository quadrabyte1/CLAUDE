"""
patio_mockup_vera.py
Vera — AI Compositing Specialist
Generates photorealistic 20'x20' bluestone patio mockups using Replicate Flux Fill Pro.
"""

import os
import sys
import time
import urllib.request
from pathlib import Path

import replicate
import requests
from PIL import Image, ImageDraw, ImageFilter
import numpy as np

# ─── Paths ───────────────────────────────────────────────────────────────────
BASE = Path("/Users/fourierflight/GIT/CLAUDE-GitHub/SHARED_WORK_FOLDER")
SRC  = BASE / "owner_inbox"
OUT  = BASE / "owner_inbox"

PHOTOS = {
    "rear":  SRC / "house_clean_rear.jpg",
    "patio": SRC / "house_clean_patio.jpg",
    "angle": SRC / "house_clean_angle.jpg",
    "porch": SRC / "house_clean_porch.jpg",
}

# ─── Mask polygons (pixel coords, 5712×4284) ─────────────────────────────────
# Coordinates were derived by visually analyzing the photos at full resolution.
# Each polygon traces the ground plane where the patio belongs.
# (0,0) = top-left corner of image.

W, H = 5712, 4284

MASKS = {

    # ── REAR VIEW ──────────────────────────────────────────────────────────────
    # Straight-on rear. House facade fills center. Ground starts at foundation
    # line (~y=2700).  The patio occupies the yard between the house and the
    # camera, spanning roughly the full width of the house.
    "rear": [
        # left edge (fence/property boundary)
        (420,  H),          # bottom-left of frame
        (420,  2750),       # foundation left corner
        # across the house foundation
        (1800, 2620),       # left side of house base
        (2040, 2580),       # left door jamb base
        (2600, 2580),       # center below door
        (3680, 2620),       # right side of house base
        (4900, 2700),       # right foundation
        # right edge
        (5300, H),          # bottom-right of frame
    ],

    # ── PATIO VIEW ─────────────────────────────────────────────────────────────
    # Angled view from right side. Flagstone area is center/left. Driveway is
    # bottom-right (must NOT be covered).  Ground plane recedes upper-left.
    "patio": [
        # start at bottom-left
        (0,    H),
        # left edge going up — fence/property boundary on left
        (0,    3500),
        # upper-left: where patio meets house left-side foundation
        (600,  2800),
        # sweep across the upper edge of the patio area (house foundation)
        (1400, 2600),
        (2200, 2400),
        # rightward along the back of the existing stone area
        (3000, 2550),
        (3400, 2700),
        # drop to the right edge — STOP before the driveway gutter
        # the driveway starts around x=4000 at the bottom
        (3600, 3200),
        (3800, H),
        # bottom edge back to left
    ],

    # ── ANGLE VIEW (back-left corner) ──────────────────────────────────────────
    # House is on right. Open yard lower-right. Fence/shed upper-left.
    # Patio attaches to house right side and extends into yard.
    "angle": [
        # lower-right yard area
        (5712, H),           # bottom-right
        (5712, 3200),        # right edge mid
        # upper-right: house foundation (right side)
        (4800, 3000),
        (4200, 2900),
        # sweep left along the foundation line
        (3200, 2950),
        (2600, 3100),
        # left boundary: debris/shed area — patio doesn't extend this far left
        (2000, 3400),
        (1800, H),           # bottom edge left stop
    ],

    # ── PORCH VIEW ─────────────────────────────────────────────────────────────
    # Existing covered porch with white railings. Camera is from yard looking at
    # porch. Dense foreground bushes obscure the ground.  The patio ground
    # surface is mostly hidden behind vegetation — we mask the visible ground
    # patches and the area between camera and porch steps.
    "porch": [
        # ground area visible below/around the bushes — mainly lower band
        (0,    H),
        (0,    3600),
        # left edge of visible ground
        (400,  3200),
        # above bush line where porch deck meets ground
        (1400, 2900),
        (2200, 2800),        # near porch steps base
        (3000, 2850),
        (3800, 3000),
        (4600, 3200),
        (5200, 3500),
        (5712, 3800),
        (5712, H),
    ],
}

# ─── Prompts ─────────────────────────────────────────────────────────────────

BASE_PROMPT = (
    "A 20 by 20 foot bluestone patio at ground level, "
    "natural blue-gray bluestone pavers laid in a rectangular ashlar pattern, "
    "with a 1-foot-wide charcoal-toned picture frame border running around the full perimeter, "
    "interior field pavers oriented perpendicular to the border, "
    "tight mortar joints, flat and flush with the surrounding lawn grade, "
    "patio meets the house foundation seamlessly, "
    "soft afternoon sunlight, photorealistic architectural photography, "
    "high detail, matching the existing yellow clapboard Colonial house exterior"
)

PROMPTS = {
    "rear":  BASE_PROMPT + (
        ", straight-on rear elevation view, "
        "patio centered in yard below the back door, "
        "natural shadows from the house"
    ),
    "patio": BASE_PROMPT + (
        ", angled perspective view from the right, "
        "patio terminates before the driveway on the right side, "
        "slight perspective foreshortening of pavers toward the upper-left, "
        "warm late-afternoon light from the right"
    ),
    "angle": BASE_PROMPT + (
        ", back-left corner angle view, "
        "patio visible in lower-right yard area attaching to house foundation, "
        "lawn edges meet patio cleanly on left and far sides, "
        "dappled spring sunlight"
    ),
    "porch": BASE_PROMPT + (
        ", close view of covered back porch with white railings, "
        "patio surface visible below and in front of the porch, "
        "partial occlusion by existing foreground shrubbery, "
        "porch deck level sits slightly above the patio grade, steps visible"
    ),
}

# ─── Helpers ─────────────────────────────────────────────────────────────────

def make_mask(key: str, size: tuple[int, int]) -> Image.Image:
    """Create a feathered binary mask for the given photo key."""
    w, h = size
    # Scale polygon from design coords (5712×4284) to actual image size
    sx = w / W
    sy = h / H
    poly = [(int(x * sx), int(y * sy)) for x, y in MASKS[key]]

    mask = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(mask)
    draw.polygon(poly, fill=255)

    # Feather edges with Gaussian blur then re-threshold to keep binary-ish
    mask = mask.filter(ImageFilter.GaussianBlur(radius=60))
    # Re-strengthen the mask so center stays white
    arr = np.array(mask, dtype=np.float32)
    arr = np.clip(arr * 1.6, 0, 255).astype(np.uint8)
    return Image.fromarray(arr, "L")


def download_image(url: str, dest: Path) -> Path:
    """Download a URL to dest path."""
    print(f"  Downloading result → {dest.name}")
    if hasattr(url, "read"):
        # It's a file-like object (replicate FileOutput)
        data = url.read()
        dest.write_bytes(data)
    elif isinstance(url, str) and url.startswith("http"):
        resp = requests.get(url, timeout=120)
        resp.raise_for_status()
        dest.write_bytes(resp.content)
    else:
        # Try reading as file-like
        try:
            data = url.read()
            dest.write_bytes(data)
        except Exception:
            raise ValueError(f"Cannot handle Replicate output type: {type(url)}")
    return dest


def make_comparison(original: Path, result: Path, out: Path):
    """Save a side-by-side before/after comparison image."""
    orig_img   = Image.open(original).convert("RGB")
    result_img = Image.open(result).convert("RGB")

    # Resize both to same height (1080px for manageable file size)
    TARGET_H = 1080
    def resize_h(img, th):
        ratio = th / img.height
        return img.resize((int(img.width * ratio), th), Image.LANCZOS)

    orig_r   = resize_h(orig_img,   TARGET_H)
    result_r = resize_h(result_img, TARGET_H)

    gap   = 20
    total_w = orig_r.width + result_r.width + gap
    canvas  = Image.new("RGB", (total_w, TARGET_H + 60), (30, 30, 30))
    canvas.paste(orig_r,   (0, 0))
    canvas.paste(result_r, (orig_r.width + gap, 0))

    # Labels
    from PIL import ImageFont
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 36)
    except Exception:
        font = ImageFont.load_default()

    draw = ImageDraw.Draw(canvas)
    draw.text((10, TARGET_H + 10),                        "BEFORE", fill=(200, 200, 200), font=font)
    draw.text((orig_r.width + gap + 10, TARGET_H + 10),  "AFTER",  fill=(100, 220, 100), font=font)

    canvas.save(out, quality=92)
    print(f"  Comparison saved → {out.name}")


# ─── Main pipeline ────────────────────────────────────────────────────────────

def process_photo(key: str):
    photo_path = PHOTOS[key]
    print(f"\n{'='*60}")
    print(f"  Processing: {key} ({photo_path.name})")
    print(f"{'='*60}")

    # Load original to get actual dimensions
    orig = Image.open(photo_path)
    W_img, H_img = orig.size
    print(f"  Dimensions: {W_img} x {H_img}")

    # Step 1: Create mask
    mask_path = OUT / f"patio_mask_{key}.png"
    mask = make_mask(key, (W_img, H_img))
    mask.save(mask_path)
    print(f"  Mask saved → {mask_path.name}")

    # Step 2: Call Flux Fill Pro
    prompt = PROMPTS[key]
    print(f"  Calling Replicate flux-fill-pro …")
    print(f"  Prompt: {prompt[:100]}…")

    with open(photo_path, "rb") as img_f, open(mask_path, "rb") as msk_f:
        output = replicate.run(
            "black-forest-labs/flux-fill-pro",
            input={
                "image":  img_f,
                "mask":   msk_f,
                "prompt": prompt,
                "steps":  50,
                "output_format": "jpg",
                "output_quality": 95,
            }
        )

    print(f"  API call complete. Output type: {type(output)}")

    # Step 3: Download result
    result_path = OUT / f"patio_mockup_vera_{key}.jpg"
    download_image(output, result_path)

    # Step 4: Before/after comparison
    comp_path = OUT / f"patio_compare_vera_{key}.jpg"
    make_comparison(photo_path, result_path, comp_path)

    print(f"  Done: {key}")
    return result_path


def main():
    print("Vera — Patio Mockup Generator")
    print(f"Working dir: {BASE}")
    print(f"Photos: {list(PHOTOS.keys())}")

    # Verify API token — also check a local .env file
    token = os.environ.get("REPLICATE_API_TOKEN")
    if not token:
        env_paths = [
            BASE / ".env",
            BASE.parent / ".env",
            Path.home() / ".env",
        ]
        for ep in env_paths:
            if ep.exists():
                for line in ep.read_text().splitlines():
                    line = line.strip()
                    if line.startswith("REPLICATE_API_TOKEN"):
                        _, _, val = line.partition("=")
                        token = val.strip().strip('"').strip("'")
                        os.environ["REPLICATE_API_TOKEN"] = token
                        print(f"  Loaded token from {ep}")
                        break
            if token:
                break

    if not token:
        print("ERROR: REPLICATE_API_TOKEN not set.")
        print("  Set it with: export REPLICATE_API_TOKEN=r8_xxx")
        print("  Or create a .env file in the project root with: REPLICATE_API_TOKEN=r8_xxx")
        sys.exit(1)
    print(f"Replicate token: {'*' * 8}{token[-4:]}")

    results = {}
    errors  = {}

    for key in PHOTOS:
        try:
            result = process_photo(key)
            results[key] = result
        except Exception as e:
            print(f"\n  ERROR processing '{key}': {e}")
            import traceback
            traceback.print_exc()
            errors[key] = str(e)

    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    for key, path in results.items():
        print(f"  ✓ {key}: {path.name}")
    for key, err in errors.items():
        print(f"  ✗ {key}: {err}")


if __name__ == "__main__":
    main()
