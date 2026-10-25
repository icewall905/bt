#!/bin/bash
# Install bt-mode on the projector host (run as root on 10.0.10.73).
# - /home/console/bin/bt-mode
# - xbindkeys: remote button 6 (Ctrl+Shift+Y) -> bt-mode
# - other *-mode scripts kill the bt-app window when switching away
set -euo pipefail
BIN=/home/console/bin
TS=$(date +%Y%m%d_%H%M%S)
HERE=$(cd "$(dirname "$0")" && pwd)

install -o console -g console -m 755 "$HERE/bt-mode" "$BIN/bt-mode"

RC=/home/console/.xbindkeysrc
if ! grep -q 'bin/bt-mode' "$RC"; then
  cp -a "$RC" "$RC.bak.bt.$TS"
  printf '"/home/console/bin/bt-mode"\n  Control+Shift+y\n' >> "$RC"
fi

for f in desktop-mode jellyfin-mode kodi-mode smarttube-mode steam-mode youtube-tv-mode vacuumtube-mode; do
  p="$BIN/$f"
  [ -f "$p" ] || continue
  grep -q 'pkill -f bt-app' "$p" && continue
  cp -a "$p" "$p.bak.bt.$TS"
  # add right after the first competitor kill line
  sed -i '0,/^\( *\)pkill -f \(kodi\|vacuumtube\) .*$/s//&\n\1pkill -f bt-app      2>\/dev\/null \&/' "$p"
done

# xbindkeys re-reads its rc on SIGHUP
pkill -HUP -x xbindkeys || true
echo "bt-mode installed (remote button 6 / Ctrl+Shift+Y)"
