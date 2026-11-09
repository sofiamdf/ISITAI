import { useEffect, useState } from 'react';
import './App.css';
import { analyzeImage, friendlyMessage, getHealth, validateImage } from './api/client';
import type { AnalysisResult, Health, ModelName } from './api/types';
import History from './components/History';
import ImagePicker from './components/ImagePicker';
import ModelSelect from './components/ModelSelect';
import ResultCard from './components/ResultCard';
import StatusBanner from './components/StatusBanner';

export default function App() {
  const subtitle = '¿Esta imagen es real o la generó una IA?';
  const [typedSubtitle, setTypedSubtitle] = useState(() =>
    window.matchMedia('(prefers-reduced-motion: reduce)').matches ? subtitle : '',
  );

  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

    let character = 0;
    const timer = window.setInterval(() => {
      character += 1;
      setTypedSubtitle(subtitle.slice(0, character));
      if (character >= subtitle.length) window.clearInterval(timer);
    }, 60);

    return () => window.clearInterval(timer);
  }, []);

  // Estado del servicio (GET /v1/health)
  const [health, setHealth] = useState<Health | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [healthTry, setHealthTry] = useState(0); // al subirlo se vuelve a pedir el health

  // Lo que eligió la persona
  const [model, setModel] = useState<ModelName | ''>('');
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);

  // Resultado del análisis
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [historyKey, setHistoryKey] = useState(0); // al subirlo, el historial se vuelve a pedir

  // Al abrir la página (y cada vez que se reintenta), pedir el health.
  useEffect(() => {
    let cancelled = false; // evita actualizar el estado si el componente ya se cerró
    getHealth()
      .then((h) => {
        if (cancelled) return;
        setHealth(h);
        setHealthError(null);
        setModel((current) => current || h.default_model); // preselecciona el predeterminado
      })
      .catch((e) => {
        if (!cancelled) setHealthError(friendlyMessage(e));
      });
    return () => {
      cancelled = true;
    };
  }, [healthTry]);

  function handleFile(chosen: File) {
    const problem = validateImage(chosen);
    if (problem) {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
      setFile(null);
      setPreviewUrl(null);
      setResult(null);
      setError(problem);
      return;
    }
    if (previewUrl) URL.revokeObjectURL(previewUrl); // libera la vista previa anterior
    setFile(chosen);
    setPreviewUrl(URL.createObjectURL(chosen));
    setResult(null);
    setError(null);
  }

  async function handleAnalyze() {
    if (!file) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      setResult(await analyzeImage(file, model || undefined));
      setHistoryKey((k) => k + 1); // el backend ya guardó este análisis: refrescar la lista
    } catch (e) {
      setError(friendlyMessage(e));
    } finally {
      setLoading(false);
    }
  }

  const canAnalyze = file !== null && !loading && health?.status !== 'down';

  return (
    <main className="app">
      <header className="app-header">
        <div className="brand-frame">
          <img className="brand-logo" src="/isitai-logo-display.png" alt="ISITAI" />
        </div>
        <h1 className="visually-hidden">ISITAI</h1>
        <p className="subtitle" aria-label={subtitle}>
          <span className="subtitle-typed" aria-hidden="true">
            {typedSubtitle}
          </span>
          {typedSubtitle.length < subtitle.length && (
            <span className="typing-caret" aria-hidden="true" />
          )}
        </p>
      </header>

      <StatusBanner
        health={health}
        error={healthError}
        onRetry={() => {
          setHealthError(null);
          setHealthTry((n) => n + 1);
        }}
      />

      <section className="analysis-panel" aria-label="Analizar imagen">
        <div className="field">
          <label htmlFor="model">Modelo</label>
          <ModelSelect
            models={health?.models ?? []}
            value={model}
            defaultModel={health?.default_model ?? null}
            disabled={!health || loading}
            onChange={setModel}
          />
        </div>

        <ImagePicker file={file} previewUrl={previewUrl} disabled={loading} onFile={handleFile} />

        {file && (
          <button
            type="button"
            className={`btn btn-primary${loading ? ' btn-loading' : ''}`}
            disabled={!canAnalyze}
            aria-busy={loading}
            onClick={handleAnalyze}
          >
            {loading && <span className="button-spinner" aria-hidden="true" />}
            {loading ? 'Analizando…' : 'Analizar imagen'}
          </button>
        )}

        {error && (
          <div className="banner banner-error" role="alert">
            {error}
          </div>
        )}

        {result && <ResultCard result={result} />}
      </section>
      <History refreshKey={historyKey} />
    </main>
  );
}