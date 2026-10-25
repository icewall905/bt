"""Local video cache: queue sync, eviction, reconcile and the one-at-a-time download loop.

Runs as its own process (`python -m bt.downloader`). Files live at MEDIA_DIR/<id[:2]>/<id>.mp4; downloads are
staged in MEDIA_DIR/.tmp/<id>/ (yt-dlp `.part` files, resumable) and moved into place atomically when done.
"""
from __future__ import annotations

import logging
import os
import random
import re
import shutil
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Optional

from sqlmodel import Session, col, func, select

from .. import ytdl
from ..config import MEDIA_DIR
from ..db import emit, get_agent_control, get_agent_state, get_settings, save_setting, session, \
    yt_request_counts
from ..models import Candidate, Category, Download, Video, WatchHistory, now

log = logging.getLogger("bt.downloader")

VID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
MAX_ATTEMPTS = 3
RETRY_BASE_S = 600  # 10 min, 20 min, ...
OWN_BLOCK_BACKOFF_S = 3600
STATE_EVERY_S = 1.0
CONTROL_EVERY_S = 2.0
EST_BYTES_PER_S = 600_000  # ~1080p H.264 + AAC, used to reserve room before a download
GB = 1_000_000_000


# ---------------------------------------------------------------- paths

def rel_path(video_id: str) -> str:
    return f"{video_id[:2]}/{video_id}.mp4"


def abs_path(rel: str) -> Optional[Path]:
    """Resolve a DB-stored relative path safely under MEDIA_DIR."""
    if not rel:
        return None
    p = (MEDIA_DIR / rel).resolve()
    return p if MEDIA_DIR.resolve() in p.parents else None


def staging_dir(video_id: str) -> Path:
    return MEDIA_DIR / ".tmp" / video_id


def _aware(d: Optional[datetime]) -> Optional[datetime]:
    return d.replace(tzinfo=timezone.utc) if d is not None and d.tzinfo is None else d


def _parse_ts(v) -> Optional[datetime]:
    if not v:
        return None
    try:
        return _aware(datetime.fromisoformat(str(v).replace("Z", "+00:00")))
    except ValueError:
        return None


# ---------------------------------------------------------------- accounting / queue / eviction

def used_bytes(s: Session) -> int:
    return int(s.exec(select(func.coalesce(func.sum(Download.size_bytes), 0))
                      .where(Download.status == "done")).one() or 0)


def max_bytes(cfg: dict) -> int:
    return int(float(cfg.get("max_gb") or 0) * GB)


def sync_queue(s: Session, cfg: dict) -> int:
    """Queue every accepted, non-dismissed candidate that has no Download row yet (auto == 'accepted').
    Rows that were evicted or deleted by the user are not re-queued automatically."""
    if cfg.get("auto", "accepted") != "accepted":
        return 0
    have = select(Download.video_id)
    ids = s.exec(select(Candidate.video_id).where(Candidate.status == "accepted",
                                                  Candidate.dismissed == False,  # noqa: E712
                                                  col(Candidate.video_id).not_in(have)).distinct()).all()
    for vid in ids:
        if VID_RE.match(vid):
            s.add(Download(video_id=vid, status="queued"))
    if ids:
        s.commit()
    return len(ids)


def _retry_ready(d: Download, t: datetime) -> bool:
    if d.status != "error" or d.attempts >= MAX_ATTEMPTS:
        return False
    last = _aware(d.finished_at) or _aware(d.created_at)
    return last is None or t >= last + timedelta(seconds=RETRY_BASE_S * (2 ** max(d.attempts - 1, 0)))


