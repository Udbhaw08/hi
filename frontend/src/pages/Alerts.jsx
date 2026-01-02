import React, { useEffect, useState, useCallback } from 'react';
import { fetchAlerts, fetchAlertReport } from '../api';

const POLL_MS = 5000;

const Alerts = ({ admin }) => {
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [selected, setSelected] = useState(null); // alert object
  const [reportText, setReportText] = useState('');
  const [reportLoading, setReportLoading] = useState(false);

  // If user not admin we still allow preview, but mask sensitive fields
  const isPreview = !admin;

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const res = await fetchAlerts({ limit: 100 });
      setAlerts(res.data.alerts || []);
    } catch (e) {
      setError('Failed to load alerts');
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); const id = setInterval(load, POLL_MS); return () => clearInterval(id); }, [load]);

  const viewReport = async (alert) => {
    setSelected(alert); setReportText(''); setReportLoading(true);
    try {
      const res = await fetchAlertReport(alert._id, 'txt');
      setReportText(res.data);
    } catch (e) {
      setReportText('Failed to fetch report');
    } finally { setReportLoading(false); }
  };

  const downloadReport = async (alert) => {
    try {
      const res = await fetchAlertReport(alert._id, 'txt');
      const blob = new Blob([res.data], { type: 'text/plain' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url; a.download = `incident_${alert._id}.txt`; a.click();
      URL.revokeObjectURL(url);
    } catch (e) { /* silent */ }
  };

  return (
    <div className="card" style={{ padding: 0 }}>
      <div style={{ padding: '24px 28px', borderBottom:'1px solid #e5e7eb', display:'flex', alignItems:'center', justifyContent:'space-between' }}>
        <div>
          <h2 style={{ margin:'0 0 4px' }}>Alerts {isPreview && <span style={{ fontSize:12, color:'#6b7280', marginLeft:8 }}>(Preview)</span>}</h2>
          <div style={{ fontSize:12, color:'#6b7280' }}>{isPreview ? 'Public preview — sensitive fields masked' : 'Refined threat events (blacklist & unknown rules)'}</div>
        </div>
        <div style={{ display:'flex', gap:8 }}>
          <button onClick={load} style={{ background:'#2563eb', padding:'8px 14px', fontSize:13 }}>Refresh</button>
          {!isPreview && <button onClick={()=>{ /* reserved for admin controls */ }} style={{ padding:'8px 12px' }}>Admin</button>}
        </div>
      </div>
      <div style={{ display: 'flex', flexDirection: 'row', gap: '24px' }}>
        <div style={{ flex: '1', padding: 24 }}>
        {error && <div style={{ color:'#dc2626', fontSize:13, marginBottom:12 }}>{error}</div>}
        {loading && <div style={{ fontSize:13, color:'#6b7280', marginBottom:12 }}>Loading...</div>}
        {(!alerts || alerts.length===0) && !loading && <div style={{ fontSize:13, color:'#6b7280' }}>No alerts yet.</div>}
        {alerts && alerts.length>0 && (
          <div style={{ overflowX:'auto' }}>
            <table style={{ width:'100%', borderCollapse:'collapse', fontSize:12 }}>
              <thead>
                <tr style={{ background:'#f9fafb', textAlign:'left' }}>
                  {['Time','Cam','Track','Identity','Flag','Action','Weapons','Type','Match','Pose',''].map(h => <th key={h} style={{ padding:'8px 10px', borderBottom:'1px solid #e5e7eb' }}>{h}</th>)}
                </tr>
              </thead>
              <tbody>
                {alerts.map(a => {
                  const dt = new Date(a.ts*1000).toISOString().slice(11,19); // HH:MM:SS
                  const weapons = (a.weapon_classes||[]).join(',');
                  const identityLabel = a.name ? (isPreview ? `${a.name.split('')[0]}***` : a.name) : (isPreview ? 'Unknown' : (a.person_id || 'Unknown'));
                  const poseSnippet = (a.pose_keypoints && a.pose_keypoints.length) ? JSON.stringify((a.pose_keypoints).slice(0,6)) : '-';
                  const isSelected = false;
                  return (
                    <tr key={a._id} style={{ 
                      borderBottom:'1px solid #f1f5f9',
                      background: 'transparent'
                    }}>
                      <td style={{ padding:'6px 10px' }}>{dt}</td>
                      <td style={{ padding:'6px 10px' }}>{a.cam_id}</td>
                      <td style={{ padding:'6px 10px' }}>{a.track_id}</td>
                      <td style={{ padding:'6px 10px' }}>{identityLabel}</td>
                      <td style={{ padding:'6px 10px' }}>{isPreview ? (a.flag ? a.flag : '-') : (a.flag || '-')}</td>
                      <td style={{ padding:'6px 10px' }}>{a.action}</td>
                      <td style={{ padding:'6px 10px' }}>{weapons || '-'}</td>
                      <td style={{ padding:'6px 10px' }}>{a.type}</td>
                      <td style={{ padding:'6px 10px' }}>{a.match_score?.toFixed?.(2) || '-'}</td>
                      <td style={{ padding:'6px 10px', maxWidth:220, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>{poseSnippet}</td>
                      <td style={{ padding:'6px 10px', whiteSpace:'nowrap', display:'flex', gap:6 }}>
                        <button style={{ background:'#fff', color:'#2563eb', border:'1px solid #93c5fd', padding:'4px 8px', fontSize:11 }} onClick={()=>viewReport(a)}>View</button>
                        <button style={{ background:'#2563eb', padding:'4px 8px', fontSize:11 }} onClick={()=>downloadReport(a)}>Download</button>
                      </td>
                  </tr>
                );
              })}
             </tbody>
           </table>
         </div>
       )}
        </div>
      </div>
      {selected && (
        <div style={{ position:'fixed', inset:0, background:'rgba(0,0,0,0.4)', display:'flex', alignItems:'center', justifyContent:'center', zIndex:1000 }} onClick={()=>setSelected(null)}>
          <div style={{ background:'#fff', width:'min(900px,90%)', maxHeight:'80vh', overflow:'auto', borderRadius:12, boxShadow:'0 10px 30px -8px rgba(0,0,0,0.25)', padding:24 }} onClick={e=>e.stopPropagation()}>
            <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:12 }}>
              <h3 style={{ margin:0, fontSize:18 }}>Report: {selected._id}</h3>
              <button onClick={()=>setSelected(null)} style={{ background:'#fff', color:'#111', border:'1px solid #e5e7eb', padding:'6px 10px', fontSize:12 }}>Close</button>
            </div>
            {reportLoading ? <div style={{ fontSize:13, color:'#6b7280' }}>Loading report...</div> : (
              <pre style={{ fontSize:11, background:'#f8fafc', padding:16, borderRadius:8, lineHeight:1.4, whiteSpace:'pre-wrap' }}>{reportText}</pre>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
export default Alerts;