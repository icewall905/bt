"""Counterexamples and race checks for evidence-weighted rule revision."""
import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, select

from bt.agent import knowledge, memory, learn
from bt.db import engine, init_db, session
from bt.main import app
from bt.models import Feedback, Lesson, LessonEvidenceState, LessonRevision, MemoryCore, Profile, Video


@pytest.fixture(autouse=True)
def fresh():
    SQLModel.metadata.drop_all(engine)
    init_db()


def seed(support=1, explicit=False, subject="ferrets"):
    with session() as s:
        pid = s.exec(select(Profile)).first().id
        ids = []
        for i in range(support):
            v = Video(id=f"support{i}", title=f"{subject} video {i}")
            fb = Feedback(profile_id=pid, video_id=v.id, rating=-1, text="Boring")
            s.add(v); s.add(fb); s.flush(); ids.append(fb.id)
        le = Lesson(profile_id=pid, text=f"Avoid {subject} videos", source_feedback_ids=ids)
        s.add(le); s.flush()
        if explicit:
            knowledge.register(s, le, explicit=True)
        s.commit()
        return le


def feedback(le, video="opposing1", *, pid=None):
    with session() as s:
        if not s.get(Video, video):
            s.add(Video(id=video, title="Engaging ferret documentary"))
        f = Feedback(profile_id=pid or le.profile_id, video_id=video, rating=2, text="Engaging and fun")
        s.add(f); s.commit()
        return f.id


def runtime(stances=None, approve=True, explicit=False, hook=None):
    calls = []
    def chat(messages, **kw):
        name = kw["schema_name"]
        calls.append(name)
        body = json.loads(messages[-1]["content"])
        if hook:
            hook(name)
        if name == "lesson_evidence":
            return {"explicit_instruction": explicit, "assessments": [
                {"feedback_id": item["feedback_id"],
                 "stance": (stances or {}).get(item["feedback_id"], "support" if item["rating"] == -1 else "contradict"),
                 "reason": "Specifically relevant to the topic preference"}
                for item in body["feedback"]]}
        if name == "lesson_revision":
            return {"text": "Do not assume a general dislike of ferrets; one earlier video was boring for an unspecified reason.",
                    "reason": "Independent positive examples correct the topic generalization"}
        if name == "lesson_revision_audit":
            return {"ok": approve, "reason": "Two independent liked ferret videos disprove a categorical dislike; original dislike remains specific."}
        raise AssertionError(name)
    return SimpleNamespace(llm=SimpleNamespace(chat_json=chat), check=lambda: None,
                           event=lambda *a, **k: None), calls


def proposal(le, *ids):
    return {"lesson_id": le.id, "text": "Do not assume a general dislike of ferrets; one earlier video was boring for an unspecified reason.",
            "feedback_ids": list(ids)}


def test_weak_ferret_inference_changes_after_two_independent_positive_videos():
    le = seed()
    with session() as s:
        s.add(MemoryCore(profile_id=le.profile_id, text="Ferrets are boring",
                         sources={str(le.id): memory.fingerprint(le)})); s.commit()
    f1 = feedback(le)
    rt, calls = runtime()
    assert knowledge.review(rt, le.profile_id, proposal(le, f1), {f1}) is None
    assert calls == ["lesson_evidence"]
    f2 = feedback(le, "opposing2")
    report = knowledge.review(rt, le.profile_id, proposal(le, f2), {f2})
    assert report and report["lesson_id"] == le.id
    with session() as s:
        revised = s.get(Lesson, le.id)
        assert revised.category_id == le.category_id and revised.channel_id == le.channel_id
        assert "unspecified" in revised.text
        original = s.exec(select(LessonRevision)).one()
        assert original.before == le.text and original.evidence["opposing_videos"] == 2
        assert len(original.evidence["feedback"]) == 3
        assert memory.select_memory(s, le.profile_id, [revised])[0] == ""


def test_strong_lion_pattern_survives_one_or_two_exceptions():
    le = seed(support=5, subject="people keeping lions as pets")
    rt, calls = runtime()
    f1, f2 = feedback(le), feedback(le, "opposing2")
    assert knowledge.review(rt, le.profile_id, proposal(le, f1, f2), {f1, f2}) is None
    assert calls == ["lesson_evidence"]
    with session() as s:
        assert s.get(Lesson, le.id).text == le.text
        assert knowledge.describe(s, le) == {"kind": "supported pattern", "support": 5, "opposition": 2}


