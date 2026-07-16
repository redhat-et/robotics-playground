// When embedded in the RHOAI dashboard via Module Federation, REST API
// requests route through the dashboard proxy under /physical-ai.
// WebSocket connections bypass the dashboard (it doesn't proxy WS
// upgrades) and connect directly to the backend's OpenShift Route.
const EMBEDDED_PREFIX = '/physical-ai';

const isEmbedded = window.location.pathname.startsWith('/physicalAiStudio/');

export const API_BASE = isEmbedded ? EMBEDDED_PREFIX : '';

export interface BackendConfig {
  wsUrl: string;
  rerunViewerUrl: string;
  rerunGrpcUrl: string;
  rerunAssetsUrl: string;
}

const EMPTY_CONFIG: BackendConfig = { wsUrl: '', rerunViewerUrl: '', rerunGrpcUrl: '', rerunAssetsUrl: '' };

let _configPromise: Promise<BackendConfig> | null = null;

function fetchConfig(): Promise<BackendConfig> {
  return fetch(`${API_BASE}/api/config`)
    .then((r) => r.json())
    .then((data: Partial<BackendConfig>) => ({
      wsUrl: data.wsUrl ?? '',
      rerunViewerUrl: data.rerunViewerUrl ?? '',
      rerunGrpcUrl: data.rerunGrpcUrl ?? '',
      rerunAssetsUrl: data.rerunAssetsUrl ?? '',
    }))
    .catch(() => EMPTY_CONFIG);
}

export function getBackendConfig(): Promise<BackendConfig> {
  if (!_configPromise) {
    _configPromise = fetchConfig();
  }
  return _configPromise;
}

export function getWsBase(): Promise<string> {
  if (!isEmbedded) return Promise.resolve('');
  return getBackendConfig().then((c) => c.wsUrl);
}
