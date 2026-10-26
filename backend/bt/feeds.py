"""Channel RSS feeds (cheap, no yt-dlp): https://www.youtube.com/feeds/videos.xml?channel_id=UC..."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import httpx

from .db import log_yt_request
from .ytdl import YtBlocked, YtError, YtUnavailable, yt_proxy

FEED_URL = "https://www.youtube.com/feeds/videos.xml"
NS = {"a": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015",
      "media": "http://search.yahoo.com/mrss/"}
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36"


def _dt(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    return d.astimezone(timezone.utc) if d.tzinfo else d.replace(tzinfo=timezone.utc)


def parse_feed(xml: str | bytes) -> list[dict]:
    root = ET.fromstring(xml)
    ch_name = root.findtext("a:title", default="", namespaces=NS)
    ch_id = root.findtext("yt:channelId", default="", namespaces=NS)
    out = []
    for e in root.findall("a:entry", NS):
        vid = e.findtext("yt:videoId", default="", namespaces=NS)
        if not vid:
            continue
        link = (e.find("a:link", NS).get("href") if e.find("a:link", NS) is not None else "") or ""
        views = 0
        stats = e.find("media:group/media:community/media:statistics", NS)
        if stats is not None:
            try:
                views = int(stats.get("views") or 0)
            except ValueError:
                pass
        out.append({
            "id": vid,
            "title": e.findtext("a:title", default="", namespaces=NS),
            "channel_id": e.findtext("yt:channelId", default=ch_id, namespaces=NS) or ch_id,
            "channel_name": e.findtext("a:author/a:name", default=ch_name, namespaces=NS) or ch_name,
            "duration_s": 0,  # unknown from RSS
            "view_count": views,
            "thumbnail": f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg",
            "published_at": _dt(e.findtext("a:published", namespaces=NS)),
            "is_short": "/shorts/" in link,
            "is_live": False,
        })
    return out


def channel_feed(channel_id: str, origin: str = "worker") -> list[dict]:
    """Latest ~15 uploads as entry dicts (duration unknown = 0). Raises YtBlocked/YtUnavailable/YtError."""
    try:
        r = httpx.get(FEED_URL, params={"channel_id": channel_id}, headers={"User-Agent": UA}, timeout=15,
                      follow_redirects=True, proxy=yt_proxy() or None)
        r.raise_for_status()
        entries = parse_feed(r.content)
    except Exception as e:
        log_yt_request("rss", origin, False, f"rss {channel_id}: {str(e)[:200]}")
        code = e.response.status_code if isinstance(e, httpx.HTTPStatusError) else 0
        if code in (403, 429):
            raise YtBlocked(f"rss {channel_id}: HTTP {code}") from e
        if code == 404:
            raise YtUnavailable(f"rss {channel_id}: not found") from e
        raise YtError(f"rss {channel_id}: {e}") from e
    log_yt_request("rss", origin, True, f"rss {channel_id}: {len(entries)} entries")
    return entries
