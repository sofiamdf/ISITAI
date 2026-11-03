'''Caché de resultados sobre DynamoDB (reemplaza a ElastiCache/Valkey).

Misma interfaz que la versión con Valkey: result_key, get_result, put_result y ping.
Si la caché falla, se registra y el análisis sigue sin ella.
'''
import json
import logging
import os
import time

import boto3

log = logging.getLogger(__name__)

_table = None
_disabled_until = 0.0  


def _get_table():
    global _table
    if _table is None:
        _table = boto3.resource('dynamodb').Table(os.environ['CACHE_TABLE'])
    return _table


def _available():
    return time.monotonic() >= _disabled_until


def _trip():
    global _disabled_until
    _disabled_until = time.monotonic() + 30


def result_key(model_id, model, sha256):
    return f'isitai:v1:{model_id}:{model}:{sha256}'

def get_result(key, ttl_seconds):
    '''Devuelve el resultado y renueva su TTL; None si no está, venció o la caché falla.'''
    if not _available():
        return None
    try:
        item = _get_table().get_item(Key={'cache_key': key}).get('Item')
        if not item:
            return None
        now = int(time.time())
        # DynamoDB borra por TTL con demora (hasta ~48 h): se vuelve a chequear acá.
        if int(item['expires_at']) <= now:
            return None
        # Equivale al GETEX de Valkey: cada acierto renueva el TTL. Si falla, no importa.
        try:
            _get_table().update_item(
                Key={'cache_key': key},
                UpdateExpression='SET expires_at = :e',
                ExpressionAttributeValues={':e': now + ttl_seconds},
            )
        except Exception:
            log.warning('cache_renew_failed', exc_info=True)
        return json.loads(item['value'])
    except Exception:
        log.warning('cache_get_failed', exc_info=True)
        _trip()
        return None


def put_result(key, value, ttl_seconds):
    if not _available():
        return
    try:
        _get_table().put_item(Item={
            'cache_key': key,
            'value': json.dumps(value), 
            'expires_at': int(time.time()) + ttl_seconds,
        })
    except Exception:
        log.warning('cache_set_failed', exc_info=True)
        _trip()


def ping():
    try:
        _get_table().get_item(Key={'cache_key': '__ping__'})
        return True
    except Exception:
        log.warning('cache_ping_failed', exc_info=True)
        return False
