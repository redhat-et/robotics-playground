import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import ChatPanel from '../../src/components/ChatPanel';

describe('ChatPanel', () => {
  it('renders the text input with placeholder', () => {
    render(<ChatPanel />);
    expect(screen.getByPlaceholderText('Tell the robot what to do...')).toBeDefined();
  });

  it('renders the Send button', () => {
    render(<ChatPanel />);
    expect(screen.getByText('Send')).toBeDefined();
  });
});
