import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import App from '../src/App';

describe('App', () => {
  it('renders the Robotics Playground heading', () => {
    render(<App />);
    expect(screen.getByText('Robotics Playground')).toBeDefined();
  });

  it('renders the description text', () => {
    render(<App />);
    expect(
      screen.getByText(/Experiment with robot policy models/)
    ).toBeDefined();
  });
});
