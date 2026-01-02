import React from 'react';
import { Brain, Eye, Zap, Lock } from 'lucide-react';
import '../styles/KeyHighlights.css';
import highlightsBg from '../assets/images/sections/highlights-bg.webp';

const KeyHighlights = () => {
  const highlights = [
    { icon: Brain, title: 'Advanced AI', description: 'Cutting-edge machine learning algorithms for', keyword: 'real-time threat detection' },
    { icon: Eye, title: 'Multi-Source', description: 'Seamless integration of CCTV, drone, and bodycam for', keyword: 'comprehensive monitoring' },
    { icon: Zap, title: 'Instant Response', description: 'Lightning-fast processing with', keyword: '<50ms response time' },
    { icon: Lock, title: 'Seamless Integration ', description: 'Integrate with existing infrastructure', keyword: 'Legacy Compatible & Portable' },
  ];
  return (
    <section className="key-highlights-section" id="key-highlights">
      <div className="kh-bg-container">
        <div className="kh-background-layer">
          <img src={highlightsBg} alt="DRISHTI Features" className="kh-bg-image" />
          <div className="kh-bg-placeholder"></div>
        </div>
        <div className="kh-overlay"></div>
        <div className="kh-content-wrapper">
          <div className="kh-container">
            <div className="kh-header">
              <h2 className="kh-title">Why Choose<span className="kh-highlight"> DRISHTI</span>
                <svg className="kh-title-underline" viewBox="0 0 280 12" xmlns="http://www.w3.org/2000/svg"><path d="M2 9c90-4 190-4 276 0" stroke="#fbbf24" strokeWidth="4" fill="none" strokeLinecap="round"/></svg>
              </h2>
            </div>
            <div className="kh-grid">
              <div className="kh-features-column">
                {highlights.map((h,i)=> (
                  <div key={i} className="kh-feature-box">
                    <div className="kh-feature-number">{i+1}</div>
                    <div className="kh-feature-content">
                      <h3 className="kh-feature-title">{h.title}</h3>
                      <p className="kh-feature-desc">{h.description} <span className="kh-keyword">{h.keyword}</span></p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};
export default KeyHighlights;