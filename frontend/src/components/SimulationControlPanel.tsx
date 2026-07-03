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
    <Flex direction={{ default: 'column' }} spaceItems={{ default: 'spaceItemsSm' }}>
      <Flex>
        <FlexItem>
          <Button variant="primary">Play</Button>
        </FlexItem>
        <FlexItem>
          <Button variant="danger">Stop</Button>
        </FlexItem>
        <FlexItem>
          <Button variant="secondary">Reset</Button>
        </FlexItem>
      </Flex>
      <FlexItem>
        <Label color="grey">Idle</Label>
      </FlexItem>
    </Flex>
  </div>
);

export default SimulationControlPanel;
