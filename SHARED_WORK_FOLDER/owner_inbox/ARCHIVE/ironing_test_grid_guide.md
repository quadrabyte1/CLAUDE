# How to Use the NuggetsInclusive Ironing Test Grid

---

## 1. What Is Ironing?

Ironing is a slicer feature that sends the hot nozzle over the top layer of a flat surface a second time, with very little or no extrusion, to melt and flatten any ridges left by normal printing. Think of it like ironing wrinkles out of fabric. The result is a smoother, sometimes glossy top surface with fewer visible layer lines.

The four settings you'll be tuning:

| Setting | What it does | Typical range |
|---|---|---|
| **Flow** | How much filament extrudes during the iron pass (% of normal) | 5–60% |
| **Speed** | How fast the nozzle moves during the iron pass | 10–50 mm/s |
| **Line spacing** | Distance between parallel ironing passes | ~0.1–0.3 mm |
| **Pattern** | Rectilinear (straight lines) or concentric (rings) | — |

Flow and speed are the two most important dials. Too much flow leaves blobs at edges; too little leaves bare patches. Too fast and the surface stays rough; too slow wastes time without much gain.

---

## 2. The NuggetsInclusive Test Grid

**Model:** [Ironing Test - Bambulab Swatches](https://makerworld.com/en/models/2455055-ironing-test-bambulab-swatches) (MakerWorld, free)

NuggetsInclusive is a 3D printing content creator on MakerWorld. This model is a compact grid of flat swatches — each square is roughly 12 mm across — where every square is pre-configured with a different combination of ironing speed and flow. After printing, you keep the grid as a physical reference card (like a paint chip), label the winner, and you have your settings permanently on hand.

The grid spans:
- **Speed:** 15 to 45 mm/s in 5 mm/s steps
- **Flow:** 0% to 60% in 5% steps

---

## 3. How to Print It

1. Download the `.3mf` file from the MakerWorld link above.
2. Open it in **Bambu Studio** or **OrcaSlicer**. The 3MF includes pre-configured process settings — do not override the ironing settings per-square, as those are baked into the file.
3. Use the same filament you want to calibrate. Ironing behaves differently across materials; run one grid per filament type.
4. The full grid uses a bit over 50 g of filament and takes a while to print — but you only need to do this once per filament type.
5. Standard layer height and top/bottom settings are fine. Do not add brim unless needed for adhesion.

> Note: The file is labelled "Bambulab Swatches" but the underlying ironing parameters work the same in OrcaSlicer.

---

## 4. How to Read the Results

After printing, hold the grid at a low angle under a light (raking light works best — a desk lamp or a window). Tilt it back and forth. This catches surface texture that's hard to see straight-on.

**What you're looking for:**

| Appearance | What it means |
|---|---|
| Smooth, even sheen — matte or satin | Good balance of flow and speed |
| Shiny grooves or stripe lines | Flow too low — nozzle isn't depositing enough to fill gaps |
| Raised ridges or blobbing at square edges | Flow too high — over-extrusion |
| Rough or unchanged surface | Speed too fast — nozzle isn't dwelling long enough to melt |
| Dragged marks or smearing | Speed too slow combined with excess flow |

The differences between adjacent squares are often subtle — more tactile than visual. Run a fingernail lightly across several squares; the smoothest one will catch the least.

**Reading the layout:** Each square is labeled with its speed and flow values (speed first, then flow, e.g. "25 / 20%"). Columns step through speed; rows step through flow. The label is embossed into or next to each square on the print.

---

## 5. Dialing In Your Final Settings

1. Pick the square that looks and feels the best.
2. Note its speed and flow values from the label.
3. In **Bambu Studio**: Go to Process → Quality → enable Advanced Settings → scroll to Ironing. Enter your speed and flow values there.
4. In **OrcaSlicer**: Go to Process → Quality → Ironing. Same fields.
5. Enable ironing on "Top surfaces" or "Topmost surface only" — the latter is faster and usually sufficient.

**Practical starting point** if you want a shortcut before printing the grid: 30% flow at 30–40 mm/s works well for PLA on Bambu machines. Use the grid to confirm or refine from there.

Once you've dialed in a filament, write the winning settings on the back of the grid swatch with a marker. Future you will thank present you.

---

## Sources

- [Ironing Test - Bambulab Swatches by NuggetsInclusive (MakerWorld)](https://makerworld.com/en/models/2455055-ironing-test-bambulab-swatches)
- [Ironing | Prusa Knowledge Base](https://help.prusa3d.com/article/ironing_177488)
- [Ironing | OrcaSlicer Wiki](https://orcaslicer3d.org/wiki/ironing/)
- [Ironing Settings Test | Adaptive Curmudgeon](https://adaptivecurmudgeon.com/2025/07/25/ironing-settings-test/) — real-world walkthrough of a similar test grid
- [Ironing calibration: speed & flow (MakerWorld)](https://makerworld.com/en/models/30075-ironing-calibration-speed-flow-15-40mm-s-10-50%25) — similar grid for cross-reference
