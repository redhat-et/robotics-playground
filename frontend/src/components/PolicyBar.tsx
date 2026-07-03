import React, { useState } from 'react';
import {
  Button,
  Flex,
  FlexItem,
  FormSelect,
  FormSelectOption,
} from '@patternfly/react-core';

const policies = [
  { value: 'dreamzero-v1', label: 'DreamZero v1' },
  { value: 'humanoidbench-v1', label: 'HumanoidBench Baseline' },
];

const PolicyBar: React.FC = () => {
  const [selectedPolicy, setSelectedPolicy] = useState(policies[0].value);

  return (
    <Flex
      justifyContent={{ default: 'justifyContentSpaceBetween' }}
      alignItems={{ default: 'alignItemsCenter' }}
      className="policy-bar"
    >
      <Flex alignItems={{ default: 'alignItemsCenter' }}>
        <FlexItem>Policy:</FlexItem>
        <FlexItem>
          <FormSelect
            id="policy-select"
            value={selectedPolicy}
            onChange={(_event, value) => setSelectedPolicy(value)}
            aria-label="Select policy"
          >
            {policies.map((policy) => (
              <FormSelectOption
                key={policy.value}
                value={policy.value}
                label={policy.label}
              />
            ))}
          </FormSelect>
        </FlexItem>
      </Flex>
      <FlexItem>
        <Button variant="secondary">Split</Button>
      </FlexItem>
    </Flex>
  );
};

export default PolicyBar;
