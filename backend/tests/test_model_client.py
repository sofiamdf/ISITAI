import json
import time

import pytest

from isitai import config, model_client
from conftest import PNG, PNG_SHA256
from mock_model import handler as mock


@pytest.fixture
def mock_url(serve, monkeypatch):
    monkeypatch.setenv('MOCK_API_KEY', 'clave')
    monkeypatch.setenv('MOCK_LATENCY_MS', '0')
    url = serve(mock.handler)
    monkeypatch.setattr(config, 'MODEL_API_URL', url)
    monkeypatch.setattr(config, 'MODEL_API_KEY', 'clave')
    return url


def fake(status=200, body=None, delay=0, raw=None):
    def handler(event, context):
        time.sleep(delay)
        return {'statusCode': status, 'body': raw if raw is not None else json.dumps(body or {})}
    return handler


def test_predict_against_mock(mock_url):
    result = model_client.predict(PNG, PNG_SHA256, 'image/png', 'cnn')
    assert result == {'prob_ai': 0.5, 'prob_real': 0.5, 'label': 'uncertain', 'model': 'cnn',
                      'model_version': 'mock-0.1'}


def test_health_against_mock(mock_url):
    assert model_client.health()['default_model'] == 'resnet18'


def test_wrong_key_is_model_error(mock_url, monkeypatch):
    monkeypatch.setattr(config, 'MODEL_API_KEY', 'mala')
    with pytest.raises(model_client.ModelError, match='401'):
        model_client.predict(PNG, PNG_SHA256, 'image/png', 'cnn')


@pytest.mark.parametrize('handler,match', [
    (fake(500, {'error': 'boom'}), '500'),
    (fake(200, {'label': 'ai'}), 'sin prob_ai'),
    (fake(200, {'prob_ai': 1.5}), 'fuera de rango'),
    (fake(200, raw='<html>'), 'no es JSON'),
])
def test_bad_answers_are_model_errors(serve, monkeypatch, handler, match):
    monkeypatch.setattr(config, 'MODEL_API_URL', serve(handler))
    with pytest.raises(model_client.ModelError, match=match):
        model_client.predict(PNG, PNG_SHA256, 'image/png', 'mlp')


def test_label_derived_when_missing(serve, monkeypatch):
    monkeypatch.setattr(config, 'MODEL_API_URL', serve(fake(200, {'prob_ai': 0.9, 'model_version': 'x'})))
    result = model_client.predict(PNG, PNG_SHA256, 'image/png', 'mlp')
    assert result['label'] == 'ai' and result['model'] == 'mlp'


def test_timeout(serve, monkeypatch):
    monkeypatch.setattr(config, 'MODEL_API_URL', serve(fake(200, {'prob_ai': 0.5}, delay=1.0)))
    monkeypatch.setattr(config, 'MODEL_TIMEOUT_SECONDS', 0.2)
    with pytest.raises(model_client.ModelTimeout):
        model_client.predict(PNG, PNG_SHA256, 'image/png', 'mlp')


def test_unreachable(monkeypatch):
    monkeypatch.setattr(config, 'MODEL_API_URL', 'http://127.0.0.1:9')
    with pytest.raises(model_client.ModelError):
        model_client.health()
