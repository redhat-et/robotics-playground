import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import VisualizationPanel from '../src/components/VisualizationPanel';

describe('VisualizationPanel', () => {
  it('shows empty state when not connected', () => {
    render(<VisualizationPanel connected={false} />);
    expect(screen.getByText('Connecting to backend...')).toBeInTheDocument();
  });

  it('renders Rerun iframe when connected', () => {
    render(<VisualizationPanel connected={true} />);
    const iframe = document.querySelector('iframe');
    expect(iframe).not.toBeNull();
    expect(iframe?.title).toBe('Rerun Viewer');
  });

  it('iframe src contains correct Rerun version', () => {
    render(<VisualizationPanel connected={true} />);
    const iframe = document.querySelector('iframe');
    expect(iframe?.src).toContain('version/0.33.1');
  });

  it('iframe src contains gRPC connection URL', () => {
    render(<VisualizationPanel connected={true} />);
    const iframe = document.querySelector('iframe');
    expect(iframe?.src).toContain('rerun+http://');
    expect(iframe?.src).toContain(':9876/proxy');
  });

  it('does not render iframe when disconnected', () => {
    render(<VisualizationPanel connected={false} />);
    const iframe = document.querySelector('iframe');
    expect(iframe).toBeNull();
  });
});
