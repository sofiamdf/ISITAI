import base64
import json
import urllib.error
import urllib.request

from isitai import config


class ModelError(Exception):
    pass


class ModelTimeout(ModelError):
    pass


def _call(method, path, payload=None, timeout=None):
    request = urllib.request.Request(
        f'{config.MODEL_API_URL}{path}', method=method,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={'Content-Type': 'application/json', 'X-Api-Key': config.MODEL_API_KEY},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout or config.MODEL_TIMEOUT_SECONDS) as response:
            return json.loads(response.read())
    except TimeoutError as exc:
        raise ModelTimeout('timeout') from exc
    except urllib.error.HTTPError as exc:
        raise ModelError(f'El modelo respondió {exc.code}') from exc
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, TimeoutError):
            raise ModelTimeout('timeout') from exc
        raise ModelError('No se pudo contactar al modelo') from exc
    except json.JSONDecodeError as exc:
        raise ModelError('Respuesta del modelo que no es JSON') from exc


def predict(data, sha256, content_type, model):
    body = _call('POST', '/v1/predict', {
        'image_b64': base64.b64encode(data).decode(),
        'sha256': sha256,
        'content_type': content_type,
        'model': model,
    })
    return _validate(body, model)


def health(timeout=3):
    return _call('GET', '/v1/health', timeout=timeout)


def _validate(body, model):
    try:
        prob_ai = float(body['prob_ai'])
    except (KeyError, TypeError, ValueError) as exc:
        raise ModelError('Respuesta del modelo sin prob_ai') from exc
    if not 0.0 <= prob_ai <= 1.0:
        raise ModelError('prob_ai fuera de rango')
    label = body.get('label')
    if label not in ('ai', 'real', 'uncertain'):
        label = 'ai' if prob_ai > 0.5 else 'real' if prob_ai < 0.5 else 'uncertain'
    return {
        'prob_ai': prob_ai,
        'prob_real': round(1.0 - prob_ai, 6),
        'label': label,
        'model': str(body.get('model', model)),
        'model_version': str(body.get('model_version', 'desconocida')),
    }