def next_download(s: Session, last_category: Optional[int] = None) -> tuple[Optional[Download], Optional[int]]:
    """Pinned (manual) first, oldest request first; then auto queue round-robin across categories,
    each category ordered by highest score, newest."""
    t = now()
    rows = [d for d in s.exec(select(Download).where(col(Download.status).in_(["queued", "error"]))).all()
            if d.status == "queued" or _retry_ready(d, t)]
    if not rows:
        return None, last_category
    pinned = sorted([d for d in rows if d.pinned], key=lambda d: _aware(d.created_at) or t)
    if pinned:
        return pinned[0], last_category
    ids = [d.video_id for d in rows]
    cands = s.exec(select(Candidate, Video).join(Video, Video.id == Candidate.video_id, isouter=True)
                   .where(col(Candidate.video_id).in_(ids), Candidate.status == "accepted",
                          Candidate.dismissed == False)).all()  # noqa: E712
    by_cat: dict[int, list[tuple]] = {}
    for c, v in cands:
        pub = _aware(v.published_at) if v and v.published_at else datetime.min.replace(tzinfo=timezone.utc)
        by_cat.setdefault(c.category_id, []).append((-(c.score or 0), -pub.timestamp(), c.video_id))
    if not by_cat:
        return None, last_category
    cats = sorted(by_cat)
    after = [c for c in cats if last_category is not None and c > last_category]
    cat = (after or cats)[0]
    best = sorted(by_cat[cat])[0][2]
    return next(d for d in rows if d.video_id == best), cat


def eviction_order(s: Session, allow_wanted: bool) -> list[Download]:
    """Done, non-pinned downloads in eviction order:
    0) finished by every profile that watched them, 1) no longer wanted (dismissed/rejected/no accepted
    candidate), 2) still wanted (only when allow_wanted). LRU (last played, else finished) within a group."""
    done = s.exec(select(Download).where(Download.status == "done", Download.pinned == False)).all()  # noqa: E712
    if not done:
        return []
    ids = [d.video_id for d in done]
    wanted = set(s.exec(select(Candidate.video_id).where(col(Candidate.video_id).in_(ids),
                                                         Candidate.status == "accepted",
                                                         Candidate.dismissed == False)).all())  # noqa: E712
    hist: dict[str, list[bool]] = {}
    for vid, fin in s.exec(select(WatchHistory.video_id, WatchHistory.finished)
                           .where(col(WatchHistory.video_id).in_(ids))).all():
        hist.setdefault(vid, []).append(bool(fin))
    epoch = datetime.min.replace(tzinfo=timezone.utc)

    def group(d: Download) -> int:
        if hist.get(d.video_id) and all(hist[d.video_id]):
            return 0
        return 1 if d.video_id not in wanted else 2

    out = [d for d in done if allow_wanted or group(d) < 2]
    return sorted(out, key=lambda d: (group(d), _aware(d.last_played_at) or _aware(d.finished_at) or epoch))


def delete_files(d: Download) -> None:
    p = abs_path(d.path) if d.path else abs_path(rel_path(d.video_id))
    if p:
        p.unlink(missing_ok=True)
        try:
            p.parent.rmdir()  # only if empty
        except OSError:
            pass
    shutil.rmtree(staging_dir(d.video_id), ignore_errors=True)


def evict(s: Session, d: Download, reason: str) -> int:
    size = d.size_bytes
    delete_files(d)
    d.status, d.size_bytes, d.progress = "evicted", 0, 0.0
    s.add(d)
    s.commit()
    title = (s.get(Video, d.video_id) or Video(id=d.video_id)).title or d.video_id
    emit("download", f"🗑️ Evicted {title} ({size / 1e6:.0f} MB) — {reason}", "info", video_id=d.video_id,
         payload={"size_bytes": size, "reason": reason})
    return size


def make_room(s: Session, cfg: dict, need: int, allow_wanted: bool) -> bool:
    """Evict until used + need <= cap. Returns False if it can't (everything left is pinned/wanted)."""
    cap = max_bytes(cfg)
    used = used_bytes(s)
    if used + need <= cap:
        return True
    for d in eviction_order(s, allow_wanted):
        used -= evict(s, d, "over storage cap")
        if used + need <= cap:
            return True
    return used + need <= cap


