import { useState, useEffect } from 'react';
import {
  recordSittingHeight,
  recordStandingHeight,
  saveCalibration as saveCalibrationAPI,
  getNoiseThresholds,
  updateNoiseThresholds,
  getWebcamPostureSettings,
  updateWebcamPostureSettings,
  calibrateWebcamPosture
} from '../services/api';

function Settings() {
  const [sittingHeight, setSittingHeight] = useState(80);
  const [standingOffset, setStandingOffset] = useState(10);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [currentState, setCurrentState] = useState('');

  // calibration mode
  const [calibMode, setCalibMode] = useState(false);
  const [calibSitting, setCalibSitting] = useState(null);
  const [calibStanding, setCalibStanding] = useState(null);
  const [calibMessage, setCalibMessage] = useState('');

  // noise thresholds
  const [noiseThresholds, setNoiseThresholds] = useState({ quiet: 50, normal: 60, loud: 70 });
  const [noiseMessage, setNoiseMessage] = useState('');

  // webcam posture settings
  const [webcamAvailable, setWebcamAvailable] = useState(false);
  const [webcamBaseline, setWebcamBaseline] = useState(null);
  const [webcamTolerances, setWebcamTolerances] = useState({
    ear_span: 0.15,
    head_drop: 0.15
  });
  const [webcamMessage, setWebcamMessage] = useState('');

  // Load current settings on mount
  useEffect(() => {
    fetchSettings();
    getNoiseThresholds().then(setNoiseThresholds).catch(console.error);
    getWebcamPostureSettings()
      .then((data) => {
        setWebcamAvailable(Boolean(data.webcam_available));
        if (data.baseline) setWebcamBaseline(data.baseline);
        if (data.tolerances) setWebcamTolerances(data.tolerances);
      })
      .catch(console.error);
  }, []);

  const fetchSettings = async () => {
    try {
      const response = await fetch('http://localhost:8000/settings/posture');
      const data = await response.json();
      setSittingHeight(data.sitting_height_cm);
      setStandingOffset(data.standing_offset_cm);
      setCurrentState(data.current_state);
    } catch (error) {
      console.error('Failed to fetch settings:', error);
    }
  };

  const handleSave = async () => {
    setLoading(true);
    setMessage('');

    try {
      const response = await fetch('http://localhost:8000/settings/posture', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          sitting_height_cm: parseFloat(sittingHeight),
          standing_offset_cm: parseFloat(standingOffset),
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setMessage(`Settings saved! Standing threshold: ${data.standing_threshold_cm.toFixed(1)}cm`);
        await fetchSettings();
      } else {
        setMessage('Failed to save settings');
      }
    } catch (error) {
      setMessage('Error saving settings: ' + error.message);
    } finally {
      setLoading(false);
    }
  };

  const recordSitting = async () => {
    setCalibMessage('');
    try {
      const data = await recordSittingHeight();
      setCalibSitting(data.sitting_height_cm);
      setCalibMessage(`Sitting position recorded: ${data.sitting_height_cm.toFixed(1)}cm`);
    } catch (error) {
      setCalibMessage('Error: ' + error.message);
    }
  };

  const recordStanding = async () => {
    setCalibMessage('');
    try {
      const data = await recordStandingHeight();
      setCalibStanding(data.standing_height_cm);
      setCalibMessage(`Standing position recorded: ${data.standing_height_cm.toFixed(1)}cm`);
    } catch (error) {
      setCalibMessage('Error: ' + error.message);
    }
  };

  const saveCalibration = async () => {
    if (!calibSitting || !calibStanding) {
      setCalibMessage('Please record both sitting and standing heights first');
      return;
    }

    setLoading(true);
    setCalibMessage('');

    try {
      const data = await saveCalibrationAPI(calibSitting, calibStanding);
      setCalibMessage(`Calibration saved! Threshold: ${data.threshold.toFixed(1)}cm`);
      setCalibMode(false);
      await fetchSettings();
    } catch (error) {
      setCalibMessage('Error: ' + error.message);
    } finally {
      setLoading(false);
    }
  };

  const saveNoiseSettings = async () => {
    setLoading(true);
    setNoiseMessage('');
    try {
      await updateNoiseThresholds(noiseThresholds);
      setNoiseMessage('Noise thresholds saved!');
    } catch (error) {
      setNoiseMessage('Error: ' + error.message);
    } finally {
      setLoading(false);
    }
  };

  const saveWebcamSettings = async () => {
    setLoading(true);
    setWebcamMessage('');
    try {
      const data = await updateWebcamPostureSettings(webcamTolerances);
      if (data.baseline) setWebcamBaseline(data.baseline);
      if (data.tolerances) setWebcamTolerances(data.tolerances);
      setWebcamMessage('Webcam posture tolerances saved!');
    } catch (error) {
      setWebcamMessage('Error: ' + error.message);
    } finally {
      setLoading(false);
    }
  };

  const runWebcamCalibration = async () => {
    setLoading(true);
    setWebcamMessage('');
    try {
      const data = await calibrateWebcamPosture(10, 4);
      setWebcamBaseline(data.baseline);
      if (data.tolerances) setWebcamTolerances(data.tolerances);
      setWebcamMessage('Webcam baseline calibrated successfully!');
    } catch (error) {
      setWebcamMessage('Error: ' + error.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <h1>Settings</h1>
      
      <div className="card" style={{ maxWidth: '600px' }}>
        <h2>Posture Detection</h2>
        
        <div style={{ marginBottom: '20px' }}>
          <p style={{ color: '#666', fontSize: '14px' }}>
            Configure your desk height to detect sitting and standing positions.
            The system uses smoothing to filter out sensor spikes.
          </p>
        </div>

        {currentState && (
          <div style={{ 
            padding: '10px', 
            marginBottom: '20px', 
            backgroundColor: currentState === 'standing' ? '#e3f2fd' : '#fff3e0',
            borderRadius: '4px',
            textAlign: 'center'
          }}>
            <strong>Current Posture:</strong> {currentState.toUpperCase()}
          </div>
        )}

        <div style={{ marginBottom: '20px' }}>
          <label style={{ display: 'block', marginBottom: '8px', fontWeight: 'bold' }}>
            Sitting Desk Height (cm)
          </label>
          <input
            type="number"
            value={sittingHeight}
            onChange={(e) => setSittingHeight(e.target.value)}
            min="10"
            max="200"
            step="1"
            style={{
              width: '100%',
              padding: '8px',
              fontSize: '16px',
              border: '1px solid #ccc',
              borderRadius: '4px'
            }}
          />
          <small style={{ color: '#666', fontSize: '12px' }}>
            Maximum height when sitting (e.g., 80cm)
          </small>
        </div>

        <div style={{ marginBottom: '20px' }}>
          <label style={{ display: 'block', marginBottom: '8px', fontWeight: 'bold' }}>
            Standing Detection Offset (cm)
          </label>
          <input
            type="number"
            value={standingOffset}
            onChange={(e) => setStandingOffset(e.target.value)}
            min="5"
            max="50"
            step="1"
            style={{
              width: '100%',
              padding: '8px',
              fontSize: '16px',
              border: '1px solid #ccc',
              borderRadius: '4px'
            }}
          />
          <small style={{ color: '#666', fontSize: '12px' }}>
            Distance above sitting height to be considered standing (default: 10cm)
          </small>
        </div>

        <div style={{ 
          padding: '12px', 
          backgroundColor: '#f5f5f5', 
          borderRadius: '4px',
          marginBottom: '20px'
        }}>
          <strong>Standing threshold:</strong> {(parseFloat(sittingHeight) + parseFloat(standingOffset)).toFixed(1)}cm
          <br />
          <small style={{ color: '#666' }}>
            You'll be marked as standing when desk height ≥ this value
          </small>
        </div>

        <button
          onClick={handleSave}
          disabled={loading}
          style={{
            width: '100%',
            padding: '12px',
            fontSize: '16px',
            fontWeight: 'bold',
            backgroundColor: '#007bff',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: loading ? 'not-allowed' : 'pointer',
            opacity: loading ? 0.6 : 1
          }}
        >
          {loading ? 'Saving...' : 'Save Settings'}
        </button>

        {message && (
          <div style={{
            marginTop: '15px',
            padding: '10px',
            backgroundColor: message.includes('saved') ? '#d4edda' : '#f8d7da',
            color: message.includes('saved') ? '#155724' : '#721c24',
            borderRadius: '4px',
            fontSize: '14px'
          }}>
            {message}
          </div>
        )}
      </div>

      <div className="card" style={{ maxWidth: '600px', marginTop: '20px' }}>
        <h2>Automatic Calibration</h2>
        <p style={{ color: '#666', fontSize: '14px', marginBottom: '15px' }}>
          For best results, automatically capture your desk heights
        </p>

        {!calibMode ? (
          <button
            onClick={() => setCalibMode(true)}
            style={{
              padding: '10px 20px',
              fontSize: '16px',
              backgroundColor: '#28a745',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer'
            }}
          >
            Start Calibration
          </button>
        ) : (
          <div>
            <div style={{ marginBottom: '15px' }}>
              <p style={{ fontWeight: 'bold', marginBottom: '10px' }}>
                Step 1: Sit at your desk
              </p>
              <button
                onClick={recordSitting}
                disabled={loading}
                style={{
                  padding: '10px 20px',
                  fontSize: '14px',
                  backgroundColor: calibSitting ? '#6c757d' : '#007bff',
                  color: 'white',
                  border: 'none',
                  borderRadius: '4px',
                  cursor: 'pointer',
                  marginRight: '10px'
                }}
              >
                {calibSitting ? `✓ Recorded: ${calibSitting.toFixed(1)}cm` : 'Record Sitting Height'}
              </button>
            </div>

            <div style={{ marginBottom: '15px' }}>
              <p style={{ fontWeight: 'bold', marginBottom: '10px' }}>
                Step 2: Raise desk to standing
              </p>
              <button
                onClick={recordStanding}
                disabled={loading}
                style={{
                  padding: '10px 20px',
                  fontSize: '14px',
                  backgroundColor: calibStanding ? '#6c757d' : '#007bff',
                  color: 'white',
                  border: 'none',
                  borderRadius: '4px',
                  cursor: 'pointer',
                  marginRight: '10px'
                }}
              >
                {calibStanding ? `✓ Recorded: ${calibStanding.toFixed(1)}cm` : 'Record Standing Height'}
              </button>
            </div>

            <div>
              <button
                onClick={saveCalibration}
                disabled={loading || !calibSitting || !calibStanding}
                style={{
                  padding: '10px 20px',
                  fontSize: '16px',
                  fontWeight: 'bold',
                  backgroundColor: '#28a745',
                  color: 'white',
                  border: 'none',
                  borderRadius: '4px',
                  cursor: (loading || !calibSitting || !calibStanding) ? 'not-allowed' : 'pointer',
                  opacity: (loading || !calibSitting || !calibStanding) ? 0.6 : 1,
                  marginRight: '10px'
                }}
              >
                {loading ? 'Saving...' : 'Save Calibration'}
              </button>
              <button
                onClick={() => {
                  setCalibMode(false);
                  setCalibSitting(null);
                  setCalibStanding(null);
                  setCalibMessage('');
                }}
                style={{
                  padding: '10px 20px',
                  fontSize: '16px',
                  backgroundColor: '#6c757d',
                  color: 'white',
                  border: 'none',
                  borderRadius: '4px',
                  cursor: 'pointer'
                }}
              >
                Cancel
              </button>
            </div>

            {calibMessage && (
              <div style={{
                marginTop: '15px',
                padding: '10px',
                backgroundColor: calibMessage.includes('Error') ? '#f8d7da' : '#d4edda',
                color: calibMessage.includes('Error') ? '#721c24' : '#155724',
                borderRadius: '4px',
                fontSize: '14px'
              }}>
                {calibMessage}
              </div>
            )}
          </div>
        )}
      </div>

      <div className="card" style={{ maxWidth: '600px', marginTop: '20px' }}>
        <h2>Noise Level Thresholds</h2>
        <p style={{ color: '#666', fontSize: '14px', marginBottom: '20px' }}>
          Set dB levels for noise classification (Quiet, Normal, Moderate, Loud).
        </p>

        <div style={{ display: 'grid', gap: '15px' }}>
          <div>
            <label style={{ fontWeight: 'bold' }}>Quiet (below dB)</label>
            <input
              type="number"
              value={noiseThresholds.quiet}
              onChange={(e) => setNoiseThresholds({...noiseThresholds, quiet: parseFloat(e.target.value)})}
              style={{ width: '100%', padding: '8px', fontSize: '16px', border: '1px solid #ccc', borderRadius: '4px' }}
            />
          </div>
          <div>
            <label style={{ fontWeight: 'bold' }}>Normal (below dB)</label>
            <input
              type="number"
              value={noiseThresholds.normal}
              onChange={(e) => setNoiseThresholds({...noiseThresholds, normal: parseFloat(e.target.value)})}
              style={{ width: '100%', padding: '8px', fontSize: '16px', border: '1px solid #ccc', borderRadius: '4px' }}
            />
          </div>
          <div>
            <label style={{ fontWeight: 'bold' }}>Loud (above dB)</label>
            <input
              type="number"
              value={noiseThresholds.loud}
              onChange={(e) => setNoiseThresholds({...noiseThresholds, loud: parseFloat(e.target.value)})}
              style={{ width: '100%', padding: '8px', fontSize: '16px', border: '1px solid #ccc', borderRadius: '4px' }}
            />
          </div>
        </div>

        <button
          onClick={saveNoiseSettings}
          disabled={loading}
          style={{
            width: '100%',
            padding: '12px',
            marginTop: '20px',
            fontSize: '16px',
            fontWeight: 'bold',
            backgroundColor: '#2196f3',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: loading ? 'not-allowed' : 'pointer',
            opacity: loading ? 0.6 : 1
          }}
        >
          {loading ? 'Saving...' : 'Save Noise Settings'}
        </button>

        {noiseMessage && (
          <div style={{
            marginTop: '15px',
            padding: '10px',
            backgroundColor: noiseMessage.includes('Error') ? '#f8d7da' : '#d4edda',
            color: noiseMessage.includes('Error') ? '#721c24' : '#155724',
            borderRadius: '4px'
          }}>
            {noiseMessage}
          </div>
        )}
      </div>

      <div className="card" style={{ maxWidth: '600px', marginTop: '20px' }}>
        <h3>How it works</h3>
        <ul style={{ lineHeight: '1.8', color: '#555' }}>
          <li>Set your typical sitting desk height</li>
          <li>The system adds an offset to determine the standing threshold</li>
          <li>Uses a 5-sample moving average to filter out sensor spikes</li>
          <li>If the smoothed distance ≥ standing threshold, you're standing</li>
          <li>Otherwise, you're sitting</li>
        </ul>
      </div>

      <div className="card" style={{ maxWidth: '600px', marginTop: '20px' }}>
        <h2>Webcam Posture Calibration</h2>
        <p style={{ color: '#666', fontSize: '14px', marginBottom: '12px' }}>
          Sit up straight, hit calibrate, then hold still for 10s. After that the system
          compares your head and shoulder position to that baseline — move too far forward
          and it flags a slouch.
        </p>

        <div style={{ marginBottom: '14px' }}>
          <strong>Webcam status:</strong> {webcamAvailable ? 'Available' : 'Not available'}
        </div>

        {webcamBaseline ? (
          <div style={{
            padding: '10px',
            borderRadius: '4px',
            backgroundColor: '#f5f5f5',
            marginBottom: '14px'
          }}>
            <div><strong>Current baseline</strong></div>
            <div>Ear span: {webcamBaseline.ear_span?.toFixed(4)}</div>
            <div>Head-shoulder gap: {webcamBaseline.head_shoulder_gap?.toFixed(4)}</div>
            <div>Samples captured: {webcamBaseline.sample_count}</div>
          </div>
        ) : (
          <p style={{ color: '#777', marginBottom: '14px' }}>No webcam baseline saved yet.</p>
        )}

        <button
          onClick={runWebcamCalibration}
          disabled={loading || !webcamAvailable}
          style={{
            width: '100%',
            padding: '10px',
            marginBottom: '14px',
            fontSize: '15px',
            fontWeight: 'bold',
            backgroundColor: '#6f42c1',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: (loading || !webcamAvailable) ? 'not-allowed' : 'pointer',
            opacity: (loading || !webcamAvailable) ? 0.6 : 1
          }}
        >
          {loading ? 'Calibrating... (hold still)' : 'Calibrate Good Posture (10s)'}
        </button>

        <div style={{ display: 'grid', gap: '10px' }}>
          <div>
            <label style={{ fontWeight: 'bold' }}>Ear Span Tolerance</label>
            <p style={{ color: '#666', fontSize: '12px', margin: '2px 0 6px' }}>
              How much your head can move toward the camera before triggering (0.15 = 15% wiggle room)
            </p>
            <input
              type="number"
              step="0.01"
              min="0"
              max="1"
              value={webcamTolerances.ear_span}
              onChange={(e) => setWebcamTolerances({
                ...webcamTolerances,
                ear_span: parseFloat(e.target.value)
              })}
              style={{ width: '100%', padding: '8px', border: '1px solid #ccc', borderRadius: '4px' }}
            />
          </div>
          <div>
            <label style={{ fontWeight: 'bold' }}>Head Drop Tolerance</label>
            <p style={{ color: '#666', fontSize: '12px', margin: '2px 0 6px' }}>
              How much your head can drop toward your shoulders before triggering (0.15 = 15% wiggle room)
            </p>
            <input
              type="number"
              step="0.01"
              min="0"
              max="1"
              value={webcamTolerances.head_drop}
              onChange={(e) => setWebcamTolerances({
                ...webcamTolerances,
                head_drop: parseFloat(e.target.value)
              })}
              style={{ width: '100%', padding: '8px', border: '1px solid #ccc', borderRadius: '4px' }}
            />
          </div>
        </div>

        <button
          onClick={saveWebcamSettings}
          disabled={loading || !webcamAvailable}
          style={{
            width: '100%',
            padding: '10px',
            marginTop: '14px',
            fontSize: '15px',
            fontWeight: 'bold',
            backgroundColor: '#17a2b8',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: (loading || !webcamAvailable) ? 'not-allowed' : 'pointer',
            opacity: (loading || !webcamAvailable) ? 0.6 : 1
          }}
        >
          {loading ? 'Saving...' : 'Save Webcam Tolerances'}
        </button>

        {webcamMessage && (
          <div style={{
            marginTop: '12px',
            padding: '10px',
            backgroundColor: webcamMessage.includes('Error') ? '#f8d7da' : '#d4edda',
            color: webcamMessage.includes('Error') ? '#721c24' : '#155724',
            borderRadius: '4px'
          }}>
            {webcamMessage}
          </div>
        )}
      </div>
    </div>
  );
}

export default Settings;