def test_incidental_lion_like_is_irrelevant_not_a_contradiction():
    le = seed(support=1, subject="people keeping lions as pets")
    ids = [feedback(le, f"incidental{i}") for i in range(4)]
    rt, calls = runtime(stances={i: "irrelevant" for i in ids})
    assert knowledge.review(rt, le.profile_id, proposal(le, *ids), set(ids)) is None
    with session() as s:
        assert knowledge.describe(s, le)["opposition"] == 0
    assert "lesson_revision_audit" not in calls


def test_duplicate_video_feedback_is_only_one_example():
    le = seed()
    ids = [feedback(le, "same-video") for _ in range(4)]
    rt, calls = runtime()
    assert knowledge.review(rt, le.profile_id, proposal(le, *ids), set(ids)) is None
    assert "lesson_revision_audit" not in calls
    with session() as s:
        assert knowledge.describe(s, le)["opposition"] == 1


def test_mixed_legacy_batch_is_reassessed_and_unrelated_items_do_not_count():
    le = seed(support=5)
    ids = [feedback(le, "opposing1"), feedback(le, "opposing2")]
    rt, calls = runtime(stances={fid: "irrelevant" for fid in le.source_feedback_ids[1:]})
    assert knowledge.review(rt, le.profile_id, proposal(le, *ids), set(ids))
    assert "lesson_revision_audit" in calls


def test_explicit_or_user_edited_rule_is_never_automatically_revised():
    le = seed(explicit=True)
    ids = [feedback(le, f"opposing{i}") for i in range(6)]
    rt, calls = runtime()
    assert knowledge.review(rt, le.profile_id, proposal(le, *ids), set(ids)) is None
    assert calls == []
    with TestClient(app) as client:
        client.patch(f"/api/lessons/{le.id}", json={"text": "Never suggest pet lions"})
    with session() as s:
        assert knowledge.describe(s, s.get(Lesson, le.id))["kind"] == "explicit"


def test_direct_instruction_in_original_feedback_is_protected():
    le = seed()
    ids = [feedback(le, "opposing1"), feedback(le, "opposing2")]
    rt, calls = runtime(explicit=True)
    assert knowledge.review(rt, le.profile_id, proposal(le, *ids), set(ids)) is None
    assert "lesson_revision_audit" not in calls
    with session() as s:
        assert s.get(LessonEvidenceState, le.id).protected


def test_rejected_semantic_audit_keeps_original_rule():
    le = seed()
    ids = [feedback(le, "opposing1"), feedback(le, "opposing2")]
    rt, calls = runtime(approve=False)
    assert knowledge.review(rt, le.profile_id, proposal(le, *ids), set(ids)) is None
    assert "lesson_revision_audit" in calls
    with session() as s:
        assert s.get(Lesson, le.id).text == le.text
        assert s.exec(select(LessonRevision)).all() == []


def test_user_edit_during_model_review_wins():
    le = seed()
    ids = [feedback(le, "opposing1"), feedback(le, "opposing2")]
    def edit(name):
        if name == "lesson_revision":
            return {"text": "Do not assume a general dislike of ferrets; one earlier video was boring for an unspecified reason.",
                    "reason": "Independent positive examples correct the topic generalization"}
        if name == "lesson_revision_audit":
            with session() as s:
                row = s.get(Lesson, le.id)
                row.text = "Explicitly keep my rule"
                knowledge.register(s, row, explicit=True)
                s.add(row); s.commit()
    rt, _ = runtime(hook=edit)
    assert knowledge.review(rt, le.profile_id, proposal(le, *ids), set(ids)) is None
    with session() as s:
        assert s.get(Lesson, le.id).text == "Explicitly keep my rule"


def test_deleted_feedback_does_not_keep_counting_as_evidence():
    le = seed()
    f1 = feedback(le)
    rt, _ = runtime()
    knowledge.review(rt, le.profile_id, proposal(le, f1), {f1})
    with session() as s:
        s.delete(s.get(Feedback, f1)); s.commit()
        assert knowledge.describe(s, le)["opposition"] == 0
    f2 = feedback(le, "opposing2")
    assert knowledge.review(rt, le.profile_id, proposal(le, f2), {f2}) is None


def test_forged_feedback_and_cross_profile_references_are_rejected():
    le = seed()
    rt, calls = runtime()
    assert knowledge.review(rt, le.profile_id, proposal(le, 99999), {99999}) is None
    assert knowledge.review(rt, le.profile_id, proposal(le, 99999), set()) is None
    with session() as s:
        p = Profile(name="Other"); s.add(p); s.commit()
        other = p.id
    fid = feedback(le, pid=other)
    assert knowledge.review(rt, le.profile_id, proposal(le, fid), {fid}) is None
    assert knowledge.review(rt, other, proposal(le, fid), {fid}) is None
    assert calls == []


