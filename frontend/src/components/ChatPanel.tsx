import React, { useState, useRef, useEffect } from 'react';
import {
  Button,
  Content,
  Flex,
  FlexItem,
  TextInput,
} from '@patternfly/react-core';
import type { ChatMessage } from '../hooks/useSession';

interface ChatPanelProps {
  messages: ChatMessage[];
  onSendInstruction: (text: string) => void;
  connected: boolean;
}

const ChatPanel: React.FC<ChatPanelProps> = ({ messages, onSendInstruction, connected }) => {
  const [input, setInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (typeof messagesEndRef.current?.scrollIntoView === 'function') {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages]);

  const handleSend = () => {
    const text = input.trim();
    if (!text) return;
    onSendInstruction(text);
    setInput('');
  };

  const handleKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="chat-panel">
      <Content component="h2">Instructions</Content>
      <div className="chat-panel__messages">
        {messages.map((msg) => (
          <div key={msg.id} className={`chat-panel__message chat-panel__message--${msg.role}`}>
            <span className="chat-panel__message-text">{msg.text}</span>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>
      <Flex className="chat-panel__input">
        <FlexItem grow={{ default: 'grow' }}>
          <TextInput
            aria-label="Chat message"
            placeholder="Tell the robot what to do..."
            value={input}
            onChange={(_event, value) => setInput(value)}
            onKeyDown={handleKeyDown}
            isDisabled={!connected}
          />
        </FlexItem>
        <FlexItem>
          <Button variant="primary" onClick={handleSend} isDisabled={!connected || !input.trim()}>
            Send
          </Button>
        </FlexItem>
      </Flex>
    </div>
  );
};

export default ChatPanel;
