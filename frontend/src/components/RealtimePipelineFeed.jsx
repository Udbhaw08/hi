import React, { useEffect, useRef, useState } from 'react';

/*
RealtimePipelineFeed
Uses ws:// backend /ws/pipeline/{cam_id}?mode=binary for ultra low latency (mirrors cv2.imshow performance).
Falls back to base64 JSON frames if binary fails (set WS_REQUIRE_BASE64=1 on server or pass prop forceBase64).
Shows latest events (person actions, weapons, identities) under the video.
*/
export default function RealtimePipelineFeed({ camId=0, showEvents=true, forceBase64=false, procMode='full' }) {
  const imgRef = useRef(null);
  const wsRef = useRef(null);
  const frameUrlRef = useRef(null);
  const [connected, setConnected] = useState(false);
  const [events, setEvents] = useState([]);
  const [mode, setMode] = useState(forceBase64 ? 'base64' : 'binary');
  const [error, setError] = useState(null);
  const [fps, setFps] = useState(0);
  const lastTsRef = useRef(0);
  const lastFrameWallRef = useRef(performance.now());
  const framesCounterRef = useRef(0);
  const fpsIntervalRef = useRef(null);

  useEffect(() => {
    let cancelled = false;

    function connect(attempt=0) {
      if (cancelled) return;
      const wsProto = window.location.protocol === 'https:' ? 'wss' : 'ws';
      const url = `${wsProto}://localhost:8000/ws/pipeline/${camId}?mode=${mode}&proc=${procMode}`;
      const ws = new WebSocket(url);
      ws.binaryType = 'blob';
      wsRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
        setError(null);
        // FPS calc
        if (fpsIntervalRef.current) clearInterval(fpsIntervalRef.current);
        fpsIntervalRef.current = setInterval(() => {
            const now = performance.now();
            const elapsed = (now - lastFrameWallRef.current) / 1000.0;
            // simple rolling fps based on frames counted in interval window
            const fpsCalc = framesCounterRef.current / (elapsed || 1);
            setFps(fpsCalc.toFixed(1));
            framesCounterRef.current = 0;
            lastFrameWallRef.current = now;
        }, 1000);
      };

      ws.onmessage = (ev) => {
        if (typeof ev.data === 'string') {
          // JSON text (init, events, or base64 frame)
          try {
            const msg = JSON.parse(ev.data);
            if (msg.type === 'init') {
              if (msg.mode && msg.mode !== mode) setMode(msg.mode);
              // optional: we could reflect backend-selected proc mode here later
            } else if (msg.type === 'events') {
              setEvents(msg.events || []);
            } else if (msg.type === 'frame' && msg.jpeg_b64) {
              // base64 still
              const b = atob(msg.jpeg_b64);
              const arr = new Uint8Array(b.length);
              for (let i=0;i<b.length;i++) arr[i] = b.charCodeAt(i);
              const blob = new Blob([arr], { type: 'image/jpeg' });
              updateFrame(blob, msg.ts);
            }
          } catch (_) { /* ignore */ }
        } else if (ev.data instanceof Blob) {
          // binary JPEG frame
            updateFrame(ev.data, Date.now()/1000.0);
        }
      };

      ws.onerror = () => {
        setError('Stream error');
      };

      ws.onclose = () => {
        setConnected(false);
        if (fpsIntervalRef.current) { clearInterval(fpsIntervalRef.current); fpsIntervalRef.current=null; }
        // attempt reconnect
        setTimeout(() => connect(Math.min(attempt+1, 10)), 800 + attempt*400);
      };
    }

    function updateFrame(blob, ts) {
      if (lastTsRef.current === ts) return;
      lastTsRef.current = ts;
      // revoke old
      if (frameUrlRef.current) URL.revokeObjectURL(frameUrlRef.current);
      const url = URL.createObjectURL(blob);
      frameUrlRef.current = url;
      if (imgRef.current) imgRef.current.src = url;
      framesCounterRef.current += 1;
    }

    connect();

    return () => {
      cancelled = true;
      try { wsRef.current && wsRef.current.close(); } catch(_){ }
      if (frameUrlRef.current) URL.revokeObjectURL(frameUrlRef.current);
      if (fpsIntervalRef.current) clearInterval(fpsIntervalRef.current);
    };
  }, [camId, mode, forceBase64, procMode]);

  return (
    <div className="video-tile" style={{position:'relative'}}>
      <div style={{display:'flex', justifyContent:'space-between', alignItems:'center'}}>
        <h4 style={{margin:0}}>Pipeline Cam {camId}</h4>
        <div style={{fontSize:11, opacity:0.75}}>
          {connected? <span style={{color:'#3fb950'}}>LIVE</span>: <span style={{color:'#d29922'}}>Reconnecting…</span>} &nbsp;FPS:{fps} &nbsp;Mode:{procMode}
        </div>
      </div>
      <div style={{width:'100%', aspectRatio:'4/3', background:'#000', border:'1px solid #30363d', borderRadius:6, marginTop:6, position:'relative'}}>
        <img ref={imgRef} alt={`Cam ${camId}`} style={{width:'100%', height:'100%', objectFit:'contain', display:'block'}} />
        {!connected && <div style={{position:'absolute', inset:0, display:'flex', alignItems:'center', justifyContent:'center', fontSize:12, color:'#b1bac4'}}>Connecting...</div>}
      </div>
      {error && <div style={{marginTop:4, fontSize:12, color:'#f85149'}}>{error}</div>}
      {showEvents && (
        <div style={{marginTop:6, maxHeight:140, overflow:'auto', fontSize:11, lineHeight:1.25, background:'#f9fafb', padding:6, borderRadius:4, border:'1px solidrgb(1, 5, 9)'}}>
          {events.length===0 && <div style={{opacity:0.5}}>No events yet</div>}
          {events.map((ev,i) => {
            if (ev.type==='person') {
              const ident = ev.identity ? ` | ${ev.identity.name || ev.identity.person_id} (${ev.identity.flag})` : '';
              return <div key={i}>ID {ev.track_id}: {ev.action}{ident}</div>;
            } else {
              return <div key={i}>{ev.cls} {ev.confidence?.toFixed?.(2)}</div>;
            }
          })}
        </div>
      )}
    </div>
  );
}
