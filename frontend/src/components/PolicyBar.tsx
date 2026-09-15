import React, { useState, useEffect } from 'react';
import {
  Button,
  Flex,
  FlexItem,
  FormSelect,
  FormSelectOption,
  Label,
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
  policyStatus: string;
  policyError: string;
}

const POLICY_LABELS: Record<string, { text: string; color: 'grey' | 'green' | 'orange' | 'red' }> = {
  disconnected: { text: 'Not connected', color: 'grey' },
  connecting: { text: 'Connecting…', color: 'orange' },
  connected: { text: 'Connected', color: 'green' },
};

const POLICY_ERROR_LABELS: Record<string, { text: string; color: 'grey' | 'green' | 'orange' | 'red' }> = {
  server_not_found: { text: 'Server not found', color: 'red' },
  server_starting: { text: 'Server starting…', color: 'orange' },
  server_not_responding: { text: 'Server not responding', color: 'red' },
  connection_failed: { text: 'Connection failed', color: 'red' },
};

const PolicyBar: React.FC<PolicyBarProps> = ({ isSidebarOpen, onToggleSidebar, selectedModel, onSelectModel, policyStatus, policyError }) => {
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

  const policyLabel = policyStatus === 'error' && policyError
    ? POLICY_ERROR_LABELS[policyError] ?? POLICY_ERROR_LABELS.connection_failed
    : POLICY_LABELS[policyStatus] ?? POLICY_LABELS.disconnected;

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
              isDisabled={models.length === 0}
            >
              <FormSelectOption key="none" value="" label="— Select model —" />
              {models.map((model) => (
                <FormSelectOption
                  key={model.id}
                  value={model.id}
                  label={model.name}
                />
              ))}
            </FormSelect>
          )}
        </FlexItem>
        <FlexItem>
          <Label color={policyLabel.color}>{policyLabel.text}</Label>
        </FlexItem>
      </Flex>
      <FlexItem>
        <Button variant="secondary">Split</Button>
      </FlexItem>
    </Flex>
  );
};

export default PolicyBar;
