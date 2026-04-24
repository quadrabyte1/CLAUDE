"""
patio_mockup_vera_porch.py
Vera — AI Compositing Specialist

Generates a photorealistic rectangular bluestone patio mockup for the
porch view only, using Replicate Flux Fill Pro.

Patio specs (v3):
  - Rectangular shape in perspective (~14 ft wide × ~28 ft deep)
  - Extends from the base of the porch stairs ~28 ft outward into the yard
  - Runs most of the porch width but does NOT wrap around the corner
  - Picture-frame border: 1-foot darker perimeter band
  - Bluestone pavers in ashlar/running bond pattern
  - At grade level, flat on the ground
"""

import os
import sys
from pathlib import Path

import replicate
import requests
from PIL import Image, ImageDraw, ImageFilter
import numpy as np

# ─── Paths ────────────────────────────────────────────────────────────────────
BASE  = Path("/Users/fourierflight/GIT/CLAUDE-GitHub/SHARED_WORK_FOLDER")
SRC   = BASE / "owner_inbox"
OUT   = BASE / "owner_inbox"

PHOTO = SRC / "house_clean_porch.jpg"

# ─── Mask polygon ─────────────────────────────────────────────────────────────
# Porch photo: 5712 × 4284 px
# Camera is in the yard looking up toward the covered porch.
# The patio occupies the ground in front of and below the porch.
#
# Perspective geometry:
#   Top edge  — runs along the base of the porch floor/stairs
#               (porch spans roughly x=2200 to x=5200, y≈3000-3100)
#   Bottom edge — wider due to perspective convergence at the camera
#               (widens out to cover the full lower portion of the frame)
#   Left/right edges converge toward the top (vanishing point)
#
# The mask is intentionally generous at the bottom so the AI can blend
# through the foreground vegetation naturally.

MASK_POLYGON = [
    (1800, 2200),   # top-left  — wider coverage, clear the bushes
    (5000, 2200),   # top-right — stops before the porch corner
    (5712, 4284),   # bottom-right — full frame width for perspective
    (0,    4284),   # bottom-left  — full frame width for perspective
]

# ─── Prompt ───────────────────────────────────────────────────────────────────
PROMPT = (
    "Flat bluestone paver patio on the ground extending 20 feet outward from "
    "the covered porch into the open yard, approximately 14 feet wide. "
    "NOT a deck, NOT raised, NO wood. Natural blue-gray bluestone pavers laid "
    "directly on the ground at grade level in an ashlar running-bond pattern. "
    "A 1-foot-wide charcoal-toned picture-frame border of darker stone pavers "
    "runs around the full perimeter. Interior field pavers oriented "
    "perpendicular to the border pavers. Tight mortar joints. "
    "The patio surface is completely flat and flush with the surrounding lawn. "
    "The patio is large and clearly visible, stretching far into the yard. "
    "Green lawn flanking both sides. The existing covered porch with white "
    "columns and white railings remains unchanged above. "
    "Do NOT add any furniture, planters, benches, pots, railings, "
    "handrails, fences, or any objects. Do NOT add anything that was not "
    "in the original photo. No new structures of any kind. "
    "Only the flat patio surface and surrounding green lawn. "
    "Soft natural afternoon sunlight. "
    "Photorealistic architectural photography, high detail, "
    "matching the existing yellow clapboard Colonial house exterior."
)

# ─── Helpers ──────────────────────────────────────────────────────────────────

def make_mask(polygon: list[tuple[int, int]], size: tuple[int, int]) -> Image.Image:
    """Create a feathered binary mask from a polygon."""
    w, h = size
    mask = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(mask)
    draw.polygon(polygon, fill=255)

    # Feather edges slightly so the inpaint blends into surroundings
    mask = mask.filter(ImageFilter.GaussianBlur(radius=40))
    arr  = np.array(mask, dtype=np.float32)
    arr  = np.clip(arr * 1.8, 0, 255).astype(np.uint8)
    return Image.fromarray(arr, "L")


def make_preview(photo: Path, polygon: list[tuple[int, int]], out: Path):
    """Save a green-tinted preview overlay showing the mask area."""
    base = Image.open(photo).convert("RGB")
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.polygon(polygon, fill=(0, 200, 0, 120))  # semi-transparent green
    base_rgba = base.convert("RGBA")
    composite = Image.alpha_composite(base_rgba, overlay)
    # Draw polygon outline in bright green
    draw2 = ImageDraw.Draw(composite)
    draw2.line(polygon + [polygon[0]], fill=(0, 255, 0, 255), width=8)
    composite.convert("RGB").save(out, quality=88)
    print(f"  Preview saved → {out.name}")


