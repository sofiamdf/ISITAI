import base64
import binascii
import json
import logging
import time
from decimal import Decimal

from isitai import config

log = logging.getLogger(__name__)
_state = {'table': None}


def enabled():
    return bool(config.HISTORY_TABLE)


def _table():
    if _state['table'] is None:
        import boto3
        _state['table'] = boto3.resource('dynamodb').Table(config.HISTORY_TABLE)
    return _state['table']


def save(session_id, requested_at, item):
    if not enabled():
        return
    record = {
        'session_id': session_id,
        'sk': requested_at + '#' + item['request_id'],
        'requested_at': requested_at,
        'request_id': item['request_id'],
        'sha256': item['sha256'],
        'file_name': item.get('file_name', ''),
        'content_type': item['content_type'],
        'size_bytes': item['size_bytes'],
        'label': item['label'],
        'prob_ai': Decimal(str(item['prob_ai'])),
        'model': item['model'],
        'model_version': item['model_version'],
        'cache_hit': item['cache_hit'],
        'latency_ms': item['latency_ms'],
        'expires_at': int(time.time()) + config.HISTORY_RETENTION_DAYS * 86400,
    }
    try:
        _table().put_item(Item=record)
    except Exception:
        log.exception('history_save_failed')


def _decode_cursor(cursor):
    try:
        key = json.loads(base64.urlsafe_b64decode(cursor.encode()))
    except (binascii.Error, UnicodeDecodeError, ValueError) as exc:
        raise ValueError('cursor inválido') from exc
    if not isinstance(key, dict) or set(key) != {'session_id', 'sk'}:
        raise ValueError('cursor inválido')
    return key


def list_for_session(session_id, limit=20, cursor=None):
    from boto3.dynamodb.conditions import Key
    params = {'KeyConditionExpression': Key('session_id').eq(session_id), 'ScanIndexForward': False, 'Limit': limit}
    if cursor:
        start = _decode_cursor(cursor)
        if start['session_id'] != session_id:
            raise ValueError('cursor de otra sesión')
        params['ExclusiveStartKey'] = start
    response = _table().query(**params)
    last_key = response.get('LastEvaluatedKey')
    next_cursor = base64.urlsafe_b64encode(json.dumps(last_key).encode()).decode() if last_key else None
    return response['Items'], next_cursor
