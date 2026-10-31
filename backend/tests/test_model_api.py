import base64
import hashlib
import io
import json
from pathlib import Path

import numpy as np
import onnx
import pytest
from onnx import TensorProto, helper, numpy_helper
from PIL import Image

import handler as model_api
import preprocess
from conftest import PNG, parse, url_event

MODEL_API = Path(__file__).resolve().parents[1] / 'model_api'


def tiny_onnx(path, weights):
    graph = helper.make_graph(
        [helper.make_node('ReduceMean', ['input'], ['avg'], axes=[2, 3], keepdims=0),
         helper.make_node('MatMul', ['avg', 'w'], ['logits'])],
        'tiny',
        [helper.make_tensor_value_info('input', TensorProto.FLOAT, ['batch', 3, 16, 16])],
        [helper.make_tensor_value_info('logits', TensorProto.FLOAT, ['batch', 2])],
        [numpy_helper.from_array(np.asarray(weights, dtype=np.float32), 'w')],
    )
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid('', 17)], ir_version=10)  # ONNX Runtime 1.31 lee hasta IR 13
    onnx.save(model, str(path))


@pytest.fixture
def models(tmp_path, monkeypatch):
    tiny_onnx(tmp_path / 'mlp.onnx', [[0, 4], [0, 4], [0, 4]])        # imagen clara -> FAKE
    tiny_onnx(tmp_path / 'resnet18.onnx', [[4, 0], [4, 0], [4, 0]])   # imagen clara -> REAL
    spec = {'input_size': 16, 'jpeg_quality': 90, 'input_name': 'input', 'output_name': 'logits'}
    manifest = {'schema': 1, 'default_model': 'resnet18', 'uncertain_band': 0.1,
                'models': {'mlp': {**spec, 'file': 'mlp.onnx', 'version': 'mlp-test'},
                           'resnet18': {**spec, 'file': 'resnet18.onnx', 'version': 'resnet-test'}}}
    (tmp_path / 'models.json').write_text(json.dumps(manifest))
    monkeypatch.setattr(model_api, 'MODELS_DIR', tmp_path)
    monkeypatch.setattr(model_api, '_state', {'sessions': {}})
    monkeypatch.setenv('MODEL_API_KEY', 'clave')
    return manifest


def white_jpeg():
    buf = io.BytesIO()
    Image.new('RGB', (40, 30), (250, 250, 250)).save(buf, format='JPEG')
    return buf.getvalue()


def predict_body(data, model=None):
    body = {'image_b64': base64.b64encode(data).decode(), 'sha256': hashlib.sha256(data).hexdigest(),
            'content_type': 'image/jpeg'}
    return {**body, 'model': model} if model else body


def test_health_lists_models_and_default(models):
    status, body = parse(model_api.handler(url_event('GET', '/v1/health'), None))
    assert status == 200 and body['default_model'] == 'resnet18' and body['model_version'] == 'resnet-test'
    assert body['models'] == [{'id': 'mlp', 'version': 'mlp-test'}, {'id': 'resnet18', 'version': 'resnet-test'}]


def test_predict_uses_requested_model(models):
    _, default = parse(model_api.handler(url_event('POST', '/v1/predict', predict_body(white_jpeg())), None))
    _, mlp = parse(model_api.handler(url_event('POST', '/v1/predict', predict_body(white_jpeg(), 'mlp')), None))
    assert default['model'] == 'resnet18' and default['label'] == 'real' and default['prob_ai'] < 0.1
    assert mlp['model'] == 'mlp' and mlp['label'] == 'ai' and mlp['prob_ai'] > 0.9
    assert mlp['model_version'] == 'mlp-test' and isinstance(mlp['inference_ms'], int)


def test_probability_matches_preprocess_and_softmax(models):
    x = preprocess.to_model_input(PNG, 16, 90)
    logits = x.mean(axis=(2, 3))[0] @ np.full((3, 2), [0, 4], dtype=np.float32)
    expected = float(np.exp(logits[1]) / np.exp(logits).sum())
    _, body = parse(model_api.handler(url_event('POST', '/v1/predict', predict_body(PNG, 'mlp')), None))
    assert body['prob_ai'] == pytest.approx(expected, abs=1e-5)


def test_uncertain_band(models):
    gray = io.BytesIO()
    Image.new('RGB', (16, 16), (128, 128, 128)).save(gray, format='PNG')
    tiny_onnx(model_api.MODELS_DIR / 'mlp.onnx', [[0, 0.05], [0, 0.05], [0, 0.05]])
    _, body = parse(model_api.handler(url_event('POST', '/v1/predict', predict_body(gray.getvalue(), 'mlp')), None))
    assert body['label'] == 'uncertain'


@pytest.mark.parametrize('body,code', [
    ({'image_b64': 'no-es-base64!', 'sha256': 'x', 'content_type': 'image/png'}, 'invalid_image'),
    ({'image_b64': base64.b64encode(b'no es una imagen').decode(), 'sha256': 'x', 'content_type': 'image/png'}, 'invalid_image'),
    ({'image_b64': 'aGVsbG8=', 'sha256': 'x', 'content_type': 'image/png', 'model': 'cnn'}, 'unknown_model'),
    ({'sha256': 'x', 'content_type': 'image/png'}, 'missing_image_b64'),
])
def test_bad_requests_are_400(models, body, code):
    status, response = parse(model_api.handler(url_event('POST', '/v1/predict', body), None))
    assert status == 400 and response['error'] == code


def test_wrong_key_is_401(models):
    status, _ = parse(model_api.handler(url_event('GET', '/v1/health', key='mala'), None))
    assert status == 401


def test_committed_models_match_preprocess():
    manifest_path = MODEL_API / 'models' / 'models.json'
    if not manifest_path.exists():
        pytest.skip('Todavía no hay modelos en model_api/models')
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    local = hashlib.sha256((MODEL_API / 'preprocess.py').read_bytes().replace(b'\r\n', b'\n')).hexdigest()
    assert manifest['preprocess_sha256'] == local, 'preprocess.py no coincide con el del repo de ML'
    for name, spec in manifest['models'].items():
        data = (MODEL_API / 'models' / spec['file']).read_bytes()
        assert hashlib.sha256(data).hexdigest() == spec['sha256'], f'{name}: el ONNX no es el exportado'
