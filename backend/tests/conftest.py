import base64
import itertools
import json
import threading

import pytest

from local_server import make_server

PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==')
PNG_SHA256 = '497790947d4666760ce38f3c00e852c71fdb66cae849bae8e9ede352719e1581'
_ids = itertools.count()


class Ctx:
    def __init__(self):
        self.aws_request_id = f'req-{next(_ids)}'


def api_event(body=PNG, content_type='image/png', b64=True, query=None, session='prueba-1234', method='POST'):
    headers = {'content-type': content_type}
    if session is not None:
        headers['x-session-id'] = session
    return {
        'headers': headers,
        'queryStringParameters': query,
        'requestContext': {'http': {'method': method}},
        'isBase64Encoded': b64,
        'body': base64.b64encode(body).decode() if b64 else body.decode('latin-1'),
    }


def url_event(method, path, body=None, key='clave'):
    return {
        'rawPath': path,
        'headers': {'x-api-key': key, 'content-type': 'application/json'},
        'requestContext': {'http': {'method': method, 'path': path}},
        'isBase64Encoded': False,
        'body': json.dumps(body) if body is not None else None,
    }


def parse(response):
    return response['statusCode'], json.loads(response['body'])


@pytest.fixture
def serve():
    servers = []

    def start(handler_fn):
        server = make_server(handler_fn)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        servers.append(server)
        return f'http://127.0.0.1:{server.server_port}'

    yield start
    for server in servers:
        server.shutdown()


def backend_schema_errors(schema, body):
    from pathlib import Path

    import yaml
    from jsonschema import Draft202012Validator
    from referencing import Registry, Resource
    from referencing.jsonschema import DRAFT202012

    spec = yaml.safe_load((Path(__file__).resolve().parents[2] / 'docs' / 'backend-api.yaml').read_text(encoding='utf-8'))
    registry = Registry().with_resource('urn:backend-api', Resource.from_contents(spec, default_specification=DRAFT202012))
    validator = Draft202012Validator({'$ref': f'urn:backend-api#/components/schemas/{schema}'}, registry=registry)
    return [e.message for e in validator.iter_errors(body)]
