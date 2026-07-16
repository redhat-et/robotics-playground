import React, { useState, useEffect } from 'react';
import {
  Button,
  Flex,
  FlexItem,
  FormSelect,
  FormSelectOption,
  Spinner,
} from '@patternfly/react-core';
import { BarsIcon } from '@patternfly/react-icons';
import { API_BASE } from '../utils/apiBase';

interface Model {
  id: string;
  name: string;
  type: string;
}

interface PolicyBarProps {
  isSidebarOpen: boolean;
  onToggleSidebar: () => void;
  selectedModel: string;
  onSelectModel: (modelId: string) => void;
  disabled?: boolean;
}

const PolicyBar: React.FC<PolicyBarProps> = ({ isSidebarOpen, onToggleSidebar, selectedModel, onSelectModel, disabled }) => {
  const [models, setModels] = useState<Model[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API_BASE}/api/models?type=robotics`)
      .then((res) => res.json())
      .then((data) => {
        const fetched: Model[] = data.models ?? [];
        setModels(fetched);
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
        <FlexItem>
          <Button
            variant="plain"
            aria-label="Toggle sidebar"
            aria-expanded={isSidebarOpen}
            onClick={onToggleSidebar}
            icon={<BarsIcon />}
          />
        </FlexItem>
        <FlexItem>Policy:</FlexItem>
        <FlexItem>
          {loading ? (
            <Spinner size="md" aria-label="Loading models" />
          ) : (
            <FormSelect
              id="policy-select"
              value={selectedModel}
              onChange={(_event, value) => onSelectModel(value)}
              aria-label="Select policy"
              isDisabled={disabled || models.length === 0}
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
