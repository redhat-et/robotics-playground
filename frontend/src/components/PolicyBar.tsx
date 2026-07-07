import React, { useState, useEffect } from 'react';
import {
  Button,
  Flex,
  FlexItem,
  FormSelect,
  FormSelectOption,
  Spinner,
} from '@patternfly/react-core';
import { API_BASE } from '../utils/apiBase';

interface Model {
  id: string;
  name: string;
  type: string;
}

const PolicyBar: React.FC = () => {
  const [models, setModels] = useState<Model[]>([]);
  const [selectedPolicy, setSelectedPolicy] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API_BASE}/api/models?type=robotics`)
      .then((res) => res.json())
      .then((data) => {
        const fetched: Model[] = data.models ?? [];
        setModels(fetched);
        if (fetched.length > 0) {
          setSelectedPolicy(fetched[0].id);
        }
      })
      .catch(() => {
        setModels([]);
      })
      .finally(() => setLoading(false));
  }, []);

  return (
    <Flex
      justifyContent={{ default: 'justifyContentSpaceBetween' }}
      alignItems={{ default: 'alignItemsCenter' }}
      className="policy-bar"
    >
      <Flex alignItems={{ default: 'alignItemsCenter' }}>
        <FlexItem>Policy:</FlexItem>
        <FlexItem>
          {loading ? (
            <Spinner size="md" aria-label="Loading models" />
          ) : (
            <FormSelect
              id="policy-select"
              value={selectedPolicy}
              onChange={(_event, value) => setSelectedPolicy(value)}
              aria-label="Select policy"
              isDisabled={models.length === 0}
            >
              {models.length === 0 ? (
                <FormSelectOption key="none" value="" label="No models available" isDisabled />
              ) : (
                models.map((model) => (
                  <FormSelectOption
                    key={model.id}
                    value={model.id}
                    label={model.name}
                  />
                ))
              )}
            </FormSelect>
          )}
        </FlexItem>
      </Flex>
      <FlexItem>
        <Button variant="secondary">Split</Button>
      </FlexItem>
    </Flex>
  );
};

export default PolicyBar;
