import { useEffect, useState } from 'react';
import { ApiError, friendlyMessage, getHistory } from '../api/client';
import { HISTORY_PAGE_SIZE } from '../api/config';
import type { HistoryItem, Label } from '../api/types';

const SHORT: Record<Label, string> = { ai: 'IA', real: 'Real', uncertain: 'Incierto' };

interface Problem {
  disabled: boolean; // true cuando el despliegue no tiene tabla de historial (no es un fallo)
  message: string;
}

function toProblem(e: unknown): Problem {
  return {
    disabled: e instanceof ApiError && e.code === 'history_disabled',
    message: friendlyMessage(e),
  };
}

// refreshKey: cada vez que cambia (porque se hizo un análisis nuevo), se vuelve a pedir la lista.
export default function History({ refreshKey }: { refreshKey: number }) {
  const [items, setItems] = useState<HistoryItem[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(true); // solo para la primera carga
  const [loadingMore, setLoadingMore] = useState(false);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    let cancelled = false;
    getHistory(HISTORY_PAGE_SIZE)
      .then((page) => {
        if (cancelled) return;
        setItems(page.items);
        setNextCursor(page.next_cursor);
        setProblem(null);
      })
      .catch((e) => {
        if (!cancelled) setProblem(toProblem(e));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [refreshKey, retry]);

  async function loadMore() {
    if (!nextCursor) return;
    setLoadingMore(true);
    try {
      const page = await getHistory(HISTORY_PAGE_SIZE, nextCursor);
      setItems((prev) => [...prev, ...page.items]);
      setNextCursor(page.next_cursor);
    } catch (e) {
      setProblem(toProblem(e));
    } finally {
      setLoadingMore(false);
    }
  }

  return (
    <section className="history" aria-labelledby="history-title">
      <h2 id="history-title">Historial de esta sesión</h2>

      {loading && <p className="muted">Cargando historial…</p>}

      {!loading && problem?.disabled && (
        <p className="muted">El historial no está disponible en este entorno.</p>
      )}

      {!loading && problem && !problem.disabled && (
        <div className="banner banner-error" role="alert">
          <span>{problem.message}</span>
          <button type="button" className="btn-link" onClick={() => setRetry((n) => n + 1)}>
            Reintentar
          </button>
        </div>
      )}

      {!loading && !problem && items.length === 0 && (
        <p className="muted">Todavía no analizaste ninguna imagen.</p>
      )}

      {items.length > 0 && (
        <ul className="history-list">
          {items.map((item) => (
            <li key={item.request_id} className={`history-item history-${item.label}`}>
              <span className="history-name" title={item.file_name}>
                {item.file_name || 'Sin nombre'}
              </span>
              <span className="history-verdict">
                {SHORT[item.label]} · {Math.round(item.prob_ai * 100)}% IA
              </span>
              <span className="history-meta">
                {item.model ?? '—'}
                {item.cache_hit ? ' · desde caché' : ''} · {item.latency_ms} ms ·{' '}
                {new Date(item.requested_at).toLocaleString('es-UY')}
              </span>
            </li>
          ))}
        </ul>
      )}

      {nextCursor && (
        <button type="button" className="btn btn-secondary" disabled={loadingMore} onClick={loadMore}>
          {loadingMore ? 'Cargando…' : 'Ver más'}
        </button>
      )}
    </section>
  );
}