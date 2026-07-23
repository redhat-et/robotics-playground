import React, { useState, useEffect } from 'react';
import {
  EmptyState,
  EmptyStateBody,
} from '@patternfly/react-core';
import { CubesIcon } from '@patternfly/react-icons';
import { getBackendConfig } from '../utils/apiBase';

function toRerunScheme(url: string): string {
  if (url.startsWith('rerun+') || url.startsWith('rerun://')) return url;
  return `rerun+${url}`;
}

function buildRerunUrl(viewerBase: string, grpcBase: string, assetsUrl?: string): string {
  const withProxy = grpcBase.endsWith('/proxy') ? grpcBase : `${grpcBase}/proxy`;
  const grpcUrl = toRerunScheme(withProxy);
  let url = `${viewerBase}/?url=${encodeURIComponent(grpcUrl)}&hide_welcome_screen`;
  if (assetsUrl) {
    url += `&assets_url=${encodeURIComponent(assetsUrl)}`;
  }
  return url;
}

const CONFIG_RETRY_MS = 3000;

const VisualizationPanel: React.FC = () => {
  const [rerunUrl, setRerunUrl] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const tryLoad = () => {
      getBackendConfig().then((cfg) => {
        if (cancelled) return;
        if (cfg.rerunViewerUrl && cfg.rerunGrpcUrl) {
          setRerunUrl(buildRerunUrl(cfg.rerunViewerUrl, cfg.rerunGrpcUrl, cfg.rerunAssetsUrl));
        } else {
          setTimeout(tryLoad, CONFIG_RETRY_MS);
        }
      });
    };
    tryLoad();
    return () => { cancelled = true; };
  }, []);

  return (
    <div className="visualization-panel">
      {rerunUrl ? (
        <iframe
          src={rerunUrl}
          title="Rerun Viewer"
          className="visualization-panel__iframe"
        />
      ) : (
        <EmptyState
          titleText="Rerun Viewer"
          headingLevel="h3"
          icon={CubesIcon}
          variant="lg"
        >
          <EmptyStateBody>
            Connecting to backend...
          </EmptyStateBody>
        </EmptyState>
      )}
    </div>
  );
};

export default VisualizationPanel;
