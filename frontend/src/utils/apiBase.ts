// When embedded in the RHOAI dashboard via Module Federation, REST API
// requests route through the dashboard proxy under /physical-ai.
// WebSocket connections bypass the dashboard (it doesn't proxy WS
// upgrades) and connect directly to the backend's OpenShift Route.
const EMBEDDED_PREFIX = '/physical-ai';

const isEmbedded = window.location.pathname.startsWith('/physicalAiStudio/');

export const API_BASE = isEmbedded ? EMBEDDED_PREFIX : '';

let _wsBase = '';
let _wsBasePromise: Promise<string> | null = null;

function fetchWsBase(): Promise<string> {
  if (!isEmbedded) return Promise.resolve('');
  return fetch(`${API_BASE}/api/config`)
    .then((r) => r.json())
    .then((data: { wsUrl?: string }) => {
      _wsBase = data.wsUrl ?? '';
      return _wsBase;
    })
    .catch(() => '');
}

export function getWsBase(): Promise<string> {
  if (!isEmbedded) return Promise.resolve('');
  if (!_wsBasePromise) {
    _wsBasePromise = fetchWsBase();
  }
  return _wsBasePromise;
}
