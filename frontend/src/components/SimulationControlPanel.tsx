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
  state: string;
  bridgeStatus: string;
  onSimControl: (action: string, speed?: number) => void;
}

const STATE_LABELS: Record<string, { text: string; color: 'grey' | 'green' | 'orange' | 'red' }> = {
  idle: { text: 'Idle', color: 'grey' },
  running: { text: 'Running', color: 'green' },
  paused: { text: 'Paused', color: 'orange' },
  error: { text: 'Error', color: 'red' },
};

const BRIDGE_LABELS: Record<string, { text: string; color: 'grey' | 'green' | 'red' }> = {
  mock: { text: 'Mock', color: 'grey' },
  connected: { text: 'Connected', color: 'green' },
  disconnected: { text: 'Disconnected', color: 'red' },
};

const SimulationControlPanel: React.FC<SimulationControlPanelProps> = ({
  state,
  bridgeStatus,
  onSimControl,
}) => {
  const [speed, setSpeed] = useState(1.0);
  const label = STATE_LABELS[state] ?? STATE_LABELS.idle;
  const bridgeLabel = BRIDGE_LABELS[bridgeStatus] ?? BRIDGE_LABELS.mock;
  const isRunning = state === 'running';
  const isPaused = state === 'paused';

  return (
    <div className="simulation-control-panel">
      <Flex justifyContent={{ default: 'justifyContentSpaceBetween' }} alignItems={{ default: 'alignItemsCenter' }}>
        <FlexItem>
          <Content component="h2" style={{ margin: 0 }}>Simulation Control</Content>
        </FlexItem>
        <FlexItem>
          <Flex spaceItems={{ default: 'spaceItemsSm' }}>
            <FlexItem>
              <Label color={bridgeLabel.color}>{bridgeLabel.text}</Label>
            </FlexItem>
            <FlexItem>
              <Label color={label.color}>{label.text}</Label>
            </FlexItem>
          </Flex>
        </FlexItem>
      </Flex>
      <Flex alignItems={{ default: 'alignItemsCenter' }}>
        <FlexItem>
          <Button
            variant="primary"
            size="sm"
            onClick={() => onSimControl(isRunning ? 'pause' : 'play', speed)}
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
            isDisabled={isRunning}
          >
            Step
          </Button>
        </FlexItem>
        <FlexItem>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => onSimControl('reset')}
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