def test_new_lesson_cites_only_relevant_feedback_not_the_whole_batch():
    with session() as s:
        pid = s.exec(select(Profile)).first().id
        relevant = Feedback(profile_id=pid, video_id="ferret", rating=-1, text="Boring")
        unrelated = Feedback(profile_id=pid, video_id="science", rating=2)
        s.add(relevant); s.add(unrelated); s.commit()
    out = {"lessons": [{"text": "One ferret video was boring; reason unspecified", "category_id": None,
                        "channel_id": None, "replaces_lesson_id": None,
                        "source_feedback_ids": [relevant.id]}], "reviews": []}
    rt = SimpleNamespace(llm=SimpleNamespace(chat_json=lambda *a, **k: out), check=lambda: None,
                         state=lambda *a, **k: None, event=lambda *a, **k: None,
                         llm_ok=lambda: True)
    assert learn._process_profile(rt, pid, [relevant, unrelated]) == 2
    with session() as s:
        rule = s.exec(select(Lesson)).one()
        assert rule.source_feedback_ids == [relevant.id]
        assert knowledge.describe(s, rule)["kind"] == "unreviewed inference"


def test_inference_repeated_in_another_playlist_does_not_change_scope():
    from bt.models import Category
    le = seed()
    with session() as s:
        c = Category(profile_id=le.profile_id, name="Other")
        s.add(c); s.flush()
        row = s.get(Lesson, le.id)
        row.category_id = c.id
        s.add(row); s.commit()
        le = row
    ids = [feedback(le, f"opposing{i}") for i in range(3)]  # No playlist: outside the rule's scope.
    rt, calls = runtime()
    assert knowledge.review(rt, le.profile_id, proposal(le, *ids), set(ids)) is None
    assert "lesson_revision_audit" not in calls
    with session() as s:
        assert knowledge.describe(s, le)["opposition"] == 0


def test_review_cannot_omit_or_duplicate_feedback_evidence():
    le = seed()
    fid = feedback(le)
    rt, _ = runtime()
    rt.llm.chat_json = lambda *a, **k: {"explicit_instruction": False, "assessments": []}
    with pytest.raises(ValueError, match="omitted"):
        knowledge.review(rt, le.profile_id, proposal(le, fid), {fid})
    with session() as s:
        assert s.get(Lesson, le.id).text == le.text
        assert s.get(LessonEvidenceState, le.id) is None


def test_confidence_only_changes_keep_core_usable_but_rebuild_next_run():
    le = seed()
    with session() as s:
        knowledge.register(s, s.get(Lesson, le.id)); s.commit()
    rt = SimpleNamespace(check=lambda: None, state=lambda *a, **k: None,
                         llm=SimpleNamespace(chat_json=lambda *a, **k: {"ok": True, "issues": []}))
    memory.compact_profile(rt, le.profile_id, 12000)
    with session() as s:
        old = memory.latest(s, le.profile_id)
        old_id = old.id
        assert "unreviewed inference" in old.text
    fid = feedback(le)
    review_rt, _ = runtime()
    knowledge.review(review_rt, le.profile_id, proposal(le, fid), {fid})
    with session() as s:
        assert memory.select_memory(s, le.profile_id, [s.get(Lesson, le.id)])[0] == old.text
    assert memory.compact_profile(rt, le.profile_id, 12000)["status"] == "compacted"
    with session() as s:
        assert memory.latest(s, le.profile_id).id != old_id
        assert "1 supporting, 1 opposing" in memory.latest(s, le.profile_id).text


def test_review_preserves_new_support_arriving_during_model_call():
    le = seed()
    ids = [feedback(le, "opposing1"), feedback(le, "opposing2")]
    def reinforce(name):
        if name == "lesson_revision_audit":
            with session() as s:
                fb = Feedback(profile_id=le.profile_id, video_id="new-support", rating=-1, text="Boring again")
                s.add(fb); s.flush()
                row = s.get(Lesson, le.id)
                row.source_feedback_ids = [*row.source_feedback_ids, fb.id]
                s.add(row); s.commit()
    rt, _ = runtime(hook=reinforce)
    with pytest.raises(ValueError, match="evidence changed"):
        knowledge.review(rt, le.profile_id, proposal(le, *ids), set(ids))
    with session() as s:
        assert s.get(Lesson, le.id).text == le.text
        assert len(s.get(Lesson, le.id).source_feedback_ids) == 2
