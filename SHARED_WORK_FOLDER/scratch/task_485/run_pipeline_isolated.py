"""
Run the gradient_surface_diagnostic pipeline on Los Lagos Hole 16, but with
ALL outputs (3MF, serial.json) redirected into scratch/task_485 so nothing
in EliteGolfMoments/ or its serial.json is disturbed.

Captures the full stdout of the pipeline (including the `_verify_fringe_boundary`
diagnostics) into scratch/task_485/pipeline_stdout.log.
"""
from __future__ import annotations
import os
import shutil
import sys
from pathlib import Path

REPO = Path("/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER").resolve()
APP = REPO / "app"
sys.path.insert(0, str(APP))

SCRATCH = REPO / "scratch" / "task_485"
SCRATCH.mkdir(parents=True, exist_ok=True)

# ── Stage a scratch course tree that mirrors the real Los Lagos layout ──
FAKE_COURSE = "TaskFourEightFive"
FAKE_ROOT = SCRATCH / "GolfCourses" / FAKE_COURSE
(FAKE_ROOT / "EGMs").mkdir(parents=True, exist_ok=True)
(FAKE_ROOT / "3MFs").mkdir(parents=True, exist_ok=True)
(FAKE_ROOT / "Images").mkdir(parents=True, exist_ok=True)

REAL_EGM = REPO / "EliteGolfMoments" / "GolfCourses" / "Los Lagos" / "EGMs" / "Los Lagos (Hole 16).egm"
REAL_IMG_DIR = REPO / "EliteGolfMoments" / "GolfCourses" / "Los Lagos" / "Images"

# We keep the EGM's course = "Los Lagos" so the image path in it resolves, then
# override the course_paths output target so the 3MF/serial write into scratch.
# Simpler alternative: patch the EGM's course to FAKE_COURSE and copy the image.
import json
egm = json.loads(REAL_EGM.read_text())
img_name = egm["image"]
img_course = egm.get("imageCourse", "Los Lagos")

# Copy image into scratch Images/
src_img_dir = REPO / "EliteGolfMoments" / "GolfCourses" / img_course / "Images"
src_img = src_img_dir / img_name
dst_img = FAKE_ROOT / "Images" / img_name
if not dst_img.exists():
    shutil.copy2(src_img, dst_img)

# Point the EGM at our fake course
egm["course"] = FAKE_COURSE
egm["imageCourse"] = FAKE_COURSE
scratch_egm = FAKE_ROOT / "EGMs" / f"{FAKE_COURSE} (Hole 16).egm"
scratch_egm.write_text(json.dumps(egm, indent=2))

# Prime a serial.json so peek/commit lands in scratch
(FAKE_ROOT / "serial.json").write_text(json.dumps({"next": 900}))

# Monkey-patch EGM_BASE so course_paths(FAKE_COURSE) resolves into scratch
import generate_stl_3mf
generate_stl_3mf.EGM_BASE = str(SCRATCH / "GolfCourses")

# The diagnostic imports course_paths at the top of the file. Patch there too.
import gradient_surface_diagnostic as gsd
gsd.course_paths = generate_stl_3mf.course_paths  # already patched via EGM_BASE

# serial_engraver reads a course-relative serial.json — same EGM_BASE mechanism
import serial_engraver
if hasattr(serial_engraver, "EGM_BASE"):
    serial_engraver.EGM_BASE = str(SCRATCH / "GolfCourses")

# Run pipeline
log_path = SCRATCH / "pipeline_stdout.log"
print(f"Running run_pipeline on: {scratch_egm}")
print(f"Logging stdout to:       {log_path}")

import io
buf = io.StringIO()
class Tee:
    def __init__(self, a, b):
        self.a, self.b = a, b
    def write(self, s):
        self.a.write(s); self.b.write(s)
    def flush(self):
        self.a.flush(); self.b.flush()

orig_stdout = sys.stdout
sys.stdout = Tee(orig_stdout, buf)
try:
    out = gsd.run_pipeline(str(scratch_egm))
finally:
    sys.stdout = orig_stdout
    log_path.write_text(buf.getvalue())

print(f"\nGenerated: {out}")
print(f"Log: {log_path}")
