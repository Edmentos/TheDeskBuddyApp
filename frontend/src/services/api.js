const API_BASE_URL = 'http://127.0.0.1:8000';

export async function getHealth() {
  try {
    const response = await fetch(`${API_BASE_URL}/health`);
    if (!response.ok) {
      throw new Error('Health check failed');
    }
    return await response.json();
  } catch (error) {
    console.error('Error fetching health:', error);
    throw error;
  }
}

export async function listSerialPorts() {
  try {
    const response = await fetch(`${API_BASE_URL}/serial/ports`);
    if (!response.ok) {
      throw new Error('Failed to list serial ports');
    }
    return await response.json();
  } catch (error) {
    console.error('Error listing serial ports:', error);
    throw error;
  }
}

export async function connectToSerial(port, baudrate = 115200) {
  try {
    const response = await fetch(`${API_BASE_URL}/serial/connect`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ port, baudrate }),
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to connect to serial port');
    }
    return await response.json();
  } catch (error) {
    console.error('Error connecting to serial:', error);
    throw error;
  }
}

export async function autoConnectToSerial(baudrate = 115200) {
  try {
    const response = await fetch(`${API_BASE_URL}/serial/auto-connect?baudrate=${baudrate}`, {
      method: 'POST',
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to auto-connect to ESP32');
    }
    return await response.json();
  } catch (error) {
    console.error('Error auto-connecting to serial:', error);
    throw error;
  }
}

export async function disconnectFromSerial() {
  try {
    const response = await fetch(`${API_BASE_URL}/serial/disconnect`, {
      method: 'POST',
    });
    if (!response.ok) {
      throw new Error('Failed to disconnect from serial port');
    }
    return await response.json();
  } catch (error) {
    console.error('Error disconnecting from serial:', error);
    throw error;
  }
}

export async function getSerialStatus() {
  try {
    const response = await fetch(`${API_BASE_URL}/serial/status`);
    if (!response.ok) {
      throw new Error('Failed to get serial status');
    }
    return await response.json();
  } catch (error) {
    console.error('Error getting serial status:', error);
    throw error;
  }
}

export async function getSerialData() {
  try {
    const response = await fetch(`${API_BASE_URL}/serial/data`);
    if (!response.ok) {
      throw new Error('Failed to get serial data');
    }
    return await response.json();
  } catch (error) {
    console.error('Error getting serial data:', error);
    throw error;
  }
}

export async function querySensorReadings(sensorName, startTime, endTime, page = 1, pageSize = 100) {
  try {
    const params = new URLSearchParams({
      sensor_name: sensorName,
      page: page.toString(),
      page_size: pageSize.toString()
    });

    if (startTime) {
      params.append('start_time', startTime);
    }
    if (endTime) {
      params.append('end_time', endTime);
    }

    const response = await fetch(`${API_BASE_URL}/readings/query?${params}`);
    if (!response.ok) {
      throw new Error('Failed to query sensor readings');
    }
    return await response.json();
  } catch (error) {
    console.error('Error querying sensor readings:', error);
    throw error;
  }
}

export async function recordSittingHeight() {
  try {
    const response = await fetch(`${API_BASE_URL}/settings/calibrate/record-sitting`, {
      method: 'POST',
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to record sitting height');
    }
    return await response.json();
  } catch (error) {
    console.error('Error recording sitting height:', error);
    throw error;
  }
}

export async function recordStandingHeight() {
  try {
    const response = await fetch(`${API_BASE_URL}/settings/calibrate/record-standing`, {
      method: 'POST',
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to record standing height');
    }
    return await response.json();
  } catch (error) {
    console.error('Error recording standing height:', error);
    throw error;
  }
}

export async function saveCalibration(sittingHeight, standingHeight) {
  try {
    const response = await fetch(`${API_BASE_URL}/settings/calibrate/save`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        sitting_height_cm: sittingHeight,
        standing_height_cm: standingHeight,
      }),
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to save calibration');
    }
    return await response.json();
  } catch (error) {
    console.error('Error saving calibration:', error);
    throw error;
  }
}

export async function getCurrentCalibration() {
  try {
    const response = await fetch(`${API_BASE_URL}/settings/calibrate/current`);
    if (!response.ok) {
      throw new Error('Failed to get current calibration');
    }
    return await response.json();
  } catch (error) {
    console.error('Error getting current calibration:', error);
    throw error;
  }
}

export async function getPostureStats(startTime, endTime) {
  try {
    const params = new URLSearchParams();
    if (startTime) {
      params.append('start_time', startTime);
    }
    if (endTime) {
      params.append('end_time', endTime);
    }

    const response = await fetch(`${API_BASE_URL}/readings/posture/stats?${params}`);
    if (!response.ok) {
      throw new Error('Failed to get posture stats');
    }
    return await response.json();
  } catch (error) {
    console.error('Error getting posture stats:', error);
    throw error;
  }
}

export async function getCurrentPosture() {
  try {
    const response = await fetch(`${API_BASE_URL}/readings/posture/current`);
    if (!response.ok) {
      throw new Error('Failed to get current posture');
    }
    return await response.json();
  } catch (error) {
    console.error('Error getting current posture:', error);
    throw error;
  }
}
