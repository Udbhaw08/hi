import React from 'react';
import { Target, Lightbulb, Shield, Zap } from 'lucide-react';
import '../styles/About.css';

const About = () => {
  return (
    <div className="about-page">
      <div className="container">
        {/* Header */}
        <div className="about-header">
          <h1 className="about-title">About DRISHTI</h1>
          <p className="about-subtitle">Building the future of intelligent security surveillance</p>
        </div>
        {/* Problem Statement */}
        <section className="about-section">
          <div className="section-icon-wrapper"><Target className="section-icon" size={40} /></div>
          <h2 className="about-section-title">Problem Statement</h2>
          <div className="about-content">
            <p className="about-text"><strong>Problem Statement </strong></p>
            <p className="about-text">In today’s fast-growing world ‘ malls, metro stations, campuses, and busy markets ‘ thousands of CCTV cameras record footage
every second, but most of it is never analyzed in real time. In 2022 alone, over 47,000 children went missing, and more than 90%
of surveillance feeds stayed unmonitored , leading to delayed action during fights, thefts, or emergencies.</p>
            <p className="about-text">Even during the Maha
Kumbh 2025, where around 450 million people gathered, and 2,700 AI cameras were installed to find missing persons, over
20,000 people had to be traced manually ,showing how difficult real-time detection and response still is in large crowds.</p>
          </div>
        </section>
        {/* Our Solution */}
        <section className="about-section">
          <div className="section-icon-wrapper solution"><Lightbulb className="section-icon" size={40} /></div>
          <h2 className="about-section-title">Our Solution</h2>
          <div className="about-content">
            <p className="about-text">DRISHTI is an advanced AI-powered video analysis platform designed specifically for  security . Our system leverages cutting-edge machine learning algorithms to provide real-time threat detection and automated incident reporting.</p>
            <div className="features-list">
              <div className="feature-item"><div className="feature-number">01</div><div className="feature-content"><h3 className="feature-title">Multi-Video Monitoring</h3><p className="feature-desc">Simultaneously analyze up to 16 camera feeds using advanced computer vision</p></div></div>
              <div className="feature-item"><div className="feature-number">02</div><div className="feature-content"><h3 className="feature-title">Real-Time Detection</h3><p className="feature-desc">Identify threats, suspicious activities, and persons of interest in milliseconds</p></div></div>
              <div className="feature-item"><div className="feature-number">03</div><div className="feature-content"><h3 className="feature-title">Automated Reporting</h3><p className="feature-desc">Generate comprehensive incident reports instantly with video evidence and analytics</p></div></div>
              <div className="feature-item"><div className="feature-number">04</div><div className="feature-content"><h3 className="feature-title">Face Recognition</h3><p className="feature-desc">Match faces against a database of known individuals with 98.5% accuracy</p></div></div>
            </div>
          </div>
        </section>
        {/* Technology Stack */}
        <section className="about-section">
          <div className="section-icon-wrapper tech"><Zap className="section-icon" size={40} /></div>
          <h2 className="about-section-title">Technology Stack</h2>
          <div className="about-content">
            <div className="tech-grid">
              <div className="tech-card"><h4 className="tech-name">Deep Learning</h4><p className="tech-desc">TensorFlow, PyTorch, YOLO</p></div>
              <div className="tech-card"><h4 className="tech-name">Computer Vision</h4><p className="tech-desc">OpenCV, MediaPipe</p></div>
              <div className="tech-card"><h4 className="tech-name">Backend</h4><p className="tech-desc">Python, FastAPI, Node.js</p></div>
              <div className="tech-card"><h4 className="tech-name">Frontend</h4><p className="tech-desc">React, Vite</p></div>
              <div className="tech-card"><h4 className="tech-name">Database</h4><p className="tech-desc">PostgreSQL, Redis</p></div>
              <div className="tech-card"><h4 className="tech-name">Cloud</h4><p className="tech-desc">AWS, Docker</p></div>
            </div>
          </div>
        </section>
        {/* Vision & Mission */}
        <section className="about-section">
          <div className="section-icon-wrapper mission"><Shield className="section-icon" size={40} /></div>
          <h2 className="about-section-title">Our Vision & Mission</h2>
          <div className="about-content">
            <div className="vision-mission-grid">
              <div className="vm-card"><h3 className="vm-title">Vision</h3><p className="vm-text">To revolutionize security surveillance through AI, making national security operations more efficient, accurate, and proactive in threat detection and prevention.</p></div>
              <div className="vm-card"><h3 className="vm-title">Mission</h3><p className="vm-text">Empower security forces with cutting-edge AI technology that reduces response times, eliminates human error, and provides actionable intelligence for critical decision-making.</p></div>
            </div>
          </div>
        </section>
        {/* Impact Stats */}
        <section className="impact-section">
          <h2 className="impact-title">Expected Impact</h2>
          <div className="impact-grid">
            <div className="impact-card"><div className="impact-value">80%</div><div className="impact-label">Reduction in Response Time</div></div>
            <div className="impact-card"><div className="impact-value">95%</div><div className="impact-label">Threat Detection Accuracy</div></div>
            <div className="impact-card"><div className="impact-value">70%</div><div className="impact-label">Decrease in Manual Monitoring</div></div>
            <div className="impact-card"><div className="impact-value">24/7</div><div className="impact-label">Continuous Operations</div></div>
          </div>
        </section>
      </div>
    </div>
  );
};
export default About;