import os
import tempfile

os.environ.setdefault('BT_DATA_DIR', tempfile.mkdtemp(prefix='bt-llm-provider-test-'))

import httpx
from fastapi.testclient import TestClient
from bt.main import app
from bt.api import agent
from bt.db import get_settings
from bt.llm import prepare_chat_body


def test_direct_provider_chat_options():
    original = {'model': 'gpt-5', 'max_tokens': 512, 'temperature': 0.4,
                'chat_template_kwargs': {'enable_thinking': False}}
    openai = prepare_chat_body('https://api.openai.com/v1', original.copy())
    assert openai == {'model': 'gpt-5', 'max_completion_tokens': 512}
    claude = prepare_chat_body('https://api.anthropic.com/v1', original.copy())
    assert claude == {'model': 'gpt-5', 'max_tokens': 512}
    assert prepare_chat_body('http://localhost:8080/v1', original.copy()) == original


def test_discovery_uses_unsaved_key_and_preserves_saved_connection(monkeypatch):
    requests = []
    def handler(request):
        requests.append((str(request.url), request.headers.get('authorization')))
        if request.url.path.endswith('/models'):
            return httpx.Response(200, json={'data': [{'id': 'model-b'}, {'id': 'model-a'}, {'id': 'model-a'}]})
        return httpx.Response(200, json={'choices': [{'message': {'content': 'pong'}}]})
    real = httpx.AsyncClient
    monkeypatch.setattr(agent.httpx, 'AsyncClient', lambda **kw: real(transport=httpx.MockTransport(handler), **kw))
    with TestClient(app) as c:
        c.put('/api/settings/llm', json={'base_url': 'http://my-custom:8080/v1', 'api_key': 'private-key', 'model': 'mine'})
        for base, expected in [
            ('https://opencode.ai/inference/go/openai/v1', 'https://opencode.ai/inference/go/v1/models'),
            ('https://opencode.ai/inference/openai/v1', 'https://opencode.ai/inference/v1/models'),
            ('https://openrouter.ai/api/v1', 'https://openrouter.ai/api/v1/models'),
            ('https://api.deepseek.com', 'https://api.deepseek.com/models'),
            ('https://api.x.ai/v1', 'https://api.x.ai/v1/models'),
            ('https://dashscope-intl.aliyuncs.com/compatible-mode/v1', 'https://dashscope-intl.aliyuncs.com/compatible-mode/v1/models'),
        ]:
            r = c.post('/api/agent/llm-models', json={'base_url': base, 'api_key': 'new-key'})
            assert r.json() == {'ok': True, 'models': ['model-a', 'model-b']}
            assert requests[-1] == (expected, 'Bearer new-key')
        r = c.post('/api/agent/llm-models', json={'base_url': 'https://openrouter.ai/api/v1', 'api_key': ''})
        assert r.status_code == 200 and requests[-1][1] is None
        n = len(requests)
        assert c.post('/api/agent/llm-models', json={'base_url': 'https://openrouter.ai/api/v1', 'api_key': '********'}).status_code == 400
        assert c.post('/api/agent/llm-test', json={'base_url': 'https://openrouter.ai/api/v1', 'api_key': '********'}).status_code == 400
        assert len(requests) == n
        assert c.put('/api/settings/llm', json={'base_url': 'https://openrouter.ai/api/v1', 'api_key': '********'}).status_code == 400
        assert get_settings()['llm']['base_url'] == 'http://my-custom:8080/v1'
        assert get_settings()['llm']['api_key'] == 'private-key'
        assert c.post('/api/agent/llm-models', json={'base_url': 'http://my-custom:8080/v1', 'api_key': '********'}).status_code == 200
        assert requests[-1][1] == 'Bearer private-key'
        r = c.post('/api/agent/llm-test', json={'base_url': 'https://opencode.ai/inference/go/openai/v1', 'api_key': 'new-key', 'model': 'model-a'})
        assert r.json()['ok'] and requests[-1][0] == 'https://opencode.ai/inference/go/openai/v1/chat/completions'


def test_model_discovery_errors_are_visible_and_chat_test_can_skip_listing(monkeypatch):
    def handler(request):
        if request.url.path.endswith('/models'):
            return httpx.Response(404, json={'error': 'no catalogue'})
        return httpx.Response(200, json={'choices': [{'message': {'content': 'pong'}}]})
    real = httpx.AsyncClient
    monkeypatch.setattr(agent.httpx, 'AsyncClient', lambda **kw: real(transport=httpx.MockTransport(handler), **kw))
    with TestClient(app) as c:
        body = {'base_url': 'http://custom:8080/v1', 'api_key': '', 'model': 'mine'}
        result = c.post('/api/agent/llm-models', json=body).json()
        assert not result['ok'] and '404' in result['error']
        result = c.post('/api/agent/llm-test', json=body).json()
        assert result['ok'] and result['reply'] == 'pong' and result['models'] == []
        assert c.post('/api/agent/llm-models', json={'base_url': 'ftp://invalid', 'api_key': ''}).status_code == 400
