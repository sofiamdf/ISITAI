import base64
import sys
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

HERE = Path(__file__).resolve().parent


class Context:
    def __init__(self):
        self.aws_request_id = str(uuid.uuid4())


def make_server(handler_fn, port=0, cors=False):
    class Adapter(BaseHTTPRequestHandler):
        def _send(self, status, headers, data):
            self.send_response(status)
            for key, value in headers.items():
                self.send_header(key, value)
            if cors:
                self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _handle(self, method):
            length = int(self.headers.get('Content-Length') or 0)
            body = self.rfile.read(length) if length else b''
            url = urlsplit(self.path)
            event = {
                'version': '2.0', 'rawPath': url.path, 'rawQueryString': url.query,
                'queryStringParameters': dict(parse_qsl(url.query)) or None,
                'headers': {k.lower(): v for k, v in self.headers.items()},
                'requestContext': {'http': {'method': method, 'path': url.path}},
                'body': base64.b64encode(body).decode() if body else None,
                'isBase64Encoded': bool(body),
            }
            result = handler_fn(event, Context())
            text = result.get('body') or ''
            data = base64.b64decode(text) if result.get('isBase64Encoded') else text.encode()
            self._send(result.get('statusCode', 200), result.get('headers') or {}, data)

        def do_GET(self):
            self._handle('GET')

        def do_POST(self):
            self._handle('POST')

        def do_OPTIONS(self):
            self._send(204, {'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
                             'Access-Control-Allow-Headers': 'content-type, x-session-id, x-file-name'}, b'')

        def log_message(self, *args):
            pass

    return ThreadingHTTPServer(('127.0.0.1', port), Adapter)


def api_router():
    sys.path.insert(0, str(HERE / 'src'))
    from isitai.handlers import analyze, health, history
    routes = {('POST', '/v1/analyze'): analyze.handler, ('GET', '/v1/history'): history.handler,
              ('GET', '/v1/health'): health.handler}

    def route(event, context):
        target = routes.get((event['requestContext']['http']['method'], event['rawPath']))
        if target is None:
            return {'statusCode': 404, 'body': '{"message":"Not Found"}'}
        return target(event, context)
    return route


def load_handler(kind):
    if kind == 'api':
        return api_router()
    folders = {'mock': 'mock_model', 'model': 'model_api'}
    if kind not in folders:
        raise SystemExit('Uso: python local_server.py mock|model|api [puerto]')
    sys.path.insert(0, str(HERE / folders[kind]))
    import handler
    return handler.handler


if __name__ == '__main__':
    kind = sys.argv[1] if len(sys.argv) > 1 else ''
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8001
    server = make_server(load_handler(kind), port, cors=kind == 'api')
    print(f'{kind} en http://127.0.0.1:{port} (Ctrl+C para cortar)')
    server.serve_forever()
