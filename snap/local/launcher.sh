#!/bin/bash
set -euo pipefail
APPDIR="${SNAP}/share/universal-downloader"

# GNOME-Extension setzt PYTHONHOME auf das SDK — das hat kein tkinter/_ssl.
unset PYTHONHOME
export PYTHONNOUSERSITE=1
export PATH="${SNAP}/usr/bin:${SNAP}/bin:${PATH:-}"
export PYTHONPATH="${APPDIR}:${SNAP}/lib/python3.12/site-packages:${SNAP}/usr/lib/python3/dist-packages:${SNAP}/usr/lib/python3.12:${SNAP}/usr/lib/python3.12/lib-dynload"
export TCL_LIBRARY="${SNAP}/usr/share/tcltk/tcl8.6"
export TK_LIBRARY="${SNAP}/usr/share/tcltk/tk8.6"

for d in "${SNAP}/usr/lib/"*-linux-gnu; do
  if [ -d "$d" ]; then
    extra="$d"
    [ -d "${d}/blas" ] && extra="${extra}:${d}/blas"
    [ -d "${d}/lapack" ] && extra="${extra}:${d}/lapack"
    export LD_LIBRARY_PATH="${extra}${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
  fi
done

cd "$APPDIR"
# python3 kommt aus core24 (/usr/bin); im App-Snap ist er nicht gestaged.
if [ -x "${SNAP}/usr/bin/python3" ]; then
  exec "${SNAP}/usr/bin/python3" "${APPDIR}/start.py" "$@"
fi
exec /usr/bin/python3 "${APPDIR}/start.py" "$@"
