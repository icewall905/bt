"""Slow external video requests must not reserve the SQLite connection pool."""
import asyncio

import httpx
from fastapi import HTTPException
from sqlalchemy import event

from bt.api import agent, video
from bt.db import engine, init_db, session
from bt.main import app


def test_concurrent_slow_searches_release_profile_connections(monkeypatch):
    init_db()

    async def exercise():
        count = 0
        reached = asyncio.Event()
        release = asyncio.Event()

        async def slow_youtube(*args, **kwargs):
            nonlocal count
            count += 1
            if count == 20:
                reached.set()
            await release.wait()
            raise HTTPException(503, "simulated slow upstream")

        monkeypatch.setattr(video, "_yt", slow_youtube)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            tasks = [asyncio.create_task(client.get("/api/search", params={"q": str(i)})) for i in range(20)]
            try:
                await asyncio.wait_for(reached.wait(), timeout=5)
                assert engine.pool.checkedout() == 0
                assert (await asyncio.wait_for(client.get("/api/health"), timeout=2)).status_code == 200
            finally:
                release.set()
                responses = await asyncio.gather(*tasks)
            assert all(r.status_code == 503 for r in responses)

    asyncio.run(exercise())


def test_activity_status_reuses_the_callers_connection():
    init_db()
    count = 0
    peak = 0

    def checkout(*_args):
        nonlocal count, peak
        count += 1
        peak = max(peak, count)

    def checkin(*_args):
        nonlocal count
        count -= 1

    event.listen(engine, "checkout", checkout)
    event.listen(engine, "checkin", checkin)
    try:
        with session() as s:
            result = agent.status_payload(s)
            assert "state" in result and "budget" in result
        assert peak == 1 and count == 0
    finally:
        event.remove(engine, "checkout", checkout)
        event.remove(engine, "checkin", checkin)
