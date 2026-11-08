import argparse
import concurrent.futures as cf
import json
import os
import struct
import subprocess
import time
import urllib.error
import urllib.request
import zlib

# nombre: (ancho, alto, fracción de filas con ruido). El ruido fija el peso del archivo y los píxeles, el trabajo
# de decodificar: "foto" imita una foto de celular de 12 MP y unos 3 MB.
SIZES = {
    'chica': (64, 64, 1.0),
    'mediana': (1280, 960, 0.1),
    'foto': (4000, 3000, 0.08),
    'maxima': (4000, 3000, 0.11),
}
REPORT = ('filter @type = "REPORT" | stats count() as n, pct(@billedDuration, 50) as facturado_p50, '
          'max(@maxMemoryUsed) / 1000000 as memoria_mb, max(@initDuration) as init_ms')


def png(w, h, frac):
    noisy = {int(i / frac) for i in range(int(h * frac))}
    flat = b'\x80' * (w * 3)
    raw = b''.join(b'\x00' + (os.urandom(w * 3) if y in noisy else flat) for y in range(h))

    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))
    header = struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0)
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', header) + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b'')


def analyze(api, image, model, session):
    request = urllib.request.Request(f'{api}/v1/analyze?model={model}', data=image, method='POST',
                                     headers={'Content-Type': 'image/png', 'X-Session-Id': session})
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=35) as response:
            status, body = response.status, json.loads(response.read())
    except urllib.error.HTTPError as exc:
        status = exc.code
        try:
            body = json.loads(exc.read() or b'{}')
        except ValueError:
            body = {}
    except (urllib.error.URLError, TimeoutError) as exc:
        status, body = 0, {'error': str(exc)}
    return status, body, (time.perf_counter() - started) * 1000


def pct(values, q):
    values = sorted(values)
    return round(values[round(q * (len(values) - 1))]) if values else '-'


def stats(rows):
    ok = [r for r in rows if r[0] == 200]
    codes = {}
    for r in rows:
        codes[r[0]] = codes.get(r[0], 0) + 1
    return {'codigos': codes, 'cliente_p50': pct([r[2] for r in ok], 0.5), 'cliente_p95': pct([r[2] for r in ok], 0.95),
            'servidor_p50': pct([r[1]['latency_ms'] for r in ok], 0.5),
            'aciertos': sum(1 for r in ok if r[1].get('cache_hit'))}


def insights(group, window):
    query = subprocess.run(['aws', 'logs', 'start-query', '--log-group-name', group, '--start-time', str(int(window[0])),
                            '--end-time', str(int(window[1]) + 1), '--query-string', REPORT,
                            '--query', 'queryId', '--output', 'text'], capture_output=True, text=True, check=True)
    while True:
        time.sleep(2)
        result = json.loads(subprocess.run(['aws', 'logs', 'get-query-results', '--query-id', query.stdout.strip(),
                                            '--output', 'json'], capture_output=True, text=True, check=True).stdout)
        if result['status'] in ('Complete', 'Failed', 'Cancelled', 'Timeout'):
            break
    rows = result.get('results') or [[]]
    return {f['field']: f['value'] for f in rows[0]}


def tamanos(args):
    session = f'pruebas-{int(time.time())}'
    blocks = []
    for model in args.models:
        for name, spec in SIZES.items():
            images = [png(*spec) for _ in range(args.n)]
            time.sleep(1.2)
            t0 = time.time()
            new = [analyze(args.api, image, model, session) for image in images]
            t1 = time.time()
            time.sleep(1.2)
            t2 = time.time()
            repeated = [analyze(args.api, images[0], model, session) for _ in range(args.n)]
            t3 = time.time()
            blocks.append({'modelo': model, 'imagen': name, 'kb': len(images[0]) // 1024, 'primero': new[0],
                           'nuevas': stats(new), 'repetidas': stats(repeated), 'v_nuevas': (t0, t1), 'v_rep': (t2, t3)})
            print(f'{model:9} {name:8} {len(images[0]) // 1024:5} KB  nuevas {blocks[-1]["nuevas"]}  '
                  f'repetidas {blocks[-1]["repetidas"]}', flush=True)
    for model in args.models:
        first = next(b['primero'] for b in blocks if b['modelo'] == model)
        print(f'Primer pedido a {model}: HTTP {first[0]}, servidor {first[1].get("latency_ms")} ms, cliente {first[2]:.0f} ms')
    if args.sin_logs:
        return
    print('Esperando 90 s a que CloudWatch reciba los logs...', flush=True)
    time.sleep(90)
    print('modelo    imagen      KB | modelo: n facturado_p50 memoria_mb init_ms | analyze nueva: facturado_p50 | '
          'analyze repetida: facturado_p50')
    for b in blocks:
        m = insights('/aws/lambda/isitai-model', b['v_nuevas'])
        a = insights('/aws/lambda/isitai-analyze', b['v_nuevas'])
        r = insights('/aws/lambda/isitai-analyze', b['v_rep'])
        print(f'{b["modelo"]:9} {b["imagen"]:8} {b["kb"]:5} | {m.get("n")} {m.get("facturado_p50")} '
              f'{m.get("memoria_mb")} {m.get("init_ms")} | {a.get("facturado_p50")} | {r.get("facturado_p50")}', flush=True)


def carga(args):
    session = f'carga-{int(time.time())}'
    total = args.rate * args.seconds
    images = [png(*SIZES['chica']) for _ in range(total + args.burst)]
    with cf.ThreadPoolExecutor(max_workers=50) as pool:
        started = time.perf_counter()
        futures = []
        for i in range(total):
            delay = started + i / args.rate - time.perf_counter()
            if delay > 0:
                time.sleep(delay)
            futures.append(pool.submit(analyze, args.api, images[i], args.model, session))
        sustained = [f.result() for f in futures]
    print(f'Sostenida, {args.rate} por segundo durante {args.seconds} s: {stats(sustained)}', flush=True)
    time.sleep(5)
    with cf.ThreadPoolExecutor(max_workers=args.burst) as pool:
        burst = list(pool.map(lambda image: analyze(args.api, image, args.model, session), images[total:]))
    print(f'Ráfaga de {args.burst} simultáneos: {stats(burst)}', flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('modo', choices=['tamanos', 'carga'])
    parser.add_argument('api')
    parser.add_argument('--models', nargs='+', default=['mlp', 'cnn', 'resnet18'])
    parser.add_argument('--model', default='resnet18')
    parser.add_argument('--n', type=int, default=5)
    parser.add_argument('--rate', type=int, default=10)
    parser.add_argument('--seconds', type=int, default=30)
    parser.add_argument('--burst', type=int, default=40)
    parser.add_argument('--sin-logs', action='store_true')
    args = parser.parse_args()
    args.api = args.api.rstrip('/')
    tamanos(args) if args.modo == 'tamanos' else carga(args)


if __name__ == '__main__':
    main()
