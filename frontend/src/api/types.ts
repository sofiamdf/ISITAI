export type Label = 'ai' | 'real' | 'uncertain';

export type ModelName = 'mlp' | 'cnn' | 'resnet18';

export interface AnalysisResult {
  request_id: string;
  sha256: string;
  label: Label;
  prob_ai: number;
  prob_real: number;
  model: ModelName;
  model_version: string;
  cache_hit: boolean;
  latency_ms: number;
  analyzed_at: string;
}

export interface ModelInfo {
  id: ModelName;
  version: string;
}

export interface Health {
  status: 'ok' | 'degraded' | 'down';
  model_id: string; // "mock" o "real-xxxxxxxx"
  default_model: ModelName;
  models: ModelInfo[];
  model?: { reachable: boolean; model_version: string | null };
  cache?: { reachable: boolean | null }; // null = el despliegue no tiene caché
  history?: { reachable: boolean | null }; // null = el despliegue no tiene historial
}