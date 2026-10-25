#!/bin/sh
set -e
# YouTube breaks yt-dlp regularly; optionally pull the newest release at start.
if [ "${BT_YTDLP_AUTOUPDATE:-1}" = "1" ]; then
  pip install -q -U --pre "yt-dlp[default]" || echo "yt-dlp update failed, using bundled version"
fi
exec "$@"
