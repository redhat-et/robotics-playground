import { describe, it, expect, afterEach, vi } from 'vitest';

describe('apiBase', () => {
  const originalPathname = window.location.pathname;

  afterEach(() => {
    Object.defineProperty(window, 'location', {
      value: { ...window.location, pathname: originalPathname },
      writable: true,
    });
    // Clear module cache so the next import re-evaluates
    vi.resetModules();
  });

  it('returns empty string in standalone mode', async () => {
    Object.defineProperty(window, 'location', {
      value: { ...window.location, pathname: '/' },
      writable: true,
    });
    const { API_BASE } = await import('../src/utils/apiBase');
    expect(API_BASE).toBe('');
  });

  it('returns /physical-ai when embedded in RHOAI', async () => {
    Object.defineProperty(window, 'location', {
      value: { ...window.location, pathname: '/physicalAiStudio/roboticsPlayground' },
      writable: true,
    });
    const { API_BASE } = await import('../src/utils/apiBase');
    expect(API_BASE).toBe('/physical-ai');
  });
});
