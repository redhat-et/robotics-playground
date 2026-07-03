import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import SimulationControlPanel from '../../src/components/SimulationControlPanel';

describe('SimulationControlPanel', () => {
  it('renders Play, Stop, and Reset buttons', () => {
    render(<SimulationControlPanel />);
    expect(screen.getByText('Play')).toBeDefined();
    expect(screen.getByText('Stop')).toBeDefined();
    expect(screen.getByText('Reset')).toBeDefined();
  });

  it('renders the Idle status label', () => {
    render(<SimulationControlPanel />);
    expect(screen.getByText('Idle')).toBeDefined();
  });
});
