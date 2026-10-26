from bt.models import Candidate, Video
from bt.playlist import order_playlist


def row(id, topic="", score=85, channel="", source="", duration=600, title=""):
    return (Candidate(video_id=id, category_id=1, score=score, tags=[topic] if topic else [], source=source),
            Video(id=id, title=title, channel_id=channel, duration_s=duration))


def ids(rows):
    return [v.id for _, v in rows]


def test_spaces_topics_even_when_the_quality_sort_clusters_them():
    rows = [row("a1", "space", 92), row("a2", "space", 91), row("a3", "space", 90),
            row("b1", "music", 89), row("b2", "music", 88), row("c1", "animals", 87)]
    mixed = order_playlist(rows)
    assert ids(mixed)[:3] == ["a1", "b1", "c1"]
    assert all(a.tags[0] != b.tags[0] for (a, _), (b, _) in zip(mixed, mixed[1:]))
    assert sorted(ids(mixed)) == sorted(ids(rows))
    assert ids(order_playlist(rows)) == ids(mixed)  # stable across requests


def test_creator_spacing_quality_floor_and_legacy_fallbacks():
    assert ids(order_playlist([row("a", channel="one", score=90),
                               row("b", channel="one", score=89),
                               row("c", channel="two", score=85)])) == ["a", "c", "b"]
    assert ids(order_playlist([row("a", "space", 99), row("b", "space", 98),
                               row("c", "music", 65)])) == ["a", "b", "c"]
    for fallback in [{"source": "search: space builds"}, {"title": "Building a giant marble run"}]:
        assert ids(order_playlist([row("a", score=90, **fallback), row("b", score=89, **fallback),
                                   row("c", score=85)])) == ["a", "c", "b"]


def test_autoplay_uses_current_video_and_duration_is_a_soft_nudge():
    current = row("current", "space")
    assert ids(order_playlist([row("a", "space", 90), row("b", "music", 85)], [current])) == ["b", "a"]
    assert ids(order_playlist([row("a", duration=1800, score=90), row("b", duration=1800, score=89),
                               row("c", duration=300, score=88)])) == ["a", "c", "b"]


def test_empty_single_topic_unknown_metadata_and_generic_tags_are_safe():
    assert order_playlist([]) == []
    rows = [row("a", "space", 90), row("b", "space", 89), row("c", "space", 88)]
    assert ids(order_playlist(rows)) == ["a", "b", "c"]
    unknown = [row("a", "fun", 90), row("b", "educational", 89), row("c", "fun", 88)]
    assert ids(order_playlist(unknown)) == ["a", "b", "c"]


def test_known_runtime_buckets_mix_gently_and_unknown_duration_is_neutral():
    rows = [row("short1", duration=120), row("short2", duration=180), row("short3", duration=240),
            row("medium", duration=600), row("long", duration=1800)]
    assert ids(order_playlist(rows))[:3] == ["short1", "medium", "long"]
    # Pacing cannot displace a meaningfully stronger pick, and missing metadata is not a bucket.
    assert ids(order_playlist([row("a", duration=0, score=90), row("b", duration=0, score=89),
                               row("c", duration=120, score=88)])) == ["a", "b", "c"]
    assert ids(order_playlist([row("a", duration=120, score=95), row("b", duration=180, score=94),
                               row("c", duration=600, score=85)])) == ["a", "b", "c"]
