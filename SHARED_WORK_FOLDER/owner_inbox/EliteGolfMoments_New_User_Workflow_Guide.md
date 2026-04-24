# EliteGolfMoments — New User Workflow Guide

This guide covers the two things you will most often produce:

1. **A 3D model of a golf hole** (green surface, fringe, and sand traps) — delivered as a `.3mf` assembly file and a set of individual `.stl` pieces ready to print.
2. **A commemorative plaque** for the person who made a hole-in-one at that hole — delivered as a `.3mf` file ready to load in Bambu Studio.

---

## 1. What You Will Produce

**Hole model** — a multi-piece 3D print of the putting green and its immediate surroundings. The finished files include a smooth green surface (with grass texture), a terraced/stepped variant, a fringe ring, and individual sand trap pieces. Everything is bundled into a single `.3mf` assembly for Bambu Studio.

**Plaque** — an oval commemorative plaque with three lines of engraved text (course name, recipient's name, hole/club/date). Delivered as a single `.3mf` ready to print.

---

## 2. Before You Start

The following is assumed to be already in place on your machine:

- **Python environment** — all dependencies installed (Flask, OpenCV, NumPy, SciPy, trimesh, Shapely, scikit-image, matplotlib, skimage).
- **Flask app running** — launched via `./go.sh` from the repo root, listening on **port 5051**.
- **Bambu Studio** installed for slicing and printing.
- **Source imagery** — a top-down aerial/GolfLogix image of the hole already placed in the correct folder:
  ```
  EliteGolfMoments/GolfCourses/<Course Name>/Images/
  ```
  The image filename can be anything; it just needs to be in that folder before you start.
- **Folder structure** — each course has four subfolders that the app reads and writes automatically:
  ```
  EliteGolfMoments/GolfCourses/<Course Name>/
  ├── Images/    ← source imagery (you put it here)
  ├── EGMs/      ← boundary project files (auto-saved by the editor)
  ├── STLs/      ← individual piece STLs (written by the generator)
  └── 3MFs/      ← assembled 3MF files (written by the generator)
  ```

**To start the app** (if it is not already running):

```bash
cd /path/to/SHARED_WORK_FOLDER
./go.sh
```

The terminal will print `Running on http://0.0.0.0:5001`. Open a browser to `http://localhost:5051`.

---

## Part 1 — Producing a New Hole at a Golf Course

### Step 1 — Open the Boundary Editor

Navigate to:

```
http://localhost:5051/editor
```

This is the **Boundary Editor v3.10**. It is where you trace the shapes that define the green, sand traps, and contour lines on the source image.

### Step 2 — Create a New Project

Click **New Project** in the top action bar. A dialog opens asking for three things:

- **Golf Course** — type the course name exactly as it appears (or will appear) in the folder structure, e.g. `Moffett Field`. This becomes the folder name.
- **Hole Number** — e.g. `7`. This is used to name all output files.
- **Source Image** — select from the dropdown. The dropdown lists all images found in `GolfCourses/*/Images/` and in `team_inbox/`. Choose the image for this hole.

Click **OK**. The editor loads the image and immediately runs automatic boundary detection. After a few seconds you will see:

- A **green outline** (green polygon, ~8 control points).
- **Trap outlines** (red polygons, ~16 control points each, one per detected sand trap).

A status message in the top-right of the action bar confirms how many regions were detected, e.g. `Detected 3 region(s) + 0 contour(s)`.

The project is auto-saved to `EGMs/` as soon as detection completes. You do not need to manually save.

### Step 3 — Adjust the Boundaries

Inspect the auto-detected outlines against the image. Drag the circular control points to correct any region that doesn't match the actual green or trap shape.

**Mouse controls:**
- **Drag** a vertex to reposition it.
- **Right-click an edge** to insert a new vertex at that spot and immediately drag it.
- **Right-click a vertex** to remove it (minimum 3 per polygon).
- **Cmd+Z / Cmd+Shift+Z** — undo / redo.

**Adding a trap that wasn't auto-detected:** The editor currently provides Add Trap functionality accessible via JavaScript (`addTrap()`). If auto-detection missed a trap, you may need to adjust existing trap boundaries or add one manually.

Every drag automatically saves back to the `.egm` file.

**Green style:** In the action bar there is a **Green** dropdown with two options:

- `Smooth` — a continuously curved surface derived from the slope arrows.
- `Terraced` — the same surface divided into discrete stepped elevation bands.

Select the style you want before generating.

### Step 4 — Add Contour Lines (Optional)

If the hole image contains visible black contour lines (elevation isolines), you can add them for a more accurate stepped model. Click **Add Contour** in the action bar, click to place points along a contour line, then double-click or press **Enter** to finish. Click the red arrow button at the midpoint of the contour to flip which side is uphill.

Each contour line crossing adds a 10 mm elevation step by default. If you do not add any contours the generator falls back to the gradient-arrow Poisson surface, which still produces a realistic slope.

### Step 5 — Generate the 3D Models

Click the teal **Generate** button in the action bar. The button is only active when there is at least one polygon and both the course name and hole number are set.

The generator runs in the background (this takes 30–120 seconds depending on image resolution). Watch the status message in the top-right of the action bar. When it finishes you will see:

```
Generated: Moffett Field (Hole 7).3mf
```

If the status turns red with an error message, check the Flask terminal for a traceback.

### Step 6 — Verify the Outputs

After a successful generation the following files will have been written:

**STLs** (`EliteGolfMoments/GolfCourses/<Course>/STLs/`):

| File | Description |
|------|-------------|
| `<slug>_smooth_surface.stl` | Green surface with grass texture |
| `<slug>_smooth_surface_flat.stl` | Green surface, flat (no texture) |
| `<slug>_stepped_surface.stl` | Green with terraced elevation bands |
| `<slug>_fringe.stl` | Fringe ring (grass-textured, 5.6 mm mounting hole) |
| `<slug>_fringe_flat.stl` | Fringe ring, flat reference |
| `<slug>_trap_1.stl`, `_trap_2.stl`, … | One file per sand trap |

Where `<slug>` is the lowercased, underscore-separated version of `<course>_hole_<number>`, e.g. `moffett_field_hole_7`.

**3MF assembly** (`EliteGolfMoments/GolfCourses/<Course>/3MFs/`):

```
<Course> (Hole <N>).3mf
```

e.g. `Moffett Field (Hole 7).3mf`

**Diagnostic images** (`EliteGolfMoments/GolfCourses/<Course>/Images/`):

```
<slug>_arrow_directions.png   ← slope arrows overlaid on the green
<slug>_height_map.png         ← false-color height map
<slug>_gradient_contours.png  ← contour lines on the height field
```

---

## Part 2 — Producing a New Plaque for the Hole-in-One Recipient

### Step 1 — Open the Plaque Generator

Navigate to:

```
http://localhost:5051/plaque
```

This is the **Custom Text Plaque** page.

### Step 2 — Fill in the Plaque Text

The plaque has three text lines. Fill them in:

| Field | Label in UI | Example |
|-------|-------------|---------|
| Course (optional) | Course | `Moffett Field` |
| Line 1 | Line 1 — Top | `Moffett Field Golf Course` |
| Line 2 | Line 2 — Middle | `Mike Kallbrier — Hole in One` |
| Line 3 | Line 3 — Bottom | `Hole 7   8 Iron   10/9/25` |

**Course field:** If you enter a course name here the output `.3mf` will be saved to `GolfCourses/<course>/3MFs/`. If left blank it goes to `owner_inbox/`. Entering the course name is recommended so the plaque lives alongside the hole model.

You can leave any line blank if you only need one or two lines. Text is automatically scaled to fit the 130 mm plaque width.

### Step 3 — Choose Font and Style (Optional)

- **Font** — select from the dropdown of fonts available on the system. The default is `Orbitron`.
- **Bold** and **Italic** checkboxes apply to all three lines equally.

### Step 4 — Generate

Click the teal **Generate** button. Generation takes a few seconds. When complete, a green confirmation panel appears:

```
3MF generated successfully
Saved to GolfCourses/Moffett Field/3MFs/Mike_Kallbrier__Hole_in_One.3mf
```

The filename is derived from Line 2 (or Line 1 if Line 2 is blank), with special characters stripped and spaces replaced by underscores.

---

## 3. Where the Outputs Live

```
EliteGolfMoments/
├── GolfCourses/
│   └── <Course Name>/
│       ├── Images/
│       │   ├── <source image>.png
│       │   ├── <slug>_arrow_directions.png
│       │   ├── <slug>_height_map.png
│       │   └── <slug>_gradient_contours.png
│       ├── EGMs/
│       │   └── <Course> (Hole <N>).egm       ← boundary project (editable)
│       ├── STLs/
│       │   ├── <slug>_smooth_surface.stl
│       │   ├── <slug>_smooth_surface_flat.stl
│       │   ├── <slug>_stepped_surface.stl
│       │   ├── <slug>_fringe.stl
│       │   ├── <slug>_fringe_flat.stl
│       │   └── <slug>_trap_N.stl
│       └── 3MFs/
│           ├── <Course> (Hole <N>).3mf       ← hole assembly
│           └── <Recipient_Name>.3mf           ← plaque
└── Frames/
    └── (frame STEP/3MF files — physical frame parts, not generated here)
```

If no course name was given during plaque generation the plaque `.3mf` lands in `owner_inbox/` at the repo root.

---

## 4. What to Hand Off for Printing

### Hole model

Open `<Course> (Hole <N>).3mf` in Bambu Studio. This is the full assembly — it contains the smooth green surface, fringe, and all sand traps as separate objects. Assign filament colors per object in the slicer as needed:

- Green surface — green filament.
- Fringe — green filament (same shade or a slightly different texture filament).
- Sand traps — sand/beige filament.

Slice and print normally. The fringe piece has a pre-bored 5.6 mm mounting hole (in the rear corner) for a golf-ball stand peg.

### Plaque

Open `<Recipient>.3mf` in Bambu Studio. The plaque is flat and ready to print as-is, centered on the build plate. It has four parts: the oval plaque base, three text lines, and a border frame. Assign filaments:

- Plaque base and border — your choice of base color.
- Text lines — contrasting color for readability.

Slice with standard settings.

---

## 5. Reopening an Existing Hole Project

If you need to re-edit boundaries or regenerate a hole model:

1. Go to `http://localhost:5051/editor`.
2. Click **Open Project**.
3. Select the course and hole from the list.
4. The editor reloads the image and restores all polygons and contour lines from the saved `.egm` file.
5. Make adjustments, then click **Generate** again.

---

## 6. Troubleshooting Quick Hits

**App not responding at `http://localhost:5051`**

The Flask server is not running. Start it:
```bash
cd /path/to/SHARED_WORK_FOLDER
./go.sh
```

**Source image does not appear in the New Project dropdown**

The image must be in `EliteGolfMoments/GolfCourses/<Course>/Images/` (or `team_inbox/`). Add it there and reload the editor page.

**Generate button is greyed out**

The button requires at least one polygon and both a course name and hole number to be set. These are populated when you create or open a project.

**Generation fails with "EGM file not found"**

The editor's auto-save may not have completed before you clicked Generate. Click somewhere on the canvas to trigger an auto-save, wait a moment, then click Generate again.

**Plaque generation fails**

Check that the `EliteGolfMoments/Frames/Mike Kallbrier.3mf` template file exists. The plaque generator uses it as a base. If it is missing, report it — the template must be restored from version control.
