import json
import os
import urllib.error
import urllib.request
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

URL = os.environ.get('MODEL_API_URL', '').rstrip('/')
KEY = os.environ.get('MODEL_API_KEY', '')
PNG_B64 = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=='
SPEC = yaml.safe_load((Path(__file__).resolve().parents[3] / 'docs' / 'model-api.yaml').read_text(encoding='utf-8'))
REGISTRY = Registry().with_resource('urn:model-api', Resource.from_contents(SPEC, default_specification=DRAFT202012))
pytestmark = pytest.mark.skipif(not URL, reason='MODEL_API_URL no definida')


def schema_errors(path, method, status, body):
    pointer = f'/paths/{path.replace("/", "~1")}/{method}/responses/{status}/content/application~1json/schema'
    validator = Draft202012Validator({'$ref': f'urn:model-api#{pointer}'}, registry=REGISTRY)
    return [e.message for e in validator.iter_errors(body)]


def call(path, body=None, key=None):
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(URL + path, data=data, method='POST' if data else 'GET',
                                     headers={'Content-Type': 'application/json', 'X-Api-Key': key or KEY})
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read() or b'null')


def predict_body(model=None):
    body = {'image_b64': PNG_B64, 'sha256': 'x', 'content_type': 'image/png'}
    return {**body, 'model': model} if model else body


def test_health_matches_schema():
    status, body = call('/v1/health')
    assert status == 200 and schema_errors('/v1/health', 'get', 200, body) == []
    assert body['default_model'] in {m['id'] for m in body['models']}


def test_predict_each_listed_model():
    _, health = call('/v1/health')
    for model in [m['id'] for m in health['models']]:
        status, body = call('/v1/predict', predict_body(model))
        assert status == 200 and schema_errors('/v1/predict', 'post', 200, body) == []
        assert body['model'] == model


def test_predict_without_model_uses_default():
    _, health = call('/v1/health')
    status, body = call('/v1/predict', predict_body())
    assert status == 200 and body['model'] == health['default_model']


def test_rejects_wrong_key():
    status, _ = call('/v1/predict', predict_body(), key='mala-clave')
    assert status == 401


def test_rejects_missing_image():
    status, body = call('/v1/predict', {'sha256': 'x', 'content_type': 'image/png'})
    assert status == 400 and body['error'] == 'missing_image_b64'


def test_rejects_unknown_model():
    status, body = call('/v1/predict', predict_body('vit'))
    assert status == 400 and body['error'] == 'unknown_model'
