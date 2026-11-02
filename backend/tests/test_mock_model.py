import pytest

from conftest import parse, url_event
from mock_model import handler as mock

BODY = {'image_b64': 'aGVsbG8=', 'sha256': 'x', 'content_type': 'image/png'}


@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.setenv('MOCK_API_KEY', 'clave')
    monkeypatch.setenv('MOCK_LATENCY_MS', '0')


def test_health_lists_models():
    status, body = parse(mock.handler(url_event('GET', '/v1/health'), None))
    assert status == 200 and body['default_model'] == 'resnet18'
    assert [m['id'] for m in body['models']] == ['mlp', 'cnn', 'resnet18']


@pytest.mark.parametrize('model,expected', [(None, 'resnet18'), ('mlp', 'mlp'), ('cnn', 'cnn')])
def test_predict_echoes_model(model, expected):
    status, body = parse(mock.handler(url_event('POST', '/v1/predict', {**BODY, 'model': model}), None))
    assert status == 200 and body['model'] == expected and body['prob_ai'] == 0.5


def test_unknown_model_is_400():
    status, body = parse(mock.handler(url_event('POST', '/v1/predict', {**BODY, 'model': 'vit'}), None))
    assert status == 400 and body['error'] == 'unknown_model'


def test_wrong_key_is_401():
    status, _ = parse(mock.handler(url_event('GET', '/v1/health', key='mala'), None))
    assert status == 401


def test_missing_image_is_400():
    status, body = parse(mock.handler(url_event('POST', '/v1/predict', {'sha256': 'x'}), None))
    assert status == 400 and body['error'] == 'missing_image_b64'


def test_base64_body_and_invalid_json():
    event = url_event('POST', '/v1/predict')
    event.update(body='bm8gZXMganNvbg==', isBase64Encoded=True)  # "no es json"
    status, body = parse(mock.handler(event, None))
    assert status == 400 and body['error'] == 'invalid_json'


def test_unknown_path_is_404():
    status, _ = parse(mock.handler(url_event('GET', '/otra'), None))
    assert status == 404
