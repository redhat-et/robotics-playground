import React from 'react';
import {
  Flex,
  FlexItem,
} from '@patternfly/react-core';
import { CubesIcon } from '@patternfly/react-icons';

const VisualizationPanel: React.FC = () => (
  <div className="visualization-panel">
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
  </div>
);

export default VisualizationPanel;
