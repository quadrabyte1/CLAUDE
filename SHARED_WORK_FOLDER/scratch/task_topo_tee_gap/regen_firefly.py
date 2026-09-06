"""Regenerate Firefly Hole 14 3MF via run_pipeline and capture the tee_hole logs."""
import sys, os
APP_DIR = "/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/app"
sys.path.insert(0, APP_DIR)
os.chdir(APP_DIR)

from gradient_surface_diagnostic import run_pipeline

egm_path = "/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/ItWentIn/GolfCourses/Firefly/EGMs/Firefly (Hole 14).egm"

out = run_pipeline(egm_path, include_boundary_region=False, apply_fringe_frame_cap=True)
print(f"\nOUT: {out}")
