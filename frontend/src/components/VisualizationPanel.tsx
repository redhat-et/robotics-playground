import React from 'react';
import {
  Card,
  CardBody,
  Flex,
  FlexItem,
} from '@patternfly/react-core';
import { CubesIcon } from '@patternfly/react-icons';

const VisualizationPanel: React.FC = () => (
  <Card className="visualization-panel" isFullHeight>
    <CardBody>
      <Flex
        alignItems={{ default: 'alignItemsCenter' }}
        justifyContent={{ default: 'justifyContentCenter' }}
        direction={{ default: 'column' }}
        style={{ height: '100%' }}
      >
        <FlexItem>
          <CubesIcon />
        </FlexItem>
        <FlexItem>Rerun Viewer</FlexItem>
      </Flex>
    </CardBody>
  </Card>
);

export default VisualizationPanel;
