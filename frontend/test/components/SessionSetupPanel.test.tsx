import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import SessionSetupPanel from '../../src/components/SessionSetupPanel';

describe('SessionSetupPanel', () => {
  it('renders the model selector with DreamZero v1 option', () => {
    render(<SessionSetupPanel />);
    expect(screen.getByText('DreamZero v1')).toBeDefined();
  });

  it('renders the Start Session button', () => {
    render(<SessionSetupPanel />);
    expect(screen.getByText('Start Session')).toBeDefined();
  });
});
