import React, { useState, useEffect } from 'react';
import {
  EmptyState,
  EmptyStateBody,
} from '@patternfly/react-core';
import { CubesIcon } from '@patternfly/react-icons';
import { getBackendConfig } from '../utils/apiBase';

interface VisualizationPanelProps {
  connected: boolean;
}

function buildRerunUrl(viewerBase: string, grpcBase: string): string {
  const grpcUrl = grpcBase.endsWith('/proxy') ? grpcBase : `${grpcBase}/proxy`;
  return `${viewerBase}/?url=${encodeURIComponent(grpcUrl)}&hide_welcome_screen`;
}

function buildLocalRerunUrl(): string {
  const host = window.location.hostname;
  return buildRerunUrl(`http://${host}:9090`, `rerun+http://${host}:9876/proxy`);
}

const VisualizationPanel: React.FC<VisualizationPanelProps> = ({ connected }) => {
  const [rerunUrl, setRerunUrl] = useState<string | null>(null);

  useEffect(() => {
    getBackendConfig().then((cfg) => {
      if (cfg.rerunViewerUrl && cfg.rerunGrpcUrl) {
        setRerunUrl(buildRerunUrl(cfg.rerunViewerUrl, cfg.rerunGrpcUrl));
      } else {
        setRerunUrl(buildLocalRerunUrl());
      }
    });
  }, []);

  return (
    <div className="visualization-panel">
      {connected && rerunUrl ? (
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
