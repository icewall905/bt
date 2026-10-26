import os
import tempfile

os.environ.setdefault("BT_DATA_DIR", tempfile.mkdtemp(prefix="bt-test-"))

from fastapi.testclient import TestClient  # noqa: E402
from sqlmodel import select  # noqa: E402

from bt.db import emit, session  # noqa: E402
from bt.main import app  # noqa: E402
from bt.models import Candidate, Category, Video, WatchHistory, now  # noqa: E402
from bt.agent import data  # noqa: E402


def client():
    c = TestClient(app)
    c.__enter__()  # run lifespan (init_db)
    return c


def test_profiles_categories_feed_flow():
    c = client()
    profiles = c.get("/api/profiles").json()
    assert profiles and profiles[0]["name"]
    kid = c.post("/api/profiles", json={"name": "Kids", "emoji": "🧒"}).json()
    h = {"X-Profile-Id": str(kid["id"])}

    cat = c.post("/api/categories", json={"name": "Science", "brief": "fun science"}, headers=h).json()
    assert cat["profile_id"] == kid["id"]
    # Other profile cannot see it
    assert all(x["id"] != cat["id"] for x in c.get("/api/categories").json())
    assert c.get(f"/api/categories/{cat['id']}").status_code == 404

    with session() as s:
        s.add(Video(id="abcdefghijk", title="Egg drop", channel_id="UC1", duration_s=600))
        s.add(Candidate(category_id=cat["id"], video_id="abcdefghijk", status="accepted", score=90, summary="fun"))
        s.commit()

    home = c.get("/api/feed/home", headers=h).json()
    row = next(r for r in home if r["kind"] == "category")
    assert row["items"][0]["video"]["title"] == "Egg drop"

    # watching to the end hides it from the feed
    c.post("/api/history", json={"video_id": "abcdefghijk", "position_s": 590, "duration_s": 600}, headers=h)
    assert c.get(f"/api/feed/category/{cat['id']}", headers=h).json() == []

    fb = c.post("/api/feedback", json={"video_id": "abcdefghijk", "category_id": cat["id"], "rating": -1,
                                       "text": "mean to the cat"}, headers=h).json()
    assert fb["profile_id"] == kid["id"]
    assert c.post("/api/lessons", json={"text": "No cruelty"}, headers=h).status_code == 200
    assert len(c.get("/api/lessons", headers=h).json()) == 1

    ch = c.put("/api/channels/UC1", json={"name": "Chan", "subscribed": True}, headers=h).json()
    assert ch["subscribed"]
    assert c.delete(f"/api/profiles/{kid['id']}").json()["ok"]


def test_mark_seen():
    c = client()
    profiles = c.get("/api/profiles").json()
    h = {"X-Profile-Id": str(profiles[0]["id"])}
    cat = c.post("/api/categories", json={"name": "S", "brief": "b"}, headers=h).json()
    with session() as s:
        s.add(Video(id="seenit00000", title="Seen", channel_id="UC1", duration_s=600))
        s.add(Video(id="other000000", title="Other", channel_id="UC1", duration_s=600))
        s.add(Candidate(category_id=cat["id"], video_id="seenit00000", status="accepted", score=80, summary="x"))
        s.add(Candidate(category_id=cat["id"], video_id="other000000", status="accepted", score=70, summary="y"))
        s.commit()

    # invalid id → 404
    assert c.post("/api/history/seen", json={"video_id": "../nope"}, headers=h).status_code == 404
    r = c.post("/api/history/seen", json={"video_id": "seenit00000"}, headers=h).json()
    assert r["ok"] and r["dismissed"] == 1
    # gone from the feed, other profile's videos untouched
    feed = c.get(f"/api/feed/category/{cat['id']}", headers=h).json()
    assert [x["video"]["id"] for x in feed] == ["other000000"]
    # candidate dismissed → downloader / queue counts exclude it
    with session() as s:
        rows = {cand.video_id: cand for cand in s.exec(select(Candidate)).all()}
        assert rows["seenit00000"].dismissed and not rows["other000000"].dismissed
        cat_obj = s.get(Category, cat["id"])
        ctx = data.profile_ctx(s, profiles[0]["id"])
        assert data.prefilter({"id": "seenit00000", "duration_s": 600, "title": "Seen"}, cat_obj, ctx, False) == "already watched"
        assert data.prefilter({"id": "other000000", "duration_s": 600, "title": "Other"}, cat_obj, ctx, False) is None


def test_feedback_dislike_rejects_candidate():
    c = client()
    profiles = c.get("/api/profiles").json()
    h = {"X-Profile-Id": str(profiles[0]["id"])}
    cat = c.post("/api/categories", json={"name": "LLM stuff", "brief": "local LLM howtos"}, headers=h).json()
    with session() as s:
        s.add(Video(id="ollama00000", title="Ollama setup for total beginners", channel_id="UC1", duration_s=600))
        s.add(Candidate(category_id=cat["id"], video_id="ollama00000", status="accepted", score=80,
                        summary="gentle intro"))
        s.commit()

    r = c.post("/api/feedback", json={"video_id": "ollama00000", "category_id": cat["id"], "rating": -1,
                                      "chips": ["Boring", "Too basic"],
                                      "text": "want more advanced videos"}, headers=h).json()
    assert r["rating"] == -1
    with session() as s:
        cand = s.exec(select(Candidate).where(Candidate.video_id == "ollama00000")).first()
        assert cand.status == "rejected" and cand.dismissed and cand.judged_at is not None
        assert cand.red_flags[-1] == "Family: Boring, Too basic, want more advanced videos"
    # the verdict log shows the family's rejection, clickable like any verdict
    evs = c.get("/api/agent/events").json()
    assert any(e["kind"] == "reject" and "You rejected" in e["message"]
               and e["payload"].get("candidate_id") == cand.id for e in evs)
    # candidate detail exposes the family reason to the drawer
    d = c.get(f"/api/agent/candidates/{cand.id}").json()
    assert d["status"] == "rejected" and any("Family:" in f for f in d["red_flags"])


