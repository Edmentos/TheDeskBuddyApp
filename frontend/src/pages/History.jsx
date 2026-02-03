import { useState, useEffect } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { querySensorReadings } from '../services/api';

function History() {
  const [tempData, setTempData] = useState([]);
  const [humidData, setHumidData] = useState([]);
  const [distData, setDistData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [timeRange, setTimeRange] = useState('24h');

  useEffect(() => {
    loadData();
  }, [timeRange]);

  const getTimeRange = () => {
    const now = new Date();
    const end = now.toISOString();
    
    const hours = {
      '1h': 1,
      '6h': 6,
      '24h': 24,
      '7d': 168
    };
    
    const h = hours[timeRange] || 24;
    const start = new Date(now.getTime() - h * 60 * 60 * 1000).toISOString();
    
    return { start, end };
  };

  const loadData = async () => {
    setLoading(true);

    const times = getTimeRange();

    // just fetch them all at once
    const [tempResponse, humidResponse, distResponse] = await Promise.all([
      querySensorReadings('temp_c', times.start, times.end, 1, 200),
      querySensorReadings('hum_pct', times.start, times.end, 1, 200),
      querySensorReadings('distance_cm', times.start, times.end, 1, 200)
    ]).catch(err => {
      setError('Failed to load sensor data');
      console.error(err);
      setLoading(false);
      return [null, null, null];
    });

    if (tempResponse) {
      const formatData = (response) => {
        return response.data.map(item => ({
          timestamp: new Date(item.timestamp).toLocaleString(),
          value: item.value
        })).reverse();
      };

      setTempData(formatData(tempResponse));
      setHumidData(formatData(humidResponse));
      setDistData(formatData(distResponse));
      setError(null);
    }
    setLoading(false);
  };

  return (
    <div>
      <h1>History</h1>

      <div className="card" style={{marginBottom: '20px'}}>
        <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
          <label>Time Range:</label>
          <select value={timeRange} onChange={(e) => setTimeRange(e.target.value)}>
            <option value="1h">Last Hour</option>
            <option value="6h">Last 6 Hours</option>
            <option value="24h">Last 24 Hours</option>
            <option value="7d">Last 7 Days</option>
          </select>
          <button onClick={loadData}>Refresh</button>
        </div>
      </div>

      {loading && <div className="card">Loading...</div>}
      {error && <div className="card" style={{color: 'red'}}>{error}</div>}

      {!loading && (
        <>
          <div className="card">
            <h2>Temperature (°C)</h2>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={tempData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="timestamp" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Line type="monotone" dataKey="value" stroke="#ff6b6b" name="Temperature" />
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div className="card">
            <h2>Humidity (%)</h2>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={humidData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="timestamp" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Line type="monotone" dataKey="value" stroke="#4dabf7" name="Humidity" />
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div className="card">
            <h2>Distance (cm)</h2>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={distData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="timestamp" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Line type="monotone" dataKey="value" stroke="#51cf66" name="Distance" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </>
      )}
    </div>
  );
}

export default History;
