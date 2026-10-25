"""Profiles, categories, feeds, channels, feedback, lessons, history, settings."""
import re
from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel
from sqlmodel import Session, col, delete, func, select

from ..config import COOKIES_PATH, DEFAULT_SETTINGS
from ..db import get_session, get_settings, save_setting
from ..models import (Candidate, Category, Channel, Feedback, Lesson, Profile, ProfileChannel, Video,
                      WatchHistory, now)

router = APIRouter()


# ---------- helpers

def profile_id(x_profile_id: Optional[int] = Header(default=None), s: Session = Depends(get_session)) -> int:
    """Active profile from X-Profile-Id header; falls back to first profile."""
    if x_profile_id and s.get(Profile, x_profile_id):
        return x_profile_id
    p = s.exec(select(Profile).order_by(Profile.id)).first()
    if not p:
        raise HTTPException(400, "no profiles")
    return p.id


def _offline_ids(ids: list[str]) -> set[str]:
    from ..db import session
    from ..models import Download
    if not ids:
        return set()
    with session() as s:
        return set(s.exec(select(Download.video_id).where(col(Download.video_id).in_(ids),
                                                          Download.status == "done")).all())


def video_out(v: Video, full: bool = False, offline: Optional[bool] = None) -> dict:
    d = {
        "id": v.id, "title": v.title, "channel_id": v.channel_id, "channel_name": v.channel_name,
        "duration_s": v.duration_s, "published_at": v.published_at, "view_count": v.view_count,
        "like_count": v.like_count, "thumbnail": f"/api/thumb/{v.id}", "is_short": v.is_short,
        "is_live": v.is_live, "has_transcript": bool(v.transcript), "comment_count": len(v.comments or []),
        "offline": bool(offline) if offline is not None else v.id in _offline_ids([v.id]),
    }
    if full:
        d.update(description=v.description, tags=v.tags, chapters=v.chapters)
    return d


def candidate_out(c: Candidate, v: Optional[Video], offline: Optional[bool] = None) -> dict:
    return {
        "id": c.id, "category_id": c.category_id, "status": c.status, "source": c.source, "score": c.score,
        "summary": c.summary, "reasons": c.reasons, "red_flags": c.red_flags, "tags": c.tags,
        "error": c.error, "created_at": c.created_at, "judged_at": c.judged_at,
        "video": video_out(v, offline=offline) if v else {"id": c.video_id},
    }


def _own_category(s: Session, pid: int, cid: int) -> Category:
    c = s.get(Category, cid)
    if not c or c.profile_id != pid:
        raise HTTPException(404, "category not found")
    return c


def _apply(obj, data: dict, skip=("id", "profile_id", "created_at")):
    for k, v in data.items():
        if k not in skip and hasattr(obj, k):
            setattr(obj, k, v)
    return obj


# ---------- profiles

class ProfileIn(BaseModel):
    name: str
    emoji: str = "🙂"
    color: str = "#7c5cff"
    prefs: dict = {}


class ProfilePatch(BaseModel):
    name: Optional[str] = None
    emoji: Optional[str] = None
    color: Optional[str] = None
    prefs: Optional[dict] = None


@router.get("/profiles")
def list_profiles(s: Session = Depends(get_session)):
    return s.exec(select(Profile).order_by(Profile.id)).all()


@router.post("/profiles")
def create_profile(body: ProfileIn, s: Session = Depends(get_session)):
    p = Profile(**body.model_dump())
    s.add(p)
    s.commit()
    s.refresh(p)
    return p


@router.patch("/profiles/{pid}")
def patch_profile(pid: int, body: ProfilePatch, s: Session = Depends(get_session)):
    p = s.get(Profile, pid) or _404()
    _apply(p, body.model_dump(exclude_none=True))
    s.add(p)
    s.commit()
    return p


