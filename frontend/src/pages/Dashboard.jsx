import { useState, useEffect } from 'react';
import { getHealth, listSerialPorts, connectToSerial, autoConnectToSerial, disconnectFromSerial, getSerialStatus, getSerialData, getCurrentPosture, getPostureStats } from '../services/api';
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

  // track serial port state
  const [ports, setPorts] = useState([]);
  const [selectedPort, setSelectedPort] = useState('');
  const [serialStatus, setSerialStatus] = useState({ connected: false, port: null });
  const [serialError, setSerialError] = useState(null);
  const [connecting, setConnecting] = useState(false);

  // posture tracking
  const [postureState, setPostureState] = useState(null);
  const [postureStats, setPostureStats] = useState(null);

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

  useEffect(() => {
    async function fetchPosture() {
      try {
        const data = await getCurrentPosture();
        setPostureState(data);
      } catch (err) {
        console.error('Failed to fetch posture:', err);
      }
    }

    fetchPosture();
    const interval = setInterval(fetchPosture, 2000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    async function fetchStats() {
      try {
        const data = await getPostureStats();
        setPostureStats(data);
      } catch (err) {
        console.error('Failed to fetch stats:', err);
      }
    }

    fetchStats();
    const interval = setInterval(fetchStats, 30000);  // update every 30sec
    return () => clearInterval(interval);
  }, []);

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

      {postureState && (
        <div className="card">
          <h2>Current Posture</h2>
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '20px',
            fontSize: '18px'
          }}>
            <div style={{
              fontSize: '48px',
              padding: '20px',
              backgroundColor: postureState.current_state === 'standing' ? '#e3f2fd' : '#fff3e0',
              borderRadius: '10px'
            }}>
              {postureState.current_state === 'standing' ? '🧍' : '🪑'}
            </div>
            <div>
              <p style={{ fontWeight: 'bold', fontSize: '24px', margin: '0' }}>
                {postureState.current_state?.toUpperCase() || 'UNKNOWN'}
              </p>
              <p style={{ color: '#666', margin: '5px 0 0 0' }}>
                Distance: {postureState.smoothed_distance_cm?.toFixed(1) || '--'}cm
              </p>
            </div>
          </div>
        </div>
      )}

      {postureStats && (
        <div className="card">
          <h2>Today's Activity</h2>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
            <div>
              <p style={{ color: '#666', margin: '0 0 5px 0' }}>Sitting Time</p>
              <p style={{ fontSize: '24px', fontWeight: 'bold', margin: '0', color: '#ff9800' }}>
                {postureStats.sitting_hours?.toFixed(1) || '0'}h
              </p>
              <p style={{ color: '#666', fontSize: '14px', margin: '5px 0 0 0' }}>
                {postureStats.sitting_percentage?.toFixed(0) || '0'}%
              </p>
            </div>
            <div>
              <p style={{ color: '#666', margin: '0 0 5px 0' }}>Standing Time</p>
              <p style={{ fontSize: '24px', fontWeight: 'bold', margin: '0', color: '#4caf50' }}>
                {postureStats.standing_hours?.toFixed(1) || '0'}h
              </p>
              <p style={{ color: '#666', fontSize: '14px', margin: '5px 0 0 0' }}>
                {postureStats.standing_percentage?.toFixed(0) || '0'}%
              </p>
            </div>
          </div>
        </div>
      )}

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
