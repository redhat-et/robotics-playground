import { useState, useEffect, useRef, useCallback } from 'react';
import { API_BASE, getWsBase } from '../utils/apiBase';

export interface SessionState {
  simStatus: string;
  simState: string;
  policyStatus: string;
  modelId: string;
  instruction: string;
  step: number;
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
  sendClearInstruction: () => void;
  sendSimControl: (action: string, speed?: number) => void;
  sendSelectModel: (modelId: string) => void;
}

const WS_RECONNECT_DELAY = 2000;
let messageCounter = 0;

export function useSession(sessionId: string): UseSessionReturn {
  const wsRef = useRef<WebSocket | null>(null);
  const [connected, setConnected] = useState(false);
  const [sessionState, setSessionState] = useState<SessionState>({
    simStatus: 'disconnected',
    simState: 'idle',
    policyStatus: 'disconnected',
    modelId: '',
    instruction: '',
    step: 0,
  });
  const [messages, setMessages] = useState<ChatMessage[]>([]);


  useEffect(() => {
    let reconnectTimer: ReturnType<typeof setTimeout>;
    let disposed = false;

    async function connect() {
      if (disposed) return;

      const wsBase = await getWsBase();
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsHost = wsBase || `${protocol}//${window.location.host}${API_BASE}`;
      const ws = new WebSocket(`${wsHost}/ws/sessions/${sessionId}`);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
      };

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === 'status') {
            setSessionState({
              simStatus: msg.sim_status ?? 'disconnected',
              simState: msg.sim_state ?? 'idle',
              policyStatus: msg.policy_status ?? 'disconnected',
              modelId: msg.model_id ?? '',
              instruction: msg.instruction ?? '',
              step: msg.step ?? 0,
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

  const sendClearInstruction = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'clear_instruction' }));
      setMessages([]);
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

  const sendSelectModel = useCallback((modelId: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'select_model', model_id: modelId }));
    }
  }, []);

  return { connected, sessionState, messages, sendInstruction, sendClearInstruction, sendSimControl, sendSelectModel };
}
