import { useState, useEffect } from 'react';
import { recordSittingHeight, recordStandingHeight, saveCalibration as saveCalibrationAPI } from '../services/api';

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

  // Load current settings on mount
  useEffect(() => {
    fetchSettings();
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
        <h3>How it works</h3>
        <ul style={{ lineHeight: '1.8', color: '#555' }}>
          <li>Set your typical sitting desk height</li>
          <li>The system adds an offset to determine the standing threshold</li>
          <li>Uses a 5-sample moving average to filter out sensor spikes</li>
          <li>If the smoothed distance ≥ standing threshold, you're standing</li>
          <li>Otherwise, you're sitting</li>
        </ul>
      </div>
    </div>
  );
}

export default Settings;