def reconcile(s: Session) -> dict:
    """Startup consistency pass between DB rows and files on disk."""
    stats = {"missing": 0, "adopted": 0, "deleted": 0, "requeued": 0, "staging_removed": 0}
    for d in s.exec(select(Download).where(Download.status == "downloading")).all():
        d.status = "queued"
        s.add(d)
        stats["requeued"] += 1
    for d in s.exec(select(Download).where(Download.status == "done")).all():
        p = abs_path(d.path)
        if not p or not p.is_file():
            d.status, d.size_bytes = "evicted", 0
            s.add(d)
            stats["missing"] += 1
    s.commit()
    if MEDIA_DIR.is_dir():
        for sub in MEDIA_DIR.iterdir():
            if not sub.is_dir() or sub.name == ".tmp":
                continue
            for f in sub.iterdir():
                vid = f.stem if f.suffix == ".mp4" else ""
                if not f.is_file():
                    continue
                if not VID_RE.match(vid) or sub.name != vid[:2]:
                    if f.name.endswith((".part", ".ytdl", ".temp.mp4")) or f.suffix in (".mp4", ".m4a", ".webm"):
                        f.unlink(missing_ok=True)
                        stats["deleted"] += 1
                    continue
                d = s.get(Download, vid)
                if d and d.status == "done":
                    continue
                if d and d.status == "evicted":
                    f.unlink(missing_ok=True)  # evicted/deleted but the file survived (crash, NFS hiccup)
                    stats["deleted"] += 1
                    continue
                d = d or Download(video_id=vid)
                d.status, d.path, d.size_bytes, d.progress = "done", rel_path(vid), f.stat().st_size, 1.0
                d.finished_at = d.finished_at or now()
                s.add(d)
                stats["adopted"] += 1
        s.commit()
        tmp = MEDIA_DIR / ".tmp"
        if tmp.is_dir():
            active = set(s.exec(select(Download.video_id).where(
                col(Download.status).in_(["queued", "error", "downloading"]))).all())
            for d in tmp.iterdir():
                if d.name not in active:
                    shutil.rmtree(d, ignore_errors=True)
                    stats["staging_removed"] += 1
    return stats


# ---------------------------------------------------------------- the service

