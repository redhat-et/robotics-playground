import React, { useState } from 'react';
import {
  Button,
  Content,
  Flex,
  FlexItem,
  Label,
  Slider,
} from '@patternfly/react-core';

interface SimulationControlPanelProps {
  simStatus: string;
  simState: string;
  onSimControl: (action: string, speed?: number) => void;
}

const SIM_STATUS_LABELS: Record<string, { text: string; color: 'grey' | 'green' | 'orange' | 'red' }> = {
  disconnected: { text: 'Disconnected', color: 'red' },
  connecting: { text: 'Connecting', color: 'orange' },
  connected: { text: 'Connected', color: 'green' },
  mock: { text: 'Mock', color: 'grey' },
};

const SimulationControlPanel: React.FC<SimulationControlPanelProps> = ({
  simStatus,
  simState,
  onSimControl,
}) => {
  const [speed, setSpeed] = useState(1.0);
  const statusLabel = SIM_STATUS_LABELS[simStatus] ?? SIM_STATUS_LABELS.disconnected;
  const isRunning = simState === 'running';
  const isPaused = simState === 'paused';

  return (
    <div className="simulation-control-panel">
      <Flex justifyContent={{ default: 'justifyContentSpaceBetween' }} alignItems={{ default: 'alignItemsCenter' }}>
        <FlexItem>
          <Content component="h2" style={{ margin: 0 }}>Simulation Control</Content>
        </FlexItem>
        <FlexItem>
          <Label color={statusLabel.color}>Sim: {statusLabel.text}</Label>
        </FlexItem>
      </Flex>
      <Flex alignItems={{ default: 'alignItemsCenter' }}>
        <FlexItem>
          <Button
            variant="primary"
            size="sm"
            onClick={() => onSimControl(isRunning ? 'pause' : 'play', speed)}
            isDisabled={simStatus !== 'connected'}
          >
            {isRunning ? 'Pause' : 'Play'}
          </Button>
        </FlexItem>
        <FlexItem>
          <Button
            variant="danger"
            size="sm"
            onClick={() => onSimControl('stop')}
            isDisabled={!isRunning && !isPaused}
          >
            Stop
          </Button>
        </FlexItem>
        <FlexItem>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => onSimControl('step')}
            isDisabled={isRunning || simStatus !== 'connected'}
          >
            Step
          </Button>
        </FlexItem>
        <FlexItem>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => onSimControl('reset')}
            isDisabled={simStatus !== 'connected'}
          >
            Reset
          </Button>
        </FlexItem>
      </Flex>
      <Flex alignItems={{ default: 'alignItemsCenter' }}>
        <FlexItem>
          <Content component="small">Speed: {speed.toFixed(1)}x</Content>
        </FlexItem>
        <FlexItem grow={{ default: 'grow' }}>
          <Slider
            value={speed * 10}
            min={1}
            max={50}
            showBoundaries={false}
            onChange={(_event, val) => setSpeed(val / 10)}
            aria-label="Simulation speed"
          />
        </FlexItem>
      </Flex>
    </div>
  );
};

export default SimulationControlPanel;
