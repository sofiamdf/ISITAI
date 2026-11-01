import { useEffect, useState } from 'react';
import './App.css';
import { analyzeImage, friendlyMessage, getHealth, validateImage } from './api/client';
import type { AnalysisResult, Health, ModelName } from './api/types';
import ImagePicker from './components/ImagePicker';
import ResultCard from './components/ResultCard';
import StatusBanner from './components/StatusBanner';

export default function App() {
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
    } catch (e) {
      setError(friendlyMessage(e));
    } finally {
      setLoading(false);
    }
  }

  const canAnalyze = file !== null && !loading && health?.status !== 'down';

  return (
    <main className="app">
      <header>
        <h1>ISITAI</h1>
        <p className="subtitle">¿Esta imagen es real o la generó una IA?</p>
      </header>

      <StatusBanner
        health={health}
        error={healthError}
        onRetry={() => {
          setHealthError(null);
          setHealthTry((n) => n + 1);
        }}
      />

      <div className="field">
        <label htmlFor="model">Modelo</label>
        <select
          id="model"
          value={model}
          disabled={!health || loading}
          onChange={(e) => setModel(e.target.value as ModelName)}
        >
          {!health && <option value="">Cargando…</option>}
          {health?.models.map((m) => (
            <option key={m.id} value={m.id}>
              {m.id}
              {m.id === health.default_model ? ' (predeterminado)' : ''}
            </option>
          ))}
        </select>
      </div>

      <ImagePicker file={file} previewUrl={previewUrl} disabled={loading} onFile={handleFile} />

      <button type="button" className="btn btn-primary" disabled={!canAnalyze} onClick={handleAnalyze}>
        {loading ? 'Analizando…' : 'Analizar imagen'}
      </button>

      {error && (
        <div className="banner banner-error" role="alert">
          {error}
        </div>
      )}

      {result && <ResultCard result={result} />}
    </main>
  );
}