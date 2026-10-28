"""Optional semantic check with the configured LLM and an isolated test database.

Run with BT_MEMORY_LIVE=1 BT_DATA_DIR=$(mktemp -d) .venv/bin/python -m pytest ...
Never runs during the offline suite or writes to the production database.
"""
import os
import json
from types import SimpleNamespace

import pytest
from sqlmodel import SQLModel, select

from bt import llm
from bt.agent import knowledge, learn, memory
from bt.db import engine, get_settings, init_db, save_setting, session
from bt.models import Feedback, Lesson, LessonRevision, MemoryCore, Profile, Video

pytestmark = pytest.mark.skipif(os.environ.get("BT_MEMORY_LIVE") != "1", reason="optional real-LLM semantic check")


@pytest.mark.parametrize("old_comment", ["Boring", "The loud background music was unpleasant"], ids=["unspecified", "loud-music"])
def test_real_learner_corrects_ferret_inference_but_preserves_lion_pattern(old_comment):
    SQLModel.metadata.drop_all(engine)
    init_db()
    save_setting("llm", {"thinking": False})
    events = []
    def chat(*args, **kwargs):
        out = llm.chat_json(*args, **kwargs)
        print(kwargs.get("schema_name"), json.dumps(out))
        return out
    rt = SimpleNamespace(llm=SimpleNamespace(chat_json=chat), check=lambda: None, state=lambda *a, **k: None,
                         event=lambda *a, **k: events.append(a), llm_ok=lambda: True,
                         llm_failed=lambda *a, **k: pytest.fail(str(a)))
    with session() as s:
        pid = s.exec(select(Profile)).first().id
        s.add(Video(id="ferret-old", title="An hour of a ferret sleeping"))
        original = Feedback(profile_id=pid, video_id="ferret-old", rating=-1, text=old_comment)
        s.add(original); s.flush()
        ferret = Lesson(profile_id=pid, text="Ferrets are boring; avoid ferret videos.", source_feedback_ids=[original.id])
        s.add(ferret); s.flush()
        ids = []
        for i in range(5):
            s.add(Video(id=f"lion-old-{i}", title="A person keeping a lion as a pet in their home"))
            fb = Feedback(profile_id=pid, video_id=f"lion-old-{i}", rating=-1,
                          text="Disliked the keeping of a lion as a domestic pet. It is irresponsible and dangerous.")
            s.add(fb); s.flush(); ids.append(fb.id)
        lion = Lesson(profile_id=pid, text="Avoid videos normalizing people keeping lions as pets.", source_feedback_ids=ids)
        s.add(lion); s.flush()
        s.add(MemoryCore(profile_id=pid, sources={str(ferret.id): memory.fingerprint(ferret), str(lion.id): memory.fingerprint(lion)},
                         text=f"All playlists\n- {ferret.text} [sources {ferret.id}]\n- {lion.text} [sources {lion.id}]"))
        s.commit()
        ferret_id, lion_id, original_lion_text = ferret.id, lion.id, lion.text
    for i in range(2):
        with session() as s:
            s.add(Video(id=f"ferret-good-{i}", title=f"An engaging documentary about wild ferret behavior, part {i}",
                        description="Ferrets are the central subject. Explains their behavior using entertaining real footage."))
            fb = Feedback(profile_id=pid, video_id=f"ferret-good-{i}", rating=2, text="We loved this ferret video! Interesting and engaging.")
            s.add(fb); s.commit()
        assert learn._process_profile(rt, pid, [fb]) == 1
        with session() as s:
            row = s.get(Lesson, ferret_id)
            if i == 0:
                assert row.text == "Ferrets are boring; avoid ferret videos."
            else:
                assert row.text != "Ferrets are boring; avoid ferret videos."
                if old_comment == "Boring":
                    assert "unspecified" in row.text
                    assert "passive" not in row.text and "sleeping" not in row.text
                assert s.exec(select(LessonRevision).where(LessonRevision.lesson_id == ferret_id)).first()
    with session() as s:
        s.add(Video(id="lion-doc", title="An excellent documentary about wildlife rescue",
                    description="An informative rescue documentary. Briefly includes a man with a lion he keeps as a pet."))
        fb = Feedback(profile_id=pid, video_id="lion-doc", rating=1, text="Great documentary overall")
        s.add(fb); s.commit()
    assert learn._process_profile(rt, pid, [fb]) == 1
    with session() as s:
        assert s.get(Lesson, lion_id).text == original_lion_text
