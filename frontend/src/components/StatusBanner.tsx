import type { Health } from '../api/types';

interface Props {
  health: Health | null;
  error: string | null; // error al pedir /v1/health (no se pudo ni conectar)
  onRetry: () => void;
}

export default function StatusBanner({ health, error, onRetry }: Props) {
  if (error) {
    return (
      <div className="banner banner-error" role="alert">
        <span>{error} No sabemos si el servicio está disponible.</span>
        <button type="button" className="btn-link" onClick={onRetry}>
          Reintentar
        </button>
      </div>
    );
  }

  if (!health) {
    return <div className="banner banner-info">Conectando con el servicio…</div>;
  }

  return (
    <>
      {health.status === 'down' && (
        <div className="banner banner-error" role="alert">
          El modelo no está respondiendo en este momento. Probá de nuevo en unos minutos.
        </div>
      )}
      {health.status === 'degraded' && (
        <div className="banner banner-warn">
          Servicio degradado: alguna función auxiliar (caché o historial) no responde, pero se puede
          analizar igual.
        </div>
      )}
      {health.model_id === 'mock' && (
        <div className="banner banner-info">
          Modo de prueba: el modelo es simulado y los resultados no son reales.
        </div>
      )}
    </>
  );
}