def test_stats_page():
    c = client()
    profiles = c.get("/api/profiles").json()
    h = {"X-Profile-Id": str(profiles[0]["id"])}
    cat = c.post("/api/categories", json={"name": "Stats cat", "brief": "b"}, headers=h).json()
    with session() as s:
        s.add(Video(id="statsvid001", title="S1", channel_id="UC1", duration_s=600))
        s.add(Video(id="statsvid002", title="S2", channel_id="UC1", duration_s=600))
        s.add(Video(id="statsvid003", title="S3", channel_id="UC1", duration_s=600))
        s.add(Candidate(category_id=cat["id"], video_id="statsvid001", status="accepted", score=80, judged_at=now()))
        s.add(Candidate(category_id=cat["id"], video_id="statsvid002", status="rejected", score=20,
                        summary="shallow", judged_at=now()))
        s.add(Candidate(category_id=cat["id"], video_id="statsvid003", status="accepted", score=70, judged_at=now()))
        s.add(WatchHistory(profile_id=profiles[0]["id"], video_id="statsvid001", category_id=cat["id"],
                           finished=True, duration_s=600))
        s.commit()
    # the family dislikes the accepted one → its rejection is "family", not the AI's
    c.post("/api/feedback", json={"video_id": "statsvid001", "category_id": cat["id"], "rating": -1,
                                  "chips": ["Boring"]}, headers=h)

    r = c.get("/api/stats/page?days=7", headers=h).json()
    row = next(x for x in r["categories"] if x["id"] == cat["id"])
    assert row["counts"]["rejected_family"] == 1  # statsvid001, flipped by the feedback above
    assert row["counts"]["rejected_ai"] == 1      # statsvid002, by the judge
    assert row["counts"]["watched"] == 1 and row["watch_seconds"] == 600
    assert row["avg_score"] == 70.0  # over accepted candidates (statsvid001 is now rejected)
    assert row["counts"]["accepted"] == 1 and row["counts"]["in_queue"] == 1  # statsvid003

    ov = r["overview"]
    assert ov["videos"] >= 2 and ov["candidates"]["rejected_family"] >= 1 and ov["watched"] >= 1
    assert ov["feedback"]["dislike"] >= 1 and "waiting" in ov["downloads"] and "max_day" in ov["budget"]

    today = r["daily"][-1]
    assert today["watched"] >= 1 and today["feedback"] >= 1
    assert today["rejected_family"] >= 1 and today["rejected_ai"] >= 1
    assert today["watched_by_category"].get(str(cat["id"])) == 1
    assert len(r["daily"]) == 7 and r["daily"][0]["date"] < r["daily"][-1]["date"]


def test_block_channel_dismisses():
    c = client()
    profiles = c.get("/api/profiles").json()
    h = {"X-Profile-Id": str(profiles[0]["id"])}
    cat = c.post("/api/categories", json={"name": "S", "brief": "b"}, headers=h).json()
    with session() as s:
        s.add(Video(id="badchan0001", title="Bad 1", channel_id="UCbad", duration_s=600))
        s.add(Video(id="badchan0002", title="Bad 2", channel_id="UCbad", duration_s=600))
        s.add(Video(id="goodvid0000", title="Good", channel_id="UCgood", duration_s=600))
        s.add(Candidate(category_id=cat["id"], video_id="badchan0001", status="accepted", score=80, summary="x"))
        s.add(Candidate(category_id=cat["id"], video_id="badchan0002", status="found"))
        s.add(Candidate(category_id=cat["id"], video_id="goodvid0000", status="accepted", score=70, summary="y"))
        s.commit()

    r = c.post("/api/channels/UCbad/block", headers=h).json()
    assert r["blocked"] is True and r["dismissed"] == 2
    feed = c.get(f"/api/feed/category/{cat['id']}", headers=h).json()
    assert [x["video"]["id"] for x in feed] == ["goodvid0000"]
    # prefilter rejects the channel for future discoveries
    from bt.agent import data as d
    with session() as s:
        cat_obj = s.get(Category, cat["id"])
        ctx = d.profile_ctx(s, profiles[0]["id"])
        assert d.prefilter({"id": "newvid000001", "duration_s": 600, "title": "New",
                            "channel_id": "UCbad"}, cat_obj, ctx, False) == "blocked/distrusted channel"
        assert d.prefilter({"id": "newvid000002", "duration_s": 600, "title": "New2",
                            "channel_id": "UCgood"}, cat_obj, ctx, False) is None


def test_settings_and_agent():
    c = client()
    st = c.get("/api/settings").json()
    assert st["throttle"]["max_per_hour"] == 120
    c.put("/api/settings/llm", json={"api_key": "secret"})
    assert c.get("/api/settings").json()["llm"]["api_key"] == "********"
    c.put("/api/settings/llm", json={"api_key": "********", "model": "x"})
    from bt.db import get_settings
    assert get_settings()["llm"]["api_key"] == "secret"

    assert c.post("/api/agent/pause").json()["paused"] is True
    assert c.get("/api/agent/status").json()["control"]["paused"] is True
    assert c.post("/api/agent/resume").json()["paused"] is False
    emit("search", "hello")
    assert c.get("/api/agent/events").json()[-1]["message"] == "hello"
