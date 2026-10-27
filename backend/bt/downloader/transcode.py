"""Optional post-download GPU re-encode (NVIDIA NVENC).

Downloads are already H.264/AAC mp4 (see ytdl.download_format), so this is not about
compatibility: YouTube serves H.264 at ~4-6 Mbps, and re-encoding it with h264_nvenc at
constant quality roughly halves the bytes, so the storage cap fits about twice as many
videos — on the GPU, in seconds, without touching the CPU.

Runs only when settings cache.hw_transcode is on. If NVENC is unavailable (no GPU wired
to the container, driver mismatch, ffmpeg without nvenc) the original file is kept and
the downloader stops trying for the rest of the process.
"""
from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Callable, Optional

log = logging.getLogger("bt.downloader")

NVENC = "h264_nvenc"
CQ = 27  # constant-quality VBR target; 0-51 like x264, ~26-28 is visually safe at 1080p
PRESET = "p5"  # p1 fastest … p7 best quality per bit

UNAVAILABLE_MARKERS = (
	"libnvidia-encode",          # driver encode lib not mounted in the container
	"no capable devices",        # /dev/nvidia* missing
	"driver does not support the required nvenc api version",
	"cannot load libcuda",
	"failed to load nvidia-encode",
	"unknown encoder",           # ffmpeg build without nvenc
)


def nvenc_cmd(src: Path, dst: Path) -> list[str]:
	"""Re-encode src into dst with NVENC. Audio is copied; output is faststart mp4."""
	return [
		"ffmpeg", "-hide_banner", "-nostdin", "-loglevel", "error", "-y",
		"-i", str(src),
		"-c:v", NVENC, "-preset", PRESET, "-rc", "vbr", "-cq", str(CQ), "-b:v", "0",
		"-c:a", "copy",
		"-movflags", "+faststart",
		"-progress", "pipe:1", "-nostats",
		str(dst),
	]


def nvenc_unavailable(err: str) -> bool:
	e = err.lower()
	return any(m in e for m in UNAVAILABLE_MARKERS)


def reencode(src: Path, dst: Path, duration_s: float = 0.0,
             on_progress: Optional[Callable[[float], None]] = None,
             should_abort: Optional[Callable[[], Optional[str]]] = None) -> tuple[str, str]:
	"""Run the re-encode. -> (status, detail) with status one of:
	"ok"           dst written, replaces nothing (caller moves it);
	"aborted"      should_abort fired, ffmpeg killed, src untouched;
	"unavailable"  NVENC not usable on this host — do not retry this process;
	"failed"       anything else (stderr tail in detail)."""
	if should_abort and should_abort():
		return "aborted", "stopped before starting"
	try:
		proc = subprocess.Popen(nvenc_cmd(src, dst), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
	except FileNotFoundError:
		return "unavailable", "ffmpeg not installed"
	assert proc.stdout is not None
	for line in proc.stdout:
		if not line.startswith("out_time_ms="):
			continue
		try:
			out_ms = int(float(line.split("=", 1)[1]))
		except ValueError:
			continue
		if duration_s > 0 and on_progress:
			on_progress(min(0.999, max(0.0, out_ms / (duration_s * 1000))))
		if should_abort and should_abort():
			proc.kill()
			proc.wait()
			return "aborted", "stopped"
	err = (proc.stderr.read() or "") if proc.stderr else ""
	rc = proc.wait()
	if rc != 0 or not dst.is_file() or dst.stat().st_size == 0:
		tail = " ".join(err.strip().splitlines()[-3:])[-300:]
		return ("unavailable" if nvenc_unavailable(err) else "failed"), tail or f"ffmpeg exited {rc}"
	return "ok", ""
