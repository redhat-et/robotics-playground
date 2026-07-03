import React from 'react';
import { PageSection } from '@patternfly/react-core';
import ChatPanel from './components/ChatPanel';
import SimulationControlPanel from './components/SimulationControlPanel';
import PolicyBar from './components/PolicyBar';
import VisualizationPanel from './components/VisualizationPanel';
import './RoboticsPlayground.css';

const RoboticsPlayground: React.FC = () => (
  <PageSection padding={{ default: 'noPadding' }}>
    <div className="robotics-playground">
      <div className="robotics-playground__sidebar">
        <ChatPanel />
        <SimulationControlPanel />
      </div>
      <div className="robotics-playground__main">
        <PolicyBar />
        <VisualizationPanel />
      </div>
    </div>
  </PageSection>
);

export default RoboticsPlayground;
