'''Caché de resultados sobre DynamoDB (reemplaza a ElastiCache/Valkey).

Sin CACHE_TABLE configurada la caché queda deshabilitada: get_result devuelve None,
put_result no hace nada y ping devuelve None ("no configurada", distinto de False = caída).
Si DynamoDB falla, se registra y se saltea la caché durante 30 s.
'''
import json
import logging
import time

import boto3

from isitai import config

log = logging.getLogger(__name__)

_state = {'client': None, 'disabled_until': 0.0}


def _connect():
    return boto3.resource('dynamodb').Table(config.CACHE_TABLE)


def _table():
    if _state['client'] is None:
        _state['client'] = _connect()
    return _state['client']


def _active():
    return bool(config.CACHE_TABLE) and time.monotonic() >= _state['disabled_until']


def _trip():
    _state['client'] = None
    _state['disabled_until'] = time.monotonic() + 30


def result_key(model_id, model, sha256):
    return f'isitai:v1:{model_id}:{model}:{sha256}'


def get_result(key, ttl_seconds):
    '''Devuelve el resultado y renueva su TTL; None si no está, venció, o la caché falla o no está configurada.'''
    if not _active():
        return None
    try:
        item = _table().get_item(Key={'cache_key': key}).get('Item')
        if not item:
            return None
        now = int(time.time())
        # DynamoDB borra por TTL con demora (hasta ~48 h): se vuelve a chequear acá.
        if int(item['expires_at']) <= now:
            return None
        value = json.loads(item['value'])
    except Exception:
        log.warning('cache_get_failed', exc_info=True)
        _trip()
        return None
    # Equivale al GETEX de Valkey: cada acierto renueva el TTL. Si falla, el resultado igual sirve.
    try:
        _table().update_item(
            Key={'cache_key': key},
            UpdateExpression='SET expires_at = :e',
            ExpressionAttributeValues={':e': now + ttl_seconds},
        )
    except Exception:
        log.warning('cache_renew_failed', exc_info=True)
    return value


def put_result(key, value, ttl_seconds):
    if not _active():
        return
    try:
        _table().put_item(Item={
            'cache_key': key,
            'value': json.dumps(value),  # como texto: evita problemas de Decimal
            'expires_at': int(time.time()) + ttl_seconds,
        })
    except Exception:
        log.warning('cache_set_failed', exc_info=True)
        _trip()


def ping():
    '''True si responde, False si está caída, None si no está configurada.'''
    if not config.CACHE_TABLE:
        return None
    try:
        _table().get_item(Key={'cache_key': '__ping__'})
        return True
    except Exception:
        log.warning('cache_ping_failed', exc_info=True)
        return False