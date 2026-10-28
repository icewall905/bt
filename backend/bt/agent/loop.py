"""Main worker loop: learn → judge → enrich (1 video) → discover (if backlog small) → idle."""
from __future__ import annotations

import logging
import traceback
from typing import Optional

from sqlmodel import col, select

from ..db import session
from ..models import Candidate
from . import data, enrich, judge, learn, memory, planner
from .ratelimit import RateLimiter
from ..models import now
from .runtime import Disabled, Interrupt, Paused, Runtime, Stopped

log = logging.getLogger("bt.agent")

IDLE_S = 300  # nothing to do: re-check after this (run_now / new feedback wake earlier)
YT_WAIT_CHUNK_S = 60  # while YouTube is blocked (backoff/quiet/playing/cap), wake this often for LLM work
ERROR_SLEEP_S = 30
IDLE_MIN_S = 5  # idle never wakes for feedback sooner than this (prevents busy loops)


class Worker:
    def __init__(self, rt: Optional[Runtime] = None, **kw):
        self.rt = rt or Runtime(**kw)
        self.rl = RateLimiter(self.rt)
        self._paused_announced = False

    # ------------------------------------------------------------------ one iteration
    def iterate(self) -> bool:
        """Run one pass of the pipeline. Returns True if any work was done (or a YT wait happened)."""
        rt = self.rt
        rt.check()
        rt.take_run_now()
        if self._paused_announced:
            self._paused_announced = False
            rt.event("control", "▶️ Resumed", "info")
        did = False

        # (1) learn — LLM only, highest priority
        if rt.llm_ok() and learn.process(rt):
            did = True
        if rt.llm_ok() and not learn.pending_count() and memory.process(rt):
            did = True

        # (2) judge everything already enriched
        for cand in judge.pending():
            rt.check()
            if not rt.llm_ok():
                break
            if judge.judge_one(rt, cand):
                did = True
            if learn.pending_count() and rt.llm_ok():  # feedback arrived meanwhile → learn first
                learn.process(rt)

        # (3)+(4) YouTube work
        rt.check()
        with session() as s:
            needs = data.category_needs(s, rt.focus_category_id)
        if not needs:
            return did
        if self.rl.wait_blocker(max_wait=YT_WAIT_CHUNK_S, category=needs[0].cat):
            return True
        yt = rt.yt
        cat = None
        try:
            cand = self._next_found(needs)
            if cand is not None:
                cat = next(n.cat for n in needs if n.cat.id == cand.category_id)
                enrich.enrich_one(rt, self.rl, cand, cat)
                did = True
            rt.check()
            with session() as s:
                needs = data.category_needs(s, rt.focus_category_id)
            for need in needs:
                pend = need.counts.get("found", 0) + need.counts.get("enriched", 0)
                if pend < data.LOW_WATER:
                    cat = need.cat
                    res = planner.discover(rt, self.rl, cat)
                    if rt.focus_category_id == cat.id:
                        rt.focus_category_id = None
                    if res is not None:
                        did = True
                        break
        except planner._Skip:
            did = True
        except Exception as e:  # noqa: BLE001
            if isinstance(e, yt.YtBlocked):
                self.rl.blocked(e, cat)
                return True
            raise
        return did

    @staticmethod
    def _next_found(needs: list[data.Need]) -> Optional[Candidate]:
        with session() as s:
            for need in needs:
                c = s.exec(select(Candidate).where(Candidate.category_id == need.cat.id, Candidate.status == "found",
                                                   Candidate.dismissed == False)  # noqa: E712
                           .order_by(col(Candidate.created_at)).limit(1)).first()
                if c:
                    return c
        return None

    # ------------------------------------------------------------------ forever
    def _idle(self) -> None:
        """Nothing to do: sleep (always > 0). Wake early on run_now, or on new feedback once the LLM is usable."""
        rt = self.rt
        secs = IDLE_S
        detail = "All queues are full — checking again soon"
        if not rt.llm_ok():
            secs = max(IDLE_MIN_S, min(IDLE_S, (rt.llm_backoff_until - now()).total_seconds()))
            detail = "Waiting for the AI model to become available"
        rt.sleep(secs, "idle", detail, wake_on_run_now=True, min_s=IDLE_MIN_S,
                 until_check=lambda ctl: rt.llm_ok() and (learn.pending_count() > 0 or bool(ctl.get("memory_run_now"))))

    def _paused(self) -> None:
        rt = self.rt
        if not self._paused_announced:
            self._paused_announced = True
            rt.event("control", "⏸️ Paused — no YouTube or AI calls until resumed", "info")
        rt.state("paused", "Paused by user")
        while not rt.stop_requested and rt.control().get("paused"):
            rt._sleep(1.0)

    def _disabled(self) -> None:
        rt = self.rt
        rt.state("idle", "AI curator disabled in settings")
        while not rt.stop_requested and not rt.settings()["agent"].get("enabled", True):
            if rt.control().get("paused"):
                return
            rt._sleep(2.0)

    def _step(self) -> None:
        try:
            if not self.iterate():
                self._idle()
        except Paused:
            self._paused()
        except Disabled:
            self._disabled()

    def _on_error(self, e: Exception) -> None:
        rt = self.rt
        log.error("worker iteration failed: %s", e, exc_info=e)
        try:
            rt.event("error", f"💥 Worker error: {e}"[:500], "error",
                     payload={"traceback": "".join(traceback.format_exception(e))[-2000:]})
            rt.sleep(ERROR_SLEEP_S, "error", f"{type(e).__name__}: {e}"[:300], wake_on_run_now=True)
        except Interrupt:
            pass  # pause/disable/stop are handled by the next _step / loop condition
        except Exception:  # noqa: BLE001 — e.g. database locked; never let the worker die
            log.exception("error handler failed")
            rt._sleep(5.0)

    def run(self) -> None:
        rt = self.rt
        memory.recover()
        try:
            rt.event("control", "🤖 Curator started", "info")
            rt.state("idle", "Starting")
        except Exception:  # noqa: BLE001
            log.exception("failed to write start state")
        try:
            while not rt.stop_requested:
                try:
                    self._step()
                except Stopped:
                    break
                except Exception as e:  # noqa: BLE001
                    self._on_error(e)
        finally:
            try:
                rt.state("offline", "Worker stopped")
                rt.event("control", "🔌 Curator stopped", "info")
            except Exception:  # noqa: BLE001
                log.exception("failed to write offline state")
