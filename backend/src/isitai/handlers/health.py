from isitai import cache, config, history_repo, model_client
from isitai.http import respond, safe


def _model_status():
    try:
        body = model_client.health()
        return {'reachable': True, 'model_version': body.get('model_version'),
                'default_model': body.get('default_model'), 'models': body.get('models', [])}
    except model_client.ModelError:
        return {'reachable': False, 'model_version': None, 'default_model': None, 'models': []}


def _history_status():
    if not history_repo.enabled():
        return None
    try:
        history_repo.list_for_session('__health__', limit=1)
        return True
    except Exception:
        return False


@safe
def handler(event, context):
    model = _model_status()
    cache_ok = cache.ping()
    history_ok = _history_status()
    status = 'down' if not model['reachable'] else 'degraded' if False in (cache_ok, history_ok) else 'ok'
    available = [m for m in model['models'] if m.get('id') in config.MODELS]
    return respond(503 if status == 'down' else 200, {
        'status': status,
        'model_id': config.MODEL_ID,
        'default_model': config.DEFAULT_MODEL,
        'models': available,
        'model': {'reachable': model['reachable'], 'model_version': model['model_version']},
        'cache': {'reachable': cache_ok},
        'history': {'reachable': history_ok},
    })
