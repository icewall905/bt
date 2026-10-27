"""Drill-down counts must describe the same records as the overview and charts."""
from fastapi.testclient import TestClient
from sqlmodel import select

from bt.db import session
from bt.main import app
from bt.models import Candidate, Category, Download, Feedback, Profile, Video, WatchHistory, now


def test_explore_matches_counts_and_preserves_profile_category_context():
    with TestClient(app) as client:
        with session() as s:
            a, b = Profile(name="Explore A"), Profile(name="Explore B")
            s.add(a); s.add(b); s.commit()
            ca, cb = Category(profile_id=a.id, name="Explore science"), Category(profile_id=b.id, name="Explore art")
            s.add(ca); s.add(cb); s.commit()
            ids = [f"drillvid{i:03}" for i in range(7)]
            for i, vid in enumerate(ids):
                s.add(Video(id=vid, title=f"Drill video {i}", duration_s=600, channel_id="UCdrill"))
            for i, status in enumerate(["accepted", "accepted", "rejected", "rejected", "rejected", "found", "accepted"]):
                s.add(Candidate(category_id=ca.id, video_id=ids[i], status=status, dismissed=i in (4, 6),
                                summary=f"Reason {i}", judged_at=now() if status != "found" else None))
            s.add(Candidate(category_id=cb.id, video_id=ids[0], status="accepted", judged_at=now()))
            s.add(Feedback(profile_id=a.id, category_id=ca.id, video_id=ids[3], rating=-1))
            # Disliking a video in another category must not relabel the judge's rejection here.
            s.add(Feedback(profile_id=b.id, category_id=cb.id, video_id=ids[2], rating=-1))
            s.add(WatchHistory(profile_id=a.id, category_id=ca.id, video_id=ids[1], finished=True, duration_s=600))
            s.add(WatchHistory(profile_id=b.id, category_id=cb.id, video_id=ids[0], finished=True, duration_s=600))
            s.commit()
            aid, bid, caid, cbid = a.id, b.id, ca.id, cb.id

        def explore(metric, **params):
            response = client.get("/api/stats/explore", params={"metric": metric, **params})
            assert response.status_code == 200, response.text
            return response.json()

        stats = client.get("/api/stats/page?days=7").json()
        ov = stats["overview"]
        for metric, expected in {
            "videos": ov["videos"], "ready": ov["candidates"]["in_queue"],
            "review": ov["candidates"]["waiting_judge"], "rejected_ai": ov["candidates"]["rejected_ai"],
            "rejected_family": ov["candidates"]["rejected_family"], "dismissed": ov["candidates"]["dismissed"],
            "offline": ov["downloads"].get("done", 0), "waiting_download": ov["downloads"]["waiting"],
            "watched": ov["watched"], "feedback": sum(ov["feedback"].values()), "lessons": ov["lessons"]["active"],
        }.items():
            assert explore(metric)["total"] == expected, metric
        for cat in (c for c in stats["categories"] if c["id"] in (caid, cbid)):
            for metric, key in [("ready", "in_queue"), ("watched", "watched"), ("rejected_ai", "rejected_ai"),
                                ("rejected_family", "rejected_family"), ("dismissed", "dismissed")]:
                assert explore(metric, category_id=cat["id"])["total"] == cat["counts"][key]
        assert explore("scored", category_id=caid)["total"] == 3
        for metric, key in [("encode_queue", "queued"), ("encoded_copies", "encoded_copies"),
                            ("encode_kept", "kept_not_smaller"), ("encode_errors", "job_errors"),
                            ("encode_saved", "recorded_saved"), ("encode_not_smaller", "recorded_not_smaller"),
                            ("encode_failed", "recorded_failed")]:
            assert explore(metric)["total"] == stats["reencode"][key]
        ready = explore("ready", category_id=caid)
        assert [r["video_id"] for r in ready["items"]] == [ids[0]]
        assert ready["items"][0]["profile_id"] == aid
        assert explore("ready", category_id=cbid)["items"] == []
        rejected = explore("rejected_ai", category_id=caid)
        assert {r["video_id"] for r in rejected["items"]} == {ids[2], ids[4]}
        assert all(r["candidate_id"] and r["detail"].startswith("Reason") for r in rejected["items"])
        assert explore("decision_rejected_ai", category_id=caid)["total"] == 1
        first = explore("rejected_ai", category_id=caid, limit=1)
        second = explore("rejected_ai", category_id=caid, limit=1, offset=1)
        assert first["total"] == second["total"] == 2
        assert first["items"][0]["key"] != second["items"][0]["key"]
        today = stats["daily"][-1]
        for metric, key in [("watched", "watched"), ("found", "found"), ("accepted", "accepted"),
                            ("rejected_ai", "rejected_ai"), ("feedback", "feedback"), ("downloads", "downloads")]:
            assert explore(metric, day=today["date"])["total"] == today[key], metric
        assert client.get("/api/stats/explore?metric=unknown").status_code == 400
        assert client.get("/api/stats/explore?metric=videos&offset=-1").status_code == 422
        assert client.get("/api/stats/explore?metric=offline&day=bad-date").status_code == 422
        assert client.get("/api/stats/explore?metric=videos&category_id=99999999").status_code == 404


def test_offline_runtime_and_quality_exclude_evicted_and_queued_files():
    with TestClient(app) as client:
        before = client.get("/api/stats/page").json()["library"]
        with session() as s:
            for i, duration in enumerate([3600, 0, 9999, 8888]):
                vid = f"runtime{i:04}"
                s.add(Video(id=vid, title=f"Runtime {i}", duration_s=duration, channel_id="UCruntime", channel_name="Runtime channel"))
                s.add(Download(video_id=vid, status=["done", "done", "evicted", "queued"][i],
                               height=1234, size_bytes=100))
            s.commit()
        stats = client.get("/api/stats/page").json()
        library = stats["library"]
        assert library["duration_s"] == before["duration_s"] + 3600
        assert library["duration_known"] == before["duration_known"] + 1
        assert library["duration_unknown"] == before["duration_unknown"] + 1
        assert sum(q["count"] for q in library["quality"]) == stats["overview"]["downloads"]["done"]
        assert next(q["count"] for q in library["quality"] if q["label"] == "1234p") == 2
        detail = client.get("/api/stats/explore?metric=offline&height=1234").json()
        assert detail["total"] == 2 and all(i["offline"] for i in detail["items"])
        channels = client.get("/api/stats/explore?metric=offline_channels").json()
        assert channels["total"] == library["channels"]
        assert next(c for c in channels["items"] if c["channel_id"] == "UCruntime")["detail"] == "2 saved videos · 1.0 hours offline"
