// Detection System API - connects to the detection-system backend (port 5000)
// For NFC: The detection-system backend serves display.html at its root URL
// This module is used by the React frontend to submit detection reports

const API_HOST = window.location.hostname || 'localhost';
const DETECTION_API_BASE = `http://${API_HOST}:5000/api`;

export async function saveDetection(detectionData) {
  const response = await fetch(`${DETECTION_API_BASE}/detection`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(detectionData),
  });
  return response.json();
}

export async function getLatestDetection() {
  const response = await fetch(`${DETECTION_API_BASE}/detection/latest`);
  return response.json();
}

export async function getAllDetections() {
  const response = await fetch(`${DETECTION_API_BASE}/detections`);
  return response.json();
}

export async function deleteDetection(id) {
  const response = await fetch(`${DETECTION_API_BASE}/detection/${id}`, {
    method: 'DELETE',
  });
  return response.json();
}
