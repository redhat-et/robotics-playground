import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import ControlBar from '../../src/components/ControlBar';

describe('ControlBar', () => {
  it('renders Stop and Reset buttons', () => {
    render(<ControlBar />);
    expect(screen.getByText('Stop')).toBeDefined();
    expect(screen.getByText('Reset')).toBeDefined();
  });

  it('renders the Idle status label', () => {
    render(<ControlBar />);
    expect(screen.getByText('Idle')).toBeDefined();
  });
});
