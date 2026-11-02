import base64
import binascii
import json
import os
import time
from pathlib import Path

import numpy as np
import onnxruntime as ort
from PIL import Image

import preprocess

MODELS_DIR = Path(os.environ.get('MODELS_DIR', Path(__file__).parent / 'models'))
_state = {'sessions': {}}


def manifest():
    if 'manifest' not in _state:
        _state['manifest'] = json.loads((MODELS_DIR / 'models.json').read_text(encoding='utf-8'))
    return _state['manifest']


def _session(name):
    sessions = _state['sessions']
    if name not in sessions:
        options = ort.SessionOptions()
        options.intra_op_num_threads = os.cpu_count() or 1
        path = MODELS_DIR / manifest()['models'][name]['file']
        sessions[name] = ort.InferenceSession(str(path), options, providers=['CPUExecutionProvider'])
    return sessions[name]


def predict(name, data):
    spec = manifest()['models'][name]
    x = preprocess.to_model_input(data, spec['input_size'], spec['jpeg_quality'])
    logits = _session(name).run([spec['output_name']], {spec['input_name']: x})[0][0].astype(np.float64)
    exp = np.exp(logits - logits.max())
    prob_ai = float(exp[1] / exp.sum())
    band = manifest()['uncertain_band']
    label = 'uncertain' if abs(prob_ai - 0.5) < band else 'ai' if prob_ai > 0.5 else 'real'
    return round(prob_ai, 6), label, spec['version']


def _json(status, body):
    return {'statusCode': status, 'headers': {'Content-Type': 'application/json'}, 'body': json.dumps(body)}


def handler(event, context):
    headers = {k.lower(): v for k, v in (event.get('headers') or {}).items()}
    expected_key = os.environ.get('MODEL_API_KEY', '')
    if expected_key and headers.get('x-api-key') != expected_key:
        return _json(401, {'error': 'unauthorized'})

    method = event['requestContext']['http']['method']
    path = event.get('rawPath', '/')
    models = manifest()['models']
    default = manifest()['default_model']

    if method == 'GET' and path == '/v1/health':
        return _json(200, {'status': 'ok', 'model_version': models[default]['version'], 'default_model': default,
                           'models': [{'id': n, 'version': m['version']} for n, m in models.items()]})

    if method == 'POST' and path == '/v1/predict':
        raw = event.get('body') or '{}'
        if event.get('isBase64Encoded'):
            raw = base64.b64decode(raw)
        try:
            body = json.loads(raw)
        except json.JSONDecodeError:
            return _json(400, {'error': 'invalid_json'})
        if not body.get('image_b64'):
            return _json(400, {'error': 'missing_image_b64'})
        name = body.get('model') or default
        if name not in models:
            return _json(400, {'error': 'unknown_model'})
        started = time.perf_counter()
        try:
            prob_ai, label, version = predict(name, base64.b64decode(body['image_b64'], validate=True))
        except (binascii.Error, OSError, ValueError, Image.DecompressionBombError):
            return _json(400, {'error': 'invalid_image'})
        return _json(200, {'prob_ai': prob_ai, 'label': label, 'model': name, 'model_version': version,
                           'inference_ms': int((time.perf_counter() - started) * 1000)})

    return _json(404, {'error': 'not_found'})


if (MODELS_DIR / 'models.json').exists():
    _session(manifest()['default_model'])  # en la fase de inicio, para que el primer pedido no espere la carga
