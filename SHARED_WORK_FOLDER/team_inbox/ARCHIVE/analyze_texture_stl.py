"""
Texture Analysis Script: Push Stick STL Comparison
Topo — 3D Modeling / Computational Geometry Specialist

Compares:
  - push stick (after Fisher).stl          — plain object
  - push stick (after Fisher)_custom_amp0p50.stl — textured object

Goal: Identify the geometric technique used to apply the texture.
"""

import numpy as np
import trimesh
from pathlib import Path
import sys

INBOX = Path("/Users/fourierflight/GIT/CLAUDE-GitHub/SHARED_WORK_FOLDER/team_inbox")
PLAIN_STL  = INBOX / "push stick (after Fisher).stl"
TEXTURED_STL = INBOX / "push stick (after Fisher)_custom_amp0p50.stl"

def load_mesh(path):
    print(f"\nLoading: {path.name}")
    m = trimesh.load(str(path), force='mesh')
    print(f"  Type: {type(m)}")
    return m

def basic_stats(mesh, label):
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")
    print(f"  Vertices : {len(mesh.vertices):,}")
    print(f"  Faces    : {len(mesh.faces):,}")
    bb = mesh.bounding_box.bounds
    dims = bb[1] - bb[0]
    print(f"  Bbox min : {bb[0]}")
    print(f"  Bbox max : {bb[1]}")
    print(f"  Bbox dims: {dims}  (X={dims[0]:.3f}, Y={dims[1]:.3f}, Z={dims[2]:.3f})")
    print(f"  Volume   : {mesh.volume:.4f} mm³")
    print(f"  Surface  : {mesh.area:.4f} mm²")
    print(f"  Watertight: {mesh.is_watertight}")
    return bb, dims

def analyze_face_normals(mesh, label):
    """Histogram of face normals — tells us which faces are top/bottom/sides."""
    normals = mesh.face_normals
    print(f"\n--- Normal Distribution ({label}) ---")
    # Classify by dominant axis
    dom = np.argmax(np.abs(normals), axis=1)
    for ax, ax_name in enumerate(['X', 'Y', 'Z']):
        pos = np.sum((dom == ax) & (normals[:, ax] > 0))
        neg = np.sum((dom == ax) & (normals[:, ax] < 0))
        print(f"  Dominant {ax_name}+: {pos:,}   {ax_name}-: {neg:,}")

def find_top_face_region(mesh, z_percentile=95):
    """Return faces whose centroid Z is in the top percentile (likely the textured face)."""
    centroids = mesh.triangles_center
    z_vals = centroids[:, 2]
    threshold = np.percentile(z_vals, z_percentile)
    top_mask = z_vals >= threshold
    return top_mask, z_vals

