import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { getModelStatus, switchModel, reloadEmbeddings, fetchMetrics, startServer } from '../api';
import RealtimePipelineFeed from '../components/RealtimePipelineFeed';
import VideoUpload from '../components/VideoUpload';

export default function Streams({ admin }) {
  const cameras = [0, 1];
  // Global processing mode across feeds: 'full' | 'object' | 'face'
  const [procMode, setProcMode] = useState('object');
  const [modelInfo, setModelInfo] = useState(null);
  const [loadingModel, setLoadingModel] = useState(false);
  const [metrics, setMetrics] = useState(null);
  const [loadingMetrics, setLoadingMetrics] = useState(true);
  const [metricsErr, setMetricsErr] = useState(null);
  const [startingServer, setStartingServer] = useState(false);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const r = await fetchMetrics();
        if (alive) { setMetrics(r.data); setMetricsErr(null); }
      } catch (e) { if (alive) setMetricsErr('Metrics unavailable'); }
      finally { if (alive) setLoadingMetrics(false); }
    };
    load();
    const id = setInterval(load, 10000);
    return () => { alive = false; clearInterval(id); };
  }, []);

  const loadModelStatus = async () => {
    if (!admin) return;
    setLoadingModel(true);
    try {
      const r = await getModelStatus(admin.username, admin.password);
      setModelInfo(r.data);
    } catch { /* silent */ }
    finally { setLoadingModel(false); }
  };

  useEffect(() => { loadModelStatus(); }, [admin]);

  const doSwitch = async target => {
    if (!admin) return;
    const fd = new FormData();
    fd.append('username', admin.username);
    fd.append('password', admin.password);
    fd.append('target', target);
    await switchModel(fd);
    loadModelStatus();
  };

  const doReload = async () => {
    if (!admin) return;
    const fd = new FormData();
    fd.append('username', admin.username);
    fd.append('password', admin.password);
    await reloadEmbeddings(fd);
    loadModelStatus();
  };
  
  const handleStartServer = async () => {
    if (!admin) return;
    setStartingServer(true);
    try {
      const fd = new FormData();
      fd.append('username', admin.username);
      fd.append('password', admin.password);
      await startServer(fd);
      // Wait a moment and then reload model status
      setTimeout(() => {
        loadModelStatus();
        setStartingServer(false);
      }, 3000);
    } catch (error) {
      console.error("Error starting server:", error);
      setStartingServer(false);
    }
  };

  return (
    <div className="grid" style={{ gap: 24 }}>
      <div className="status-bar" aria-live="polite">
        <button 
          type="button" 
          className="primary" 
          onClick={handleStartServer} 
          disabled={startingServer}
          style={{ marginRight: 12 }}
        >
          {startingServer ? "Starting Server..." : "Start Backend Server"}
        </button>
        {loadingMetrics && <div className="badge" role="status">Loading metrics…</div>}
        {metricsErr && <div className="badge" data-type="error">{metricsErr}</div>}
        {metrics && (
          <>
            <div className="badge" title="Application uptime in seconds">Uptime: {metrics.uptime_sec}s</div>
            <div className="badge" title="Enrolled persons count">Persons: {metrics.persons}</div>
            {metrics.memory_mb != null && <div className="badge" title="Approximate memory usage">Mem: {metrics.memory_mb} MB</div>}
          </>
        )}
      </div>

      {admin && (
        <div className="card" style={{ order: -1 }}>
          <h3 style={{ marginTop: 0 }}>Model Status</h3>
          <button 
            type="button" 
            className="primary" 
            onClick={handleStartServer} 
            disabled={startingServer}
            style={{ marginBottom: 12 }}
          >
            {startingServer ? "Starting Server..." : "Start Backend Server"}
          </button>
          {loadingModel && <div className="badge" role="status">Loading…</div>}
          {modelInfo && (
            <div style={{ fontSize: 13, lineHeight: 1.5 }}>
              <div><strong>Loaded:</strong> {modelInfo.model_loaded}</div>
              <div><strong>Fallback:</strong> {String(modelInfo.using_fallback)}</div>
              <div><strong>Cache:</strong> {modelInfo.cache_size}</div>
              <div><strong>Last Err:</strong> {modelInfo.last_error || 'None'}</div>
              <div><strong>Available:</strong> {(modelInfo.available_models || []).join(', ') || 'n/a'}</div>
              <div className="btn-row" style={{ marginTop: 12 }}>
                <button type="button" onClick={() => doSwitch('r100')} aria-label="Switch to r100 model">Use r100</button>
                <button type="button" onClick={() => doSwitch('mobile')} aria-label="Switch to mobile model">Use mobile</button>
                <button type="button" className="secondary" onClick={doReload}>Reload Cache</button>
              </div>
            </div>
          )}
        </div>
      )}

      <div className="card">
        <h2 style={{ marginTop: 0 }}>Live Camera Streams</h2>
        <p style={{ marginTop: 4, color: '#6b7280', fontSize: 14 }}>Low-latency WebSocket pipeline with detection, tracking, pose & identity overlays.</p>
        <div className="btn-row" style={{ marginTop: 8, marginBottom: 8 }}>
          <label style={{ fontSize: 13, marginRight: 8 }}>Processing mode:</label>
          <select value={procMode} onChange={e => setProcMode(e.target.value)} aria-label="Select processing mode">
            <option value="object">Object-only</option>
            <option value="face">Face-only</option>
            <option value="full">Full (objects + identities)</option>
          </select>
        </div>
        <div className="video-grid" style={{ marginTop: 16 }}>
          {cameras.map(id => <RealtimePipelineFeed key={id} camId={id} procMode={procMode} />)}
        </div>
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Video File Processing</h3>
        {admin ? (
          <VideoUpload admin={admin} />
        ) : (
          <div style={{ fontSize: 14, color: '#6b7280' }}>
            Login as admin to upload and process recorded video. <Link to="/admin/login">Admin Login</Link>
          </div>
        )}
      </div>

      {!admin && (
        <div className="card" style={{ background: 'linear-gradient(135deg,#2563eb0d,#1d4ed80d)' }}>
          <h3 style={{ marginTop: 0 }}>Need Admin Features?</h3>
            <p style={{ marginTop: 4, lineHeight: 1.5, color: '#6b7280', fontSize: 14 }}>Authenticate to enroll whitelist / blacklist identities, toggle flags, and run offline video analysis.</p>
            <Link to="/admin/login"><button>Go to Admin Login</button></Link>
        </div>
      )}
    </div>
  );
}