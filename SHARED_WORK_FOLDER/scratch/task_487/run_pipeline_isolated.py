"""
Task 487 — run the gradient_surface_diagnostic pipeline on Los Lagos Hole 16
with the k=1 revert applied, with ALL outputs redirected into scratch/task_487
so nothing in EliteGolfMoments/ or its serial.json is disturbed.

Mirrors scratch/task_486/run_pipeline_isolated.py; only the SCRATCH root and
the FAKE_COURSE name differ.
"""
from __future__ import annotations
import io
import json
import shutil
import sys
from pathlib import Path

REPO = Path("/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER").resolve()
APP = REPO / "app"
sys.path.insert(0, str(APP))

SCRATCH = REPO / "scratch" / "task_487"
SCRATCH.mkdir(parents=True, exist_ok=True)

FAKE_COURSE = "TaskFourEightSeven"
FAKE_ROOT = SCRATCH / "GolfCourses" / FAKE_COURSE
(FAKE_ROOT / "EGMs").mkdir(parents=True, exist_ok=True)
(FAKE_ROOT / "3MFs").mkdir(parents=True, exist_ok=True)
(FAKE_ROOT / "Images").mkdir(parents=True, exist_ok=True)

REAL_EGM = REPO / "EliteGolfMoments" / "GolfCourses" / "Los Lagos" / "EGMs" / "Los Lagos (Hole 16).egm"

egm = json.loads(REAL_EGM.read_text())
img_name = egm["image"]
img_course = egm.get("imageCourse", "Los Lagos")

src_img_dir = REPO / "EliteGolfMoments" / "GolfCourses" / img_course / "Images"
src_img = src_img_dir / img_name
dst_img = FAKE_ROOT / "Images" / img_name
if not dst_img.exists():
    shutil.copy2(src_img, dst_img)

egm["course"] = FAKE_COURSE
egm["imageCourse"] = FAKE_COURSE
scratch_egm = FAKE_ROOT / "EGMs" / f"{FAKE_COURSE} (Hole 16).egm"
scratch_egm.write_text(json.dumps(egm, indent=2))

(FAKE_ROOT / "serial.json").write_text(json.dumps({"next": 900}))

import generate_stl_3mf
generate_stl_3mf.EGM_BASE = str(SCRATCH / "GolfCourses")

import gradient_surface_diagnostic as gsd
gsd.course_paths = generate_stl_3mf.course_paths

import serial_engraver
if hasattr(serial_engraver, "EGM_BASE"):
    serial_engraver.EGM_BASE = str(SCRATCH / "GolfCourses")

log_path = SCRATCH / "pipeline_stdout.log"
print(f"Running run_pipeline on: {scratch_egm}")
print(f"Logging stdout to:       {log_path}")

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

# Copy the produced 3MF to a stable filename for downstream tests.
out_path = Path(out)
stable = SCRATCH / "Los_Lagos_Hole_16_task_487_test.3mf"
shutil.copy2(out_path, stable)
print(f"\nGenerated: {out}")
print(f"Copied to: {stable}")
print(f"Log: {log_path}")
