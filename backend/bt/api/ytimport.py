"""Import from the signed-in YouTube session (cookies): subscriptions, the recommended feed,
Watch Later, Liked videos, and arbitrary playlists.

All extraction goes through the normal ytdl options (cookies + proxy if set) and is logged
as origin=user YouTube requests. Imported videos become `found` candidates for the judge
(respecting the same prefilter and backlog cap as worker discovery); imported subscriptions
become subscribed channels of the active profile.
"""
from __future__ import annotations

import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from .. import ytdl
from ..agent import data
from ..config import COOKIES_PATH
from ..db import get_session, get_settings
from ..models import Candidate, Category, Channel, ProfileChannel
from .core import profile_id

router = APIRouter()

SOURCES: dict[str, str] = {
    "recommended": "https://www.youtube.com/feed/recommended",
    "watchlater": "https://www.youtube.com/playlist?list=WL",
    "liked": "https://www.youtube.com/playlist?list=LL",
}


def _require_cookies() -> None:
    if not COOKIES_PATH.exists():
        raise HTTPException(400, "No YouTube cookies installed — upload them on the Cookies tab first")


def _flat_entries(url: str, kind: str, limit: int) -> list[dict]:
    """Flat yt-dlp entries (videos or channels) from a tab/playlist URL. Raises mapped YtErrors."""
    opts = {"extract_flat": "in_playlist", "playlistend": max(1, min(int(limit), 200))}
    info = ytdl._extract(url, kind, "user", f"import {kind}", **opts)
    return [e for e in info.get("entries") or [] if e]


@router.post("/ytimport/subscriptions")
def import_subscriptions(pid: int = Depends(profile_id), s: Session = Depends(get_session)):
    """Follow all channels the signed-in account follows, in the active profile."""
    _require_cookies()
    entries = _flat_entries("https://www.youtube.com/feed/channels", "import", 200)
    added = seen = 0
    for e in entries:
        cid = e.get("id")
        if not cid or not re.fullmatch(r"UC[A-Za-z0-9_-]{22}", str(cid)):
            continue
        ch = s.get(Channel, cid) or Channel(id=cid)
        if e.get("title"):
            ch.name = e["title"]
        if (uid := e.get("uploader_id")) and uid.startswith("@"):
            ch.handle = uid
        s.add(ch)
        pc = s.exec(select(ProfileChannel).where(ProfileChannel.profile_id == pid,
                                                 ProfileChannel.channel_id == cid)).first()
        if pc is None:
            pc = ProfileChannel(profile_id=pid, channel_id=cid)
            added += 1
        else:
            seen += 1
        if not pc.blocked:
            pc.subscribed = True
        s.add(pc)
    s.commit()
    return {"imported": added, "already_known": seen, "total": len(entries)}


class FeedImportBody(BaseModel):
    category_id: int
    source: str
    playlist_url: Optional[str] = None
    limit: int = 50


@router.post("/ytimport/feed")
def import_feed(body: FeedImportBody, pid: int = Depends(profile_id), s: Session = Depends(get_session)):
    """Add videos from a signed-in feed or playlist to a category, as candidates for the judge."""
    _require_cookies()
    cat = s.get(Category, body.category_id)
    if not cat or cat.profile_id != pid:
        raise HTTPException(404, "no such category for this profile")
    if body.source in SOURCES:
        url, source = SOURCES[body.source], f"import:{body.source}"
    elif body.source == "playlist":
        u = (body.playlist_url or "").strip()
        p = ytdl.up.urlparse(u)
        if "list=" not in (p.query or "") and "playlist" not in (p.path or ""):
            raise HTTPException(400, "not a playlist URL — paste one like "
                                     "https://www.youtube.com/playlist?list=PL…")
        if not (p.hostname or "").endswith("youtube.com"):
            raise HTTPException(400, "not a YouTube URL")
        url, source = u, "import:playlist"
    else:
        raise HTTPException(400, f"unknown source {body.source!r}")

    entries = [x for x in (ytdl._entry(e) for e in _flat_entries(url, "import", body.limit)) if x]
    hide_shorts = bool(get_settings(s)["extras"].get("hide_shorts", True))
    ctx = data.profile_ctx(s, pid)
    existing = data.candidate_ids(s, cat.id)
    room = data.FOUND_CAP - data.status_counts(s, cat.id).get("found", 0)
    added, skipped, reasons = 0, 0, {}
    for e in entries:
        why = data.prefilter(e, cat, ctx, hide_shorts, existing)
        if why is None and room <= 0:
            why = "backlog full"
        if why:
            skipped += 1
            key = why.split(" (")[0]
            reasons[key] = reasons.get(key, 0) + 1
            continue
        ytdl.upsert_video(s, e)
        s.add(Candidate(category_id=cat.id, video_id=e["id"], status="found", source=source))
        existing.add(e["id"])
        added += 1
        room -= 1
    s.commit()
    return {"found": len(entries), "added": added, "skipped": skipped,
            "skip_reasons": reasons, "category": cat.name}