def analyze_displacement(plain, textured):
    """
    Core analysis — handles misaligned coordinate origins by working in normalized space.
    Both meshes are aligned by their bounding box center before comparison.
    """
    print(f"\n{'='*60}")
    print("  DISPLACEMENT ANALYSIS")
    print(f"{'='*60}")

    p_verts = plain.vertices.copy()
    t_verts = textured.vertices.copy()

    # Print raw coordinate ranges
    p_z_min, p_z_max = p_verts[:, 2].min(), p_verts[:, 2].max()
    t_z_min, t_z_max = t_verts[:, 2].min(), t_verts[:, 2].max()
    print(f"\n  Raw Plain Z range   : [{p_z_min:.4f}, {p_z_max:.4f}]  span={p_z_max-p_z_min:.4f}")
    print(f"  Raw Textured Z range: [{t_z_min:.4f}, {t_z_max:.4f}]  span={t_z_max-t_z_min:.4f}")

    # NOTE: The two meshes have different origins.
    # Plain is at Z=[0, 20], Textured is at Z=[-10, +10.47]
    # They are the same physical object but the textured version is centered.
    # Align by translating so each mesh's Z min = 0.
    p_verts_aligned = p_verts.copy()
    p_verts_aligned[:, 2] -= p_z_min   # shift so Z_min = 0
    t_verts_aligned = t_verts.copy()
    t_verts_aligned[:, 2] -= t_z_min   # shift so Z_min = 0

    # Also align X and Y centers
    p_xy_center = (p_verts[:, :2].max(axis=0) + p_verts[:, :2].min(axis=0)) / 2
    t_xy_center = (t_verts[:, :2].max(axis=0) + t_verts[:, :2].min(axis=0)) / 2
    p_verts_aligned[:, :2] -= p_xy_center
    t_verts_aligned[:, :2] -= t_xy_center

    print(f"\n  After alignment:")
    print(f"    Plain Z    : [{p_verts_aligned[:,2].min():.4f}, {p_verts_aligned[:,2].max():.4f}]")
    print(f"    Textured Z : [{t_verts_aligned[:,2].min():.4f}, {t_verts_aligned[:,2].max():.4f}]")

    # The "top" is at the max Z of the aligned plain mesh
    z_flat = p_verts_aligned[:, 2].max()
    tol = 1.0  # mm

    p_top_mask = p_verts_aligned[:, 2] >= (z_flat - tol)
    t_top_mask = t_verts_aligned[:, 2] >= (z_flat - tol)

    p_top = p_verts_aligned[p_top_mask]
    t_top = t_verts_aligned[t_top_mask]

    print(f"\n  Vertices near top face (Z >= {z_flat - tol:.3f} after alignment):")
    print(f"    Plain   : {len(p_top):,}")
    print(f"    Textured: {len(t_top):,}")

    if len(t_top) > 0:
        t_top_z = t_top[:, 2]
        print(f"\n  Top-region Z stats (textured, aligned):")
        print(f"    min  = {t_top_z.min():.4f}")
        print(f"    max  = {t_top_z.max():.4f}")
        print(f"    mean = {t_top_z.mean():.4f}")
        print(f"    std  = {t_top_z.std():.4f}")
        print(f"    peak-to-peak amplitude = {t_top_z.max() - t_top_z.min():.4f} mm")

    # Wider band for topology comparison
    z_band_min = z_flat - 2.0
    p_band = p_verts_aligned[p_verts_aligned[:, 2] >= z_band_min]
    t_band = t_verts_aligned[t_verts_aligned[:, 2] >= z_band_min]

    print(f"\n  Band (Z >= {z_band_min:.3f}):")
    print(f"    Plain    vertices: {len(p_band):,}")
    print(f"    Textured vertices: {len(t_band):,}")
    if len(p_band) > 0:
        print(f"    Vertex count ratio: {len(t_band)/len(p_band):.1f}x")

    # Store aligned versions on the meshes for downstream use
    plain._aligned_verts = p_verts_aligned
    textured._aligned_verts = t_verts_aligned
    plain._z_flat = z_flat

    return t_top, z_flat

