import { useState, useEffect, useRef, useCallback } from 'react';

export function useDeskBuddyStream(url) {
  const [data, setData] = useState({
    temp_c: null,
    hum_pct: null,
    distance_cm: null,
    ts_utc: null
  });
  const [status, setStatus] = useState('connecting');

  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const reconnectDelayRef = useRef(500);
  const isMountedRef = useRef(true);

  const connect = useCallback(() => {
    if (!isMountedRef.current) return;

    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      if (!isMountedRef.current) return;
      setStatus('connected');
      reconnectDelayRef.current = 500;
    };

    ws.onmessage = (event) => {
      if (!isMountedRef.current) return;
      try {
        const message = JSON.parse(event.data);
        setData({
          temp_c: message.temp_c ?? null,
          hum_pct: message.hum_pct ?? null,
          distance_cm: message.distance_cm ?? null,
          ts_utc: message.ts_utc ?? null
        });
      } catch (error) {
        console.error('WebSocket parse error:', error);
      }
    };

    ws.onclose = () => {
      if (!isMountedRef.current) return;
      setStatus('disconnected');
      wsRef.current = null;

      const delay = Math.min(reconnectDelayRef.current, 5000);
      reconnectTimeoutRef.current = setTimeout(() => {
        reconnectDelayRef.current = Math.min(reconnectDelayRef.current * 2, 5000);
        setStatus('connecting');
        connect();
      }, delay);
    };

    ws.onerror = () => {
      ws.close();
    };
  }, [url]);

  useEffect(() => {
    isMountedRef.current = true;
    connect();

    return () => {
      isMountedRef.current = false;
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
      if (wsRef.current) wsRef.current.close();
    };
  }, [connect]);

  return { data, status };
}
