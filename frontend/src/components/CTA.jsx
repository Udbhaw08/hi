import React, { useState } from 'react';
import { X } from 'lucide-react';
import '../styles/CTA.css';
import ctaBg from '../assets/images/sections/cta-bg.webp';
import yoloImage from '../assets/images/tools/yolo-detection.jpeg';
import arcfaceImage from '../assets/images/tools/arcface-recognition.jpg';
import deepsortImage from '../assets/images/tools/deepsort-tracking.jpeg';
import slowfastImage from '../assets/images/tools/slowfast-action.jpeg';
import multiSourceImage from '../assets/images/tools/multi-source.jpeg';
import offlineImage from '../assets/images/tools/offline-capability.jpeg';

const CTA = () => {
  const [open, setOpen] = useState(null);
  const tools = [
    { id:1, title:'YOLOv11', subtitle:'Object Detection', short:'Real-time detection of weapons and suspicious objects', full:'Advanced YOLO architecture optimized for detecting weapons, unattended bags, and suspicious objects in video feeds with 99.2% accuracy. Processes multiple camera streams simultaneously with sub-50ms latency.', feats:['Weapon Detection','Suspicious Object Identification','Multi-Camera Support','Real-time Processing'], image:yoloImage },
    { id:2, title:'ArcFace', subtitle:'Face Recognition', short:'High-accuracy facial recognition system', full:'State-of-the-art face recognition using ArcFace embeddings with RetinaFace detection. Matches faces against NSG whitelists and watchlists with 98.5% accuracy across varying lighting and angles.', feats:['Watchlist Matching','Whitelist Filtering','Multi-Angle Recognition','10K+ Database Support'], image:arcfaceImage },
    { id:3, title:'DeepSORT', subtitle:'Person Tracking', short:'Multi-camera tracking and re-identification', full:'Advanced tracking algorithm that follows individuals across multiple camera feeds. Maintains unique IDs and tracks movement patterns for comprehensive surveillance coverage.', feats:['Cross-Camera Tracking','Unique ID Assignment','Movement Patterns','Re-identification'], image:deepsortImage },
    { id:4, title:'SlowFast', subtitle:'Action Recognition', short:'Detects suspicious behavior and activities', full:'Temporal action recognition model that identifies loitering, aggressive movements, running, and other suspicious behaviors in real-time video streams.', feats:['Loitering Detection','Aggression Recognition','Suspicious Activity Alerts','Behavior Analysis'], image:slowfastImage },
    { id:5, title:'Multi-Source Integration', subtitle:'Unified Platform', short:'CCTV, Drone, and Bodycam feeds in one system', full:'Seamlessly integrates video feeds from multiple sources including CCTV cameras, drone footage, and bodycams. Provides a unified operational view without requiring new hardware infrastructure.', feats:['CCTV Integration','Drone Feed Support','Bodycam Compatible','No New Hardware Required'], image:multiSourceImage },
    { id:6, title:'Offline Capability', subtitle:'Local Deployment', short:'Works entirely without internet connection', full:'Complete offline operation using ONNX Runtime for edge deployment. All AI models run locally on standard laptops, ensuring data security and operational independence in sensitive locations.', feats:['No Internet Required','Local Processing','Data Security','Lightweight Architecture'], image:offlineImage },
  ];
  return (
    <section className="cta-section" id="cta">
      <div className="cta-bg-container">
        <div className="cta-background-layer"><img src={ctaBg} alt="Background" className="cta-bg-image" /><div className="cta-bg-placeholder" /></div>
        <div className="cta-overlay" />
        <div className="cta-content-wrapper">
          <div className="cta-container">
            <div className="cta-header"><h2 className="cta-title">Tools & <span className="cta-highlight"> Technology Stack</span>
              <svg className="cta-title-underline" viewBox="0 0 350 12" xmlns="http://www.w3.org/2000/svg"><path d="M2 9c115-4 235-4 346 0" stroke="#fbbf24" strokeWidth="4" fill="none" strokeLinecap="round"/></svg></h2></div>
            <div className="cta-cards-grid">
              {tools.map((c,i)=> (
                <div key={c.id} className="cta-card" onClick={()=> setOpen(c)}>
                  <div className="cta-card-number">{String(i+1).padStart(2,'0')}</div>
                  <div className="cta-card-image-preview"><img src={c.image} alt={c.title} /></div>
                  <h3 className="cta-card-title">{c.title}</h3>
                  <p className="cta-card-subtitle">{c.subtitle}</p>
                  <p className="cta-card-desc">{c.short}</p>
                  <div className="cta-card-footer"><span className="learn-more">Learn More →</span></div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
      {open && (
        <div className="cta-modal-overlay" onClick={()=> setOpen(null)}>
          <div className="cta-modal-content" onClick={e=> e.stopPropagation()}>
            <button className="cta-modal-close" onClick={()=> setOpen(null)}><X size={24} /></button>
            <div className="cta-modal-grid">
              <div className="cta-modal-image-section"><img src={open.image} alt={open.title} className="cta-modal-image" /></div>
              <div className="cta-modal-details">
                <div className="modal-header-section"><h3 className="modal-title">{open.title}</h3><p className="modal-subtitle">{open.subtitle}</p></div>
                <div className="modal-description"><p>{open.full}</p></div>
                <div className="modal-features"><h4 className="features-title">Key Features:</h4><ul className="features-list">{open.feats.map((f,i)=>(<li key={i} className="feature-item"><span className="feature-dot">•</span><span>{f}</span></li>))}</ul></div>
              </div>
            </div>
          </div>
        </div>
      )}
    </section>
  );
};
export default CTA;