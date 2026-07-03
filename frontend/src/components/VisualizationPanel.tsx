import React from 'react';
import {
  EmptyState,
  EmptyStateBody,
} from '@patternfly/react-core';
import { CubesIcon } from '@patternfly/react-icons';

interface VisualizationPanelProps {
  connected: boolean;
}

const RERUN_VIEWER_URL = 'https://app.rerun.io/version/0.22.1/';

function getRerunUrl(): string {
  const grpcHost = window.location.hostname;
  const grpcPort = 9876;
  return `${RERUN_VIEWER_URL}?url=rerun://${grpcHost}:${grpcPort}`;
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
