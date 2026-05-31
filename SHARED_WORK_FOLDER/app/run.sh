#!/bin/bash
cd "$(dirname "$0")"
pip install flask --quiet 2>/dev/null
mkdir -p logs
set -o pipefail
{
  echo ""
  echo "===== $(date '+%Y-%m-%d %H:%M:%S') — server start ====="
  # -u: unbuffered stdout/stderr so prints appear live in the log (otherwise
  # Python line-buffers when its stdout is a pipe, hiding generation output
  # until the buffer flushes).
  python -u app.py 2>&1
} | tee -a logs/server.log
