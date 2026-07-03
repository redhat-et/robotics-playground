import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import ChatPanel from '../src/components/ChatPanel';

describe('ChatPanel', () => {
  it('renders the instructions heading', () => {
    render(<ChatPanel messages={[]} onSendInstruction={vi.fn()} connected={false} />);
    expect(screen.getByText('Instructions')).toBeInTheDocument();
  });

  it('disables input when not connected', () => {
    render(<ChatPanel messages={[]} onSendInstruction={vi.fn()} connected={false} />);
    const input = screen.getByPlaceholderText('Tell the robot what to do...');
    expect(input).toBeDisabled();
  });

  it('enables input when connected', () => {
    render(<ChatPanel messages={[]} onSendInstruction={vi.fn()} connected={true} />);
    const input = screen.getByPlaceholderText('Tell the robot what to do...');
    expect(input).not.toBeDisabled();
  });

  it('disables send button when input is empty', () => {
    render(<ChatPanel messages={[]} onSendInstruction={vi.fn()} connected={true} />);
    const button = screen.getByRole('button', { name: 'Send' });
    expect(button).toBeDisabled();
  });

  it('calls onSendInstruction when send button is clicked', async () => {
    const onSend = vi.fn();
    const user = userEvent.setup();
    render(<ChatPanel messages={[]} onSendInstruction={onSend} connected={true} />);

    const input = screen.getByPlaceholderText('Tell the robot what to do...');
    await user.type(input, 'pick up block');
    await user.click(screen.getByRole('button', { name: 'Send' }));

    expect(onSend).toHaveBeenCalledWith('pick up block');
  });

  it('clears input after sending', async () => {
    const user = userEvent.setup();
    render(<ChatPanel messages={[]} onSendInstruction={vi.fn()} connected={true} />);

    const input = screen.getByPlaceholderText('Tell the robot what to do...');
    await user.type(input, 'wave');
    await user.click(screen.getByRole('button', { name: 'Send' }));

    expect(input).toHaveValue('');
  });

  it('sends on Enter key', async () => {
    const onSend = vi.fn();
    const user = userEvent.setup();
    render(<ChatPanel messages={[]} onSendInstruction={onSend} connected={true} />);

    const input = screen.getByPlaceholderText('Tell the robot what to do...');
    await user.type(input, 'wave{Enter}');

    expect(onSend).toHaveBeenCalledWith('wave');
  });

  it('does not send whitespace-only input', async () => {
    const onSend = vi.fn();
    const user = userEvent.setup();
    render(<ChatPanel messages={[]} onSendInstruction={onSend} connected={true} />);

    const input = screen.getByPlaceholderText('Tell the robot what to do...');
    await user.type(input, '   {Enter}');

    expect(onSend).not.toHaveBeenCalled();
  });

  it('renders user and system messages', () => {
    const messages = [
      { id: '1', role: 'user' as const, text: 'Pick up block', timestamp: 1 },
      { id: '2', role: 'system' as const, text: 'received: Pick up block', timestamp: 2 },
    ];
    render(<ChatPanel messages={messages} onSendInstruction={vi.fn()} connected={true} />);
    expect(screen.getByText('Pick up block')).toBeInTheDocument();
    expect(screen.getByText('received: Pick up block')).toBeInTheDocument();
  });

  it('applies correct CSS class for user messages', () => {
    const messages = [
      { id: '1', role: 'user' as const, text: 'test message', timestamp: 1 },
    ];
    render(<ChatPanel messages={messages} onSendInstruction={vi.fn()} connected={true} />);
    const messageEl = screen.getByText('test message').closest('.chat-panel__message');
    expect(messageEl).toHaveClass('chat-panel__message--user');
  });

  it('applies correct CSS class for system messages', () => {
    const messages = [
      { id: '1', role: 'system' as const, text: 'system msg', timestamp: 1 },
    ];
    render(<ChatPanel messages={messages} onSendInstruction={vi.fn()} connected={true} />);
    const messageEl = screen.getByText('system msg').closest('.chat-panel__message');
    expect(messageEl).toHaveClass('chat-panel__message--system');
  });
});
