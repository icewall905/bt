"""Offline cache downloader: queue, eviction, reconcile, run_one, gating, API (no network unless BT_LIVE=1)."""
import os
import time
from datetime import timedelta
from pathlib import Path

import pytest
from sqlmodel import delete, select

from bt import ytdl
from bt.config import MEDIA_DIR
from bt.db import init_db, save_setting, session, set_agent_state, update_agent_control
from bt.downloader import service as svc
from bt.models import Candidate, Category, Download, Profile, Video, WatchHistory, YtRequest, now

IDS = [f"vid{i:08d}" for i in range(10)]  # 11 chars


@pytest.fixture(autouse=True)
def clean():
    init_db()
    with session() as s:
        for m in (Download, Candidate, WatchHistory, Category, YtRequest):
            s.exec(delete(m))
        s.commit()
    save_setting("cache", {"enabled": True, "max_gb": 1, "max_height": 720, "rate_limit": 0, "min_gap_s": 0,
                           "auto": "accepted"})
    save_setting("agent", {"enabled": True})
    update_agent_control(paused=False)
    set_agent_state(state="idle", backoff_until=None)
    import shutil
    shutil.rmtree(MEDIA_DIR, ignore_errors=True)
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    yield
    update_agent_control(paused=False)


def _cat(s, name="c"):
    pid = s.exec(select(Profile)).first().id
    c = Category(profile_id=pid, name=name)
    s.add(c)
    s.commit()
    s.refresh(c)
    return c


def _cand(s, cat, vid, score=80, status="accepted", dismissed=False, dur=10):
    if not s.get(Video, vid):
        s.add(Video(id=vid, title=f"T {vid}", duration_s=dur))
    s.add(Candidate(category_id=cat.id, video_id=vid, status=status, score=score, dismissed=dismissed))
    s.commit()


def _done(s, vid, size, pinned=False, played_ago=None):
    p = MEDIA_DIR / svc.rel_path(vid)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"x" * 10)
    d = Download(video_id=vid, status="done", path=svc.rel_path(vid), size_bytes=size, pinned=pinned,
                 finished_at=now() - timedelta(days=10),
                 last_played_at=(now() - timedelta(hours=played_ago)) if played_ago is not None else None)
    s.add(d)
    s.commit()
    return d


def test_sync_queue_and_next_round_robin():
    with session() as s:
        a, b = _cat(s, "a"), _cat(s, "b")
        _cand(s, a, IDS[0], 90)
        _cand(s, a, IDS[1], 95)
        _cand(s, b, IDS[2], 50)
        _cand(s, a, IDS[3], 99, dismissed=True)
        _cand(s, b, IDS[4], 99, status="rejected")
        s.add(Download(video_id=IDS[5], status="evicted"))
        _cand(s, b, IDS[5], 99)
        assert svc.sync_queue(s, {"auto": "accepted"}) == 3
        assert svc.sync_queue(s, {"auto": "accepted"}) == 0
        queued = {d.video_id for d in s.exec(select(Download).where(Download.status == "queued")).all()}
        assert queued == {IDS[0], IDS[1], IDS[2]}
        d, cat = svc.next_download(s, None)
        assert (d.video_id, cat) == (IDS[1], a.id)  # best score in first category
        d, cat = svc.next_download(s, cat)
        assert (d.video_id, cat) == (IDS[2], b.id)  # round-robin
        s.add(Download(video_id=IDS[6], status="queued", pinned=True))
        s.commit()
        assert svc.next_download(s, cat)[0].video_id == IDS[6]  # manual pin first


def test_retry_backoff_and_max_attempts():
    t = now()
    d = Download(video_id=IDS[0], status="error", attempts=1, finished_at=t - timedelta(seconds=30))
    assert not svc._retry_ready(d, t)
    d.finished_at = t - timedelta(seconds=svc.RETRY_BASE_S + 1)
    assert svc._retry_ready(d, t)
    d.attempts = svc.MAX_ATTEMPTS
    assert not svc._retry_ready(d, t)


def test_eviction_order_and_make_room():
    with session() as s:
        c = _cat(s)
        pid = c.profile_id
        _done(s, IDS[0], 400_000_000, played_ago=1)  # wanted, recently played
        _cand(s, c, IDS[0])
        _done(s, IDS[1], 400_000_000, played_ago=50)  # wanted, played long ago
        _cand(s, c, IDS[1])
        _done(s, IDS[2], 300_000_000)  # dismissed -> unwanted
        _cand(s, c, IDS[2], dismissed=True)
        _done(s, IDS[3], 100_000_000)  # finished by its only viewer (even though still accepted)
        _cand(s, c, IDS[3])
        s.add(WatchHistory(profile_id=pid, video_id=IDS[3], finished=True))
        _done(s, IDS[4], 900_000_000, pinned=True)
        s.commit()
        order = [d.video_id for d in svc.eviction_order(s, allow_wanted=True)]
        assert order == [IDS[3], IDS[2], IDS[1], IDS[0]]
        assert [d.video_id for d in svc.eviction_order(s, allow_wanted=False)] == [IDS[3], IDS[2]]
        # cap 1 GB, used 2.1 GB: unwanted ones go, wanted+pinned can't -> False for auto downloads
        assert svc.make_room(s, {"max_gb": 1}, 0, allow_wanted=False) is False
        st = {d.video_id: d.status for d in s.exec(select(Download)).all()}
        assert st[IDS[3]] == st[IDS[2]] == "evicted" and st[IDS[1]] == "done"
        assert not (MEDIA_DIR / svc.rel_path(IDS[3])).exists()
        assert svc.make_room(s, {"max_gb": 1.5}, 0, allow_wanted=True) is True  # pinned request may evict wanted
        assert s.get(Download, IDS[1]).status == "evicted" and s.get(Download, IDS[4]).status == "done"


