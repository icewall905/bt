"""Agent status/control + live SSE stream of AgentEvents."""
import asyncio
import json
from datetime import timedelta
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlmodel import Session, col, select

from ..db import (get_agent_control, get_agent_state, get_kv, get_session, get_settings, session, update_agent_control,
                  yt_request_counts)
from ..models import AgentEvent, Candidate, Category, now
from .core import profile_id

router = APIRouter()


def _queues(s: Session, pid: Optional[int]) -> list[dict]:
    q = select(Category)
    if pid:
        q = q.where(Category.profile_id == pid)
    out = []
    for c in s.exec(q.order_by(Category.position, Category.id)).all():
        cands = s.exec(select(Candidate.status, Candidate.dismissed).where(Candidate.category_id == c.id)).all()
        out.append({
            "category_id": c.id, "name": c.name, "emoji": c.emoji, "color": c.color, "enabled": c.enabled,
            "target": c.target_queue, "last_worked_at": c.last_worked_at,
            "accepted": sum(1 for st, d in cands if st == "accepted" and not d),
            "pending": sum(1 for st, _ in cands if st in ("found", "enriched")),
            "rejected": sum(1 for st, _ in cands if st == "rejected"),
        })
    return out


def status_payload(s: Session, pid: Optional[int] = None) -> dict:
    st = get_settings(s)["throttle"]
    return {
        "state": get_agent_state(),
        "downloader": get_kv("downloader_state", {"state": "offline"}),
        "control": get_agent_control(),
        "budget": {**yt_request_counts(), "max_hour": st["max_per_hour"], "max_day": st["max_per_day"]},
        "queues": _queues(s, pid),
    }


@router.get("/agent/status")
def agent_status(pid: int = Depends(profile_id), s: Session = Depends(get_session)):
    return status_payload(s, pid)


@router.get("/agent/events")
def agent_events(after_id: int = 0, limit: int = 200, category_id: Optional[int] = None,
                 s: Session = Depends(get_session)):
    q = select(AgentEvent).where(AgentEvent.id > after_id)
    if category_id:
        q = q.where(AgentEvent.category_id == category_id)
    if after_id:
        return s.exec(q.order_by(AgentEvent.id).limit(limit)).all()
    return list(reversed(s.exec(q.order_by(col(AgentEvent.id).desc()).limit(limit)).all()))


@router.get("/agent/stream")
async def agent_stream(request: Request, after_id: int = 0):
    """SSE: `event: state` (agent_state+control+budget, on change) and `event: agent` (each AgentEvent)."""
    def poll(last_id: int, with_state: bool):
        with session() as s:
            if last_id < 0:
                last = s.exec(select(AgentEvent).order_by(col(AgentEvent.id).desc())).first()
                return max(0, (last.id if last else 0) - 30), [], None
            evs = s.exec(select(AgentEvent).where(AgentEvent.id > last_id).order_by(AgentEvent.id).limit(100)).all()
            st = None
            if with_state:
                st = status_payload(s)
                st.pop("queues")
            return (evs[-1].id if evs else last_id), evs, st

    async def gen():
        # DB work runs in a thread so a busy SQLite never stalls the event loop (and video proxying).
        last_id = after_id
        if not last_id:
            last_id, _, _ = await run_in_threadpool(poll, -1, False)
        last_state = None
        tick = 0
        yield "retry: 3000\n\n"
        while not await request.is_disconnected():
            last_id, evs, st = await run_in_threadpool(poll, last_id, tick % 2 == 0)
            for ev in evs:
                yield f"id: {ev.id}\nevent: agent\ndata: {ev.model_dump_json()}\n\n"
            if st is not None:
                blob = json.dumps(st, default=str)
                if blob != last_state:
                    last_state = blob
                    yield f"event: state\ndata: {blob}\n\n"
            tick += 1
            if tick % 30 == 0:
                yield ": ping\n\n"
            await asyncio.sleep(1)

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/agent/pause")
def pause():
    return update_agent_control(paused=True)


@router.post("/agent/resume")
def resume():
    return update_agent_control(paused=False)


@router.post("/agent/reset-backoff")
def reset_backoff():
    """Manually clear a YouTube bot-check backoff (risky: may get blocked again)."""
    return update_agent_control(backoff_reset=True)


class RunNow(BaseModel):
    category_id: Optional[int] = None


@router.post("/agent/run")
def run_now(body: RunNow):
    """Wake the worker now (skip remaining sleep), optionally focusing one category."""
    return update_agent_control(run_now={"category_id": body.category_id, "at": now().isoformat()})


@router.post("/agent/playing")
def playing(seconds: int = 90):
    """Player heartbeat: worker holds off YouTube requests while someone is watching (if enabled)."""
    return update_agent_control(playing_until=(now() + timedelta(seconds=seconds)).isoformat())


@router.get("/agent/candidates/{cand_id}")
def candidate_detail(cand_id: int, s: Session = Depends(get_session)):
    from ..models import Video
    from .core import candidate_out
    c = s.get(Candidate, cand_id)
    if not c:
        return {"detail": "not found"}
    v = s.get(Video, c.video_id)
    out = candidate_out(c, v)
    if v:
        out["transcript_excerpt"] = (v.transcript or "")[:1500]
        out["comments"] = (v.comments or [])[:10]
    out["events"] = s.exec(select(AgentEvent).where(AgentEvent.video_id == c.video_id,
                                                    AgentEvent.category_id == c.category_id)
                           .order_by(AgentEvent.id)).all()
    return out


class LlmTest(BaseModel):
    base_url: Optional[str] = None
    model: Optional[str] = None
    api_key: Optional[str] = None


@router.post("/agent/llm-test")
async def llm_test(body: LlmTest, s: Session = Depends(get_session)):
    cfg = get_settings(s)["llm"]
    base = (body.base_url or cfg["base_url"]).rstrip("/")
    key = body.api_key if body.api_key and body.api_key != "********" else cfg.get("api_key")
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    try:
        async with httpx.AsyncClient(timeout=60) as c:
            models = (await c.get(f"{base}/models", headers=headers)).json()
            body = {"model": body.model or cfg["model"], "max_tokens": 20,
                    "messages": [{"role": "user", "content": "Reply with just: pong"}]}
            if cfg.get("thinking") is False:
                body["chat_template_kwargs"] = {"enable_thinking": False}
            r = await c.post(f"{base}/chat/completions", headers=headers, json=body)
            r.raise_for_status()
            reply = r.json()["choices"][0]["message"].get("content") or ""
            if not reply.strip() and "chat_template_kwargs" not in body:
                # A thinking model spent the whole budget reasoning (empty content): retry
                # with thinking off, the same fallback the agent worker uses.
                body["chat_template_kwargs"] = {"enable_thinking": False}
                r = await c.post(f"{base}/chat/completions", headers=headers, json=body)
                r.raise_for_status()
                reply = r.json()["choices"][0]["message"].get("content") or ""
        return {"ok": True, "models": [m.get("id") for m in models.get("data", [])], "reply": reply}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)}
