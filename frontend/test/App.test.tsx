import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import App from '../src/App';

vi.spyOn(global, 'fetch').mockResolvedValue({
  json: () => Promise.resolve({ models: [{ id: 'dreamzero-v1', name: 'DreamZero', type: 'robotics' }] }),
} as Response);

describe('App', () => {
  it('renders the masthead with app title', () => {
    render(<App />);
    expect(screen.getByText('Robotics Playground')).toBeInTheDocument();
  });

  it('renders the sidebar panel', () => {
    render(<App />);
    expect(screen.getByText('Instructions & Control')).toBeInTheDocument();
  });

  it('renders the simulation control panel', () => {
    render(<App />);
    expect(screen.getByText('Simulation Control')).toBeInTheDocument();
  });
});
