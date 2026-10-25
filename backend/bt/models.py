"""SQLModel tables. Shared by api and worker processes (same SQLite file)."""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import JSON, Column, Text, UniqueConstraint
from sqlmodel import Field, SQLModel


def now() -> datetime:
    return datetime.now(timezone.utc)


def J(default=None):
    """JSON column field."""
    return Field(default_factory=(lambda: [] if default is None else default.copy()), sa_column=Column(JSON))


class Setting(SQLModel, table=True):
    key: str = Field(primary_key=True)
    value: dict = Field(default_factory=dict, sa_column=Column(JSON))


class Profile(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    emoji: str = "🙂"
    color: str = "#7c5cff"
    prefs: dict = J({})  # per-profile overrides (e.g. sponsorblock, player)
    created_at: datetime = Field(default_factory=now)


class Category(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    profile_id: int = Field(foreign_key="profile.id", index=True)
    name: str
    emoji: str = "✨"
    color: str = "#7c5cff"
    brief: str = Field(default="", sa_column=Column(Text))  # free-text description for the AI
    seed_queries: list = J()
    seed_channels: list = J()  # channel ids/handles/urls
    include_keywords: list = J()
    exclude_keywords: list = J()
    min_duration_s: int = 60
    max_duration_s: int = 3600
    language: str = ""
    max_age_days: int = 0  # 0 = any
    target_queue: int = 20  # stop searching when this many unwatched accepted
    threshold: int = 65  # accept score
    priority: int = 1  # 1..5
    kid_safe: bool = False
    enabled: bool = True
    position: int = 0
    created_at: datetime = Field(default_factory=now)
    last_worked_at: Optional[datetime] = None


class Channel(SQLModel, table=True):
    id: str = Field(primary_key=True)  # UC...
    name: str = ""
    handle: str = ""
    avatar: str = ""
    updated_at: datetime = Field(default_factory=now)


class ProfileChannel(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("profile_id", "channel_id"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    profile_id: int = Field(foreign_key="profile.id", index=True)
    channel_id: str = Field(index=True)
    subscribed: bool = False
    blocked: bool = False
    trust: float = 0.0  # -1..1, adjusted by feedback
    last_feed_check: Optional[datetime] = None


class Video(SQLModel, table=True):
    id: str = Field(primary_key=True)  # 11-char YT id
    title: str = ""
    channel_id: str = Field(default="", index=True)
    channel_name: str = ""
    duration_s: int = 0
    published_at: Optional[datetime] = None
    thumbnail: str = ""
    view_count: int = 0
    like_count: int = 0
    description: str = Field(default="", sa_column=Column(Text))
    tags: list = J()
    chapters: list = J()  # [{start_time,end_time,title}]
    transcript: str = Field(default="", sa_column=Column(Text))
    comments: list = J()  # [{author,text,likes}]
    is_short: bool = False
    is_live: bool = False
    fetched_at: Optional[datetime] = None  # basic metadata
    enriched_at: Optional[datetime] = None  # transcript+comments


class Candidate(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("category_id", "video_id"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    category_id: int = Field(foreign_key="category.id", index=True)
    video_id: str = Field(index=True)  # no FK: rows may be flushed before their Video
    # found -> enriched -> accepted | rejected ; error
    status: str = Field(default="found", index=True)
    source: str = ""  # "search: <q>" | "rss" | "related:<id>" | "manual"
    score: Optional[int] = None
    summary: str = Field(default="", sa_column=Column(Text))
    reasons: list = J()
    red_flags: list = J()
    tags: list = J()
    error: str = ""
    dismissed: bool = False
    created_at: datetime = Field(default_factory=now)
    judged_at: Optional[datetime] = None


class Feedback(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    profile_id: int = Field(foreign_key="profile.id", index=True)
    video_id: str = Field(index=True)
    category_id: Optional[int] = None
    rating: int = 0  # -1 dislike, 0 neutral/note, 1 like, 2 love
    chips: list = J()
    text: str = Field(default="", sa_column=Column(Text))
    processed: bool = False  # distilled into lessons by worker
    created_at: datetime = Field(default_factory=now)


class Lesson(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    profile_id: int = Field(foreign_key="profile.id", index=True)
    category_id: Optional[int] = None  # None = applies to all of profile's categories
    channel_id: Optional[str] = None
    text: str = Field(sa_column=Column(Text))
    weight: float = 1.0
    active: bool = True
    source_feedback_ids: list = J()
    created_at: datetime = Field(default_factory=now)
    updated_at: datetime = Field(default_factory=now)


class WatchHistory(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("profile_id", "video_id"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    profile_id: int = Field(foreign_key="profile.id", index=True)
    video_id: str = Field(index=True)
    category_id: Optional[int] = None
    position_s: float = 0
    duration_s: float = 0
    finished: bool = False
    updated_at: datetime = Field(default_factory=now, index=True)


class AgentEvent(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    ts: datetime = Field(default_factory=now, index=True)
    level: str = "info"  # debug|info|warn|error|success
    kind: str = ""  # plan|search|rss|metadata|transcript|comments|judge|accept|reject|learn|sleep|backoff|error
    message: str = ""
    profile_id: Optional[int] = None
    category_id: Optional[int] = None
    video_id: Optional[str] = None
    payload: dict = J({})


class YtRequest(SQLModel, table=True):
    """Every outbound YouTube request (worker + api) for budgeting/visibility."""
    id: Optional[int] = Field(default=None, primary_key=True)
    ts: datetime = Field(default_factory=now, index=True)
    origin: str = "worker"  # worker | user
    kind: str = ""
    ok: bool = True
    detail: str = ""
