import React, { useState, useEffect, useRef } from 'react';
import { Camera, Upload, X, Pause, Activity, ArrowRight, FileText } from 'lucide-react';
import '../styles/Features.css';

const Features = () => {
  const [showLiveCamera, setShowLiveCamera] = useState(false);
  const [stream, setStream] = useState(null);
  const [uploadedFiles, setUploadedFiles] = useState([]);
  const videoRef = useRef(null);

  const startLiveCamera = async () => {
    try { const mediaStream = await navigator.mediaDevices.getUserMedia({ video:true, audio:false }); setStream(mediaStream); setShowLiveCamera(true); setTimeout(()=>{ if(videoRef.current) videoRef.current.srcObject=mediaStream; },100); } catch(e){ alert('Unable to access camera'); }
  };
  const stopLiveCamera = () => { if(stream){ stream.getTracks().forEach(t=> t.stop()); setStream(null);} setShowLiveCamera(false); };
  const handleMultiVideoUpload = e => { const files = Array.from(e.target.files); if(!files.length) return; const newFiles = files.map(f=> ({ file:f, name:f.name, size:(f.size/(1024*1024)).toFixed(2)+' MB', url:URL.createObjectURL(f) })); setUploadedFiles(prev=> [...prev, ...newFiles]); };
  const removeUploadedFile = idx => setUploadedFiles(prev=> prev.filter((_,i)=> i!==idx));
  useEffect(()=> ()=> { if(stream) stream.getTracks().forEach(t=> t.stop()); }, [stream]);

  return (
    <div className="features-page">
      <div className="features-container">
        <div className="features-content">
          <div className="features-header">
            <h1 className="features-main-title">DRISHTI Dashboard</h1>
            <p className="features-main-subtitle">Upload recorded videos or start live camera surveillance for AI-powered analysis</p>
          </div>
          <div className="video-input-section">
            <button className="video-input-btn" onClick={startLiveCamera}><Camera size={32} /><div className="btn-content"><span className="btn-title">Live Camera Feed</span><span className="btn-subtitle">Start webcam surveillance</span></div><ArrowRight size={20} className="btn-arrow" /></button>
            <label className="video-input-btn"><Upload size={32} /><div className="btn-content"><span className="btn-title">Upload Videos</span><span className="btn-subtitle">Analyze recorded footage</span></div><ArrowRight size={20} className="btn-arrow" /><input type="file" accept="video/*" multiple onChange={handleMultiVideoUpload} className="upload-input-hidden" /></label>
          </div>
        </div>
      </div>
      {showLiveCamera && (
        <div className="camera-modal-overlay" onClick={stopLiveCamera}>
          <div className="camera-modal-content" onClick={e=> e.stopPropagation()}>
            <button className="camera-close-btn" onClick={stopLiveCamera}><X size={24} /></button>
            <h3 className="camera-modal-title"><Camera size={24} />Live Camera Feed</h3>
            <div className="camera-video-wrapper">
              <video ref={videoRef} autoPlay playsInline className="live-camera-video" />
              <div className="recording-indicator"><span className="recording-dot"></span><span>LIVE</span></div>
            </div>
            <div className="camera-controls">
              <button className="camera-control-btn" onClick={stopLiveCamera}><Pause size={20} />Stop Camera</button>
              <button className="camera-control-btn primary"><Activity size={20} />Start Analysis</button>
            </div>
          </div>
        </div>
      )}
      {uploadedFiles.length > 0 && (
        <div className="uploaded-videos-section">
          <div className="features-container">
            <h3 className="uploaded-title"><FileText size={24} />Uploaded Videos ({uploadedFiles.length})</h3>
            <div className="uploaded-videos-grid">
              {uploadedFiles.map((f,i)=>(
                <div key={i} className="uploaded-video-card">
                  <video src={f.url} className="uploaded-video-preview" controls />
                  <div className="uploaded-video-info"><p className="video-name">{f.name}</p><p className="video-size">{f.size}</p></div>
                  <button className="remove-video-btn" onClick={()=> removeUploadedFile(i)}><X size={16} /></button>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
export default Features;