@router.delete("/profiles/{pid}")
def delete_profile(pid: int, s: Session = Depends(get_session)):
    if s.exec(select(func.count()).select_from(Profile)).one() <= 1:
        raise HTTPException(400, "cannot delete the last profile")
    p = s.get(Profile, pid) or _404()
    cats = [c.id for c in s.exec(select(Category).where(Category.profile_id == pid)).all()]
    if cats:
        s.exec(delete(Candidate).where(col(Candidate.category_id).in_(cats)))
    for m in (Category, ProfileChannel, Feedback, Lesson, WatchHistory):
        s.exec(delete(m).where(m.profile_id == pid))
    s.delete(p)
    s.commit()
    return {"ok": True}


def _404():
    raise HTTPException(404, "not found")


# ---------- categories

class CategoryIn(BaseModel):
    name: str
    emoji: str = "✨"
    color: str = "#7c5cff"
    brief: str = ""
    seed_queries: list[str] = []
    seed_channels: list[str] = []
    include_keywords: list[str] = []
    exclude_keywords: list[str] = []
    min_duration_s: int = 60
    max_duration_s: int = 3600
    language: str = ""
    max_age_days: int = 0
    target_queue: int = 20
    threshold: int = 65
    priority: int = 1
    kid_safe: bool = False
    enabled: bool = True


def _category_stats(s: Session, cid: int) -> dict:
    rows = s.exec(select(Candidate.status, func.count()).where(Candidate.category_id == cid,
                                                                 Candidate.dismissed == False)  # noqa: E712
                  .group_by(Candidate.status)).all()
    return {st: n for st, n in rows}


@router.get("/categories")
def list_categories(pid: int = Depends(profile_id), s: Session = Depends(get_session)):
    cats = s.exec(select(Category).where(Category.profile_id == pid).order_by(Category.position, Category.id)).all()
    return [{**c.model_dump(), "stats": _category_stats(s, c.id)} for c in cats]


@router.post("/categories")
def create_category(body: CategoryIn, pid: int = Depends(profile_id), s: Session = Depends(get_session)):
    pos = s.exec(select(func.count()).select_from(Category).where(Category.profile_id == pid)).one()
    c = Category(**body.model_dump(), profile_id=pid, position=pos)
    s.add(c)
    s.commit()
    s.refresh(c)
    return c


@router.get("/categories/{cid}")
def get_category(cid: int, pid: int = Depends(profile_id), s: Session = Depends(get_session)):
    c = _own_category(s, pid, cid)
    return {**c.model_dump(), "stats": _category_stats(s, c.id)}


@router.patch("/categories/{cid}")
def patch_category(cid: int, body: dict, pid: int = Depends(profile_id), s: Session = Depends(get_session)):
    c = _own_category(s, pid, cid)
    allowed = set(CategoryIn.model_fields) | {"position"}
    _apply(c, {k: v for k, v in body.items() if k in allowed})
    s.add(c)
    s.commit()
    return c


@router.delete("/categories/{cid}")
def delete_category(cid: int, pid: int = Depends(profile_id), s: Session = Depends(get_session)):
    c = _own_category(s, pid, cid)
    s.exec(delete(Candidate).where(Candidate.category_id == cid))
    s.delete(c)
    s.commit()
    return {"ok": True}


@router.post("/categories/reorder")
def reorder_categories(ids: list[int], pid: int = Depends(profile_id), s: Session = Depends(get_session)):
    for i, cid in enumerate(ids):
        c = _own_category(s, pid, cid)
        c.position = i
        s.add(c)
    s.commit()
    return {"ok": True}


# ---------- feeds

def _watched_ids(s: Session, pid: int) -> set[str]:
    return set(s.exec(select(WatchHistory.video_id).where(WatchHistory.profile_id == pid,
                                                           WatchHistory.finished == True)).all())  # noqa: E712


