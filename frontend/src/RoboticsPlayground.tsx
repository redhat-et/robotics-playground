import React from 'react';
import { PageSection } from '@patternfly/react-core';
import ChatPanel from './components/ChatPanel';
import SimulationControlPanel from './components/SimulationControlPanel';
import PolicyBar from './components/PolicyBar';
import VisualizationPanel from './components/VisualizationPanel';
import { useSession } from './hooks/useSession';
import './RoboticsPlayground.css';

const SESSION_ID = 'default';

const RoboticsPlayground: React.FC = () => {
  const { connected, sessionState, messages, sendInstruction, sendSimControl } =
    useSession(SESSION_ID);

  return (
    <PageSection padding={{ default: 'noPadding' }} isFilled>
      <div className="robotics-playground">
        <div className="robotics-playground__sidebar">
          <ChatPanel
            messages={messages}
            onSendInstruction={sendInstruction}
            connected={connected}
          />
          <SimulationControlPanel
            state={sessionState.state}
            onSimControl={sendSimControl}
          />
        </div>
        <div className="robotics-playground__main">
          <PolicyBar />
          <VisualizationPanel connected={connected} />
        </div>
      </div>
    </PageSection>
  );
};

export default RoboticsPlayground;
