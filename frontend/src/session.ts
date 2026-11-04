const KEY = 'isitai.sessionId';
let memoryId: string | null = null;

// crypto.randomUUID() solo existe en contextos seguros (HTTPS o localhost).
// Como la web desplegada en S3 se sirve por HTTP usamos crypto.getRandomValues() como alternativa que si funciona por HTTP.
export function newUuid(): string {
  if (typeof crypto.randomUUID === 'function') return crypto.randomUUID();
  const b = crypto.getRandomValues(new Uint8Array(16));
  b[6] = (b[6] & 0x0f) | 0x40; // versión 4
  b[8] = (b[8] & 0x3f) | 0x80; // variante RFC 4122
  const h = [...b].map((x) => x.toString(16).padStart(2, '0')).join('');
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20)}`;
}

export function getSessionId(): string {
  try {
    let id = localStorage.getItem(KEY);
    if (!id) {
      id = newUuid();
      localStorage.setItem(KEY, id);
    }
    return id;
  } catch {
    memoryId ??= newUuid();
    return memoryId;
  }
}