def analyze_spatial_frequency(t_top_verts, z_flat):
    """
    Estimate the spatial frequency (wavelength) of the texture pattern
    from the top-face vertices.
    """
    print(f"\n{'='*60}")
    print("  SPATIAL FREQUENCY ANALYSIS")
    print(f"{'='*60}")

    if len(t_top_verts) < 10:
        print("  Not enough top vertices for frequency analysis.")
        return

    # Work in XY plane (the textured surface is horizontal)
    xy = t_top_verts[:, :2]
    z  = t_top_verts[:, 2]

    x_range = xy[:, 0].max() - xy[:, 0].min()
    y_range = xy[:, 1].max() - xy[:, 1].min()
    print(f"\n  Top face XY extent: X={x_range:.3f} mm, Y={y_range:.3f} mm")

    # Sample along X at a fixed Y slice
    y_mid = np.median(xy[:, 1])
    y_tol = y_range * 0.05
    slice_mask = np.abs(xy[:, 1] - y_mid) < y_tol
    slice_verts = t_top_verts[slice_mask]

    if len(slice_verts) < 5:
        y_tol = y_range * 0.1
        slice_mask = np.abs(xy[:, 1] - y_mid) < y_tol
        slice_verts = t_top_verts[slice_mask]

    print(f"  X-slice at Y≈{y_mid:.3f} (±{y_tol:.3f}): {len(slice_verts)} vertices")

    if len(slice_verts) >= 5:
        # Sort by X
        order = np.argsort(slice_verts[:, 0])
        xs = slice_verts[order, 0]
        zs = slice_verts[order, 2]

        # Compute spacings between adjacent unique X positions
        spacings = np.diff(xs)
        spacings = spacings[spacings > 1e-6]
        if len(spacings) > 0:
            print(f"  Vertex spacing along X:")
            print(f"    min  = {spacings.min():.4f} mm")
            print(f"    max  = {spacings.max():.4f} mm")
            print(f"    mean = {spacings.mean():.4f} mm")

        # Z variation along the slice
        z_amp = zs.max() - zs.min()
        print(f"  Z amplitude along X-slice: {z_amp:.4f} mm")

        # Try FFT to find dominant frequency
        if len(zs) >= 16:
            # Resample to uniform grid
            x_uniform = np.linspace(xs.min(), xs.max(), len(zs))
            z_interp = np.interp(x_uniform, xs, zs)
            dx = x_uniform[1] - x_uniform[0]
            fft_vals = np.fft.rfft(z_interp - z_interp.mean())
            freqs = np.fft.rfftfreq(len(z_interp), d=dx)
            power = np.abs(fft_vals)**2
            if len(power) > 1:
                dominant_idx = np.argmax(power[1:]) + 1
                dominant_freq = freqs[dominant_idx]
                dominant_wavelength = 1.0 / dominant_freq if dominant_freq > 0 else float('inf')
                print(f"\n  FFT dominant frequency : {dominant_freq:.4f} cycles/mm")
                print(f"  Dominant wavelength    : {dominant_wavelength:.4f} mm")
                print(f"  (i.e., one bump every  ~{dominant_wavelength:.2f} mm)")

    # Also sample along Y
    x_mid = np.median(xy[:, 0])
    x_tol = x_range * 0.05
    slice_y_mask = np.abs(xy[:, 0] - x_mid) < x_tol
    slice_y_verts = t_top_verts[slice_y_mask]

    if len(slice_y_verts) < 5:
        x_tol = x_range * 0.1
        slice_y_mask = np.abs(xy[:, 0] - x_mid) < x_tol
        slice_y_verts = t_top_verts[slice_y_mask]

    print(f"\n  Y-slice at X≈{x_mid:.3f} (±{x_tol:.3f}): {len(slice_y_verts)} vertices")
    if len(slice_y_verts) >= 5:
        order = np.argsort(slice_y_verts[:, 1])
        ys = slice_y_verts[order, 1]
        zs = slice_y_verts[order, 2]
        spacings = np.diff(ys)
        spacings = spacings[spacings > 1e-6]
        if len(spacings) > 0:
            print(f"  Vertex spacing along Y:")
            print(f"    min  = {spacings.min():.4f} mm")
            print(f"    max  = {spacings.max():.4f} mm")
            print(f"    mean = {spacings.mean():.4f} mm")
        z_amp = zs.max() - zs.min()
        print(f"  Z amplitude along Y-slice: {z_amp:.4f} mm")

        if len(zs) >= 16:
            y_uniform = np.linspace(ys.min(), ys.max(), len(zs))
            z_interp = np.interp(y_uniform, ys, zs)
            dy = y_uniform[1] - y_uniform[0]
            fft_vals = np.fft.rfft(z_interp - z_interp.mean())
            freqs = np.fft.rfftfreq(len(z_interp), d=dy)
            power = np.abs(fft_vals)**2
            if len(power) > 1:
                dominant_idx = np.argmax(power[1:]) + 1
                dominant_freq = freqs[dominant_idx]
                dominant_wavelength = 1.0 / dominant_freq if dominant_freq > 0 else float('inf')
                print(f"  FFT dominant frequency : {dominant_freq:.4f} cycles/mm")
                print(f"  Dominant wavelength    : {dominant_wavelength:.4f} mm")
                print(f"  (i.e., one bump every  ~{dominant_wavelength:.2f} mm)")

