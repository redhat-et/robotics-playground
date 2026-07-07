// When embedded in the RHOAI dashboard via Module Federation, API and
// WebSocket requests must be routed through the dashboard's proxy under
// /physical-ai.  Standalone mode needs no prefix.
const EMBEDDED_PREFIX = '/physical-ai';

const isEmbedded = window.location.pathname.startsWith('/physicalAiStudio/');

export const API_BASE = isEmbedded ? EMBEDDED_PREFIX : '';