class Downloader:
    def __init__(self, sleep: Callable[[float], None] = time.sleep):
        self.stop = threading.Event()
        self._sleep = sleep
        self.last_category: Optional[int] = None
        self.blocked_until: Optional[datetime] = None
        self._state: dict = {}
        self._last_state_write = 0.0

    # ---- state
    def set_state(self, state: str, force: bool = True, **kw) -> None:
        st = {"state": state, "video_id": None, "title": "", "progress": 0.0, "speed": None, "eta": None, **kw}
        t = time.monotonic()
        if not force and t - self._last_state_write < STATE_EVERY_S:
            return
        with session() as s:
            cfg = get_settings(s)["cache"]
            st.setdefault("used_bytes", used_bytes(s))
            st.setdefault("max_bytes", max_bytes(cfg))
            st.setdefault("queue", s.exec(select(func.count()).select_from(Download)
                                          .where(col(Download.status).in_(["queued", "downloading"]))).one())
        st["updated_at"] = now().isoformat()
        self._state = st
        self._last_state_write = t
        save_setting("downloader_state", st)

    def wait(self, seconds: float) -> None:
        if self._sleep is time.sleep:
            self.stop.wait(max(0.0, seconds))  # wakes immediately on stop
        else:
            self._sleep(seconds)

    # ---- gating
    def blocker(self, check_cap: bool = True) -> Optional[tuple[str, str, float]]:
        """-> (state, detail, sleep_s) when downloads must not run now, else None."""
        st = get_settings()
        cfg = st["cache"]
        if not cfg.get("enabled", True):
            return "disabled", "Offline cache disabled", 30
        if not st["agent"].get("enabled", True):
            return "disabled", "Agent disabled", 30
        if get_agent_control().get("paused"):
            return "paused", "Paused", 5
        t = now()
        bu = _parse_ts(get_agent_state().get("backoff_until"))
        if self.blocked_until and self.blocked_until > t:
            bu = max(bu or self.blocked_until, self.blocked_until)
        if bu and bu > t:
            return "backoff", f"YouTube backoff until {bu.astimezone():%H:%M}", min(60, (bu - t).total_seconds())
        th = st["throttle"]
        if check_cap and yt_request_counts()["hour"] >= int(th.get("max_per_hour") or 10 ** 9):
            return "waiting", "Hourly YouTube request cap reached", 60
        return None

    def _abort_reason(self, video_id: str) -> Optional[str]:
        if self.stop.is_set():
            return "shutdown"
        b = self.blocker(check_cap=False)
        if b:
            return b[1]
        with session() as s:
            d = s.get(Download, video_id)
            if not d or d.status != "downloading":
                return "removed"
            prog = self._state.get("progress") if self._state.get("video_id") == video_id else None
            if prog is not None and abs((d.progress or 0) - prog) >= 0.01:
                d.progress = prog  # persisted every CONTROL_EVERY_S at most
                s.add(d)
                s.commit()
        return None

    # ---- one download
    def run_one(self, d: Download, cfg: dict) -> str:
        vid = d.video_id
        with session() as s:
            v = s.get(Video, vid)
            title = v.title if v and v.title else vid
            est = (v.duration_s if v else 0) * EST_BYTES_PER_S
            if not make_room(s, cfg, est, allow_wanted=d.pinned):
                self.set_state("full", detail="Storage cap reached (only wanted/pinned videos left)")
                return "full"
            row = s.get(Download, vid)
            if not row or row.status not in ("queued", "error"):
                return "removed"  # deleted by the user in the window since next_download()
            row.status, row.error, row.progress = "downloading", "", row.progress or 0.0
            s.add(row)
            s.commit()
        emit("download", f"📥 Downloading {title}", "info", video_id=vid)
        self.set_state("downloading", video_id=vid, title=title)
        work = staging_dir(vid)
        work.mkdir(parents=True, exist_ok=True)
        last_ctl = [0.0]

        def hook(p: dict) -> None:
            t = time.monotonic()
            if t - last_ctl[0] >= CONTROL_EVERY_S:
                last_ctl[0] = t
                reason = self._abort_reason(vid)
                if reason:
                    raise ytdl.DownloadAborted(reason)
            if p.get("status") != "downloading":
                return
            tot = p.get("total_bytes") or p.get("total_bytes_estimate") or 0
            frac = min(1.0, (p.get("downloaded_bytes") or 0) / tot) if tot else 0.0
            fi = p.get("info_dict") or {}
            has_v, has_a = fi.get("vcodec") not in ("none", None), fi.get("acodec") not in ("none", None)
            # merged download = video file then audio file; weight the (larger) video part 90 %
            prog = frac if (has_v and has_a) else (frac * 0.9 if has_v else 0.9 + frac * 0.1)
            self.set_state("downloading", force=False, video_id=vid, title=title, progress=round(prog, 4),
                           speed=p.get("speed"), eta=p.get("eta"))

        try:
            res = ytdl.download(vid, str(work), cfg.get("max_height") or 1080, cfg.get("rate_limit") or 0, hook)
        except ytdl.DownloadAborted as e:
            with session() as s:
                row = s.get(Download, vid)
                if row and row.status == "downloading":
                    row.status = "queued"  # resumes later from the .part files
                    s.add(row)
                    s.commit()
                elif row and row.status == "evicted":
                    shutil.rmtree(work, ignore_errors=True)
            emit("download", f"⏸️ Download stopped: {title} ({e})", "info", video_id=vid)
            return "aborted"
        except ytdl.YtBlocked as e:
            self.blocked_until = now() + timedelta(seconds=OWN_BLOCK_BACKOFF_S)
            self._fail(vid, str(e), count=False)
            emit("download", f"🛑 YouTube bot-check while downloading — pausing downloads ({str(e)[:120]})", "warn",
                 video_id=vid)
            return "blocked"
        except ytdl.YtUnavailable as e:
            self._fail(vid, str(e), permanent=True)
            emit("download", f"⚠️ Can't download {title}: unavailable", "warn", video_id=vid)
            return "error"
        except Exception as e:  # YtError, ffmpeg, disk, ...
            self._fail(vid, f"{type(e).__name__}: {e}")
            emit("download", f"⚠️ Download failed: {title} ({str(e)[:160]})", "warn", video_id=vid)
            return "error"

        try:
            src = Path(res["path"])
            if not src.is_file():
                self._fail(vid, "downloaded file missing")
                return "error"
            dst = MEDIA_DIR / rel_path(vid)
            dst.parent.mkdir(parents=True, exist_ok=True)
            os.replace(src, dst)  # atomic within the same filesystem
            shutil.rmtree(work, ignore_errors=True)
            size = dst.stat().st_size
            with session() as s:
                row = s.get(Download, vid)
                if not row or row.status != "downloading":  # deleted by the user meanwhile
                    dst.unlink(missing_ok=True)
                    return "aborted"
                row.status, row.path, row.size_bytes, row.progress = "done", rel_path(vid), size, 1.0
                row.height, row.vcodec, row.error, row.finished_at = res["height"], res["vcodec"], "", now()
                s.add(row)
                if res.get("info"):
                    try:
                        ytdl.upsert_video(s, res["info"])  # fills title etc. for manual "Save offline" placeholders
                    except Exception:
                        log.exception("upsert after download failed")
                s.commit()
                title = (s.get(Video, vid) or Video(id=vid)).title or title
                make_room(s, cfg, 0, allow_wanted=False)
        except Exception as e:  # NFS/IO trouble in the move or commit: fail the row, never strand it
            self._fail(vid, f"{type(e).__name__}: {e}")
            emit("download", f"⚠️ Saving download failed: {title} ({str(e)[:160]})", "warn", video_id=vid)
            return "error"
        emit("download", f"✅ Saved offline ({res['height']}p, {size / 1e6:.0f} MB): {title}", "success", video_id=vid,
             payload={"size_bytes": size, "height": res["height"]})
        return "done"

    def _fail(self, vid: str, err: str, permanent: bool = False, count: bool = True) -> None:
        with session() as s:
            row = s.get(Download, vid)
            if not row or row.status != "downloading":  # removed by the user meanwhile: keep their decision
                return
            if count:
                row.attempts = MAX_ATTEMPTS if permanent else row.attempts + 1
            row.status = "error" if count else "queued"
            row.error, row.finished_at = err[:500], now()
            s.add(row)
            s.commit()

    # ---- loop
    def iterate(self) -> float:
        """One scheduling step. Returns seconds to sleep before the next step."""
        b = self.blocker()
        if b:
            self.set_state(b[0], detail=b[1])
            return b[2]
        with session() as s:
            cfg = get_settings(s)["cache"]
            sync_queue(s, cfg)
            make_room(s, cfg, 0, allow_wanted=False)
            d, cat = next_download(s, self.last_category)
        if not d:
            self.set_state("idle", detail="Nothing to download")
            return 30
        r = self.run_one(d, cfg)
        if r == "done" or r == "error":
            self.last_category = cat
        if r == "full":
            return 300
        if r in ("aborted", "blocked", "removed"):
            return 2
        gap = float(cfg.get("min_gap_s") or 0)
        self.set_state("sleeping", detail="Pause between downloads",
                       until=(now() + timedelta(seconds=gap)).isoformat())
        return gap * random.uniform(0.8, 1.4)

    def run(self) -> None:
        with session() as s:
            st = reconcile(s)
        log.info("reconcile: %s", st)
        if any(st.values()):
            emit("download", f"🧹 Cache check: {st}", "debug", payload=st)
        try:
            while not self.stop.is_set():
                try:
                    delay = self.iterate()
                except Exception as e:  # never die; surface and retry
                    log.exception("downloader iteration failed")
                    emit("download", f"⚠️ Downloader error: {e}"[:300], "error")
                    delay = 30
                self.wait(delay)
        finally:
            try:
                with session() as s:
                    for d in s.exec(select(Download).where(Download.status == "downloading")).all():
                        d.status = "queued"
                        s.add(d)
                    s.commit()
                save_setting("downloader_state", {"state": "offline", "updated_at": now().isoformat()})
            except Exception:
                log.exception("shutdown cleanup failed")