@router.get("/feed/category/{cid}")
def category_feed(cid: int, status: str = "accepted", include_watched: bool = False, offset: int = 0,
                  limit: int = 40, pid: int = Depends(profile_id), s: Session = Depends(get_session)):
    _own_category(s, pid, cid)
    q = select(Candidate, Video).join(Video, Video.id == Candidate.video_id).where(Candidate.category_id == cid)
    if status == "pending":
        q = q.where(col(Candidate.status).in_(["found", "enriched"]), Candidate.dismissed == False)  # noqa: E712
    elif status != "all":
        q = q.where(Candidate.status == status)
    if status == "accepted":
        q = q.where(Candidate.dismissed == False)  # noqa: E712
        if not include_watched:
            watched = _watched_ids(s, pid)
            if watched:
                q = q.where(col(Candidate.video_id).not_in(watched))
        q = q.order_by(col(Candidate.score).desc(), col(Candidate.judged_at).desc())
    else:
        q = q.order_by(col(Candidate.created_at).desc())
    rows = s.exec(q.offset(offset).limit(limit)).all()
    off = _offline_ids([c.video_id for c, _ in rows])  # one batched lookup instead of one per card
    out = []
    for c, v in rows:
        d = candidate_out(c, None)
        if v:
            d["video"] = video_out(v, offline=v.id in off)
        out.append(d)
    return out


@router.get("/feed/home")
def home_feed(per_row: int = 20, pid: int = Depends(profile_id), s: Session = Depends(get_session)):
    rows = []
    # Continue watching
    hist = s.exec(select(WatchHistory, Video).join(Video, Video.id == WatchHistory.video_id)
                  .where(WatchHistory.profile_id == pid, WatchHistory.finished == False,  # noqa: E712
                         WatchHistory.position_s > 15)
                  .order_by(col(WatchHistory.updated_at).desc()).limit(per_row)).all()
    off = _offline_ids([v.id for _, v in hist])
    if hist:
        rows.append({"kind": "continue", "title": "Continue watching", "emoji": "⏯️", "items": [
            {"video": video_out(v, offline=v.id in off), "position_s": h.position_s, "category_id": h.category_id}
            for h, v in hist]})
    # Categories
    for c in s.exec(select(Category).where(Category.profile_id == pid, Category.enabled == True)  # noqa: E712
                    .order_by(Category.position, Category.id)).all():
        rows.append({"kind": "category", "category_id": c.id, "title": c.name, "emoji": c.emoji, "color": c.color,
                     "items": category_feed(c.id, "accepted", False, 0, per_row, pid, s)})
    # New from subscriptions
    subs = s.exec(select(ProfileChannel.channel_id).where(ProfileChannel.profile_id == pid,
                                                           ProfileChannel.subscribed == True)).all()  # noqa: E712
    if subs:
        vids = s.exec(select(Video).where(col(Video.channel_id).in_(subs), Video.is_short == False)  # noqa: E712
                      .order_by(col(Video.published_at).desc().nulls_last()).limit(per_row)).all()
        off = _offline_ids([v.id for v in vids])
        rows.append({"kind": "subscriptions", "title": "New from subscriptions", "emoji": "📺",
                     "items": [{"video": video_out(v, offline=v.id in off)} for v in vids]})
    return rows


@router.post("/candidates/{cand_id}/dismiss")
def dismiss_candidate(cand_id: int, pid: int = Depends(profile_id), s: Session = Depends(get_session)):
    c = s.get(Candidate, cand_id) or _404()
    _own_category(s, pid, c.category_id)
    c.dismissed = True
    s.add(c)
    s.commit()
    return {"ok": True}


class CandidateIn(BaseModel):
    video_id: str
    category_id: int


@router.post("/candidates")
def add_candidate(body: CandidateIn, pid: int = Depends(profile_id), s: Session = Depends(get_session)):
    """Manually add a video to a category (e.g. from search). Worker enriches + judges it like any other,
    but manual adds are always accepted."""
    _own_category(s, pid, body.category_id)
    v = s.get(Video, body.video_id)
    if not v or not v.fetched_at:
        from .. import ytdl
        try:
            ytdl.upsert_video(s, ytdl.video_info(body.video_id, origin="user"))
        except ytdl.YtError:
            if not v:
                s.add(Video(id=body.video_id))
    c = s.exec(select(Candidate).where(Candidate.category_id == body.category_id,
                                       Candidate.video_id == body.video_id)).first()
    if not c:
        c = Candidate(category_id=body.category_id, video_id=body.video_id, source="manual")
    c.status, c.dismissed, c.score = "accepted", False, c.score or 100
    s.add(c)
    s.commit()
    return {"ok": True}


