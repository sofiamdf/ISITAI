import base64
import hashlib
import json
import time
from datetime import datetime, timezone
from urllib.parse import unquote

from isitai import cache, config, history_repo, model_client
from isitai.http import error, lower_headers, respond, safe

ALLOWED_TYPES = {'image/jpeg', 'image/png', 'image/webp'}
SIGNATURES = {  # primeros bytes de cada formato: no alcanza con creerle al Content-Type
    'image/jpeg': lambda d: d[:3] == bytes.fromhex('ffd8ff'),
    'image/png': lambda d: d[:8] == bytes.fromhex('89504e470d0a1a0a'),
    'image/webp': lambda d: d[:4] == b'RIFF' and d[8:12] == b'WEBP',
}


def _now_iso():
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds')


@safe
def handler(event, context):
    started = time.perf_counter()
    requested_at = _now_iso()
    headers = lower_headers(event)

    session_id = headers.get('x-session-id', '')
    if not 8 <= len(session_id) <= 64:
        return error(400, 'missing_session', 'Falta el encabezado X-Session-Id (8 a 64 caracteres).')
    model = (event.get('queryStringParameters') or {}).get('model') or config.DEFAULT_MODEL
    if model not in config.MODELS:
        return error(400, 'unknown_model', f'Modelo desconocido. Opciones: {", ".join(config.MODELS)}.')
    content_type = headers.get('content-type', '').split(';')[0].strip().lower()
    if content_type not in ALLOWED_TYPES:
        return error(400, 'unsupported_type', 'Formato no soportado: se aceptan JPEG, PNG o WebP.')
    if not event.get('isBase64Encoded'):
        return error(400, 'expected_binary', 'Se esperaba la imagen como cuerpo binario.')
    data = base64.b64decode(event.get('body') or '')
    if not data:
        return error(400, 'empty_body', 'La imagen está vacía.')
    if len(data) > config.MAX_IMAGE_BYTES:
        return error(413, 'too_large', 'La imagen supera los 4 MB.')
    if not SIGNATURES[content_type](data):
        return error(400, 'content_mismatch', 'El contenido del archivo no coincide con su tipo.')

    sha256 = hashlib.sha256(data).hexdigest()
    key = cache.result_key(config.MODEL_ID, model, sha256)
    result = cache.get_result(key, config.CACHE_TTL_SECONDS)
    cache_hit = result is not None
    if not cache_hit:
        try:
            result = model_client.predict(data, sha256, content_type, model)
        except model_client.ModelTimeout:
            return error(504, 'model_timeout', 'El modelo no respondió a tiempo.')
        except model_client.ModelError as exc:
            return error(502, 'model_error', str(exc))
        result['analyzed_at'] = _now_iso()
        cache.put_result(key, result, config.CACHE_TTL_SECONDS)

    latency_ms = int((time.perf_counter() - started) * 1000)
    response = {**result, 'request_id': context.aws_request_id, 'sha256': sha256,
                'cache_hit': cache_hit, 'latency_ms': latency_ms}
    history_repo.save(session_id, requested_at, {
        **response,
        'file_name': unquote(headers.get('x-file-name', ''))[:200],
        'content_type': content_type,
        'size_bytes': len(data),
    })
    # Lo lee CloudWatch Logs Insights para medir latencias y aciertos de caché
    print(json.dumps({'event': 'analyze_done', 'cache_hit': cache_hit, 'latency_ms': latency_ms,
                      'model_id': config.MODEL_ID, 'model': model, 'size_bytes': len(data)}))
    return respond(200, response)
