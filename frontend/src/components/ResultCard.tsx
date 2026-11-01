import type { AnalysisResult, Label } from '../api/types';

const VERDICT: Record<Label, string> = {
  ai: 'Probablemente generada por IA',
  real: 'Probablemente real',
  uncertain: 'No concluyente',
};

export default function ResultCard({ result }: { result: AnalysisResult }) {
  const pctAi = Math.round(result.prob_ai * 100);
  const pctReal = Math.round(result.prob_real * 100);

  return (
    <section className={`result result-${result.label}`} aria-live="polite">
      <h2 className="result-title">{VERDICT[result.label]}</h2>

      <div
        className="meter"
        role="meter"
        aria-label="Probabilidad de que la imagen sea generada por IA"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={pctAi}
      >
        <div className="meter-fill" style={{ width: `${pctAi}%` }} />
      </div>
      <div className="meter-labels">
        <span>Real {pctReal}%</span>
        <span>IA {pctAi}%</span>
      </div>

      <dl className="details">
        <div>
          <dt>Modelo</dt>
          <dd>
            {result.model} ({result.model_version})
          </dd>
        </div>
        <div>
          <dt>Tiempo</dt>
          <dd>{result.latency_ms} ms</dd>
        </div>
        <div>
          <dt>Origen</dt>
          <dd>{result.cache_hit ? 'Desde caché' : 'Calculado ahora'}</dd>
        </div>
        <div>
          <dt>Fecha</dt>
          <dd>{new Date(result.analyzed_at).toLocaleString('es-UY')}</dd>
        </div>
        <div>
          <dt>SHA-256</dt>
          <dd title={result.sha256}>{result.sha256.slice(0, 12)}…</dd>
        </div>
      </dl>
    </section>
  );
}