def test_reconcile():
    with session() as s:
        s.add(Download(video_id=IDS[0], status="done", path=svc.rel_path(IDS[0]), size_bytes=5))  # file missing
        s.add(Download(video_id=IDS[1], status="downloading"))
        s.add(Download(video_id=IDS[2], status="evicted"))
        s.commit()
    for vid in (IDS[2], IDS[3]):  # IDS[2]: evicted but file survived, IDS[3]: orphan -> adopt
        p = MEDIA_DIR / svc.rel_path(vid)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"abc")
    (MEDIA_DIR / "zz").mkdir()
    (MEDIA_DIR / "zz" / "junk.mp4").write_bytes(b"x")
    (MEDIA_DIR / ".tmp" / IDS[7]).mkdir(parents=True)  # staging without an active row
    (MEDIA_DIR / ".tmp" / IDS[1]).mkdir(parents=True)  # staging of a resumable download: keep
    with session() as s:
        st = svc.reconcile(s)
        assert st == {"missing": 1, "adopted": 1, "deleted": 2, "requeued": 1, "staging_removed": 1}
        assert s.get(Download, IDS[0]).status == "evicted"
        assert s.get(Download, IDS[1]).status == "queued"
        d = s.get(Download, IDS[3])
        assert d.status == "done" and d.size_bytes == 3
    assert not (MEDIA_DIR / svc.rel_path(IDS[2])).exists()
    assert (MEDIA_DIR / ".tmp" / IDS[1]).exists() and not (MEDIA_DIR / ".tmp" / IDS[7]).exists()


def _fake_download(content=b"\0" * 1000, hook_calls=1, exc=None):
    def fake(vid, workdir, max_height, rate_limit, hook=None, origin="worker"):
        for i in range(hook_calls):
            hook({"status": "downloading", "downloaded_bytes": 500, "total_bytes": 1000, "speed": 1e6, "eta": 1,
                  "info_dict": {"vcodec": "avc1", "acodec": "none"}})
        if exc:
            raise exc
        p = Path(workdir) / f"{vid}.mp4"
        p.write_bytes(content)
        return {"path": str(p), "height": 720, "vcodec": "avc1.4d401f", "acodec": "mp4a.40.2", "title": "T"}
    return fake


def _queue(vid, **kw):
    with session() as s:
        if not s.get(Video, vid):
            s.add(Video(id=vid, title="Title", duration_s=10))
        s.add(Download(video_id=vid, status="queued", **kw))
        s.commit()
        return s.get(Download, vid)


def test_run_one_success_atomic(monkeypatch):
    monkeypatch.setattr(svc.ytdl, "download", _fake_download())
    d = _queue(IDS[0], pinned=True)
    dl = svc.Downloader(sleep=lambda s: None)
    assert dl.run_one(d, {"max_gb": 1, "max_height": 720}) == "done"
    with session() as s:
        row = s.get(Download, IDS[0])
        assert (row.status, row.height, row.size_bytes, row.progress) == ("done", 720, 1000, 1.0)
    assert (MEDIA_DIR / svc.rel_path(IDS[0])).stat().st_size == 1000
    assert not svc.staging_dir(IDS[0]).exists()
    from bt.db import get_kv
    assert get_kv("downloader_state")["state"] == "downloading"


def test_run_one_errors(monkeypatch):
    dl = svc.Downloader(sleep=lambda s: None)
    cfg = {"max_gb": 1}
    monkeypatch.setattr(svc.ytdl, "download", _fake_download(exc=ytdl.YtUnavailable("This video is unavailable")))
    assert dl.run_one(_queue(IDS[0]), cfg) == "error"
    monkeypatch.setattr(svc.ytdl, "download", _fake_download(exc=ytdl.YtError("ffmpeg exploded")))
    assert dl.run_one(_queue(IDS[1]), cfg) == "error"
    monkeypatch.setattr(svc.ytdl, "download", _fake_download(exc=ytdl.YtBlocked("Sign in to confirm")))
    assert dl.run_one(_queue(IDS[2]), cfg) == "blocked"
    with session() as s:
        a, b, c = (s.get(Download, i) for i in IDS[:3])
        assert (a.status, a.attempts) == ("error", svc.MAX_ATTEMPTS)
        assert (b.status, b.attempts) == ("error", 1)
        assert (c.status, c.attempts) == ("queued", 0)
    assert dl.blocker()[0] == "backoff"


