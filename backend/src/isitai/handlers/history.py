from isitai import history_repo
from isitai.http import error, lower_headers, respond, safe

FIELDS = ('requested_at', 'request_id', 'sha256', 'file_name', 'label', 'prob_ai', 'model',
          'model_version', 'cache_hit', 'latency_ms')


@safe
def handler(event, context):
    session_id = lower_headers(event).get('x-session-id', '')
    if not 8 <= len(session_id) <= 64:
        return error(400, 'missing_session', 'Falta el encabezado X-Session-Id (8 a 64 caracteres).')
    if not history_repo.enabled():
        return error(503, 'history_disabled', 'El historial no está configurado en este despliegue.')
    query = event.get('queryStringParameters') or {}
    try:
        limit = min(max(int(query.get('limit', '20')), 1), 50)
    except ValueError:
        limit = 20
    try:
        items, next_cursor = history_repo.list_for_session(session_id, limit, query.get('cursor'))
    except ValueError:
        return error(400, 'invalid_cursor', 'Cursor inválido.')
    return respond(200, {'items': [{f: item.get(f) for f in FIELDS} for item in items],
                         'next_cursor': next_cursor})