def analyze_topology_change(plain, textured):
    """
    Determine whether the texture was achieved by:
    A) Subdividing the top face and displacing (most likely)
    B) Replacing the top face with a new mesh patch
    C) Simply perturbing existing vertices

    Uses aligned vertices (stored by analyze_displacement).
    """
    print(f"\n{'='*60}")
    print("  TOPOLOGY CHANGE ANALYSIS")
    print(f"{'='*60}")

    p_verts = plain._aligned_verts
    t_verts = textured._aligned_verts
    z_flat = plain._z_flat
    tol = 1.0

    # Non-top vertices
    p_non_top = p_verts[p_verts[:, 2] < (z_flat - tol)]
    t_non_top = t_verts[t_verts[:, 2] < (z_flat - tol)]

    print(f"\n  Non-top vertices (aligned Z < {z_flat - tol:.3f}):")
    print(f"    Plain   : {len(p_non_top):,}")
    print(f"    Textured: {len(t_non_top):,}")

    delta = len(t_non_top) - len(p_non_top)
    print(f"    Delta   : {delta:+,}")

    if abs(delta) < 50:
        print("\n  CONCLUSION: Non-top topology is UNCHANGED.")
        print("  => Texture was applied ONLY to the top face.")
        print("  => Technique: top face was SUBDIVIDED + Z-displaced (replaced with a fine grid).")
    else:
        print(f"\n  NOTE: Non-top vertex count differs by {delta} — texture may affect side walls too.")

    p_top_count = len(p_verts) - len(p_non_top)
    t_top_count = len(t_verts) - len(t_non_top)
    print(f"\n  Top-region vertices:")
    print(f"    Plain   : {p_top_count:,}")
    print(f"    Textured: {t_top_count:,}")
    if p_top_count > 0:
        print(f"    Ratio   : {t_top_count / p_top_count:.1f}x")
        print(f"  => Top face was subdivided by ~{t_top_count / p_top_count:.0f}x in vertex count.")

def analyze_normal_perturbation(plain, textured):
    """
    Compare face normals between plain and textured meshes for the top region.
    Uses aligned vertex positions to compute face centroids.
    """
    print(f"\n{'='*60}")
    print("  NORMAL PERTURBATION ANALYSIS")
    print(f"{'='*60}")

    z_flat = plain._z_flat
    tol = 1.5

    # Recompute face centroids in aligned space
    p_verts = plain._aligned_verts
    t_verts = textured._aligned_verts

    p_face_verts = p_verts[plain.faces]   # (N, 3, 3)
    t_face_verts = t_verts[textured.faces]

    p_cents = p_face_verts.mean(axis=1)
    t_cents = t_face_verts.mean(axis=1)

    p_top_mask = p_cents[:, 2] >= (z_flat - tol)
    t_top_mask = t_cents[:, 2] >= (z_flat - tol)

    p_top_normals = plain.face_normals[p_top_mask]
    t_top_normals = textured.face_normals[t_top_mask]

    print(f"\n  Plain top-face normals ({len(p_top_normals)} faces):")
    if len(p_top_normals) > 0:
        print(f"    Z-component: mean={p_top_normals[:,2].mean():.4f}, std={p_top_normals[:,2].std():.6f}")
        print(f"    X-component: mean={p_top_normals[:,0].mean():.6f}, std={p_top_normals[:,0].std():.6f}")
        print(f"    Y-component: mean={p_top_normals[:,1].mean():.6f}, std={p_top_normals[:,1].std():.6f}")
        # Are they all [0,0,1]?
        all_upward = np.all(p_top_normals[:, 2] > 0.99)
        print(f"    All pointing straight up (Z > 0.99): {all_upward}")

    print(f"\n  Textured top-face normals ({len(t_top_normals)} faces):")
    if len(t_top_normals) > 0:
        print(f"    Z-component: mean={t_top_normals[:,2].mean():.4f}, std={t_top_normals[:,2].std():.4f}")
        print(f"    X-component: mean={t_top_normals[:,0].mean():.6f}, std={t_top_normals[:,0].std():.4f}")
        print(f"    Y-component: mean={t_top_normals[:,1].mean():.6f}, std={t_top_normals[:,1].std():.4f}")
        all_upward = np.all(t_top_normals[:, 2] > 0.99)
        print(f"    All pointing straight up (Z > 0.99): {all_upward}")

        # Distribution of normal tilt
        tilt = np.arccos(np.clip(t_top_normals[:, 2], -1, 1)) * 180 / np.pi
        print(f"\n  Normal tilt angle from vertical:")
        print(f"    min  = {tilt.min():.2f}°")
        print(f"    max  = {tilt.max():.2f}°")
        print(f"    mean = {tilt.mean():.2f}°")
        print(f"    std  = {tilt.std():.2f}°")
        if tilt.max() > 5:
            print("  => Normals are SIGNIFICANTLY PERTURBED — confirms real vertex displacement.")
        else:
            print("  => Normals are nearly flat — displacement may be very subtle.")

