import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import VisualizationPanel from '../src/components/VisualizationPanel';

const MOCK_CONFIG = {
  wsUrl: 'wss://example.com',
  rerunViewerUrl: 'https://example.com/rerun',
  rerunGrpcUrl: 'https://example.com/grpc',
  rerunAssetsUrl: 'https://app.rerun.io/version/0.33.1/',
};

vi.mock('../src/utils/apiBase', () => ({
  getBackendConfig: vi.fn(),
}));

import { getBackendConfig } from '../src/utils/apiBase';
const mockGetBackendConfig = vi.mocked(getBackendConfig);

describe('VisualizationPanel', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    mockGetBackendConfig.mockReset();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('shows empty state while config is loading', () => {
    mockGetBackendConfig.mockReturnValue(new Promise(() => {}));
    render(<VisualizationPanel connected={false} />);
    expect(screen.getByText('Connecting to backend...')).toBeInTheDocument();
  });

  it('renders Rerun iframe when config succeeds', async () => {
    mockGetBackendConfig.mockResolvedValue(MOCK_CONFIG);
    render(<VisualizationPanel connected={true} />);

    await act(async () => {
      await vi.runAllTimersAsync();
    });

    const iframe = document.querySelector('iframe');
    expect(iframe).not.toBeNull();
    expect(iframe?.title).toBe('Rerun Viewer');
  });

  it('iframe src uses config URLs', async () => {
    mockGetBackendConfig.mockResolvedValue(MOCK_CONFIG);
    render(<VisualizationPanel connected={true} />);

    await act(async () => {
      await vi.runAllTimersAsync();
    });

    const iframe = document.querySelector('iframe');
    expect(iframe?.src).toContain('/rerun/');
    expect(iframe?.src).toContain('url=');
    expect(iframe?.src).toContain('grpc');
  });

  it('retries when config returns empty URLs', async () => {
    const EMPTY = { wsUrl: '', rerunViewerUrl: '', rerunGrpcUrl: '', rerunAssetsUrl: '' };
    mockGetBackendConfig.mockResolvedValue(EMPTY);

    render(<VisualizationPanel connected={true} />);

    await act(async () => {
      await Promise.resolve();
    });
    expect(document.querySelector('iframe')).toBeNull();
    expect(mockGetBackendConfig).toHaveBeenCalledTimes(1);

    mockGetBackendConfig.mockResolvedValue(MOCK_CONFIG);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(3000);
    });

    expect(mockGetBackendConfig).toHaveBeenCalledTimes(2);
    const iframe = document.querySelector('iframe');
    expect(iframe).not.toBeNull();
    expect(iframe?.title).toBe('Rerun Viewer');
  });

  it('does not render iframe when disconnected', () => {
    mockGetBackendConfig.mockReturnValue(new Promise(() => {}));
    render(<VisualizationPanel connected={false} />);
    const iframe = document.querySelector('iframe');
    expect(iframe).toBeNull();
  });
});
