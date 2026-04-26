import { useState, useEffect, useRef } from 'react';
import {
  getHealth,
  listSerialPorts,
  connectToSerial,
  autoConnectToSerial,
  disconnectFromSerial,
  getSerialStatus,
  getSerialData,
  getCurrentPosture,
  getPostureStats,
  getNoiseThresholds,
  getWebcamPostureSettings,
  stopWebcamWorker,
  startWebcamWorker
} from '../services/api';
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

const getNoiseLevel = (db, thresholds) => {
  if (db < thresholds.quiet) return { level: 'Quiet', color: '#4caf50', icon: '🔇' };
  if (db < thresholds.normal) return { level: 'Normal', color: '#2196f3', icon: '🔉' };
  if (db < thresholds.loud) return { level: 'Moderate', color: '#ff9800', icon: '🔊' };
  return { level: 'Loud', color: '#f44336', icon: '📢' };
};

function Dashboard() {
  const [health, setHealth] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [noiseThresholds, setNoiseThresholds] = useState({ quiet: 50, normal: 60, loud: 70 });

  // track serial port state
  const [ports, setPorts] = useState([]);
  const [selectedPort, setSelectedPort] = useState('');
  const [serialStatus, setSerialStatus] = useState({ connected: false, port: null });
  const [serialData, setSerialData] = useState(null);
  const [serialError, setSerialError] = useState(null);
  const [connecting, setConnecting] = useState(false);

  // posture tracking
  const [postureState, setPostureState] = useState(null);
  const [postureStats, setPostureStats] = useState(null);
  const [webcamEvents, setWebcamEvents] = useState([]);
  const [slouchTrend, setSlouchTrend] = useState([]);
  const [lastWebcamTs, setLastWebcamTs] = useState(null);
  const [webcamPreviewError, setWebcamPreviewError] = useState('');
  const [webcamPreviewReady, setWebcamPreviewReady] = useState(false);
  const [webcamControlBusy, setWebcamControlBusy] = useState(false);
  const [backendWebcamPaused, setBackendWebcamPaused] = useState(false);
  const webcamPreviewRef = useRef(null);
  const webcamLocalStreamRef = useRef(null);

  const { data: sensorData, status: wsStatus } = useDeskBuddyStream('ws://localhost:8000/stream');

  // ask for notification permission once on load so the alert can fire without a user gesture
  useEffect(() => {
    if ('Notification' in window && Notification.permission === 'default') {
      Notification.requestPermission();
    }
  }, []);

  const formatValue = (value, unit, decimals = 1) =>
    value == null ? '--' : `${Number(value).toFixed(decimals)}${unit}`;

  useEffect(() => {
    getNoiseThresholds().then(setNoiseThresholds).catch(console.error);
  }, []);

  useEffect(() => {
    async function syncWebcamWorkerState() {
      try {
        const data = await getWebcamPostureSettings();
        setBackendWebcamPaused(!data.running);
      } catch (err) {
        // If settings endpoint fails, keep current UI state.
      }
    }

    syncWebcamWorkerState();
    const interval = setInterval(syncWebcamWorkerState, 5000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (sensorData.ts && sensorData.slouch_score != null) {
      setLastWebcamTs(sensorData.ts);
      setSlouchTrend((prev) => [...prev.slice(-19), Number(sensorData.slouch_score)]);
    }

    if (sensorData.stream_type === 'webcam_posture_event' && sensorData.event_type) {
      const eventText = sensorData.event_type === 'state_changed'
        ? `State changed: ${sensorData.from_state} -> ${sensorData.to_state}`
        : `Slouching sustained (${sensorData.duration_sec}s)`;
      setWebcamEvents((prev) => [...prev.slice(-4), { ts: sensorData.ts, text: eventText }]);

      if (sensorData.event_type === 'slouching_sustained' && 'Notification' in window && Notification.permission === 'granted') {
        // tag replaces the previous alert instead of stacking them
        new Notification('Posture Alert', {
          body: `You've been slouching for ${Math.round(sensorData.duration_sec)}s — sit up straight!`,
          tag: 'slouch-alert'
        });
      }
    }
  }, [sensorData]);

  const stopPreview = () => {
    const stream = webcamLocalStreamRef.current;
    if (stream) {
      stream.getTracks().forEach((track) => track.stop());
      webcamLocalStreamRef.current = null;
    }
    if (webcamPreviewRef.current) {
      webcamPreviewRef.current.srcObject = null;
    }
    setWebcamPreviewReady(false);
  };

  const startPreview = async () => {
    stopPreview();

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      setWebcamPreviewError('Browser camera API is not available.');
      return false;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'user' },
        audio: false
      });

      webcamLocalStreamRef.current = stream;
      if (webcamPreviewRef.current) {
        webcamPreviewRef.current.srcObject = stream;
      }
      setWebcamPreviewReady(true);
      setWebcamPreviewError('');
      return true;
    } catch (err) {
      setWebcamPreviewReady(false);
      setWebcamPreviewError(
        'Unable to access webcam preview. Camera may be busy (often by backend worker).'
      );
      return false;
    }
  };

  // No auto-start: backend worker owns the camera on load.
  // Preview is only started when user explicitly pauses the backend.
  useEffect(() => {
    return () => {
      stopPreview();
    };
  }, []);

  const handlePauseBackendWebcam = async () => {
    setWebcamControlBusy(true);
    try {
      const data = await stopWebcamWorker();
      setBackendWebcamPaused(!data.running);

      // Give the backend capture a short moment to release the camera.
      await new Promise((resolve) => setTimeout(resolve, 400));
      const started = await startPreview();
      if (!started) {
        setWebcamPreviewError('Backend webcam paused. Retrying local preview...');
      }
    } catch (err) {
      setWebcamPreviewError(err.message || 'Failed to pause backend webcam worker.');
    } finally {
      setWebcamControlBusy(false);
    }
  };

  const handleResumeBackendWebcam = async () => {
    setWebcamControlBusy(true);
    try {
      stopPreview();
      const data = await startWebcamWorker();
      setBackendWebcamPaused(!data.running);
      setWebcamPreviewError('');
    } catch (err) {
      setWebcamPreviewError(err.message || 'Failed to resume backend webcam worker.');
    } finally {
      setWebcamControlBusy(false);
    }
  };

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
  const webcamFresh = lastWebcamTs && (Date.now() / 1000 - lastWebcamTs) < 8;
  const webcamAvailable = wsStatus === 'connected' && webcamFresh;
  const postureLabel = sensorData.posture_state || 'unknown';
  const postureColor = postureLabel === 'good'
    ? '#4caf50'
    : postureLabel === 'warning'
      ? '#ff9800'
      : postureLabel === 'slouching'
        ? '#f44336'
        : '#9e9e9e';

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

      {sensorData.sensor === 'noise_db' && sensorData.value != null && (
        <div className="card" style={{
          backgroundColor: (() => {
            const info = getNoiseLevel(sensorData.value, noiseThresholds);
            return info.color + '15';
          })(),
          border: (() => {
            const info = getNoiseLevel(sensorData.value, noiseThresholds);
            return `2px solid ${info.color}`;
          })()
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
            <div style={{ fontSize: '48px' }}>
              {getNoiseLevel(sensorData.value, noiseThresholds).icon}
            </div>
            <div>
              <h2 style={{
                margin: '0 0 8px 0',
                color: getNoiseLevel(sensorData.value, noiseThresholds).color
              }}>
                Noise Level: {getNoiseLevel(sensorData.value, noiseThresholds).level}
              </h2>
              <p style={{
                fontSize: '32px',
                fontWeight: 'bold',
                margin: '0',
                color: getNoiseLevel(sensorData.value, noiseThresholds).color
              }}>
                {sensorData.value.toFixed(1)} dB
              </p>
            </div>
          </div>
        </div>
      )}

      <div className="card" style={{ borderLeft: `6px solid ${postureColor}` }}>
        <h2>Webcam Posture</h2>

        <div style={{ marginBottom: '12px' }}>
          <strong>Camera preview (local only):</strong>
          {webcamPreviewError && (
            <p style={{ margin: '6px 0', color: '#f44336' }}>{webcamPreviewError}</p>
          )}
          <div style={{ display: 'flex', gap: '8px', margin: '8px 0', alignItems: 'center' }}>
            <button onClick={handlePauseBackendWebcam} disabled={webcamControlBusy || backendWebcamPaused}>
              {webcamControlBusy ? 'Working...' : 'Pause & Preview'}
            </button>
            <button onClick={handleResumeBackendWebcam} disabled={webcamControlBusy || !backendWebcamPaused}>
              {webcamControlBusy ? 'Working...' : 'Resume Detection'}
            </button>
            <span style={{ fontSize: '13px', color: backendWebcamPaused ? '#ff9800' : '#4caf50' }}>
              {backendWebcamPaused ? 'Detection paused — preview active' : 'Backend is analysing posture'}
            </span>
          </div>
          <div style={{ marginTop: '8px' }}>
            <video
              ref={webcamPreviewRef}
              autoPlay
              muted
              playsInline
              style={{
                width: '280px',
                maxWidth: '100%',
                borderRadius: '8px',
                border: '1px solid #ddd',
                transform: 'scaleX(-1)',
                backgroundColor: '#111'
              }}
            />
            {!webcamPreviewReady && !webcamPreviewError && (
              <p style={{ marginTop: '6px', color: '#666' }}>
                {backendWebcamPaused
                  ? 'Starting camera preview...'
                  : 'Click "Pause & Preview" to see the camera feed.'}
              </p>
            )}
          </div>
        </div>

        {!webcamAvailable ? (
          <div style={{ color: '#777' }}>
            <p style={{ margin: '8px 0' }}>Webcam is unavailable or no posture data yet.</p>
            {backendWebcamPaused && (
              <p style={{ margin: '8px 0' }}>Backend webcam worker is paused, so posture score is not updating.</p>
            )}
            <p style={{ margin: '8px 0' }}>Check camera permissions and make sure no other app is using it.</p>
          </div>
        ) : (
          <div>
            <p style={{ margin: '6px 0' }}>
              <strong>Current state:</strong>{' '}
              <span style={{ color: postureColor, fontWeight: 'bold' }}>{String(postureLabel).toUpperCase()}</span>
            </p>
            <p style={{ margin: '6px 0' }}>
              <strong>Live slouch score:</strong> {sensorData.slouch_score?.toFixed(1) ?? '--'}
            </p>
            <p style={{ margin: '6px 0' }}>
              <strong>Confidence:</strong> {sensorData.confidence?.toFixed(1) ?? '--'}%
            </p>

            <div style={{ marginTop: '10px' }}>
              <strong>Recent trend:</strong>
              <div style={{ display: 'flex', gap: '4px', marginTop: '8px', alignItems: 'flex-end' }}>
                {slouchTrend.slice(-12).map((score, idx) => (
                  <div
                    key={`${idx}-${score}`}
                    title={`Score ${score.toFixed(1)}`}
                    style={{
                      width: '10px',
                      height: `${Math.max(6, Math.min(48, score * 0.6))}px`,
                      backgroundColor: score < 35 ? '#4caf50' : score < 60 ? '#ff9800' : '#f44336',
                      borderRadius: '2px'
                    }}
                  />
                ))}
              </div>
            </div>

            {webcamEvents.length > 0 && (
              <div style={{ marginTop: '12px' }}>
                <strong>Recent events:</strong>
                {webcamEvents.slice().reverse().map((evt) => (
                  <p key={`${evt.ts}-${evt.text}`} style={{ margin: '4px 0', color: '#666' }}>
                    {evt.text}
                  </p>
                ))}
              </div>
            )}
          </div>
        )}
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
