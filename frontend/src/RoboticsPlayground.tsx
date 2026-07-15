import React, { useEffect, useState } from 'react';
import { PageSection } from '@patternfly/react-core';
import ChatPanel from './components/ChatPanel';
import SimulationControlPanel from './components/SimulationControlPanel';
import PolicyBar from './components/PolicyBar';
import VisualizationPanel from './components/VisualizationPanel';
import { useSession } from './hooks/useSession';
import './RoboticsPlayground.css';

const SESSION_ID = 'default';

const RoboticsPlayground: React.FC = () => {
  const [selectedModel, setSelectedModel] = useState('');
  const { connected, sessionState, messages, sendInstruction, sendSimControl, sendSelectModel } =
    useSession(SESSION_ID);

  useEffect(() => {
    if (sessionState.modelId) {
      setSelectedModel((prev) => (prev !== sessionState.modelId ? sessionState.modelId : prev));
    }
  }, [sessionState.modelId]);

  const handleSelectModel = (modelId: string) => {
    setSelectedModel(modelId);
    sendSelectModel(modelId);
  };

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
            bridgeStatus={sessionState.bridgeStatus}
            onSimControl={sendSimControl}
          />
        </div>
        <div className="robotics-playground__main">
          <PolicyBar
            selectedModel={selectedModel}
            onSelectModel={handleSelectModel}
            disabled={sessionState.state !== 'idle'}
          />
          <VisualizationPanel connected={connected} />
        </div>
      </div>
    </PageSection>
  );
};

export default RoboticsPlayground;
