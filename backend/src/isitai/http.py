import functools
import json
import logging
from decimal import Decimal

log = logging.getLogger(__name__)


def _default(value):
    if isinstance(value, Decimal):
        return float(value)
    return str(value)


def respond(status, body):
    return {'statusCode': status, 'headers': {'Content-Type': 'application/json'}, 'body': json.dumps(body, default=_default)}


def error(status, code, message):
    return respond(status, {'error': {'code': code, 'message': message}})


def safe(handler):
    @functools.wraps(handler)
    def wrapper(event, context):
        try:
            return handler(event, context)
        except Exception:
            log.exception('unhandled_error')
            return error(500, 'internal_error', 'Error interno. Intente de nuevo más tarde.')
    return wrapper


def lower_headers(event):
    return {k.lower(): v for k, v in (event.get('headers') or {}).items()}
