import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import SimulationControlPanel from '../src/components/SimulationControlPanel';

describe('SimulationControlPanel', () => {
  it('shows Play button when idle', () => {
    render(<SimulationControlPanel simState="idle" simStatus="connected" onSimControl={vi.fn()} />);
    expect(screen.getByText('Play')).toBeInTheDocument();
  });

  it('shows Pause button when running', () => {
    render(<SimulationControlPanel simState="running" simStatus="connected" onSimControl={vi.fn()} />);
    expect(screen.getByText('Pause')).toBeInTheDocument();
  });

  it('calls onSimControl with play and speed when Play is clicked', async () => {
    const onControl = vi.fn();
    const user = userEvent.setup();
    render(<SimulationControlPanel simState="idle" simStatus="connected" onSimControl={onControl} />);

    await user.click(screen.getByText('Play'));
    expect(onControl).toHaveBeenCalledWith('play', 1.0);
  });

  it('calls onSimControl with pause and speed when Pause is clicked', async () => {
    const onControl = vi.fn();
    const user = userEvent.setup();
    render(<SimulationControlPanel simState="running" simStatus="connected" onSimControl={onControl} />);

    await user.click(screen.getByText('Pause'));
    expect(onControl).toHaveBeenCalledWith('pause', 1.0);
  });

  it('calls onSimControl with stop when Stop is clicked', async () => {
    const onControl = vi.fn();
    const user = userEvent.setup();
    render(<SimulationControlPanel simState="running" simStatus="connected" onSimControl={onControl} />);

    await user.click(screen.getByText('Stop'));
    expect(onControl).toHaveBeenCalledWith('stop');
  });

  it('disables Stop button when idle', () => {
    render(<SimulationControlPanel simState="idle" simStatus="connected" onSimControl={vi.fn()} />);
    expect(screen.getByRole('button', { name: 'Stop' })).toBeDisabled();
  });

  it('disables Step button when running', () => {
    render(<SimulationControlPanel simState="running" simStatus="connected" onSimControl={vi.fn()} />);
    expect(screen.getByRole('button', { name: 'Step' })).toBeDisabled();
  });

  it('enables Step button when idle and connected', async () => {
    const onControl = vi.fn();
    const user = userEvent.setup();
    render(<SimulationControlPanel simState="idle" simStatus="connected" onSimControl={onControl} />);

    const stepBtn = screen.getByRole('button', { name: 'Step' });
    expect(stepBtn).not.toBeDisabled();
    await user.click(stepBtn);
    expect(onControl).toHaveBeenCalledWith('step');
  });

  it('calls onSimControl with reset when Reset is clicked', async () => {
    const onControl = vi.fn();
    const user = userEvent.setup();
    render(<SimulationControlPanel simState="running" simStatus="connected" onSimControl={onControl} />);

    await user.click(screen.getByText('Reset'));
    expect(onControl).toHaveBeenCalledWith('reset');
  });

  it('disables Play and Step when sim is disconnected', () => {
    render(<SimulationControlPanel simState="idle" simStatus="disconnected" onSimControl={vi.fn()} />);
    expect(screen.getByRole('button', { name: /Play/ })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Step' })).toBeDisabled();
  });

  it('shows Connected status badge', () => {
    render(<SimulationControlPanel simState="idle" simStatus="connected" onSimControl={vi.fn()} />);
    expect(screen.getByText('Connected')).toBeInTheDocument();
  });

  it('shows Mock mode status badge', () => {
    render(<SimulationControlPanel simState="idle" simStatus="mock" onSimControl={vi.fn()} />);
    expect(screen.getByText('Mock mode')).toBeInTheDocument();
  });

  it('shows Connecting status badge when disconnected', () => {
    render(<SimulationControlPanel simState="idle" simStatus="disconnected" onSimControl={vi.fn()} />);
    expect(screen.getByText('Connecting…')).toBeInTheDocument();
  });

  it('renders speed slider', () => {
    render(<SimulationControlPanel simState="running" simStatus="connected" onSimControl={vi.fn()} />);
    expect(screen.getByRole('slider')).toBeInTheDocument();
  });

  it('shows speed label', () => {
    render(<SimulationControlPanel simState="idle" simStatus="connected" onSimControl={vi.fn()} />);
    expect(screen.getByText('Speed: 1.0x')).toBeInTheDocument();
  });
});
