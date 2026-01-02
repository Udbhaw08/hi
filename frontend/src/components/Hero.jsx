import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, Info, Play, Brain, Zap, Shield, Eye, Camera, TrendingUp } from 'lucide-react';
import '../styles/Hero.css';
import heroVisual from '../assets/images/hero-visual.png';

const Hero = () => {
  const rotatingTexts = ['Real-time Threat Detection','AI-Powered Face Recognition','Multi-Camera Monitoring','Automated Incident Reporting','Intelligent Video Analysis'];
  const [idx, setIdx] = useState(0);
  useEffect(()=>{ const id = setInterval(()=> setIdx(i=> i===rotatingTexts.length-1?0:i+1),3000); return ()=> clearInterval(id); },[]);
  return (
    <section className="hero-section" id="hero">
      <div className="hero-container">
        <div className="hero-grid">
          <div className="hero-content-left">
            <h1 className="hero-title">
              <span className="title-regular">Advanced AI System for</span><br />
              <span className="title-highlight"><span className="highlight-text"> AI-powered  surveillance</span>
                <svg className="title-underline" viewBox="0 0 300 12" xmlns="http://www.w3.org/2000/svg"><path d="M2 9c100-4 200-4 296 0" stroke="#fbbf24" strokeWidth="3" fill="none" strokeLinecap="round"/></svg>
              </span>
            </h1>
            <p className="hero-subtitle">DRISHTI - Your intelligent surveillance companion that leverages cutting-edge AI to ensure comprehensive security monitoring</p>
            <div className="rotating-text-container"><span className="rotating-label">Featuring:</span><span className="rotating-text" key={idx}>{rotatingTexts[idx]}</span></div>
            <div className="hero-stats">
              <div className="stat-item"><div className="stat-number">96%</div><div className="stat-text">Accuracy</div></div>
              <div className="stat-divider" />
              <div className="stat-item"><div className="stat-number">&lt;50ms</div><div className="stat-text">Response</div></div>
              <div className="stat-divider" />
              <div className="stat-item"><div className="stat-number">24/7</div><div className="stat-text">Monitoring</div></div>
            </div>
            <div className="hero-buttons">
              <Link to="/streams" className="btn-primary-hero"><Play size={18} /><span>View Live Streams</span><ArrowRight size={18} className="arrow-icon" /></Link>
              <Link to="/about" className="btn-secondary-hero"><Info size={18} /><span>Learn More</span></Link>
            </div>
          </div>
          <div className="hero-content-right">
            <div className="visual-container">
              <div className="hero-image-wrapper">
                <img src={heroVisual} alt="DRISHTI AI Security System" className="hero-image" />
                <div className="floating-card card-1"><Brain size={20} /><span>AI Detection</span></div>
                <div className="floating-card card-2"><Shield size={20} /><span>Secure</span></div>
                <div className="floating-card card-3"><Zap size={20} /><span>Real-time</span></div>
                <div className="floating-card card-4"><Eye size={20} /><span>Face Recognition</span></div>
                <div className="floating-card card-5"><Camera size={20} /><span>Multi-Camera</span></div>
                <div className="floating-card card-6"><TrendingUp size={20} /><span>99.2% Accuracy</span></div>
              </div>
            </div>
          </div>
        </div>
      </div>
      <div className="hero-bg-gradient-left" />
      <div className="hero-bg-gradient-right" />
      <div className="hero-grid-bg" />
    </section>
  );
};
export default Hero;