# ---------- channels (subscriptions / blocks)

class ChannelPut(BaseModel):
    name: Optional[str] = None
    avatar: Optional[str] = None
    handle: Optional[str] = None
    subscribed: Optional[bool] = None
    blocked: Optional[bool] = None


@router.get("/channels")
def list_channels(pid: int = Depends(profile_id), s: Session = Depends(get_session)):
    rows = s.exec(select(ProfileChannel, Channel).join(Channel, Channel.id == ProfileChannel.channel_id, isouter=True)
                  .where(ProfileChannel.profile_id == pid)).all()
    return [{"id": pc.channel_id, "name": ch.name if ch else "", "handle": ch.handle if ch else "",
             "avatar": ch.avatar if ch else "", "subscribed": pc.subscribed, "blocked": pc.blocked,
             "trust": pc.trust} for pc, ch in rows if pc.subscribed or pc.blocked]


@router.put("/channels/{channel_id}")
def put_channel(channel_id: str, body: ChannelPut, pid: int = Depends(profile_id), s: Session = Depends(get_session)):
    ch = s.get(Channel, channel_id) or Channel(id=channel_id)
    for k in ("name", "avatar", "handle"):
        if (v := getattr(body, k)) is not None:
            setattr(ch, k, v)
    s.add(ch)
    pc = s.exec(select(ProfileChannel).where(ProfileChannel.profile_id == pid,
                                             ProfileChannel.channel_id == channel_id)).first()
    pc = pc or ProfileChannel(profile_id=pid, channel_id=channel_id)
    if body.subscribed is not None:
        pc.subscribed = body.subscribed
    if body.blocked is not None:
        pc.blocked = body.blocked
        if body.blocked:
            pc.subscribed = False
    s.add(pc)
    s.commit()
    return {"id": channel_id, "subscribed": pc.subscribed, "blocked": pc.blocked, "trust": pc.trust}


@router.post("/channels/{channel_id}/block")
def block_channel(channel_id: str, body: Optional[ChannelPut] = None,
                  pid: int = Depends(profile_id), s: Session = Depends(get_session)):
    """"Don't like channel": block it and dismiss its accepted/pending candidates in this profile's
    categories, so nothing lingers in the feeds and the pipeline spends no budget on it.
    (The worker prefilter already rejects blocked channels for future discoveries.)
    """
    ch = s.get(Channel, channel_id) or Channel(id=channel_id)
    for k in ("name", "avatar", "handle"):
        if body and (v := getattr(body, k)) is not None:
            setattr(ch, k, v)
    s.add(ch)
    pc = s.exec(select(ProfileChannel).where(ProfileChannel.profile_id == pid,
                                              ProfileChannel.channel_id == channel_id)).first()
    pc = pc or ProfileChannel(profile_id=pid, channel_id=channel_id)
    pc.blocked, pc.subscribed = True, False
    s.add(pc)
    cat_ids = set(s.exec(select(Category.id).where(Category.profile_id == pid)).all())
    dismissed = 0
    if cat_ids:
        vids = set(s.exec(select(Video.id).where(Video.channel_id == channel_id)).all())
        if vids:
            rows = s.exec(select(Candidate).where(col(Candidate.video_id).in_(vids),
                                                 col(Candidate.category_id).in_(cat_ids),
                                                 Candidate.status.in_(["accepted", "found", "enriched"]))).all()
            for c in rows:
                c.dismissed = True
                s.add(c)
                dismissed += 1
    s.commit()
    return {"id": channel_id, "subscribed": False, "blocked": True, "trust": pc.trust, "dismissed": dismissed}


# ---------- feedback & lessons

class FeedbackIn(BaseModel):
    video_id: str
    category_id: Optional[int] = None
    rating: int = 0
    chips: list[str] = []
    text: str = ""


