import React from 'react';
import {
  Button,
  Content,
  Flex,
  FlexItem,
  TextInput,
} from '@patternfly/react-core';

const ChatPanel: React.FC = () => (
  <div className="chat-panel">
    <Content component="h2">Instructions</Content>
    <div className="chat-panel__messages" />
    <Flex className="chat-panel__input">
      <FlexItem grow={{ default: 'grow' }}>
        <TextInput aria-label="Chat message" placeholder="Tell the robot what to do..." />
      </FlexItem>
      <FlexItem>
        <Button variant="primary">Send</Button>
      </FlexItem>
    </Flex>
  </div>
);

export default ChatPanel;
