import sys, os
APP_DIR = "/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/app"
sys.path.insert(0, APP_DIR)
os.chdir(APP_DIR)

from gradient_surface_diagnostic import run_pipeline

egm_path = "/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/ItWentIn/GolfCourses/Stanford/EGMs/Stanford (Hole 08).egm"
out = run_pipeline(egm_path, include_boundary_region=False, apply_fringe_frame_cap=True)
print(f"OUT: {out}")
