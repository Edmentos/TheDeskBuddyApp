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
