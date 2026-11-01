// URL base de la API, sin barra final. Viene de la variable VITE_API_URL
// (en desarrollo, del archivo .env.development).
export const API_URL: string = (import.meta.env.VITE_API_URL ?? '').replace(/\/$/, '');

// Modo "API falsa": la web inventa las respuestas y no llama a ningún servidor.
// Solo se activa si VITE_USE_FAKE_API vale exactamente "true".
export const USE_FAKE_API: boolean = import.meta.env.VITE_USE_FAKE_API === 'true';

// Límites que el backend también valida (la web los chequea antes para ahorrar un pedido).
export const MAX_IMAGE_BYTES = 4 * 1024 * 1024; // 4 MiB
export const ALLOWED_TYPES = ['image/jpeg', 'image/png', 'image/webp'];