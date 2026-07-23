import React, { useEffect, useState } from 'react';
import {
  Content,
  Drawer,
  DrawerActions,
  DrawerCloseButton,
  DrawerContent,
  DrawerContentBody,
  DrawerHead,
  DrawerPanelBody,
  DrawerPanelContent,
  PageSection,
} from '@patternfly/react-core';
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
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);

  const panelContent = (
    <DrawerPanelContent defaultSize="400px" minSize="300px">
      <DrawerHead>
        <Content component="h2" style={{ margin: 0 }}>Instructions &amp; Control</Content>
        <DrawerActions>
          <DrawerCloseButton onClick={() => setIsSidebarOpen(false)} />
        </DrawerActions>
      </DrawerHead>
      <DrawerPanelBody className="robotics-playground__sidebar-body">
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
      </DrawerPanelBody>
    </DrawerPanelContent>
  );

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
        <Drawer isExpanded={isSidebarOpen} isInline position="left">
          <DrawerContent panelContent={panelContent}>
            <DrawerContentBody className="robotics-playground__main">
              <PolicyBar
                isSidebarOpen={isSidebarOpen}
                onToggleSidebar={() => setIsSidebarOpen((prev) => !prev)}
                selectedModel={selectedModel}
                onSelectModel={handleSelectModel}
                disabled={sessionState.state !== 'idle'}
              />
              <VisualizationPanel />
            </DrawerContentBody>
          </DrawerContent>
        </Drawer>
      </div>
    </PageSection>
  );
};

export default RoboticsPlayground;
