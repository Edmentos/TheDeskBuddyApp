import { useState, useEffect } from 'react';
import { getHealth } from '../services/api';
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
  const { data: sensorData, status: wsStatus } = useDeskBuddyStream('ws://localhost:8000/stream');

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

  const formatValue = (value, unit, decimals = 1) =>
    value == null ? '--' : `${value.toFixed(decimals)}${unit}`;

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
    </div>
  );
}

export default Dashboard;
