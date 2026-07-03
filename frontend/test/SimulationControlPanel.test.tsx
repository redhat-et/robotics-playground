import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import SimulationControlPanel from '../src/components/SimulationControlPanel';

describe('SimulationControlPanel', () => {
  it('shows Idle label and Play button when idle', () => {
    render(<SimulationControlPanel state="idle" onSimControl={vi.fn()} />);
    expect(screen.getByText('Idle')).toBeInTheDocument();
    expect(screen.getByText('Play')).toBeInTheDocument();
  });

  it('shows Running label and Pause button when running', () => {
    render(<SimulationControlPanel state="running" onSimControl={vi.fn()} />);
    expect(screen.getByText('Running')).toBeInTheDocument();
    expect(screen.getByText('Pause')).toBeInTheDocument();
  });

  it('shows Paused label when paused', () => {
    render(<SimulationControlPanel state="paused" onSimControl={vi.fn()} />);
    expect(screen.getByText('Paused')).toBeInTheDocument();
  });

  it('calls onSimControl with play when Play is clicked', async () => {
    const onControl = vi.fn();
    const user = userEvent.setup();
    render(<SimulationControlPanel state="idle" onSimControl={onControl} />);

    await user.click(screen.getByText('Play'));
    expect(onControl).toHaveBeenCalledWith('play');
  });

  it('calls onSimControl with pause when Pause is clicked', async () => {
    const onControl = vi.fn();
    const user = userEvent.setup();
    render(<SimulationControlPanel state="running" onSimControl={onControl} />);

    await user.click(screen.getByText('Pause'));
    expect(onControl).toHaveBeenCalledWith('pause');
  });

  it('calls onSimControl with stop when Stop is clicked', async () => {
    const onControl = vi.fn();
    const user = userEvent.setup();
    render(<SimulationControlPanel state="running" onSimControl={onControl} />);

    await user.click(screen.getByText('Stop'));
    expect(onControl).toHaveBeenCalledWith('stop');
  });

  it('disables Stop button when idle', () => {
    render(<SimulationControlPanel state="idle" onSimControl={vi.fn()} />);
    expect(screen.getByRole('button', { name: 'Stop' })).toBeDisabled();
  });

  it('disables Step button when running', () => {
    render(<SimulationControlPanel state="running" onSimControl={vi.fn()} />);
    expect(screen.getByRole('button', { name: 'Step' })).toBeDisabled();
  });

  it('enables Step button when paused', async () => {
    const onControl = vi.fn();
    const user = userEvent.setup();
    render(<SimulationControlPanel state="paused" onSimControl={onControl} />);

    const stepBtn = screen.getByRole('button', { name: 'Step' });
    expect(stepBtn).not.toBeDisabled();
    await user.click(stepBtn);
    expect(onControl).toHaveBeenCalledWith('step');
  });

  it('calls onSimControl with reset when Reset is clicked', async () => {
    const onControl = vi.fn();
    const user = userEvent.setup();
    render(<SimulationControlPanel state="running" onSimControl={onControl} />);

    await user.click(screen.getByText('Reset'));
    expect(onControl).toHaveBeenCalledWith('reset');
  });

  it('shows Error label for error state', () => {
    render(<SimulationControlPanel state="error" onSimControl={vi.fn()} />);
    expect(screen.getByText('Error')).toBeInTheDocument();
  });

  it('falls back to Idle label for unknown state', () => {
    render(<SimulationControlPanel state="bogus" onSimControl={vi.fn()} />);
    expect(screen.getByText('Idle')).toBeInTheDocument();
  });
});
