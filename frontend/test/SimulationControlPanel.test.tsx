import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import SimulationControlPanel from '../src/components/SimulationControlPanel';

describe('SimulationControlPanel', () => {
  it('shows Idle label and Play button when idle', () => {
    render(<SimulationControlPanel state="idle" bridgeStatus="mock" onSimControl={vi.fn()} />);
    expect(screen.getByText('Idle')).toBeInTheDocument();
    expect(screen.getByText('Play')).toBeInTheDocument();
  });

  it('shows Running label and Pause button when running', () => {
    render(<SimulationControlPanel state="running" bridgeStatus="mock" onSimControl={vi.fn()} />);
    expect(screen.getByText('Running')).toBeInTheDocument();
    expect(screen.getByText('Pause')).toBeInTheDocument();
  });

  it('shows Paused label when paused', () => {
    render(<SimulationControlPanel state="paused" bridgeStatus="mock" onSimControl={vi.fn()} />);
    expect(screen.getByText('Paused')).toBeInTheDocument();
  });

  it('calls onSimControl with play and speed when Play is clicked', async () => {
    const onControl = vi.fn();
    const user = userEvent.setup();
    render(<SimulationControlPanel state="idle" bridgeStatus="mock" onSimControl={onControl} />);

    await user.click(screen.getByText('Play'));
    expect(onControl).toHaveBeenCalledWith('play', 1.0);
  });

  it('calls onSimControl with pause and speed when Pause is clicked', async () => {
    const onControl = vi.fn();
    const user = userEvent.setup();
    render(<SimulationControlPanel state="running" bridgeStatus="mock" onSimControl={onControl} />);

    await user.click(screen.getByText('Pause'));
    expect(onControl).toHaveBeenCalledWith('pause', 1.0);
  });

  it('calls onSimControl with stop when Stop is clicked', async () => {
    const onControl = vi.fn();
    const user = userEvent.setup();
    render(<SimulationControlPanel state="running" bridgeStatus="mock" onSimControl={onControl} />);

    await user.click(screen.getByText('Stop'));
    expect(onControl).toHaveBeenCalledWith('stop');
  });

  it('disables Stop button when idle', () => {
    render(<SimulationControlPanel state="idle" bridgeStatus="mock" onSimControl={vi.fn()} />);
    expect(screen.getByRole('button', { name: 'Stop' })).toBeDisabled();
  });

  it('disables Step button when running', () => {
    render(<SimulationControlPanel state="running" bridgeStatus="mock" onSimControl={vi.fn()} />);
    expect(screen.getByRole('button', { name: 'Step' })).toBeDisabled();
  });

  it('enables Step button when paused', async () => {
    const onControl = vi.fn();
    const user = userEvent.setup();
    render(<SimulationControlPanel state="paused" bridgeStatus="mock" onSimControl={onControl} />);

    const stepBtn = screen.getByRole('button', { name: 'Step' });
    expect(stepBtn).not.toBeDisabled();
    await user.click(stepBtn);
    expect(onControl).toHaveBeenCalledWith('step');
  });

  it('calls onSimControl with reset when Reset is clicked', async () => {
    const onControl = vi.fn();
    const user = userEvent.setup();
    render(<SimulationControlPanel state="running" bridgeStatus="connected" onSimControl={onControl} />);

    await user.click(screen.getByText('Reset'));
    expect(onControl).toHaveBeenCalledWith('reset');
  });

  it('disables Reset when bridge is disconnected', () => {
    render(<SimulationControlPanel state="running" bridgeStatus="disconnected" onSimControl={vi.fn()} />);
    const resetButton = screen.getByText('Reset');
    expect(resetButton.closest('button')).toBeDisabled();
  });

  it('shows Error label for error state', () => {
    render(<SimulationControlPanel state="error" bridgeStatus="mock" onSimControl={vi.fn()} />);
    expect(screen.getByText('Error')).toBeInTheDocument();
  });

  it('falls back to Idle label for unknown state', () => {
    render(<SimulationControlPanel state="bogus" bridgeStatus="mock" onSimControl={vi.fn()} />);
    expect(screen.getByText('Idle')).toBeInTheDocument();
  });

  it('renders bridge status label for mock', () => {
    render(<SimulationControlPanel state="idle" bridgeStatus="mock" onSimControl={vi.fn()} />);
    expect(screen.getByText('Mock')).toBeInTheDocument();
  });

  it('shows Connected label for connected bridge', () => {
    render(<SimulationControlPanel state="running" bridgeStatus="connected" onSimControl={vi.fn()} />);
    expect(screen.getByText('Connected')).toBeInTheDocument();
  });

  it('shows Disconnected label for disconnected bridge', () => {
    render(<SimulationControlPanel state="idle" bridgeStatus="disconnected" onSimControl={vi.fn()} />);
    expect(screen.getByText('Disconnected')).toBeInTheDocument();
  });

  it('renders speed slider', () => {
    render(<SimulationControlPanel state="running" bridgeStatus="mock" onSimControl={vi.fn()} />);
    expect(screen.getByRole('slider')).toBeInTheDocument();
  });

  it('shows speed label', () => {
    render(<SimulationControlPanel state="idle" bridgeStatus="mock" onSimControl={vi.fn()} />);
    expect(screen.getByText('Speed: 1.0x')).toBeInTheDocument();
  });
});
