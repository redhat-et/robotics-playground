import { useState, useEffect, useRef, useCallback } from 'react';
import { API_BASE } from '../utils/apiBase';

export interface SessionState {
  state: string;
  step: number;
  instruction: string;
  bridgeStatus: string;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'system';
  text: string;
  timestamp: number;
}

export interface UseSessionReturn {
  connected: boolean;
  sessionState: SessionState;
  messages: ChatMessage[];
  sendInstruction: (text: string) => void;
  sendSimControl: (action: string, speed?: number) => void;
}

const WS_RECONNECT_DELAY = 2000;
let messageCounter = 0;

export function useSession(sessionId: string): UseSessionReturn {
  const wsRef = useRef<WebSocket | null>(null);
  const [connected, setConnected] = useState(false);
  const [sessionState, setSessionState] = useState<SessionState>({
    state: 'idle',
    step: 0,
    instruction: '',
    bridgeStatus: 'mock',
  });
  const [messages, setMessages] = useState<ChatMessage[]>([]);


  useEffect(() => {
    let reconnectTimer: ReturnType<typeof setTimeout>;
    let disposed = false;

    function connect() {
      if (disposed) return;

      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const ws = new WebSocket(`${protocol}//${window.location.host}${API_BASE}/ws/sessions/${sessionId}`);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
      };

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === 'status') {
            setSessionState({
              state: msg.state ?? 'idle',
              step: msg.step ?? 0,
              instruction: msg.instruction ?? '',
              bridgeStatus: msg.bridge_status ?? 'mock',
            });
          } else if (msg.type === 'instruction_ack') {
            setMessages((prev) => [
              ...prev,
              {
                id: `ack-${++messageCounter}`,
                role: 'system',
                text: `${msg.status}: ${msg.text ?? ''}`.trim(),
                timestamp: Date.now(),
              },
            ]);
          }
        } catch {
          // ignore malformed messages
        }
      };

      ws.onclose = () => {
        setConnected(false);
        wsRef.current = null;
        if (!disposed) {
          reconnectTimer = setTimeout(connect, WS_RECONNECT_DELAY);
        }
      };

      ws.onerror = () => {
        ws.close();
      };
    }

    connect();

    return () => {
      disposed = true;
      clearTimeout(reconnectTimer);
      wsRef.current?.close();
    };
  }, [sessionId]);

  const sendInstruction = useCallback((text: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'instruction', text }));
      setMessages((prev) => [
        ...prev,
        {
          id: `user-${++messageCounter}`,
          role: 'user',
          text,
          timestamp: Date.now(),
        },
      ]);
    }
  }, []);

  const sendSimControl = useCallback((action: string, speed?: number) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      const msg: Record<string, unknown> = { type: 'sim_control', action };
      if (speed !== undefined) {
        msg.speed = speed;
      }
      wsRef.current.send(JSON.stringify(msg));
    }
  }, []);

  return { connected, sessionState, messages, sendInstruction, sendSimControl };
}
