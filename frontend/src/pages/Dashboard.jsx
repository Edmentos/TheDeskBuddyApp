import { useState, useEffect } from 'react';
import { getHealth, listSerialPorts, connectToSerial, autoConnectToSerial, disconnectFromSerial, getSerialStatus, getSerialData } from '../services/api';
import { useDeskBuddyStream } from '../hooks/useDeskBuddyStream';

const STATUS_MAP = {
  connected: { text: 'Live', class: 'ok' },
  connecting: { text: 'Connecting...', class: 'warning' },
  disconnected: { text: 'Disconnected', class: 'error' }
};

const SENSORS = [
  { key: 'temp_c', icon: '🌡️', label: 'Temperature', unit: '°C', decimals: 1 },
  { key: 'hum_pct', icon: '💧', label: 'Humidity', unit: '%', decimals: 0 },
  { key: 'distance_cm', icon: '📏', label: 'Distance', unit: 'cm', decimals: 1 }
];

function Dashboard() {
  const [health, setHealth] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Serial connection state
  const [ports, setPorts] = useState([]);
  const [selectedPort, setSelectedPort] = useState('');
  const [serialStatus, setSerialStatus] = useState({ connected: false, port: null });
  const [serialError, setSerialError] = useState(null);
  const [connecting, setConnecting] = useState(false);

  // WebSocket live data
  const { data: sensorData, status: wsStatus } = useDeskBuddyStream('ws://localhost:8000/stream');

  const formatValue = (value, unit, decimals = 1) =>
    value == null ? '--' : `${Number(value).toFixed(decimals)}${unit}`;

  useEffect(() => {
    async function fetchHealth() {
      try {
        const data = await getHealth();
        setHealth(data);
        setError(null);
      } catch (err) {
        setError('Failed to connect to backend');
        setHealth(null);
      } finally {
        setLoading(false);
      }
    }

    fetchHealth();
    const interval = setInterval(fetchHealth, 10000);
    return () => clearInterval(interval);
  }, []);

  // Fetch available serial ports on mount
  useEffect(() => {
    async function fetchPorts() {
      try {
        const data = await listSerialPorts();
        setPorts(data.ports || []);
        if (data.ports && data.ports.length > 0) {
          setSelectedPort(data.ports[0].port);
        }
      } catch (err) {
        console.error('Failed to list serial ports:', err);
      }
    }
    fetchPorts();
  }, []);

  // Poll serial status and data
  useEffect(() => {
    async function fetchSerialStatus() {
      try {
        const status = await getSerialStatus();
        setSerialStatus(status);
        
        if (status.connected) {
          const data = await getSerialData();
          setSerialData(data.data);
        }
      } catch (err) {
        console.error('Failed to fetch serial status:', err);
      }
    }

    fetchSerialStatus();
    const interval = setInterval(fetchSerialStatus, 1000);
    return () => clearInterval(interval);
  }, []);

  const handleConnect = async () => {
    if (!selectedPort) {
      setSerialError('Please select a port');
      return;
    }
    
    setConnecting(true);
    setSerialError(null);
    
    try {
      await connectToSerial(selectedPort);
      setSerialError(null);
    } catch (err) {
      setSerialError(err.message || 'Failed to connect');
    } finally {
      setConnecting(false);
    }
  };

  const handleAutoConnect = async () => {
    setConnecting(true);
    setSerialError(null);
    
    try {
      const result = await autoConnectToSerial();
      setSerialError(null);
      setSelectedPort(result.port);
    } catch (err) {
      setSerialError(err.message || 'Failed to auto-connect');
    } finally {
      setConnecting(false);
    }
  };

  const handleDisconnect = async () => {
    try {
      await disconnectFromSerial();
      setSerialData(null);
      setSerialError(null);
    } catch (err) {
      setSerialError(err.message || 'Failed to disconnect');
    }
  };

  const handleRefreshPorts = async () => {
    try {
      const data = await listSerialPorts();
      setPorts(data.ports || []);
      if (data.ports && data.ports.length > 0 && !selectedPort) {
        setSelectedPort(data.ports[0].port);
      }
    } catch (err) {
      setSerialError('Failed to refresh ports');
    }
  };

  const { text: statusText, class: statusClass } = STATUS_MAP[wsStatus];

  return (
    <div>
      <h1>Dashboard</h1>

      <div className="card">
        <div className="status">
          <div className={`status-indicator ${statusClass}`}></div>
          <p>Stream: {statusText}</p>
        </div>
      </div>

      <div className="sensor-grid">
        {SENSORS.map(({ key, icon, label, unit, decimals }) => (
          <div key={key} className="sensor-tile">
            <div className="sensor-icon">{icon}</div>
            <div className="sensor-label">{label}</div>
            <div className="sensor-value">{formatValue(sensorData[key], unit, decimals)}</div>
          </div>
        ))}
      </div>

      <div className="card">
        <h2>Backend Status</h2>
        {loading && <p>Loading...</p>}
        {error && (
          <div className="status">
            <div className="status-indicator error"></div>
            <p>{error}</p>
          </div>
        )}
        {health && (
          <div>
            <div className="status">
              <div className="status-indicator ok"></div>
              <p>Status: {health.status}</p>
            </div>
            <p>Time (UTC): {health.time_utc}</p>
            <div className="status">
              <div className={`status-indicator ${health.db_ok ? 'ok' : 'error'}`}></div>
              <p>Database: {health.db_ok ? 'Connected' : 'Disconnected'}</p>
            </div>
          </div>
        )}
      </div>

      <div className="card">
        <h2>ESP32 Connection</h2>
        
        <div className="status" style={{ marginBottom: '1rem' }}>
          <div className={`status-indicator ${serialStatus.connected ? 'ok' : 'error'}`}></div>
          <p>
            {serialStatus.connected 
              ? `Connected to ${serialStatus.port}` 
              : 'Not connected'}
          </p>
        </div>

        {!serialStatus.connected ? (
          <div>
            <div style={{ marginBottom: '1rem', display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
              <select 
                value={selectedPort} 
                onChange={(e) => setSelectedPort(e.target.value)}
                style={{ 
                  padding: '0.5rem', 
                  borderRadius: '4px',
                  background: '#2a2a2a',
                  color: 'white',
                  border: '1px solid #444',
                  flex: 1
                }}
              >
                {ports.length === 0 && <option value="">No ports available</option>}
                {ports.map((port) => (
                  <option key={port.port} value={port.port}>
                    {port.port} - {port.description}
                  </option>
                ))}
              </select>
              <button onClick={handleRefreshPorts}>Refresh</button>
            </div>
            
            <button 
              onClick={handleConnect} 
              disabled={connecting || !selectedPort}
              style={{ marginRight: '0.5rem' }}
            >
              {connecting ? 'Connecting...' : 'Connect'}
            </button>
            <button 
              onClick={handleAutoConnect} 
              disabled={connecting}
            >
              Auto-Connect
            </button>
          </div>
        ) : (
          <button onClick={handleDisconnect}>Disconnect</button>
        )}

        {serialError && (
          <div style={{ marginTop: '1rem', color: '#f87171' }}>
            <p>Error: {serialError}</p>
          </div>
        )}
      </div>
    </div>
  );
}

export default Dashboard;
