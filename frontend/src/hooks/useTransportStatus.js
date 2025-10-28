import { useEffect, useState } from 'react';
import { getSocketInstance, isSocketConnected } from '../lib/socket.js';

/**
 * useTransportStatus: Hook that returns "socket" or "offline" based on socket connection events
 * - Listens to connect/disconnect/connect_error events
 * - Returns "socket" when connected, "offline" otherwise
 */
export default function useTransportStatus() {
  const [status, setStatus] = useState(isSocketConnected() ? 'socket' : 'offline');

  useEffect(() => {
    const socket = getSocketInstance();

    const handleConnect = () => {
      console.log('[useTransportStatus] Socket connected');
      setStatus('socket');
    };

    const handleDisconnect = (reason) => {
      console.log('[useTransportStatus] Socket disconnected:', reason);
      setStatus('offline');
    };

    const handleConnectError = (err) => {
      console.error('[useTransportStatus] Socket connect error:', err);
      setStatus('offline');
    };

    socket.on('connect', handleConnect);
    socket.on('disconnect', handleDisconnect);
    socket.on('connect_error', handleConnectError);

    return () => {
      socket.off('connect', handleConnect);
      socket.off('disconnect', handleDisconnect);
      socket.off('connect_error', handleConnectError);
    };
  }, []);

  return status;
}
