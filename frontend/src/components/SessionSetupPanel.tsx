import React, { useState } from 'react';
import {
  Button,
  Content,
  Form,
  FormGroup,
  FormSelect,
  FormSelectOption,
} from '@patternfly/react-core';

const models = [
  { value: 'dreamzero-v1', label: 'DreamZero v1' },
  { value: 'humanoidbench-v1', label: 'HumanoidBench Baseline' },
];

const SessionSetupPanel: React.FC = () => {
  const [selectedModel, setSelectedModel] = useState(models[0].value);

  return (
    <div className="session-setup-panel">
      <Content component="h2">Session Setup</Content>
      <Form>
        <FormGroup label="Model" fieldId="model-select">
          <FormSelect
            id="model-select"
            value={selectedModel}
            onChange={(_event, value) => setSelectedModel(value)}
            aria-label="Select model"
          >
            {models.map((model) => (
              <FormSelectOption
                key={model.value}
                value={model.value}
                label={model.label}
              />
            ))}
          </FormSelect>
        </FormGroup>
        <Button variant="primary">Start Session</Button>
      </Form>
    </div>
  );
};

export default SessionSetupPanel;
