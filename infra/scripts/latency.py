import argparse
import json
import os
import statistics
import struct
import time
import urllib.error
import urllib.request
import zlib


def random_png(size=64):
    raw = b''.join(b'\x00' + os.urandom(size * 3) for _ in range(size))

    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))
    header = struct.pack('>IIBBBBB', size, size, 8, 2, 0, 0, 0)
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', header) + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b'')


def analyze(api, image, model, session):
    request = urllib.request.Request(f'{api}/v1/analyze?model={model}', data=image, method='POST',
                                     headers={'Content-Type': 'image/png', 'X-Session-Id': session})
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=35) as response:
            body = json.loads(response.read())
            status = response.status
    except urllib.error.HTTPError as exc:
        body, status = json.loads(exc.read() or b'{}'), exc.code
    return status, body, (time.perf_counter() - started) * 1000


def summary(name, rows):
    ok = [r for r in rows if r[0] == 200]
    if not ok:
        print(f'{name}: ningún 200; primer error: {rows[0][1] if rows else "-"}')
        return
    client = [r[2] for r in ok]
    server = [r[1]['latency_ms'] for r in ok]
    hits = sum(1 for r in ok if r[1]['cache_hit'])
    p95 = statistics.quantiles(client, n=20)[-1] if len(client) >= 2 else client[0]
    print(f'{name}: {len(ok)}/{len(rows)} OK, aciertos de caché {hits}; cliente p50 {statistics.median(client):.0f} ms '
          f'p95 {p95:.0f} ms; servidor (latency_ms) p50 {statistics.median(server):.0f} ms')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('api')
    parser.add_argument('--model', default='resnet18')
    parser.add_argument('--misses', type=int, default=20)
    parser.add_argument('--hits', type=int, default=40)
    args = parser.parse_args()
    api = args.api.rstrip('/')
    session = f'latency-{int(time.time())}'
    misses = [analyze(api, random_png(), args.model, session) for _ in range(args.misses)]
    image = random_png()
    hits = [analyze(api, image, args.model, session) for _ in range(args.hits + 1)][1:]  # el 1.º llena la caché
    summary('sin caché (imágenes nuevas)', misses)
    summary('misma imagen repetida', hits)


if __name__ == '__main__':
    main()