def check_grid_regularity(t_top_verts):
    """
    Check if the textured top-face vertices lie on a regular grid (indicates bump-map baking).
    """
    print(f"\n{'='*60}")
    print("  GRID REGULARITY CHECK")
    print(f"{'='*60}")

    if len(t_top_verts) < 20:
        print("  Not enough vertices.")
        return

    xy = t_top_verts[:, :2]

    # Get unique X and Y values (quantized to 0.001mm)
    x_vals = np.unique(np.round(xy[:, 0], 3))
    y_vals = np.unique(np.round(xy[:, 1], 3))

    print(f"\n  Unique X values: {len(x_vals)}")
    print(f"  Unique Y values: {len(y_vals)}")

    if len(x_vals) > 2:
        x_spacings = np.diff(x_vals)
        print(f"  X spacing: min={x_spacings.min():.4f}, max={x_spacings.max():.4f}, mean={x_spacings.mean():.4f}, std={x_spacings.std():.4f}")
        x_regular = x_spacings.std() / x_spacings.mean() < 0.01
        print(f"  X grid is regular: {x_regular}")

    if len(y_vals) > 2:
        y_spacings = np.diff(y_vals)
        print(f"  Y spacing: min={y_spacings.min():.4f}, max={y_spacings.max():.4f}, mean={y_spacings.mean():.4f}, std={y_spacings.std():.4f}")
        y_regular = y_spacings.std() / y_spacings.mean() < 0.01
        print(f"  Y grid is regular: {y_regular}")

    if len(x_vals) > 2 and len(y_vals) > 2:
        expected_grid = len(x_vals) * len(y_vals)
        actual = len(t_top_verts)
        print(f"\n  Grid completeness: {actual} actual vs {expected_grid} expected ({actual/expected_grid*100:.1f}%)")
        if actual / expected_grid > 0.8:
            print("  => REGULAR GRID confirmed — texture is a baked displacement map on a uniform grid.")
        else:
            print("  => Not a complete regular grid — may be triangulated mesh with non-grid layout.")

def summarize():
    print(f"\n{'='*60}")
    print("  SUMMARY FOR REPLICATION")
    print(f"{'='*60}")
    print("""
  Based on findings above, the texture technique is likely:

  1. IDENTIFY the top face of the STL (highest Z plane).
  2. REMOVE the original flat top face triangles.
  3. CREATE a fine regular 2D grid over the XY footprint of that face.
  4. APPLY a displacement function to the Z coordinate of each grid vertex:
       z_new = z_flat + amplitude * f(x, y)
     where f(x,y) could be:
       - sin(kx) * sin(ky)  — simple sinusoidal bump
       - Perlin/simplex noise
       - Voronoi cells (grass texture)
       - Combination
  5. TRIANGULATE the displaced grid (two triangles per quad).
  6. MERGE with the rest of the STL body.
  7. ENSURE watertightness at the boundary (seam vertices match).

  For golf green surfaces:
  - amplitude ~ 0.3–0.5 mm (matches "amp0p50" in filename)
  - Use fine grid spacing (0.5–1.0 mm) for smooth texture
  - Apply only to the green surface face, not the sides/bottom
  - For fringe: slightly coarser / higher amplitude
    """)

def main():
    plain    = load_mesh(PLAIN_STL)
    textured = load_mesh(TEXTURED_STL)

    p_bb, p_dims = basic_stats(plain,    "PLAIN    — push stick (after Fisher).stl")
    t_bb, t_dims = basic_stats(textured, "TEXTURED — push stick (after Fisher)_custom_amp0p50.stl")

    print(f"\n--- Difference ---")
    print(f"  Vertex delta: {len(textured.vertices) - len(plain.vertices):+,}")
    print(f"  Face delta  : {len(textured.faces) - len(plain.faces):+,}")
    print(f"  Volume delta: {textured.volume - plain.volume:+.4f} mm³")

    analyze_face_normals(plain,    "Plain")
    analyze_face_normals(textured, "Textured")

    t_top_verts, z_flat = analyze_displacement(plain, textured)
    analyze_topology_change(plain, textured)
    analyze_spatial_frequency(t_top_verts, z_flat)
    analyze_normal_perturbation(plain, textured)
    check_grid_regularity(t_top_verts)
    summarize()

if __name__ == "__main__":
    main()
