import React from 'react';
import {
  Button,
  Content,
  Flex,
  FlexItem,
  Label,
} from '@patternfly/react-core';

interface SimulationControlPanelProps {
  state: string;
  onSimControl: (action: string) => void;
}

const STATE_LABELS: Record<string, { text: string; color: 'grey' | 'green' | 'orange' | 'red' }> = {
  idle: { text: 'Idle', color: 'grey' },
  running: { text: 'Running', color: 'green' },
  paused: { text: 'Paused', color: 'orange' },
  error: { text: 'Error', color: 'red' },
};

const SimulationControlPanel: React.FC<SimulationControlPanelProps> = ({ state, onSimControl }) => {
  const label = STATE_LABELS[state] ?? STATE_LABELS.idle;
  const isRunning = state === 'running';
  const isPaused = state === 'paused';

  return (
    <div className="simulation-control-panel">
      <Flex justifyContent={{ default: 'justifyContentSpaceBetween' }} alignItems={{ default: 'alignItemsCenter' }}>
        <FlexItem>
          <Content component="h2" style={{ margin: 0 }}>Simulation Control</Content>
        </FlexItem>
        <FlexItem>
          <Label color={label.color}>{label.text}</Label>
        </FlexItem>
      </Flex>
      <Flex alignItems={{ default: 'alignItemsCenter' }}>
        <FlexItem>
          <Button
            variant="primary"
            size="sm"
            onClick={() => onSimControl(isRunning ? 'pause' : 'play')}
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
    </div>
  );
};

export default SimulationControlPanel;
