import os
import tempfile

os.environ.setdefault('BT_DATA_DIR', tempfile.mkdtemp(prefix='bt-dearrow-test-'))

from fastapi.testclient import TestClient
from bt import extras
from bt.main import app


def test_thumbnail_toggle_uses_community_frame_and_falls_back_without_poisoning_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(extras, 'THUMB_DIR', tmp_path)
    state = {'available': True, 'timestamp': 5}
    calls = []

    async def branding(video_id):
        return {'thumb': f'https://dearrow-thumb.ajay.app/api/v1/getThumbnail?videoID={video_id}&time={state["timestamp"]}'}

    async def fetch(url):
        calls.append(url)
        if 'dearrow-thumb.ajay.app' in url:
            return b'community-' + str(state['timestamp']).encode() if state['available'] else None
        return b'original'

    monkeypatch.setattr(extras, 'dearrow', branding)
    monkeypatch.setattr(extras, '_fetch_image', fetch)
    with TestClient(app) as c:
        normal = c.get('/api/thumb/abcdefghijk?q=hq')
        assert normal.content == b'original'
        assert 'immutable' in normal.headers['cache-control']
        state['available'] = False
        fallback = c.get('/api/thumb/abcdefghijk?q=hq&dearrow=1')
        assert fallback.content == b'original'
        assert fallback.headers['cache-control'] == 'no-store'
        state['available'] = True
        better = c.get('/api/thumb/abcdefghijk?q=hq&dearrow=1')
        assert better.content == b'community-5'
        assert better.headers['cache-control'] == 'no-store'
        state['timestamp'] = 10
        assert c.get('/api/thumb/abcdefghijk?q=hq&dearrow=1').content == b'community-10'
        assert c.get('/api/thumb/abcdefghijk?q=hq').content == b'original'
        assert c.get('/api/thumb/bad?q=hq&dearrow=1').status_code == 404
        assert c.get('/api/settings').json()['extras']['dearrow_thumbnails'] is False
    assert extras.image_host_allowed('https://dearrow-thumb.ajay.app/api/v1/getThumbnail?videoID=abcdefghijk')
    assert not extras.image_host_allowed('https://evil.ajay.app/api/v1/getThumbnail')
    assert not extras.image_host_allowed('https://dearrow-thumb.ajay.app.evil.example/image')


def test_thumbnail_without_community_selection_falls_back(tmp_path, monkeypatch):
    monkeypatch.setattr(extras, 'THUMB_DIR', tmp_path)
    async def no_branding(_):
        return None
    async def fetch(url):
        return None if 'dearrow-thumb.ajay.app' in url else b'original'
    monkeypatch.setattr(extras, 'dearrow', no_branding)
    monkeypatch.setattr(extras, '_fetch_image', fetch)
    with TestClient(app) as c:
        r = c.get('/api/thumb/abcdefghijk?dearrow=1')
        assert r.status_code == 200 and r.content == b'original'


def test_cached_dearrow_frame_is_used_when_no_community_submission(tmp_path, monkeypatch):
    monkeypatch.setattr(extras, 'THUMB_DIR', tmp_path)
    calls = []
    async def no_branding(_):
        return None
    async def fetch(url):
        calls.append(url)
        return b'cached-dearrow-frame' if 'dearrow-thumb.ajay.app' in url else b'original'
    monkeypatch.setattr(extras, 'dearrow', no_branding)
    monkeypatch.setattr(extras, '_fetch_image', fetch)
    with TestClient(app) as c:
        r = c.get('/api/thumb/abcdefghijk?dearrow=1')
        assert r.status_code == 200 and r.content == b'cached-dearrow-frame'
        assert 'time=' not in calls[0]
        assert c.get('/api/thumb/abcdefghijk').content == b'original'
