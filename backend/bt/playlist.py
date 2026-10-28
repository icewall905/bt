"""Stable, quality-aware playlist pacing, shared by browsing and autoplay.

Reorder only accepted videos; variety never changes eligibility or verdicts.
The judge supplies topic tags, with titles and discovery queries as fallbacks
for older verdicts. No LLM or network calls belong on the feed request path.
"""
from __future__ import annotations

import re

from .models import Candidate, Video

Row = tuple[Candidate, Video]
_GENERIC = {"video", "videos", "fun", "educational", "education", "entertainment",
            "family", "kids", "children", "youtube", "the", "a", "an", "and", "or",
            "of", "to", "in", "on", "with", "for", "is", "how", "why", "this", "it"}


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[^\W_]+", text.casefold()) if len(w) > 2 and w not in _GENERIC}


def _tags(c: Candidate) -> list[str]:
    return [t for tag in c.tags if isinstance(tag, str)
            and (t := " ".join(_words_ordered(tag))) and t not in _GENERIC]


def _words_ordered(text: str) -> list[str]:
    return re.findall(r"[^\W_]+", text.casefold())


def _overlap(a: set[str], b: set[str]) -> float:
    return len(a & b) / len(a | b) if a and b else 0.0


def _duration_bucket(seconds: int) -> str:
    if seconds <= 0:
        return ""
    return "short" if seconds < 300 else "medium" if seconds < 1200 else "long"


def _similarity(left: Row, right: Row, features=None) -> float:
    c, v = left
    other, ov = right
    if features is None:
        features = {}
    def feature(c, v):
        key = id(c)
        if key not in features:
            features[key] = (_tags(c), _words(v.title))
        return features[key]
    tags, words = feature(c, v)
    otags, owords = feature(other, ov)
    topic = 22.0 if tags and otags and tags[0] == otags[0] else 0.0
    topic = max(topic, 20 * _overlap(set(tags), set(otags)),
                20 * _overlap(words, owords))
    # Search batches often share a subject even when legacy tags are sparse.
    if c.source.startswith("search:") and c.source.casefold() == other.source.casefold():
        topic = max(topic, 12.0)
    channel = 14.0 if v.channel_id and v.channel_id == ov.channel_id else 0.0
    # Runtime variety is a small nudge, with a little more breathing room after long picks.
    bucket = _duration_bucket(v.duration_s)
    pacing = (3.0 if bucket == "long" else 2.0) if bucket and bucket == _duration_bucket(ov.duration_s) else 0.0
    return topic + channel + pacing


def order_playlist(rows: list[Row], recent: list[Row] | None = None,
                   limit: int | None = None) -> list[Row]:
    """Greedily space similar picks while retaining a strong quality preference.

    Input is score/recency/id sorted and breaks ties deterministically. Penalise
    repetition over the last three picks with declining weight. Cap the penalty
    at 28 score points so variety cannot bury a substantially better video.
    ``recent`` is oldest first, used by autoplay to pace against the current video.
    """
    remaining = list(rows)
    history = list(recent or [])[-3:]
    ordered = []
    features = {}
    similarities = {}

    def similarity(left, right):
        key = (id(left[0]), id(right[0]))
        if key not in similarities:
            similarities[key] = _similarity(left, right, features)
        return similarities[key]

    while remaining and (limit is None or len(ordered) < limit):
        def value(row: Row) -> float:
            penalty = sum(similarity(row, prev) * (0.5 ** i)
                          for i, prev in enumerate(reversed(history[-3:])))
            return (row[0].score if row[0].score is not None else 65) - min(28, penalty)

        index = max(range(len(remaining)), key=lambda i: value(remaining[i]))
        chosen = remaining.pop(index)
        ordered.append(chosen)
        history.append(chosen)
    return ordered
