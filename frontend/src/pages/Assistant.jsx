import React, { useState, useRef, useEffect } from 'react';
import '../styles/Assistant.css';

const API_HOST = window.location.hostname || 'localhost';
const VIGIL_API = `http://${API_HOST}:8001`;

const Assistant = () => {
  const [selectedFile, setSelectedFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [language, setLanguage] = useState('en');
  const [isDragOver, setIsDragOver] = useState(false);
  const fileInputRef = useRef(null);
  const audioRef = useRef(null);

  const handleFile = (file) => {
    if (!file) return;
    if (!['image/jpeg', 'image/png'].includes(file.type)) {
      setError('Only JPEG/PNG images are supported');
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      setError('File too large (max 5MB)');
      return;
    }
    setError(null);
    setSelectedFile(file);
    setResult(null);

    const reader = new FileReader();
    reader.onloadend = () => setPreviewUrl(reader.result);
    reader.readAsDataURL(file);

    analyzeImage(file);
  };

  const analyzeImage = async (file) => {
    setLoading(true);
    setError(null);
    setResult(null);

    const formData = new FormData();
    formData.append('image', file);
    formData.append('language', language);

    try {
      const response = await fetch(`${VIGIL_API}/analyze`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || 'Analysis failed');
      }

      const data = await response.json();
      setResult(data);
    } catch (err) {
      setError(err.message || 'Failed to connect to server. Make sure the assistant backend is running on port 8001.');
    } finally {
      setLoading(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragOver(false);
    const file = e.dataTransfer.files[0];
    handleFile(file);
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragOver(true);
  };

  const handleDragLeave = () => setIsDragOver(false);

  const handleReset = () => {
    setSelectedFile(null);
    setPreviewUrl(null);
    setResult(null);
    setError(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.src = '';
    }
  };

  const getThreatColor = (level) => {
    if (level === 'critical') return { bg: '#FFEBEE', color: '#D32F2F', border: '#D32F2F' };
    if (level === 'elevated') return { bg: '#FFF8E1', color: '#F57F17', border: '#F57F17' };
    return { bg: '#E8F5E9', color: '#2E7D32', border: '#4CAF50' };
  };

  useEffect(() => {
    if (result?.audio_base64 && audioRef.current) {
      audioRef.current.src = `data:audio/mpeg;base64,${result.audio_base64}`;
      audioRef.current.play().catch(() => {});
    }
  }, [result]);

  return (
    <div className="assist-page">
      <div className="assist-container">
        {/* Header */}
        <div className="assist-header">
          <div className="assist-header-left">
            <h1>🤖 DRISHTI Assistant</h1>
            <p>AI-Powered Visual Intelligence & Analysis</p>
          </div>
          <div className="assist-lang-badge">
            <label htmlFor="assist-lang">🌐 Language</label>
            <select
              id="assist-lang"
              value={language}
              onChange={(e) => setLanguage(e.target.value)}
            >
              <option value="en">English</option>
              <option value="hi">Hindi</option>
            </select>
          </div>
        </div>

        {/* Alert */}
        {error && (
          <div className="assist-alert assist-alert-error">{error}</div>
        )}

        <div className="assist-content">
          {/* Upload Section */}
          <div className="assist-upload-section">
            <div className="assist-section-title">📸 IMAGE ANALYSIS</div>

            {!previewUrl ? (
              <div
                className={`assist-drop-zone ${isDragOver ? 'active' : ''}`}
                onClick={() => fileInputRef.current?.click()}
                onDrop={handleDrop}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
              >
                <div className="assist-upload-icon">🖼️</div>
                <div className="assist-upload-text">Drag & Drop an image here</div>
                <div className="assist-upload-hint">or click to browse · JPEG/PNG · Max 5MB</div>
                <input
                  type="file"
                  ref={fileInputRef}
                  accept="image/jpeg, image/png"
                  onChange={(e) => handleFile(e.target.files[0])}
                  style={{ display: 'none' }}
                />
              </div>
            ) : (
              <div className="assist-preview-wrapper">
                <img src={previewUrl} alt="Preview" className="assist-preview-img" />
                {loading && (
                  <div className="assist-loading-overlay">
                    <div className="assist-spinner"></div>
                    <div className="assist-loading-text">Analyzing image...</div>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Results Section */}
          <div className="assist-results-section">
            <div className="assist-section-title">📋 ANALYSIS RESULTS</div>

            {!result && !loading && (
              <div className="assist-placeholder">
                <div className="assist-placeholder-icon">🔍</div>
                <p>Upload an image to get AI-powered analysis</p>
                <p className="assist-placeholder-sub">
                  DRISHTI Assistant uses Gemini AI to detect threats, identify subjects,
                  and generate audio narration of findings.
                </p>
              </div>
            )}

            {loading && !result && (
              <div className="assist-placeholder">
                <div className="assist-spinner-inline"></div>
                <p>Processing with Gemini AI...</p>
              </div>
            )}

            {result && (
              <>
                {/* Badges */}
                <div className="assist-badges">
                  <span
                    className="assist-badge"
                    style={{
                      background: getThreatColor(result.metadata?.threat_level).bg,
                      color: getThreatColor(result.metadata?.threat_level).color,
                      borderColor: getThreatColor(result.metadata?.threat_level).border,
                    }}
                  >
                    🛡️ Threat: {(result.metadata?.threat_level || 'normal').toUpperCase()}
                  </span>
                  <span className="assist-badge assist-badge-scene">
                    🏢 Scene: {(result.metadata?.scene_type || 'unknown').toUpperCase()}
                  </span>
                  <span className="assist-badge assist-badge-subject">
                    👤 Subjects: {result.metadata?.subject_count || 0}
                  </span>
                </div>

                {/* Narration */}
                <div className="assist-narration">
                  <div className="assist-narration-label">📝 Analysis Report</div>
                  <div className="assist-narration-text">{result.narration}</div>
                </div>

                {/* Audio */}
                {result.audio_base64 && (
                  <div className="assist-audio-section">
                    <div className="assist-narration-label">🔊 Audio Narration</div>
                    <audio ref={audioRef} controls className="assist-audio-player" />
                  </div>
                )}

                {/* Reset */}
                <button className="assist-reset-btn" onClick={handleReset}>
                  🔄 NEW ANALYSIS
                </button>
              </>
            )}
          </div>
        </div>

        {/* Footer Info */}
        <div className="assist-info">
          <strong>💡 How it works:</strong> Upload any surveillance image → AI analyzes for threats, 
          identifies subjects and scene type → Generates detailed report with voice narration.
        </div>
      </div>
    </div>
  );
};

export default Assistant;
