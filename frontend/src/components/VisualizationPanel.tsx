import React from 'react';
import {
  EmptyState,
  EmptyStateBody,
} from '@patternfly/react-core';
import { CubesIcon } from '@patternfly/react-icons';

interface VisualizationPanelProps {
  connected: boolean;
}

function getRerunUrl(): string {
  const host = window.location.hostname;
  const webViewerPort = 9090;
  const grpcPort = 9876;
  const grpcUrl = `rerun+http://${host}:${grpcPort}/proxy`;
  return `http://${host}:${webViewerPort}/?url=${encodeURIComponent(grpcUrl)}&hide_welcome_screen`;
}

const VisualizationPanel: React.FC<VisualizationPanelProps> = ({ connected }) => (
  <div className="visualization-panel">
    {connected ? (
      <iframe
        src={getRerunUrl()}
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

export default VisualizationPanel;
