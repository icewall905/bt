"""Worker runtime: control polling, interruptible sleeps, state/event helpers, pluggable backends."""
from __future__ import annotations

import logging
import random
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from ..db import emit, get_agent_control, get_agent_state, get_settings, set_agent_state, update_agent_control
from ..models import Category, now

log = logging.getLogger("bt.agent")

TICK_S = 1.0  # control is polled at least this often during waits (contract: <= 2 s)
LLM_BACKOFF_S = 300


class Interrupt(Exception):
    """Unwinds the current step back to the main loop (no YT/LLM call is made after it)."""


class Paused(Interrupt):
    pass


class Disabled(Interrupt):
    pass


class Stopped(Interrupt):
    pass


def aware(d: Optional[datetime]) -> Optional[datetime]:
    """Treat naive datetimes as UTC; return aware UTC."""
    if d is None:
        return None
    return d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d.astimezone(timezone.utc)


def parse_ts(v: Any) -> Optional[datetime]:
    """Parse an ISO timestamp (offset, trailing Z or naive=UTC) to aware UTC."""
    if not v:
        return None
    if isinstance(v, datetime):
        return aware(v)
    s = str(v).strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        return aware(datetime.fromisoformat(s))
    except ValueError:
        return None


def iso(d: Optional[datetime]) -> Optional[str]:
    return aware(d).isoformat() if d else None


def candidate_id(category_id: int, video_id: str) -> Optional[int]:
    from sqlmodel import select

    from ..db import session
    from ..models import Candidate
    with session() as s:
        return s.exec(select(Candidate.id).where(Candidate.category_id == category_id,
                                                 Candidate.video_id == video_id)).first()


class Runtime:
    """Shared context passed to every pipeline step.

    `yt`, `feeds`, `llm` are modules (or fakes with the same interface), imported lazily so the
    worker package imports even while bt.ytdl / bt.feeds are missing.
    """

    def __init__(self, yt=None, feeds=None, llm=None, thumb=None, sleep=time.sleep, clock=time.monotonic):
        self._yt, self._feeds, self._llm = yt, feeds, llm
        self.thumb = thumb  # callable(video_id) -> data URL | None; default judge.fetch_thumb
        self._sleep, self._clock = sleep, clock
        self.stop_requested = False
        self.llm_backoff_until: Optional[datetime] = None
        prev = get_agent_state()
        # Circuit-breaker state survives restarts (persisted inside agent_state).
        self.backoff_n: int = int(prev.get("backoff_n") or 0)
        self.backoff_until: Optional[datetime] = parse_ts(prev.get("backoff_until"))
        self.focus_category_id: Optional[int] = None
        self.rng = random.Random()

    # ---- backends
    @property
    def yt(self):
        if self._yt is None:
            from .. import ytdl
            self._yt = ytdl
        return self._yt

    @property
    def feeds(self):
        if self._feeds is None:
            from .. import feeds
            self._feeds = feeds
        return self._feeds

    @property
    def llm(self):
        if self._llm is None:
            from .. import llm
            self._llm = llm
        return self._llm

    # ---- settings / control
    def settings(self) -> dict:
        return get_settings()

    def throttle(self) -> dict:
        return self.settings()["throttle"]

    def control(self) -> dict:
        return get_agent_control()

    def playing(self, ctl: Optional[dict] = None, th: Optional[dict] = None) -> Optional[datetime]:
        th = th or self.throttle()
        if not th.get("pause_while_playing"):
            return None
        until = parse_ts((ctl or self.control()).get("playing_until"))
        return until if until and until > now() else None

    def check(self, ctl: Optional[dict] = None) -> dict:
        """Raise if we must stop doing work right now. Call between every step."""
        if self.stop_requested:
            raise Stopped()
        ctl = ctl if ctl is not None else self.control()
        if ctl.get("paused"):
            raise Paused()
        if not self.settings()["agent"].get("enabled", True):
            raise Disabled()
        if ctl.get("backoff_reset"):
            self.reset_backoff(manual=True)
            update_agent_control(backoff_reset=False)
        return ctl

    def take_run_now(self, ctl: Optional[dict] = None) -> bool:
        ctl = ctl if ctl is not None else self.control()
        rn = ctl.get("run_now")
        if rn:
            update_agent_control(run_now=None)
            if isinstance(rn, dict) and rn.get("category_id"):
                self.focus_category_id = int(rn["category_id"])
            return True
        return False

    def reset_backoff(self, manual: bool = False) -> None:
        had = self.backoff_until is not None or self.backoff_n
        self.backoff_n, self.backoff_until = 0, None
        if manual and had:
            self.event("backoff", "▶️ Backoff cleared — resuming YouTube requests", "info")

    # ---- llm health
    def llm_ok(self) -> bool:
        return not (self.llm_backoff_until and self.llm_backoff_until > now())

    def llm_failed(self, what: str, err: Exception, **kw) -> None:
        self.llm_backoff_until = now() + timedelta(seconds=LLM_BACKOFF_S)
        self.event("error", f"⚠️ LLM unavailable while {what} — retrying in {LLM_BACKOFF_S // 60} min ({err})"[:500],
                   "warn", payload={"error": str(err)[:500], "until": iso(self.llm_backoff_until)}, **kw)

    # ---- visibility
    def state(self, state: str, detail: str = "", category: Optional[Category] = None, **kw) -> None:
        st = {"state": state, "detail": detail, "backoff_n": self.backoff_n,
              "backoff_until": iso(self.backoff_until), "llm_backoff_until": iso(self.llm_backoff_until)}
        if category is not None:
            st.update(category_id=category.id, category_name=category.name, profile_id=category.profile_id)
        st.update({k: v for k, v in kw.items() if v is not None})
        set_agent_state(**st)

    def event(self, kind: str, message: str, level: str = "info", category: Optional[Category] = None,
              video_id: Optional[str] = None, payload: Optional[dict] = None, **kw):
        if category is not None:
            kw.setdefault("category_id", category.id)
            kw.setdefault("profile_id", category.profile_id)
        payload = dict(payload or {})
        if video_id and kw.get("category_id") and "candidate_id" not in payload:
            cid = candidate_id(kw["category_id"], video_id)
            if cid is not None:
                payload["candidate_id"] = cid  # lets the UI open /api/agent/candidates/{id}
        log.log(logging.WARNING if level in ("warn", "error") else logging.INFO, "%s", message)
        return emit(kind, message, level, video_id=video_id, payload=payload, **kw)

    # ---- waiting
    def sleep(self, seconds: float, state: str = "sleeping", detail: str = "", category: Optional[Category] = None,
              wake_on_run_now: bool = False, allow_paused: bool = False, until_check=None, min_s: float = 0,
              **kw) -> bool:
        """Interruptible wait. Polls control every TICK_S.

        Raises Paused/Disabled/Stopped (unless allow_paused). Returns True if woken early by run_now or
        `until_check()` returning True, False if the full duration elapsed.
        """
        if seconds <= 0:
            return False
        start = self._clock()
        end = start + seconds
        self.state(state, detail, category, until=iso(now() + timedelta(seconds=seconds)), **kw)
        while True:
            if self.stop_requested:
                raise Stopped()
            ctl = self.control()
            if not allow_paused:
                self.check(ctl)
            if wake_on_run_now and ctl.get("run_now"):
                return True
            if until_check is not None and self._clock() - start >= min_s and until_check(ctl):
                return True
            left = end - self._clock()
            if left <= 0:
                return False
            self._sleep(min(TICK_S, left))
