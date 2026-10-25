"""Enrich one `found` candidate: video_info + transcript + comments (each separately rate-limited)."""
from __future__ import annotations

from ..db import session
from ..models import Candidate, Category, Video, now
from . import data
from .runtime import Runtime


def _fail(rt: Runtime, rl, cand_id: int, cat: Category, title: str, err: Exception, what: str) -> None:
    rl.failed()
    with session() as s:
        c = s.get(Candidate, cand_id)
        if c is None:
            return
        c.status, c.error = "error", f"{what}: {err}"[:500]
        s.add(c)
        s.commit()
    rt.event("error", f"⚠️ Skipped {title or c.video_id} — {what} failed: {err}"[:500], "warn", cat,
             video_id=c.video_id, payload={"error": str(err)[:500], "step": what})


def enrich_one(rt: Runtime, rl, cand: Candidate, cat: Category) -> str:
    """Returns resulting candidate status. YtBlocked propagates (caller opens the circuit breaker)."""
    yt, th = rt.yt, rt.throttle()
    with session() as s:
        v = s.get(Video, cand.video_id)
        title = v.title if v else cand.video_id
        data.touch_category(s, cat.id)
        if s.get(Candidate, cand.id) is None or s.get(Category, cat.id) is None:
            return "gone"  # deleted meanwhile
        if v and v.enriched_at:
            c = s.get(Candidate, cand.id)
            c.status = "enriched"
            s.add(c)
            s.commit()
            rt.event("metadata", f"♻️ Already researched: {title} — reusing transcript & comments", "debug", cat,
                     video_id=cand.video_id)
            return "enriched"

    st = dict(video_id=cand.video_id, title=title)
    # 1) full metadata
    rl.wait_turn("metadata", cat, **st)
    rt.state("fetching", f"Fetching details: {title}", cat, **st)
    rt.event("metadata", f"📄 Fetching details: {title}", "info", cat, video_id=cand.video_id)
    try:
        info = yt.video_info(cand.video_id, origin="worker")
    except yt.YtBlocked:
        raise
    except yt.YtError as e:
        _fail(rt, rl, cand.id, cat, title, e, "metadata")
        return "error"
    rl.success()
    with session() as s:
        v = yt.upsert_video(s, info)
        if not v.chapters and info.get("chapters"):
            v.chapters = info["chapters"]
        v.fetched_at = v.fetched_at or now()
        s.add(v)
        s.commit()
        title = v.title or title
        st["title"] = title
        why = data.prefilter(v.model_dump(), cat, data.profile_ctx(s, cat.profile_id),
                             bool(rt.settings()["extras"].get("hide_shorts", True)))
        c = s.get(Candidate, cand.id)
        if c is None:
            return "gone"
        if why:
            c.status, c.red_flags, c.summary, c.judged_at = "rejected", [f"prefilter: {why}"], "", now()
            s.add(c)
            s.commit()
    if why:
        rt.event("reject", f"🚫 Filtered: {title} — {why}", "info", cat, video_id=cand.video_id,
                 payload={"prefilter": why})
        return "rejected"

    # 2) transcript (optional — a failure is not fatal)
    rt.check()
    rl.wait_turn("transcript", cat, **st)
    rt.state("transcript", f"Reading transcript: {title}", cat, **st)
    rt.event("transcript", f"📜 Reading transcript: {title}", "info", cat, video_id=cand.video_id)
    try:
        tr = yt.transcript(info, int(th.get("transcript_max_chars") or 40000)) or ""
        rl.success()
    except yt.YtBlocked:
        raise
    except yt.YtError as e:
        rl.failed()
        tr = ""
        rt.event("transcript", f"⚠️ No transcript for {title}: {e}"[:500], "warn", cat, video_id=cand.video_id)

    # 3) comments (optional)
    rt.check()
    n = int(th.get("max_comments") or 40)
    rl.wait_turn("comments", cat, **st)
    rt.state("comments", f"Reading comments: {title}", cat, **st)
    try:
        cm = list(yt.comments(cand.video_id, max_comments=n, origin="worker") or [])
        rl.success()
    except yt.YtBlocked:
        raise
    except yt.YtError as e:
        rl.failed()
        cm = []
        rt.event("comments", f"⚠️ Comments unavailable for {title}: {e}"[:500], "warn", cat, video_id=cand.video_id)
    rt.event("comments", f"💬 Read {len(cm)} comments: {title}", "info", cat, video_id=cand.video_id,
             payload={"comments": len(cm), "transcript_chars": len(tr)})

    with session() as s:
        v = s.get(Video, cand.video_id) or Video(id=cand.video_id)
        v.transcript, v.comments, v.enriched_at = tr, cm, now()
        s.add(v)
        c = s.get(Candidate, cand.id)
        if c is not None:  # enrichment is kept on the Video even if the candidate was deleted meanwhile
            c.status = "enriched"
            s.add(c)
        s.commit()
        if c is None:
            return "gone"
    return "enriched"
