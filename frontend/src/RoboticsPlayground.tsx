import React from 'react';
import { PageSection } from '@patternfly/react-core';
import SessionSetupPanel from './components/SessionSetupPanel';
import ChatPanel from './components/ChatPanel';
import VisualizationPanel from './components/VisualizationPanel';
import ControlBar from './components/ControlBar';
import './RoboticsPlayground.css';

const RoboticsPlayground: React.FC = () => (
  <PageSection>
    <div className="robotics-playground">
      <div className="robotics-playground__sidebar">
        <SessionSetupPanel />
        <ChatPanel />
      </div>
      <div className="robotics-playground__main">
        <VisualizationPanel />
      </div>
      <div className="robotics-playground__footer">
        <ControlBar />
      </div>
    </div>
  </PageSection>
);

export default RoboticsPlayground;
