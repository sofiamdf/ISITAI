import pytest

from isitai import cache, config, history_repo, model_client
from isitai.handlers import analyze
from conftest import PNG, PNG_SHA256, Ctx, api_event, parse


@pytest.fixture
def model_calls(monkeypatch):
    calls = []

    def fake_predict(data, sha256, content_type, model):
        calls.append((sha256, content_type, model))
        return {'prob_ai': 0.5, 'prob_real': 0.5, 'label': 'uncertain', 'model': model, 'model_version': 'test'}

    monkeypatch.setattr(model_client, 'predict', fake_predict)
    monkeypatch.setattr(config, 'CACHE_TABLE', '')
    monkeypatch.setattr(config, 'HISTORY_TABLE', '')
    return calls


@pytest.fixture
def saved(monkeypatch):
    rows = []
    monkeypatch.setattr(history_repo, 'save', lambda session, at, item: rows.append((session, item)))
    return rows


def call(**kwargs):
    return parse(analyze.handler(api_event(**kwargs), Ctx()))


def test_ok_returns_contract_fields(model_calls, saved):
    status, body = call()
    assert status == 200 and body['sha256'] == PNG_SHA256 and body['cache_hit'] is False
    assert body['model'] == 'resnet18' and body['label'] == 'uncertain'
    assert {'request_id', 'latency_ms', 'analyzed_at', 'prob_real', 'model_version'} <= set(body)
    assert model_calls == [(PNG_SHA256, 'image/png', 'resnet18')]
    session, row = saved[0]
    assert session == 'prueba-1234' and row['size_bytes'] == len(PNG) and row['model'] == 'resnet18'


def test_model_from_query(model_calls, saved):
    status, body = call(query={'model': 'mlp'})
    assert status == 200 and body['model'] == 'mlp' and model_calls[0][2] == 'mlp'


@pytest.mark.parametrize('kwargs,status,code', [
    ({'session': None}, 400, 'missing_session'),
    ({'session': 'corta'}, 400, 'missing_session'),
    ({'query': {'model': 'vit'}}, 400, 'unknown_model'),
    ({'content_type': 'image/gif'}, 400, 'unsupported_type'),
    ({'b64': False}, 400, 'expected_binary'),
    ({'body': b''}, 400, 'empty_body'),
    ({'body': b'\xff\xd8\xff' + b'0' * (4 * 1024 * 1024)}, 413, 'too_large'),
    ({'content_type': 'image/jpeg'}, 400, 'content_mismatch'),  # bytes de PNG declarados como JPEG
])
def test_validation_errors(model_calls, saved, kwargs, status, code):
    got_status, body = call(**kwargs)
    assert (got_status, body['error']['code']) == (status, code)
    assert model_calls == [] and saved == []


def test_content_type_with_parameters(model_calls, saved):
    status, _ = call(content_type='image/png; charset=binary')
    assert status == 200


@pytest.mark.parametrize('exc,status,code', [
    (model_client.ModelTimeout('timeout'), 504, 'model_timeout'),
    (model_client.ModelError('El modelo respondió 500'), 502, 'model_error'),
])
def test_model_failures(monkeypatch, saved, exc, status, code):
    def boom(*args):
        raise exc
    monkeypatch.setattr(model_client, 'predict', boom)
    monkeypatch.setattr(config, 'CACHE_TABLE', '')
    got_status, body = call()
    assert (got_status, body['error']['code']) == (status, code) and saved == []


def test_unexpected_error_is_500_without_trace(model_calls, monkeypatch):
    def boom(*args):
        raise KeyError('secreto')
    monkeypatch.setattr(history_repo, 'save', boom)
    status, body = call()
    assert status == 500 and body['error']['code'] == 'internal_error' and 'secreto' not in str(body)


def test_second_request_hits_cache(model_calls, saved, monkeypatch):
    store = {}
    monkeypatch.setattr(config, 'CACHE_TABLE', 'isitai-cache.example')
    monkeypatch.setattr(cache, 'get_result', lambda key, ttl: store.get(key))
    monkeypatch.setattr(cache, 'put_result', lambda key, value, ttl: store.update({key: value}))
    _, first = call(query={'model': 'cnn'})
    _, second = call(query={'model': 'cnn'})
    _, other_model = call(query={'model': 'mlp'})
    assert first['cache_hit'] is False and second['cache_hit'] is True and other_model['cache_hit'] is False
    assert second['analyzed_at'] == first['analyzed_at'] and len(model_calls) == 2
    assert set(store) == {f'isitai:v1:mock:cnn:{PNG_SHA256}', f'isitai:v1:mock:mlp:{PNG_SHA256}'}
    assert [row['cache_hit'] for _, row in saved] == [False, True, False]


def test_cache_down_still_analyzes(model_calls, saved, monkeypatch):
    def broken():
        raise ConnectionError('caída')
    monkeypatch.setattr(config, 'CACHE_TABLE', 'isitai-cache.example')
    monkeypatch.setattr(cache, '_state', {'client': None, 'disabled_until': 0.0})
    monkeypatch.setattr(cache, '_connect', broken)
    status, body = call()
    assert status == 200 and body['cache_hit'] is False and len(model_calls) == 1


def test_png_jpeg_and_webp_signatures():
    assert analyze.SIGNATURES['image/png'](PNG)
    assert analyze.SIGNATURES['image/jpeg'](bytes.fromhex('ffd8ffe0') + b'x')
    assert analyze.SIGNATURES['image/webp'](b'RIFF\x00\x00\x00\x00WEBPVP8 ')
    assert not analyze.SIGNATURES['image/webp'](PNG)


def test_responses_match_backend_contract(model_calls, saved):
    from conftest import backend_schema_errors
    _, ok = call(query={'model': 'cnn'})
    _, bad = call(query={'model': 'vit'})
    assert backend_schema_errors('AnalysisResult', ok) == []
    assert backend_schema_errors('Error', bad) == []
