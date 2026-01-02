import React from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';
import '../styles/ProblemSolution.css';
import problemBg from '../assets/images/sections/problem-solution-bg.jpg';

const ProblemSolution = () => {
  return (
    <section className="problem-solution-section" id="problem-solution">
      <div className="ps-bg-container">
        <div className="ps-background-layer">
          <img src={problemBg} alt="DRISHTI System" className="ps-bg-image" />
          <div className="ps-bg-placeholder"></div>
        </div>
        <div className="ps-overlay"></div>
        <div className="ps-content-wrapper">
          <div className="ps-container">
            <div className="ps-header">
              <h2 className="ps-title">DRISHTI</h2>
              <div className="ps-description">
                <p className="ps-desc-line">Advanced <span className="highlight-inline">AI-powered video surveillance</span> system designed for security.</p>
                <p className="ps-desc-line">Real-time threat detection, facial recognition, and automated incident reporting in one unified platform.</p>
              </div>
            </div>
            <div className="ps-cta-box">
              <div className="ps-cta-inner">
                <h3 className="ps-cta-title"><span className="cta-highlight">Revolutionizing</span><span className="cta-text"> Security Operations</span>
                  <svg className="title-underline-red" viewBox="0 0 500 12" xmlns="http://www.w3.org/2000/svg"><path d="M2 9c165-4 335-4 496 0" stroke="#dc2626" strokeWidth="3" fill="none" strokeLinecap="round"/></svg>
                </h3>
                <p className="ps-cta-description">DRISHTI combines cutting-edge artificial intelligence with comprehensive video analysis to provide unparalleled security monitoring capabilities for national defense operations.</p>
                <Link to="/about" className="ps-discover-btn"><span>Discover More About DRISHTI</span><ArrowRight size={22} /></Link>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};
export default ProblemSolution;