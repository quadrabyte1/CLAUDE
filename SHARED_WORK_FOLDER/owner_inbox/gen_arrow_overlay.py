"""
Standalone script: generate arrow_vs_output overlay PNG for a given EGM.
Usage: python gen_arrow_overlay.py <egm_path> <out_png>

Runs the full detect_arrows → build_gradient_field → solve_poisson_height
pipeline (unit-vector arrows, direction only) and saves the two-panel overlay PNG.
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

import cv2
import gradient_surface_diagnostic as gd

def main(egm_path: str, out_png: str) -> None:
    print(f"[overlay] Loading EGM: {egm_path}")
    egm_data, image_path, green_boundary_px = gd.load_egm(egm_path)
    print(f"[overlay] Image: {image_path}")

    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(f"Cannot read image: {image_path}")
    print(f"[overlay] Image size: {img.shape[1]}x{img.shape[0]}")

    print("[overlay] Detecting arrows (unit vectors, direction only)…")
    arrows = gd.detect_arrows(img, green_boundary_px)  # uses updated defaults: navy+dark mask, max_arrow_area=1200
    print(f"[overlay] Found {len(arrows)} arrows")

    GRID_RES = 200
    print(f"[overlay] Building gradient field ({GRID_RES}x{GRID_RES})…")
    xs_grid, ys_grid, inside_mask, Gx, Gy = gd.build_gradient_field(
        arrows, green_boundary_px, grid_res=GRID_RES
    )

    import numpy as np
    if arrows:
        print(f"[overlay] Gx range: [{Gx[inside_mask].min():.3f}, {Gx[inside_mask].max():.3f}]")
        print(f"[overlay] Gy range: [{Gy[inside_mask].min():.3f}, {Gy[inside_mask].max():.3f}]")
        print("[overlay] Solving Poisson…")
        Z = gd.solve_poisson_height(inside_mask, Gx, Gy)
    else:
        print("[overlay] No arrows — flat fallback Z")
        Z = np.where(inside_mask, 0.0, float("nan"))

    print(f"[overlay] Saving overlay PNG: {out_png}")
    gd.save_arrow_vs_output_overlay(img, arrows, Z, xs_grid, ys_grid, green_boundary_px, out_png)
    print("[overlay] Done.")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python gen_arrow_overlay.py <egm_path> <out_png>")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])
