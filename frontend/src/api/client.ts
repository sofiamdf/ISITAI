import { getSessionId } from '../session';
import { ALLOWED_TYPES, API_URL, MAX_IMAGE_BYTES, USE_FAKE_API } from './config';
import type { AnalysisResult, Health, HistoryItem, HistoryPage, ModelName } from './types';

// ---------- Errores ----------

export class ApiError extends Error {
  status: number; // código HTTP (0 si ni siquiera hubo respuesta)
  code: string; // "too_large", "model_timeout", "network", etc.

  constructor(status: number, code: string, message: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

const FRIENDLY: Record<string, string> = {
  unsupported_type: 'Solo se aceptan imágenes JPEG, PNG o WebP.',
  content_mismatch: 'El contenido del archivo no coincide con su tipo. ¿Es una imagen válida?',
  empty_body: 'El archivo está vacío.',
  too_large: 'La imagen supera el máximo de 4 MiB. Intentá de nuevo con una imagen más pequeña.',
  model_error: 'El modelo falló al analizar la imagen. Probá de nuevo.',
  model_timeout: 'El modelo tardó demasiado en responder. Probá de nuevo en un rato.',
  rate_limited: 'Demasiados pedidos seguidos. Esperá unos segundos.',
  history_disabled: 'El historial no está disponible en este entorno.',
  timeout: 'El servidor tardó demasiado en responder.',
  network: 'No se pudo conectar con el servidor.',
};

export function friendlyMessage(err: unknown): string {
  if (err instanceof ApiError) {
    return FRIENDLY[err.code] ?? 'Ocurrió un error inesperado. Probá de nuevo.';
  }
  return 'Ocurrió un error inesperado. Probá de nuevo.';
}

// El backend responde errores como {"error": {"code", "message"}},
// pero API Gateway (404, 429) responde {"message": "..."}. Hay que aceptar las dos formas.
async function toApiError(res: Response): Promise<ApiError> {
  let code = `http_${res.status}`;
  let message = res.statusText;
  try {
    const body = await res.json();
    if (body?.error?.code) {
      code = body.error.code;
      message = body.error.message;
    } else if (typeof body?.message === 'string') {
      message = body.message;
    }
  } catch {
    // el cuerpo no era JSON: nos quedamos con los valores por defecto
  }
  if (res.status === 429) code = 'rate_limited';
  return new ApiError(res.status, code, message);
}

// ---------- Pedido genérico con timeout ----------

// API Gateway corta a los 30 s, así que no tiene sentido esperar más.
async function request(path: string, init: RequestInit = {}): Promise<Response> {
  if (!API_URL) {
    throw new ApiError(0, 'network', 'Falta configurar VITE_API_URL');
  }
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 30_000);
  try {
    return await fetch(`${API_URL}${path}`, { ...init, signal: controller.signal });
  } catch (e) {
    if (e instanceof DOMException && e.name === 'AbortError') {
      throw new ApiError(0, 'timeout', 'Timeout');
    }
    throw new ApiError(0, 'network', 'No se pudo conectar');
  } finally {
    clearTimeout(timer);
  }
}

// ---------- Validación previa en el navegador ----------

// Devuelve un mensaje de error, o null si el archivo está bien.
export function validateImage(file: File): string | null {
  if (!ALLOWED_TYPES.includes(file.type)) return FRIENDLY.unsupported_type;
  if (file.size === 0) return FRIENDLY.empty_body;
  if (file.size > MAX_IMAGE_BYTES) return FRIENDLY.too_large;
  return null;
}

// ---------- Funciones públicas ----------

export async function getHealth(): Promise<Health> {
  if (USE_FAKE_API) return fakeHealth();
  const res = await request('/v1/health');
  // Con status "down" el backend responde 503 pero con el mismo formato de Health.
  if (res.ok || res.status === 503) return (await res.json()) as Health;
  throw await toApiError(res);
}

export async function analyzeImage(file: File, model?: ModelName): Promise<AnalysisResult> {
  if (USE_FAKE_API) return fakeAnalyze(file, model);
  const query = model ? `?model=${encodeURIComponent(model)}` : '';
  const res = await request(`/v1/analyze${query}`, {
    method: 'POST',
    headers: {
      'Content-Type': file.type,
      'X-Session-Id': getSessionId(),
      'X-File-Name': encodeURIComponent(file.name),
    },
    body: file, // los bytes originales, sin recomprimir
  });
  if (!res.ok) throw await toApiError(res);
  return (await res.json()) as AnalysisResult;
}

// limit = cuántas filas; cursor = el next_cursor de la página anterior (para pedir la siguiente).
export async function getHistory(limit: number, cursor?: string): Promise<HistoryPage> {
  if (USE_FAKE_API) return fakeHistory(limit, cursor);
  const params = new URLSearchParams({ limit: String(limit) });
  if (cursor) params.set('cursor', cursor);
  const res = await request(`/v1/history?${params}`, {
    headers: { 'X-Session-Id': getSessionId() },
  });
  if (!res.ok) throw await toApiError(res);
  return (await res.json()) as HistoryPage;
}

// ---------- Modo API falsa ----------

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));
const fakeStore: HistoryItem[] = []; 

async function fakeHealth(): Promise<Health> {
  await sleep(300);
  return {
    status: 'ok',
    model_id: 'mock',
    default_model: 'resnet18',
    models: [
      { id: 'mlp', version: 'mock-0.1' },
      { id: 'cnn', version: 'mock-0.1' },
      { id: 'resnet18', version: 'mock-0.1' },
    ],
    model: { reachable: true, model_version: 'mock-0.1' },
    cache: { reachable: null },
    history: { reachable: null },
  };
}

async function fakeAnalyze(file: File, model: ModelName = 'resnet18'): Promise<AnalysisResult> {
  await sleep(800);
  const digest = await crypto.subtle.digest('SHA-256', await file.arrayBuffer());
  const sha256 = [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, '0')).join('');
  const result: AnalysisResult = {
    request_id: crypto.randomUUID(),
    sha256,
    label: 'uncertain',
    prob_ai: 0.5,
    prob_real: 0.5,
    model,
    model_version: 'mock-0.1',
    cache_hit: false,
    latency_ms: 800,
    analyzed_at: new Date().toISOString(),
  };
  fakeStore.unshift({
    requested_at: result.analyzed_at,
    request_id: result.request_id,
    sha256: result.sha256,
    file_name: file.name,
    label: result.label,
    prob_ai: result.prob_ai,
    model: result.model,
    model_version: result.model_version,
    cache_hit: result.cache_hit,
    latency_ms: result.latency_ms,
  });
  return result;
}

async function fakeHistory(limit: number, cursor?: string): Promise<HistoryPage> {
  await sleep(300);
  const start = cursor ? Number(cursor) : 0;
  const end = start + limit;
  return {
    items: fakeStore.slice(start, end),
    next_cursor: end < fakeStore.length ? String(end) : null,
  };
}