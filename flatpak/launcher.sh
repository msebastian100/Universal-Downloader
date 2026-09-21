#!/bin/bash
set -euo pipefail
APPDIR="/app/share/universal-downloader"
export PYTHONPATH="${APPDIR}${PYTHONPATH:+:${PYTHONPATH}}"
export TCL_LIBRARY="${TCL_LIBRARY:-/app/lib/tcl9.0}"
export TK_LIBRARY="${TK_LIBRARY:-/app/lib/tk9.0}"
export PATH="/app/bin:/app/lib/ffmpeg/bin:${PATH:-}"
cd "$APPDIR"
exec python3 "${APPDIR}/start.py" "$@"
