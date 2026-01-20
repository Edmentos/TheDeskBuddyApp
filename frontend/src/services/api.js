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
