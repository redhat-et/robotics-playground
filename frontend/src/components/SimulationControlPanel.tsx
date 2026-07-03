import React from 'react';
import {
  Button,
  Content,
  Flex,
  FlexItem,
  Label,
} from '@patternfly/react-core';

const SimulationControlPanel: React.FC = () => (
  <div className="simulation-control-panel">
    <Content component="h2">Simulation Control</Content>
    <Flex alignItems={{ default: 'alignItemsCenter' }}>
      <FlexItem>
        <Button variant="primary" size="sm">Play</Button>
      </FlexItem>
      <FlexItem>
        <Button variant="danger" size="sm">Stop</Button>
      </FlexItem>
      <FlexItem>
        <Button variant="secondary" size="sm">Step</Button>
      </FlexItem>
      <FlexItem>
        <Button variant="secondary" size="sm">Reset</Button>
      </FlexItem>
      <FlexItem grow={{ default: 'grow' }} />
      <FlexItem>
        <Label color="grey">Idle</Label>
      </FlexItem>
    </Flex>
  </div>
);

export default SimulationControlPanel;
