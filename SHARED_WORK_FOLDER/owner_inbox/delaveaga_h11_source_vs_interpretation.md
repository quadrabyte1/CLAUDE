# Delaveaga H11: source vs interpretation (Topo, diagnose-only)

**Verdict: interpretation. The source image is fine.** Arrow detection and the downhill sign are also fine. The Poisson solver is wrong.

## Evidence
- Source: green = high (top-left), blue = low (bottom). Arrows point downhill toward blue. Numbers are slope %. Nothing odd at top-center. Arrows there exit the green edge, which is normal.
- Detected arrows (103) match the drawn arrows in direction (red-over-navy overlay, left panel of the experiment image). Sign is right: flipping it makes correlation with the image colour worse (+0.59 vs -0.59).
- Pit location = the solver's pin cell. `solve_poisson_height` pins the first inside cell in row-major order (`gradient_surface_diagnostic.py` ~1330-1345) to 0. That cell is px (273,66), exactly the "LOW 0.000" pit.
- The Neumann Poisson system has net non-zero divergence. The RHS (~1305-1325) uses `Gx/Gy` that are 0 outside the mask, so fake divergence appears along the whole boundary. A single Dirichlet pin then acts as a point sink. Result: a spike at the pin and a flattened rest (range ~100-186, S/E edges brown instead of blue).
- Control: a plain least-squares gradient fit (no pin) on the same arrows gives high top-left, low bottom-right/south, matching the image. Correlation with image blueness is -0.82 vs -0.59 now.

## Secondary
- `detect_arrows` rejected 4 blobs within 30 px of a decimal dot (~1100). Some may be real arrows. Minor.

## Fix (concept)
Replace the pinned Poisson solve with a least-squares fit of grid differences to G (or build a consistent Neumann RHS and pin via least squares or mean-zero). Do not pin a boundary cell.

## Images
`owner_inbox/diagnostics/h11_experiment_pin_vs_lsq.png` (left: source + arrows + pin star; middle: current; right: least-squares fit).
