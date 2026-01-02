import { useState } from 'react';

export default function VideoFeed({ camId }) {
  const [err, setErr] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [processing, setProcessing] = useState(true);
  const url = `http://localhost:8000/video/stream/${camId}?process=${processing}&_=${refreshKey}`;

  const handleError = () => {
    if(!err) setErr(true);
    setTimeout(() => {
      setErr(false);
      setRefreshKey(k => k + 1);
    }, 3000);
  };

  const toggleProcessing = () => {
    setProcessing(p => !p);
    setRefreshKey(k => k + 1); // force img reload
  };

  return (
    <div className="video-tile">
      <div style={{display:'flex', justifyContent:'space-between', alignItems:'center'}}>
        <h4 style={{margin:0}}>Camera {camId}</h4>
        <button onClick={toggleProcessing} style={{padding:'4px 10px', fontSize:12}}>
          {processing ? 'Stop Processing' : 'Start Processing'}
        </button>
      </div>
      {err && <div className="alert" style={{margin:'6px 0'}}>Stream error – retrying…</div>}
      <img
        src={url}
        alt={`Cam ${camId}`}
        style={{width:'100%', aspectRatio:'4 / 3', objectFit:'cover', background:'#000', borderRadius:6, border:'1px solid #30363d', marginTop:6}}
        onError={handleError}
      />
      <div style={{marginTop:4, fontSize:12, opacity:0.7}}>Processing: {processing ? 'ON (faces labeled)' : 'OFF (raw feed)'}</div>
    </div>
  );
}
