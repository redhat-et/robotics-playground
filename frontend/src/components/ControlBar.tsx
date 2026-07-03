import React from 'react';
import {
  Button,
  Flex,
  FlexItem,
  Label,
} from '@patternfly/react-core';

const ControlBar: React.FC = () => (
  <Flex
    justifyContent={{ default: 'justifyContentSpaceBetween' }}
    alignItems={{ default: 'alignItemsCenter' }}
    className="control-bar"
  >
    <Flex>
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
);

export default ControlBar;
