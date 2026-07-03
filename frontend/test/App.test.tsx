import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import ChatPanel from '../src/components/ChatPanel';
import SimulationControlPanel from '../src/components/SimulationControlPanel';

describe('ChatPanel', () => {
  it('renders the instructions heading', () => {
    render(<ChatPanel messages={[]} onSendInstruction={vi.fn()} connected={false} />);
    expect(screen.getByText('Instructions')).toBeDefined();
  });

  it('disables input when not connected', () => {
    render(<ChatPanel messages={[]} onSendInstruction={vi.fn()} connected={false} />);
    const input = screen.getByPlaceholderText('Tell the robot what to do...');
    expect(input).toBeDefined();
    expect((input as HTMLInputElement).disabled).toBe(true);
  });

  it('renders messages', () => {
    const messages = [
      { id: '1', role: 'user' as const, text: 'Pick up block', timestamp: 1 },
      { id: '2', role: 'system' as const, text: 'received', timestamp: 2 },
    ];
    render(<ChatPanel messages={messages} onSendInstruction={vi.fn()} connected={true} />);
    expect(screen.getByText('Pick up block')).toBeDefined();
    expect(screen.getByText('received')).toBeDefined();
  });
});

describe('SimulationControlPanel', () => {
  it('renders with idle state', () => {
    render(<SimulationControlPanel state="idle" onSimControl={vi.fn()} />);
    expect(screen.getByText('Idle')).toBeDefined();
    expect(screen.getByText('Play')).toBeDefined();
  });

  it('shows Pause button when running', () => {
    render(<SimulationControlPanel state="running" onSimControl={vi.fn()} />);
    expect(screen.getByText('Running')).toBeDefined();
    expect(screen.getByText('Pause')).toBeDefined();
  });
});