def download_image(url, dest: Path) -> Path:
    """Download Replicate output (URL string or file-like) to dest."""
    print(f"  Downloading result → {dest.name}")
    if hasattr(url, "read"):
        dest.write_bytes(url.read())
    elif isinstance(url, str) and url.startswith("http"):
        resp = requests.get(url, timeout=120)
        resp.raise_for_status()
        dest.write_bytes(resp.content)
    else:
        try:
            dest.write_bytes(url.read())
        except Exception:
            raise ValueError(f"Cannot handle Replicate output type: {type(url)}")
    return dest


def make_comparison(original: Path, result: Path, out: Path):
    """Save a side-by-side before/after comparison image."""
    orig_img   = Image.open(original).convert("RGB")
    result_img = Image.open(result).convert("RGB")

    TARGET_H = 1080

    def resize_h(img, th):
        ratio = th / img.height
        return img.resize((int(img.width * ratio), th), Image.LANCZOS)

    orig_r   = resize_h(orig_img,   TARGET_H)
    result_r = resize_h(result_img, TARGET_H)

    gap     = 20
    total_w = orig_r.width + result_r.width + gap
    canvas  = Image.new("RGB", (total_w, TARGET_H + 60), (30, 30, 30))
    canvas.paste(orig_r,   (0, 0))
    canvas.paste(result_r, (orig_r.width + gap, 0))

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


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("Vera — Porch Patio Mockup v3")
    print(f"Photo: {PHOTO}")

    # ── Verify API token ──────────────────────────────────────────────────────
    token = os.environ.get("REPLICATE_API_TOKEN")
    if not token:
        for ep in [BASE / ".env", BASE.parent / ".env", Path.home() / ".env"]:
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
        print("  export REPLICATE_API_TOKEN=r8_xxx")
        sys.exit(1)
    print(f"  Token: {'*' * 8}{token[-4:]}")

    # ── Load photo & verify dimensions ───────────────────────────────────────
    orig = Image.open(PHOTO)
    W_img, H_img = orig.size
    print(f"  Dimensions: {W_img} × {H_img}")
    assert (W_img, H_img) == (5712, 4284), \
        f"Unexpected image size {W_img}×{H_img}; update polygon coordinates."

    # ── Step 1: Create mask ───────────────────────────────────────────────────
    mask_path = OUT / "patio_mask_porch_v6.png"
    print(f"\nStep 1: Creating mask …")
    print(f"  Polygon: {MASK_POLYGON}")
    mask = make_mask(MASK_POLYGON, (W_img, H_img))
    mask.save(mask_path)
    print(f"  Mask saved → {mask_path.name}")

    # ── Step 2: Preview overlay ───────────────────────────────────────────────
    preview_path = OUT / "patio_preview_porch_v6.jpg"
    print(f"\nStep 2: Creating preview overlay …")
    make_preview(PHOTO, MASK_POLYGON, preview_path)

    # ── Step 3: Call Flux Fill Pro ────────────────────────────────────────────
    print(f"\nStep 3: Calling Replicate flux-fill-pro …")
    print(f"  Prompt: {PROMPT[:120]} …")

    with open(PHOTO, "rb") as img_f, open(mask_path, "rb") as msk_f:
        output = replicate.run(
            "black-forest-labs/flux-fill-pro",
            input={
                "image":          img_f,
                "mask":           msk_f,
                "prompt":         PROMPT,
                "steps":          50,
                "output_format":  "jpg",
                "output_quality": 95,
            }
        )

    print(f"  API call complete. Output type: {type(output)}")

    # ── Step 4: Download result ───────────────────────────────────────────────
    result_path = OUT / "patio_mockup_vera_porch_v6.jpg"
    print(f"\nStep 4: Downloading result …")
    download_image(output, result_path)

    # ── Step 5: Before/after comparison ──────────────────────────────────────
    comp_path = OUT / "patio_compare_vera_porch_v6.jpg"
    print(f"\nStep 5: Creating comparison …")
    make_comparison(PHOTO, result_path, comp_path)

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print("DONE")
    print(f"  Mask:       {mask_path.name}")
    print(f"  Preview:    {preview_path.name}")
    print(f"  Mockup:     {result_path.name}")
    print(f"  Comparison: {comp_path.name}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
