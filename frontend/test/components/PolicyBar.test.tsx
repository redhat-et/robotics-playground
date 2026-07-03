import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import PolicyBar from '../../src/components/PolicyBar';

describe('PolicyBar', () => {
  it('renders the policy selector with DreamZero v1 option', () => {
    render(<PolicyBar />);
    expect(screen.getByText('DreamZero v1')).toBeDefined();
  });

  it('renders the Split button', () => {
    render(<PolicyBar />);
    expect(screen.getByText('Split')).toBeDefined();
  });
});
