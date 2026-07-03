import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import App from '../src/App';

describe('App', () => {
  it('renders the Session Setup panel', () => {
    render(<App />);
    expect(screen.getByText('Session Setup')).toBeDefined();
  });

  it('renders the Send button in the chat panel', () => {
    render(<App />);
    expect(screen.getByText('Send')).toBeDefined();
  });

  it('renders the Rerun Viewer placeholder', () => {
    render(<App />);
    expect(screen.getByText('Rerun Viewer')).toBeDefined();
  });

  it('renders Stop and Reset buttons', () => {
    render(<App />);
    expect(screen.getByText('Stop')).toBeDefined();
    expect(screen.getByText('Reset')).toBeDefined();
  });

  it('renders the Idle status label', () => {
    render(<App />);
    expect(screen.getByText('Idle')).toBeDefined();
  });
});
