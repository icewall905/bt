"""Imports seed refillable playlists directly, without a judge backlog."""
import pytest
from fastapi import HTTPException
from sqlmodel import Session, SQLModel, create_engine, select

from bt.api import ytimport
from bt.agent import data
from bt.models import Candidate, Category, Profile, WatchHistory


@pytest.fixture
def imported(monkeypatch):
    engine = create_engine('sqlite://')
    SQLModel.metadata.create_all(engine)
    entries = [dict(id=f'video{i:06d}', title=f'Science {i}', channel_name='Lab',
                    duration_s=600) for i in range(30)]
    monkeypatch.setattr(ytimport, '_require_cookies', lambda: None)
    monkeypatch.setattr(ytimport, '_flat_entries', lambda *args: entries)
    monkeypatch.setattr(ytimport.ytdl, '_entry', lambda e: e)
    with Session(engine) as s:
        profile = Profile(name='Import test')
        s.add(profile)
        s.commit()
        yield s, profile.id, entries


def test_new_playlist_uses_every_video_and_refills_seen_spots(imported, monkeypatch):
    s, pid, entries = imported
    calls = []

    def generate(messages, **kwargs):
        calls.append(messages)
        return {'brief': 'Curious lab science demonstrations.', 'seed_queries': ['science experiments']}

    monkeypatch.setattr(ytimport.llm, 'chat_json', generate)
    result = ytimport.import_feed(ytimport.FeedImportBody(
        playlist_name='Science playlist', source='liked'), pid, s)
    assert result['added'] == 30  # Not limited by the 12-video judge inbox.
    assert len(calls) == 1
    assert all(e['title'] in calls[0][1]['content'] for e in entries)
    cat = s.get(Category, result['category_id'])
    assert cat.brief == result['brief']
    assert cat.seed_queries == ['science experiments']
    assert cat.target_queue == 30
    rows = s.exec(select(Candidate).where(Candidate.category_id == cat.id)).all()
    assert all(c.status == 'accepted' for c in rows)
    assert data.accepted_unwatched(s, cat) == 30
    s.add(WatchHistory(profile_id=pid, video_id=entries[0]['id'], finished=True))
    s.commit()
    assert cat.target_queue - data.accepted_unwatched(s, cat) == 1


def test_generation_failure_does_not_leave_playlist(imported, monkeypatch):
    s, pid, _ = imported
    monkeypatch.setattr(ytimport.llm, 'chat_json', lambda *a, **kw: {'brief': '', 'seed_queries': []})
    with pytest.raises(HTTPException) as exc:
        ytimport.import_feed(ytimport.FeedImportBody(playlist_name='Fail', source='liked'), pid, s)
    assert exc.value.status_code == 502
    assert s.exec(select(Category)).all() == []


def test_existing_playlist_import_is_direct_and_deduplicated(imported, monkeypatch):
    s, pid, entries = imported
    cat = Category(profile_id=pid, name='Existing', brief='Keep this prompt')
    s.add(cat)
    s.commit()
    def unexpected(*a, **kw):
        raise AssertionError('Existing playlists do not need a generated prompt')
    monkeypatch.setattr(ytimport.llm, 'chat_json', unexpected)
    body = ytimport.FeedImportBody(category_id=cat.id, source='liked')
    assert ytimport.import_feed(body, pid, s)['added'] == 30
    result = ytimport.import_feed(body, pid, s)
    assert result['added'] == 0
    assert result['skipped'] == len(entries)
    assert cat.brief == 'Keep this prompt'
    other = Profile(name='Other')
    s.add(other)
    s.commit()
    with pytest.raises(HTTPException) as exc:
        ytimport.import_feed(body, other.id, s)
    assert exc.value.status_code == 404


def test_category_creation_from_playlist_preserves_preferences(imported, monkeypatch):
    from bt.api.core import CategoryCreateIn, create_category
    s, pid, entries = imported
    monkeypatch.setattr(ytimport.llm, 'chat_json', lambda *a, **kw: {
        'brief': 'Science demonstrations from the imported playlist.', 'seed_queries': ['lab science']})
    # Public playlist extraction does not require an installed cookie file.
    monkeypatch.setattr(ytimport, '_require_cookies', lambda: pytest.fail('public playlists need no cookies'))
    cat = create_category(CategoryCreateIn(
        name='My science', playlist_url='https://www.youtube.com/playlist?list=PLtest',
        emoji='🔬', brief='Avoid shouting.', color='#123456', target_queue=40,
        seed_queries=['physics experiments'], kid_safe=True, enabled=False), pid, s)
    assert cat.profile_id == pid
    assert cat.name == 'My science' and cat.emoji == '🔬' and cat.color == '#123456'
    assert cat.target_queue == 40 and cat.kid_safe and not cat.enabled
    assert 'Science demonstrations' in cat.brief and 'Avoid shouting.' in cat.brief
    assert cat.seed_queries == ['lab science', 'physics experiments']
    rows = s.exec(select(Candidate).where(Candidate.category_id == cat.id)).all()
    assert len(rows) == len(entries) and all(c.status == 'accepted' for c in rows)


def test_category_playlist_generation_failure_is_atomic(imported, monkeypatch):
    from bt.api.core import CategoryCreateIn, create_category
    s, pid, _ = imported
    monkeypatch.setattr(ytimport.llm, 'chat_json', lambda *a, **kw: {'brief': '', 'seed_queries': []})
    with pytest.raises(HTTPException):
        create_category(CategoryCreateIn(name='Retry me', playlist_url='https://youtube.com/playlist?list=PLtest'), pid, s)
    assert s.exec(select(Category)).all() == []
    assert s.exec(select(Candidate)).all() == []
