import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import ChatPanel from '../../src/components/ChatPanel';

describe('ChatPanel', () => {
  it('renders the text input', () => {
    render(<ChatPanel />);
    expect(screen.getByLabelText('Chat message')).toBeDefined();
  });

  it('renders the Send button', () => {
    render(<ChatPanel />);
    expect(screen.getByText('Send')).toBeDefined();
  });
});
