import os
import tempfile
import time

os.environ.setdefault("BT_DATA_DIR", tempfile.mkdtemp(prefix="bt-playback-test-"))

from fastapi.testclient import TestClient
from bt.main import app
from bt.db import session
from bt.models import PlaybackTarget


def test_registration_delivery_ack_offline_and_receiver_credentials():
    with TestClient(app) as c:
        r = c.post('/api/playback/targets', json={'name': ' Media center '}).json()
        path = f'/api/playback/targets/{r["id"]}'
        headers = {'X-Receiver-Token': r['token']}
        assert r['name'] == 'Media center'
        targets = c.get('/api/playback/targets').json()
        public = next(t for t in targets if t['id'] == r['id'])
        assert public['online'] and 'token' not in public and 'token_hash' not in public
        assert c.post(path + '/heartbeat', json={}).status_code == 403
        assert c.delete(path).status_code == 403
        sent = c.post(path + '/commands', json={'action': 'play', 'video_id': 'abcdefghijk'})
        assert sent.status_code == 200
        command = c.post(path + '/heartbeat', json={}, headers=headers).json()['command']
        assert command['video_id'] == 'abcdefghijk'
        assert command['id'] == sent.json()['command_id']
        assert c.post(path + '/heartbeat', json={'ack': command['id'], 'video_id': 'abcdefghijk',
                                               'paused': False, 'position_s': 12}, headers=headers).json()['command'] is None
        state = next(t for t in c.get('/api/playback/targets').json() if t['id'] == r['id'])['state']
        assert state['video_id'] == 'abcdefghijk' and not state['paused']
        # Unacknowledged commands expire, so reconnecting screens do not play stale requests.
        with session() as s:
            target = s.get(PlaybackTarget, r['id'])
            target.command = {**target.command, 'created_at': time.time() - 31}
            s.add(target)
            s.commit()
        assert c.post(path + '/heartbeat', json={}, headers=headers).json()['command'] is None
        with session() as s:
            target = s.get(PlaybackTarget, r['id'])
            target.last_seen = time.time() - 21
            s.add(target)
            s.commit()
        assert c.post(path + '/commands', json={'action': 'pause'}).status_code == 409
        assert c.post(path + '/heartbeat', json={}, headers=headers).status_code == 200
        assert c.delete(path, headers=headers).status_code == 200
        assert c.post(path + '/commands', json={'action': 'pause'}).status_code == 404


def test_command_validation_and_sender_profile():
    with TestClient(app) as c:
        r = c.post('/api/playback/targets', json={'name': 'Screen'}).json()
        path = f'/api/playback/targets/{r["id"]}'
        receiver_headers = {'X-Receiver-Token': r['token']}
        assert c.post('/api/playback/targets', json={'name': '  '}).status_code == 422
        assert c.post(path + '/commands', json={'action': 'play'}).status_code == 422
        assert c.post(path + '/commands', json={'action': 'play', 'video_id': '../oops'}).status_code == 422
        assert c.post(path + '/commands', json={'action': 'shell'}).status_code == 422
        p = c.post('/api/profiles', json={'name': 'Casting family'}).json()
        h = {'X-Profile-Id': str(p['id'])}
        cat = c.post('/api/categories', json={'name': 'Cast queue'}, headers=h).json()
        assert c.post(path + '/commands', json={'action': 'play', 'video_id': 'abcdefghijk',
                                               'category_id': cat['id']}).status_code == 404
        assert c.post(path + '/commands', json={'action': 'play', 'video_id': 'abcdefghijk',
                                               'category_id': cat['id']}, headers=h).status_code == 200
        cmd = c.post(path + '/heartbeat', json={}, headers=receiver_headers).json()['command']
        assert cmd['profile_id'] == p['id'] and cmd['category_id'] == cat['id']
        # Latest command wins; receiver status updates must not clobber commands.
        c.post(path + '/commands', json={'action': 'pause'}, headers=h)
        cmd2 = c.post(path + '/heartbeat', json={'ack': cmd['id']}, headers=receiver_headers).json()['command']
        assert cmd2['id'] != cmd['id'] and cmd2['action'] == 'pause'
        c.delete(path, headers=receiver_headers)
