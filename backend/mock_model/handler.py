import base64
import json
import os
import time

MODEL_VERSION = 'mock-0.1'
MODELS = ('mlp', 'cnn', 'resnet18')
DEFAULT_MODEL = 'resnet18'


def _json(status, body):
    return {'statusCode': status, 'headers': {'Content-Type': 'application/json'}, 'body': json.dumps(body)}


def handler(event, context):
    headers = {k.lower(): v for k, v in (event.get('headers') or {}).items()}
    expected_key = os.environ.get('MOCK_API_KEY', '')
    if expected_key and headers.get('x-api-key') != expected_key:
        return _json(401, {'error': 'unauthorized'})

    method = event['requestContext']['http']['method']
    path = event.get('rawPath', '/')

    if method == 'GET' and path == '/v1/health':
        return _json(200, {'status': 'ok', 'model_version': MODEL_VERSION, 'default_model': DEFAULT_MODEL,
                           'models': [{'id': m, 'version': MODEL_VERSION} for m in MODELS]})

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
        model = body.get('model') or DEFAULT_MODEL
        if model not in MODELS:
            return _json(400, {'error': 'unknown_model'})
        started = time.perf_counter()
        time.sleep(int(os.environ.get('MOCK_LATENCY_MS', '800')) / 1000)
        return _json(200, {
            'prob_ai': 0.5,
            'label': 'uncertain',
            'model': model,
            'model_version': MODEL_VERSION,
            'inference_ms': int((time.perf_counter() - started) * 1000),
        })

    return _json(404, {'error': 'not_found'})