@router.post("/feedback")
def add_feedback(body: FeedbackIn, pid: int = Depends(profile_id), s: Session = Depends(get_session)):
    f = Feedback(**body.model_dump(), profile_id=pid)
    s.add(f)
    # A dislike removes it from the category feed right away.
    if body.rating < 0 and body.category_id:
        c = s.exec(select(Candidate).where(Candidate.category_id == body.category_id,
                                           Candidate.video_id == body.video_id)).first()
        if c:
            c.dismissed = True
            s.add(c)
    s.commit()
    s.refresh(f)
    return f


@router.get("/feedback")
def list_feedback(limit: int = 100, pid: int = Depends(profile_id), s: Session = Depends(get_session)):
    rows = s.exec(select(Feedback, Video).join(Video, Video.id == Feedback.video_id, isouter=True)
                  .where(Feedback.profile_id == pid).order_by(col(Feedback.created_at).desc()).limit(limit)).all()
    off = _offline_ids([f.video_id for f, _ in rows])
    return [{**f.model_dump(), "video": video_out(v, offline=v.id in off) if v else {"id": f.video_id}}
            for f, v in rows]


@router.delete("/feedback/{fid}")
def delete_feedback(fid: int, pid: int = Depends(profile_id), s: Session = Depends(get_session)):
    f = s.get(Feedback, fid)
    if not f or f.profile_id != pid:
        _404()
    s.delete(f)
    s.commit()
    return {"ok": True}


class LessonIn(BaseModel):
    text: str
    category_id: Optional[int] = None
    channel_id: Optional[str] = None
    weight: float = 1.0
    active: bool = True


@router.get("/lessons")
def list_lessons(pid: int = Depends(profile_id), s: Session = Depends(get_session)):
    return s.exec(select(Lesson).where(Lesson.profile_id == pid).order_by(col(Lesson.updated_at).desc())).all()


@router.post("/lessons")
def create_lesson(body: LessonIn, pid: int = Depends(profile_id), s: Session = Depends(get_session)):
    lesson = Lesson(**body.model_dump(), profile_id=pid)
    s.add(lesson)
    s.commit()
    s.refresh(lesson)
    return lesson


@router.patch("/lessons/{lid}")
def patch_lesson(lid: int, body: dict, pid: int = Depends(profile_id), s: Session = Depends(get_session)):
    lesson = s.get(Lesson, lid)
    if not lesson or lesson.profile_id != pid:
        _404()
    _apply(lesson, {k: v for k, v in body.items() if k in LessonIn.model_fields})
    lesson.updated_at = now()
    s.add(lesson)
    s.commit()
    return lesson


@router.delete("/lessons/{lid}")
def delete_lesson(lid: int, pid: int = Depends(profile_id), s: Session = Depends(get_session)):
    lesson = s.get(Lesson, lid)
    if not lesson or lesson.profile_id != pid:
        _404()
    s.delete(lesson)
    s.commit()
    return {"ok": True}


# ---------- watch history

class HistoryIn(BaseModel):
    video_id: str
    position_s: float
    duration_s: float = 0
    category_id: Optional[int] = None
    finished: bool = False


@router.post("/history")
def save_history(body: HistoryIn, pid: int = Depends(profile_id), s: Session = Depends(get_session)):
    h = s.exec(select(WatchHistory).where(WatchHistory.profile_id == pid,
                                          WatchHistory.video_id == body.video_id)).first()
    h = h or WatchHistory(profile_id=pid, video_id=body.video_id)
    h.position_s, h.duration_s = body.position_s, body.duration_s or h.duration_s
    h.category_id = body.category_id or h.category_id
    h.finished = body.finished or (h.duration_s > 0 and body.position_s >= h.duration_s * 0.92)
    h.updated_at = now()
    s.add(h)
    s.commit()
    return {"ok": True, "finished": h.finished}


@router.get("/history")
def list_history(limit: int = 60, pid: int = Depends(profile_id), s: Session = Depends(get_session)):
    rows = s.exec(select(WatchHistory, Video).join(Video, Video.id == WatchHistory.video_id, isouter=True)
                  .where(WatchHistory.profile_id == pid).order_by(col(WatchHistory.updated_at).desc())
                  .limit(limit)).all()
    off = _offline_ids([h.video_id for h, _ in rows])
    return [{**h.model_dump(), "video": video_out(v, offline=v.id in off) if v else {"id": h.video_id}}
            for h, v in rows]


