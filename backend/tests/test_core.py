import os
import tempfile

os.environ.setdefault("BT_DATA_DIR", tempfile.mkdtemp(prefix="bt-test-"))

from fastapi.testclient import TestClient  # noqa: E402

from bt.db import emit, session  # noqa: E402
from bt.main import app  # noqa: E402
from bt.models import Candidate, Video  # noqa: E402


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
