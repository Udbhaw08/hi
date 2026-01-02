import axios from "axios";

const API_BASE = "http://localhost:8000";

export const addPerson = (formData) =>
  axios.post(`${API_BASE}/admin/add_person`, formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });

export const adminLogin = (formData) =>
  axios.post(`${API_BASE}/admin/login`, formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });

export const getVideoFeed = (camId) =>
  `${API_BASE}/video/stream/${camId}`;

export const listPersons = (username, password) =>
  axios.get(`${API_BASE}/admin/persons`, { params: { username, password } });

export const updateFlag = (formData) =>
  axios.post(`${API_BASE}/admin/update_flag`, formData);

export const deletePerson = (formData) =>
  axios.post(`${API_BASE}/admin/delete_person`, formData);

export const uploadVideo = (formData) =>
  axios.post(`${API_BASE}/video/upload`, formData, { headers: { 'Content-Type': 'multipart/form-data' } });

export const fetchMetrics = () => axios.get(`${API_BASE}/metrics`);

export const getModelStatus = (username, password) =>
  axios.get(`${API_BASE}/admin/model_status`, { params: { username, password } });

export const switchModel = (formData) =>
  axios.post(`${API_BASE}/admin/switch_model`, formData);

export const reloadEmbeddings = (formData) =>
  axios.post(`${API_BASE}/admin/reload_embeddings`, formData);

export const selfTest = (formData) =>
  axios.post(`${API_BASE}/admin/self_test`, formData, { headers: { 'Content-Type': 'multipart/form-data' } });

export const fetchAlerts = (params={}) => axios.get(`${API_BASE}/alerts`, { params });
export const fetchAlertReport = (alertId, format='txt') => axios.get(`${API_BASE}/alerts/report/${alertId}`, { params:{ format }, responseType: format==='json' ? 'json' : 'text' });

export const startServer = (formData) =>
  axios.post(`${API_BASE}/admin/start_server`, formData, { headers: { 'Content-Type': 'multipart/form-data' } });
