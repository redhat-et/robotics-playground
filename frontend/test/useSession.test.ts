import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useSession } from '../src/hooks/useSession';

class MockWebSocket {
  static instances: MockWebSocket[] = [];
  static OPEN = 1;
  readyState = 0; // CONNECTING
  onopen: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  sent: string[] = [];

  constructor(public url: string) {
    MockWebSocket.instances.push(this);
    setTimeout(() => {
      this.readyState = 1; // OPEN
      this.onopen?.();
    }, 0);
  }

  send(data: string) {
    this.sent.push(data);
  }

  close() {
    this.readyState = 3;
    this.onclose?.();
  }

  simulateMessage(data: object) {
    this.onmessage?.({ data: JSON.stringify(data) });
  }
}

describe('useSession', () => {
  let originalWebSocket: typeof WebSocket;

  beforeEach(() => {
    MockWebSocket.instances = [];
    originalWebSocket = global.WebSocket;
    global.WebSocket = MockWebSocket as unknown as typeof WebSocket;
  });

  afterEach(() => {
    global.WebSocket = originalWebSocket;
  });

  it('starts disconnected', () => {
    const { result } = renderHook(() => useSession('test-session'));
    expect(result.current.connected).toBe(false);
  });

  it('connects to WebSocket with correct URL', () => {
    renderHook(() => useSession('test-session'));
    expect(MockWebSocket.instances).toHaveLength(1);
    expect(MockWebSocket.instances[0].url).toContain('/ws/sessions/test-session');
  });

  it('sets connected to true on open', async () => {
    const { result } = renderHook(() => useSession('test-session'));

    await act(async () => {
      await new Promise((r) => setTimeout(r, 10));
    });

    expect(result.current.connected).toBe(true);
  });

  it('updates session state on status message', async () => {
    const { result } = renderHook(() => useSession('test-session'));

    await act(async () => {
      await new Promise((r) => setTimeout(r, 10));
    });

    act(() => {
      MockWebSocket.instances[0].simulateMessage({
        type: 'status',
        state: 'running',
        step: 42,
        instruction: 'wave',
      });
    });

    expect(result.current.sessionState.state).toBe('running');
    expect(result.current.sessionState.step).toBe(42);
    expect(result.current.sessionState.instruction).toBe('wave');
  });

  it('parses bridge_status from status messages', async () => {
    const { result } = renderHook(() => useSession('test-session'));

    await act(async () => {
      await new Promise((r) => setTimeout(r, 10));
    });

    act(() => {
      MockWebSocket.instances[0].simulateMessage({
        type: 'status',
        state: 'idle',
        step: 0,
        instruction: '',
        bridge_status: 'connected',
      });
    });

    expect(result.current.sessionState.bridgeStatus).toBe('connected');
  });

  it('defaults bridgeStatus to mock when not present', async () => {
    const { result } = renderHook(() => useSession('test-session'));

    await act(async () => {
      await new Promise((r) => setTimeout(r, 10));
    });

    act(() => {
      MockWebSocket.instances[0].simulateMessage({ type: 'status' });
    });

    expect(result.current.sessionState.bridgeStatus).toBe('mock');
  });

  it('adds ack messages to chat on instruction_ack', async () => {
    const { result } = renderHook(() => useSession('test-session'));

    await act(async () => {
      await new Promise((r) => setTimeout(r, 10));
    });

    act(() => {
      MockWebSocket.instances[0].simulateMessage({
        type: 'instruction_ack',
        status: 'received',
        text: 'wave',
      });
    });

    expect(result.current.messages).toHaveLength(1);
    expect(result.current.messages[0].role).toBe('system');
    expect(result.current.messages[0].text).toContain('received');
  });

  it('sendInstruction sends JSON and adds user message', async () => {
    const { result } = renderHook(() => useSession('test-session'));

    await act(async () => {
      await new Promise((r) => setTimeout(r, 10));
    });

    act(() => {
      result.current.sendInstruction('pick up block');
    });

    const sent = JSON.parse(MockWebSocket.instances[0].sent[0]);
    expect(sent.type).toBe('instruction');
    expect(sent.text).toBe('pick up block');

    expect(result.current.messages).toHaveLength(1);
    expect(result.current.messages[0].role).toBe('user');
    expect(result.current.messages[0].text).toBe('pick up block');
  });

  it('sendSimControl sends JSON with action', async () => {
    const { result } = renderHook(() => useSession('test-session'));

    await act(async () => {
      await new Promise((r) => setTimeout(r, 10));
    });

    act(() => {
      result.current.sendSimControl('play');
    });

    const sent = JSON.parse(MockWebSocket.instances[0].sent[0]);
    expect(sent.type).toBe('sim_control');
    expect(sent.action).toBe('play');
  });

  it('sendSimControl includes speed when provided', async () => {
    const { result } = renderHook(() => useSession('test-session'));

    await act(async () => {
      await new Promise((r) => setTimeout(r, 10));
    });

    act(() => {
      result.current.sendSimControl('play', 2.5);
    });

    const sent = JSON.parse(MockWebSocket.instances[0].sent[0]);
    expect(sent.type).toBe('sim_control');
    expect(sent.action).toBe('play');
    expect(sent.speed).toBe(2.5);
  });

  it('sendSimControl omits speed when not provided', async () => {
    const { result } = renderHook(() => useSession('test-session'));

    await act(async () => {
      await new Promise((r) => setTimeout(r, 10));
    });

    act(() => {
      result.current.sendSimControl('stop');
    });

    const sent = JSON.parse(MockWebSocket.instances[0].sent[0]);
    expect(sent.speed).toBeUndefined();
  });

  it('does not send when WebSocket is not open', () => {
    const { result } = renderHook(() => useSession('test-session'));

    act(() => {
      result.current.sendInstruction('wave');
    });

    expect(MockWebSocket.instances[0].sent).toHaveLength(0);
  });

  it('handles malformed WebSocket messages gracefully', async () => {
    const { result } = renderHook(() => useSession('test-session'));

    await act(async () => {
      await new Promise((r) => setTimeout(r, 10));
    });

    act(() => {
      MockWebSocket.instances[0].onmessage?.({ data: 'not json' });
    });

    expect(result.current.sessionState.state).toBe('idle');
  });

  it('defaults missing fields in status messages', async () => {
    const { result } = renderHook(() => useSession('test-session'));

    await act(async () => {
      await new Promise((r) => setTimeout(r, 10));
    });

    act(() => {
      MockWebSocket.instances[0].simulateMessage({ type: 'status' });
    });

    expect(result.current.sessionState.state).toBe('idle');
    expect(result.current.sessionState.step).toBe(0);
    expect(result.current.sessionState.instruction).toBe('');
  });

  it('cleans up WebSocket on unmount', async () => {
    const { unmount } = renderHook(() => useSession('test-session'));

    await act(async () => {
      await new Promise((r) => setTimeout(r, 10));
    });

    const ws = MockWebSocket.instances[0];
    unmount();
    expect(ws.readyState).toBe(3); // CLOSED
  });
});
