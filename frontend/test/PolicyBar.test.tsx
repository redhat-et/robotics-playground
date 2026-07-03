import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import PolicyBar from '../src/components/PolicyBar';

const MOCK_MODELS = {
  models: [
    { id: 'dreamzero-v1', name: 'DreamZero', type: 'robotics' },
    { id: 'model-b', name: 'Model B', type: 'robotics' },
  ],
};

describe('PolicyBar', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('shows loading spinner initially', () => {
    vi.spyOn(global, 'fetch').mockReturnValue(new Promise(() => {}));
    render(<PolicyBar />);
    expect(screen.getByLabelText('Loading models')).toBeInTheDocument();
  });

  it('renders model options after fetch', async () => {
    vi.spyOn(global, 'fetch').mockResolvedValue({
      json: () => Promise.resolve(MOCK_MODELS),
    } as Response);

    render(<PolicyBar />);

    await waitFor(() => {
      expect(screen.getByText('DreamZero')).toBeInTheDocument();
    });
    expect(screen.getByText('Model B')).toBeInTheDocument();
  });

  it('selects first model by default', async () => {
    vi.spyOn(global, 'fetch').mockResolvedValue({
      json: () => Promise.resolve(MOCK_MODELS),
    } as Response);

    render(<PolicyBar />);

    await waitFor(() => {
      const select = screen.getByLabelText('Select policy') as HTMLSelectElement;
      expect(select.value).toBe('dreamzero-v1');
    });
  });

  it('shows disabled select when no models available', async () => {
    vi.spyOn(global, 'fetch').mockResolvedValue({
      json: () => Promise.resolve({ models: [] }),
    } as Response);

    render(<PolicyBar />);

    await waitFor(() => {
      expect(screen.getByText('No models available')).toBeInTheDocument();
    });
  });

  it('handles fetch error gracefully', async () => {
    vi.spyOn(global, 'fetch').mockRejectedValue(new Error('Network error'));

    render(<PolicyBar />);

    await waitFor(() => {
      expect(screen.getByText('No models available')).toBeInTheDocument();
    });
  });

  it('renders the Split button', async () => {
    vi.spyOn(global, 'fetch').mockResolvedValue({
      json: () => Promise.resolve(MOCK_MODELS),
    } as Response);

    render(<PolicyBar />);
    expect(screen.getByText('Split')).toBeInTheDocument();
  });

  it('fetches from correct API endpoint', async () => {
    const fetchSpy = vi.spyOn(global, 'fetch').mockResolvedValue({
      json: () => Promise.resolve(MOCK_MODELS),
    } as Response);

    render(<PolicyBar />);

    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalledWith('/api/models?type=robotics');
    });
  });
});