def test_hook_aborts_on_pause_and_on_delete(monkeypatch):
    monkeypatch.setattr(svc, "CONTROL_EVERY_S", 0)
    monkeypatch.setattr(svc.ytdl, "download", _fake_download())
    update_agent_control(paused=True)
    dl = svc.Downloader(sleep=lambda s: None)
    assert dl.run_one(_queue(IDS[0]), {"max_gb": 1}) == "aborted"
    with session() as s:
        assert s.get(Download, IDS[0]).status == "queued"  # resumable later
    update_agent_control(paused=False)

    def deleting(vid, workdir, max_height, rate_limit, hook=None, **k):
        with session() as s:
            row = s.get(Download, vid)
            row.status = "evicted"
            s.add(row)
            s.commit()
        return _fake_download()(vid, workdir, max_height, rate_limit, hook)

    monkeypatch.setattr(svc.ytdl, "download", deleting)
    assert dl.run_one(_queue(IDS[1]), {"max_gb": 1}) == "aborted"
    with session() as s:
        assert s.get(Download, IDS[1]).status == "evicted"
    assert not (MEDIA_DIR / svc.rel_path(IDS[1])).exists()


def test_blocker_gates():
    dl = svc.Downloader(sleep=lambda s: None)
    assert dl.blocker() is None
    update_agent_control(paused=True)
    assert dl.blocker()[0] == "paused"
    update_agent_control(paused=False)
    set_agent_state(state="backoff", backoff_until=(now() + timedelta(minutes=5)).isoformat())
    assert dl.blocker()[0] == "backoff"
    set_agent_state(state="idle", backoff_until=None)
    save_setting("cache", {"enabled": False})
    assert dl.blocker()[0] == "disabled"
    save_setting("cache", {"enabled": True})
    save_setting("agent", {"enabled": False})
    assert dl.blocker()[0] == "disabled"


def test_iterate_end_to_end(monkeypatch):
    monkeypatch.setattr(svc.ytdl, "download", _fake_download())
    with session() as s:
        _cand(s, _cat(s), IDS[0])
    dl = svc.Downloader(sleep=lambda s: None)
    dl.iterate()
    with session() as s:
        assert s.get(Download, IDS[0]).status == "done"
    assert dl.iterate() == 30  # nothing left


def test_download_opts():
    o = ytdl.download_opts("/w", 720, 8_000_000, [print])
    assert o["format"].startswith("bv*[vcodec^=avc1][height<=720]+ba[acodec^=mp4a]")
    assert o["merge_output_format"] == "mp4" and o["continuedl"] and not o["skip_download"]
    assert o["ratelimit"] == 8_000_000 and o["outtmpl"] == "/w/%(id)s.%(ext)s"
    assert o["postprocessor_args"]["merger+ffmpeg_o"] == ["-movflags", "+faststart"]
    assert o["extractor_args"]["youtubepot-bgutilhttp"]["base_url"]


def test_api_downloads_and_file_range():
    from fastapi.testclient import TestClient
    from bt.main import app
    with session() as s:
        if not s.get(Video, IDS[0]):
            s.add(Video(id=IDS[0], title="x"))
            s.commit()
        _done(s, IDS[0], 10)
    with TestClient(app) as c:
        r = c.get(f"/api/video/{IDS[0]}/file", headers={"Range": "bytes=2-5"})
        assert r.status_code == 206 and r.headers["content-range"] == "bytes 2-5/10" and len(r.content) == 4
        with session() as s:
            assert s.get(Download, IDS[0]).last_played_at is not None
        assert c.get(f"/api/video/{IDS[1]}/file").status_code == 404
        lst = c.get("/api/downloads").json()
        assert lst["items"][0]["video_id"] == IDS[0] and lst["items"][0]["video"]["offline"] is True
        assert lst["totals"]["used_bytes"] == 10
        r = c.post("/api/downloads", json={"video_id": IDS[1]}).json()
        assert r["status"] == "queued" and r["pinned"] is True
        assert c.post("/api/downloads", json={"video_id": "bad"}).status_code == 400
        assert c.delete(f"/api/downloads/{IDS[0]}").json()["ok"]
        assert not (MEDIA_DIR / svc.rel_path(IDS[0])).exists()
        assert c.get(f"/api/video/{IDS[0]}/file").status_code == 404
        assert c.delete("/api/downloads").json()["removed"] == 1


@pytest.mark.live
@pytest.mark.skipif(os.environ.get("BT_LIVE") != "1", reason="set BT_LIVE=1")
def test_live_download_short_video():
    _queue("jNQXAC9IVRw", pinned=True)
    dl = svc.Downloader(sleep=lambda s: None)
    t = time.monotonic()
    with session() as s:
        d = s.get(Download, "jNQXAC9IVRw")
    assert dl.run_one(d, {"max_gb": 1, "max_height": 1080, "rate_limit": 0}) == "done"
    p = MEDIA_DIR / svc.rel_path("jNQXAC9IVRw")
    data = p.read_bytes()
    assert data[4:8] == b"ftyp" and b"moov" in data[:4096], "faststart: moov should precede mdat"
    assert time.monotonic() - t < 120