@router.get("/history/{video_id}")
def get_history(video_id: str, pid: int = Depends(profile_id), s: Session = Depends(get_session)):
    h = s.exec(select(WatchHistory).where(WatchHistory.profile_id == pid, WatchHistory.video_id == video_id)).first()
    return h or {"video_id": video_id, "position_s": 0, "finished": False}


@router.delete("/history")
def clear_history(pid: int = Depends(profile_id), s: Session = Depends(get_session)):
    s.exec(delete(WatchHistory).where(WatchHistory.profile_id == pid))
    s.commit()
    return {"ok": True}


class SeenIn(BaseModel):
    video_id: str


@router.post("/history/seen")
def mark_seen(body: SeenIn, pid: int = Depends(profile_id), s: Session = Depends(get_session)):
    """Mark a video watched without playing it: it leaves the feeds and the AI stops suggesting it.

    Dismisses its candidates in this profile's categories (also skips enrichment/judging/download)
    and records a finished WatchHistory row (the prefilter already rejects watched videos).
    """
    if not re.match(r"^[A-Za-z0-9_-]{11}$", body.video_id):
        raise HTTPException(status_code=404, detail="no such video")
    v = s.get(Video, body.video_id)
    h = s.exec(select(WatchHistory).where(WatchHistory.profile_id == pid,
                                           WatchHistory.video_id == body.video_id)).first()
    h = h or WatchHistory(profile_id=pid, video_id=body.video_id)
    h.finished, h.updated_at = True, now()
    h.duration_s = (v.duration_s if v and v.duration_s else h.duration_s) or 0
    s.add(h)
    cat_ids = set(s.exec(select(Category.id).where(Category.profile_id == pid)).all())
    rows = s.exec(select(Candidate).where(Candidate.video_id == body.video_id,
                                          col(Candidate.category_id).in_(cat_ids))).all() if cat_ids else []
    for c in rows:
        c.dismissed = True
        s.add(c)
    s.commit()
    return {"ok": True, "dismissed": len(rows)}


# ---------- settings

def _redact(st: dict) -> dict:
    st = {**st, "llm": {**st["llm"]}}
    if st["llm"].get("api_key"):
        st["llm"]["api_key"] = "********"
    return st


@router.get("/settings")
def read_settings(s: Session = Depends(get_session)):
    st = _redact(get_settings(s))
    st["cookies"] = {"present": COOKIES_PATH.exists()}
    return st


@router.put("/settings/{key}")
def write_settings(key: str, value: dict, s: Session = Depends(get_session)):
    if key not in DEFAULT_SETTINGS:
        raise HTTPException(404, "unknown settings key")
    cur = get_settings(s)[key]
    if key == "llm" and value.get("api_key") == "********":
        value["api_key"] = cur.get("api_key", "")
    save_setting(key, {**cur, **value}, s)
    return _redact(get_settings(s))[key]


@router.put("/cookies")
async def upload_cookies(request: Request):
    """Body: raw Netscape cookies.txt content."""
    body = (await request.body()).decode("utf-8", "replace")
    if "youtube.com" not in body:
        raise HTTPException(400, "does not look like a YouTube cookies.txt")
    COOKIES_PATH.write_text(body)
    COOKIES_PATH.chmod(0o600)
    return {"present": True}


@router.delete("/cookies")
def delete_cookies():
    COOKIES_PATH.unlink(missing_ok=True)
    return {"present": False}


@router.get("/stats")
def stats(pid: int = Depends(profile_id), s: Session = Depends(get_session)):
    since = now() - timedelta(days=1)
    return {
        "videos": s.exec(select(func.count()).select_from(Video)).one(),
        "candidates_24h": s.exec(select(func.count()).select_from(Candidate).where(Candidate.created_at >= since)).one(),
        "lessons": s.exec(select(func.count()).select_from(Lesson).where(Lesson.profile_id == pid)).one(),
    }
