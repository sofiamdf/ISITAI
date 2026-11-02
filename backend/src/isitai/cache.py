import json
import logging
import os
import time

from isitai import config

log = logging.getLogger(__name__)
_state = {'client': None, 'disabled_until': 0.0}


def enabled():
    return bool(config.CACHE_ENDPOINT)


def _available():
    return enabled() and time.monotonic() >= _state['disabled_until']


def _trip(op):
    log.warning('cache_%s_failed', op, exc_info=True)
    _state['client'] = None
    _state['disabled_until'] = time.monotonic() + 30


def _connect():
    import valkey
    from developer_toolkit_elasticache import ElastiCacheIAMAuthTokenProvider
    from valkey.credentials import CredentialProvider

    class IamCredentials(CredentialProvider):
        def __init__(self, auth):
            self._auth = auth

        def get_credentials(self):
            # Un token nuevo por conexión: los tokens IAM duran 15 minutos
            return self._auth.user_id, self._auth.get_token()

    auth = ElastiCacheIAMAuthTokenProvider(serverless_cache_name=config.CACHE_NAME, user_id=config.CACHE_USER,
                                           region=os.environ.get('AWS_REGION'))
    return valkey.ValkeyCluster(host=config.CACHE_ENDPOINT, port=6379, ssl=True,
                                credential_provider=IamCredentials(auth),
                                socket_connect_timeout=2, socket_timeout=1)


def _client():
    if _state['client'] is None:
        _state['client'] = _connect()
    return _state['client']


def result_key(model_id, model, sha256):
    return f'isitai:v1:{model_id}:{model}:{sha256}'


def get_result(key, ttl_seconds):
    if not _available():
        return None
    try:
        raw = _client().getex(key, ex=ttl_seconds)
    except Exception:
        _trip('get')
        return None
    return json.loads(raw) if raw else None


def put_result(key, value, ttl_seconds):
    if not _available():
        return
    try:
        _client().set(key, json.dumps(value), ex=ttl_seconds)
    except Exception:
        _trip('set')


def ping():
    if not enabled():
        return None
    try:
        return bool(_client().ping())
    except Exception:
        _trip('ping')
        return False
