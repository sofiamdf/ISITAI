import pytest

from isitai import cache, config, history_repo
from isitai.handlers import health
from conftest import Ctx, parse
from mock_model import handler as mock


@pytest.fixture
def mock_up(serve, monkeypatch):
    monkeypatch.setenv('MOCK_API_KEY', 'clave')
    monkeypatch.setattr(config, 'MODEL_API_URL', serve(mock.handler))
    monkeypatch.setattr(config, 'MODEL_API_KEY', 'clave')
    monkeypatch.setattr(config, 'CACHE_ENDPOINT', '')
    monkeypatch.setattr(config, 'HISTORY_TABLE', '')


def test_ok_without_cache_or_history(mock_up):
    status, body = parse(health.handler({}, Ctx()))
    assert status == 200 and body['status'] == 'ok' and body['model_id'] == 'mock'
    assert [m['id'] for m in body['models']] == ['mlp', 'cnn', 'resnet18']
    assert body['cache'] == {'reachable': None} and body['history'] == {'reachable': None}


def test_models_filtered_by_config(mock_up, monkeypatch):
    monkeypatch.setattr(config, 'MODELS', ('cnn',))
    _, body = parse(health.handler({}, Ctx()))
    assert [m['id'] for m in body['models']] == ['cnn']


def test_degraded_when_cache_fails(mock_up, monkeypatch):
    monkeypatch.setattr(cache, 'ping', lambda: False)
    status, body = parse(health.handler({}, Ctx()))
    assert status == 200 and body['status'] == 'degraded'


def test_degraded_when_history_fails(mock_up, monkeypatch):
    monkeypatch.setattr(config, 'HISTORY_TABLE', 'isitai-history')
    def boom(*args, **kwargs):
        raise RuntimeError('sin permiso')
    monkeypatch.setattr(history_repo, 'list_for_session', boom)
    _, body = parse(health.handler({}, Ctx()))
    assert body['status'] == 'degraded' and body['history'] == {'reachable': False}


def test_down_when_model_unreachable(monkeypatch):
    monkeypatch.setattr(config, 'MODEL_API_URL', 'http://127.0.0.1:9')
    monkeypatch.setattr(config, 'CACHE_ENDPOINT', '')
    monkeypatch.setattr(config, 'HISTORY_TABLE', '')
    status, body = parse(health.handler({}, Ctx()))
    assert status == 503 and body['status'] == 'down' and body['models'] == []


def test_matches_backend_contract(mock_up):
    from conftest import backend_schema_errors
    _, body = parse(health.handler({}, Ctx()))
    assert backend_schema_errors('Health', body) == []
