import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import PolicyBar from '../src/components/PolicyBar';

const MOCK_MODELS = {
  models: [
    { id: 'dreamzero-v1', name: 'DreamZero', type: 'robotics' },
    { id: 'model-b', name: 'Model B', type: 'robotics' },
  ],
};

const defaultProps = {
  isSidebarOpen: true,
  onToggleSidebar: vi.fn(),
  selectedModel: '',
  onSelectModel: vi.fn(),
};

describe('PolicyBar', () => {
  let onSelectModel: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    vi.restoreAllMocks();
    onSelectModel = vi.fn();
  });

  it('shows loading spinner initially', () => {
    vi.spyOn(global, 'fetch').mockReturnValue(new Promise(() => {}));
    render(<PolicyBar {...defaultProps} onSelectModel={onSelectModel} />);
    expect(screen.getByLabelText('Loading models')).toBeInTheDocument();
  });

  it('renders model options after fetch', async () => {
    vi.spyOn(global, 'fetch').mockResolvedValue({
      json: () => Promise.resolve(MOCK_MODELS),
    } as Response);

    render(<PolicyBar {...defaultProps} selectedModel="dreamzero-v1" onSelectModel={onSelectModel} />);

    await waitFor(() => {
      expect(screen.getByText('DreamZero')).toBeInTheDocument();
    });
    expect(screen.getByText('Model B')).toBeInTheDocument();
  });

  it('does not auto-select a model when selectedModel is empty', async () => {
    vi.spyOn(global, 'fetch').mockResolvedValue({
      json: () => Promise.resolve(MOCK_MODELS),
    } as Response);

    render(<PolicyBar {...defaultProps} onSelectModel={onSelectModel} />);

    await waitFor(() => {
      expect(screen.getByText('DreamZero')).toBeInTheDocument();
    });
    expect(onSelectModel).not.toHaveBeenCalled();
  });

  it('does not auto-select when selectedModel is provided', async () => {
    vi.spyOn(global, 'fetch').mockResolvedValue({
      json: () => Promise.resolve(MOCK_MODELS),
    } as Response);

    render(<PolicyBar {...defaultProps} selectedModel="model-b" onSelectModel={onSelectModel} />);

    await waitFor(() => {
      expect(screen.getByText('DreamZero')).toBeInTheDocument();
    });
    expect(onSelectModel).not.toHaveBeenCalled();
  });

  it('shows disabled select when no models available', async () => {
    vi.spyOn(global, 'fetch').mockResolvedValue({
      json: () => Promise.resolve({ models: [] }),
    } as Response);

    render(<PolicyBar {...defaultProps} onSelectModel={onSelectModel} />);

    await waitFor(() => {
      expect(screen.getByText('No models available')).toBeInTheDocument();
    });
  });

  it('disables select when disabled prop is true', async () => {
    vi.spyOn(global, 'fetch').mockResolvedValue({
      json: () => Promise.resolve(MOCK_MODELS),
    } as Response);

    render(<PolicyBar {...defaultProps} selectedModel="dreamzero-v1" onSelectModel={onSelectModel} disabled />);

    await waitFor(() => {
      const select = screen.getByLabelText('Select policy') as HTMLSelectElement;
      expect(select.disabled).toBe(true);
    });
  });

  it('handles fetch error gracefully', async () => {
    vi.spyOn(global, 'fetch').mockRejectedValue(new Error('Network error'));

    render(<PolicyBar {...defaultProps} onSelectModel={onSelectModel} />);

    await waitFor(() => {
      expect(screen.getByText('No models available')).toBeInTheDocument();
    });
  });

  it('calls onSelectModel on change', async () => {
    vi.spyOn(global, 'fetch').mockResolvedValue({
      json: () => Promise.resolve(MOCK_MODELS),
    } as Response);

    render(<PolicyBar {...defaultProps} selectedModel="dreamzero-v1" onSelectModel={onSelectModel} />);

    await waitFor(() => {
      expect(screen.getByText('DreamZero')).toBeInTheDocument();
    });

    fireEvent.change(screen.getByLabelText('Select policy'), { target: { value: 'model-b' } });
    expect(onSelectModel).toHaveBeenCalledWith('model-b');
  });

  it('fetches from correct API endpoint', async () => {
    const fetchSpy = vi.spyOn(global, 'fetch').mockResolvedValue({
      json: () => Promise.resolve(MOCK_MODELS),
    } as Response);

    render(<PolicyBar {...defaultProps} onSelectModel={onSelectModel} />);

    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalledWith('/api/models?type=robotics');
    });
  });

  it('renders sidebar toggle button', () => {
    vi.spyOn(global, 'fetch').mockReturnValue(new Promise(() => {}));
    render(<PolicyBar {...defaultProps} />);
    expect(screen.getByLabelText('Toggle sidebar')).toBeInTheDocument();
  });

  it('calls onToggleSidebar when toggle button is clicked', async () => {
    const onToggle = vi.fn();
    const user = userEvent.setup();
    vi.spyOn(global, 'fetch').mockReturnValue(new Promise(() => {}));
    render(<PolicyBar {...defaultProps} onToggleSidebar={onToggle} />);

    await user.click(screen.getByLabelText('Toggle sidebar'));
    expect(onToggle).toHaveBeenCalledOnce();
  });

  it('sets aria-expanded based on isSidebarOpen', () => {
    vi.spyOn(global, 'fetch').mockReturnValue(new Promise(() => {}));
    const { rerender } = render(<PolicyBar {...defaultProps} isSidebarOpen={true} />);
    expect(screen.getByLabelText('Toggle sidebar')).toHaveAttribute('aria-expanded', 'true');

    rerender(<PolicyBar {...defaultProps} isSidebarOpen={false} />);
    expect(screen.getByLabelText('Toggle sidebar')).toHaveAttribute('aria-expanded', 'false');
  });
});
