import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, Info, Play, Brain, Zap, Shield, Eye, Camera, TrendingUp } from 'lucide-react';
import { gsap } from 'gsap';
import TrueFocus from './animations/TrueFocus';
import '../styles/Hero.css';
import heroVisual from '../assets/images/hero-visual.png';

// TargetCursor Component (integrated)
const TargetCursor = ({ targetSelector = '.cursor-target', spinDuration = 2, hideDefaultCursor = true, hoverDuration = 0.2, parallaxOn = true }) => {
  const cursorRef = useRef(null);
  const cornersRef = useRef(null);
  const spinTl = useRef(null);
  const dotRef = useRef(null);
  const isActiveRef = useRef(false);
  const targetCornerPositionsRef = useRef(null);
  const tickerFnRef = useRef(null);
  const activeStrengthRef = useRef(0);

  const isMobile = useMemo(() => {
    if (typeof window === 'undefined') return true;
    const hasTouchScreen = 'ontouchstart' in window || navigator.maxTouchPoints > 0;
    const isSmallScreen = window.innerWidth <= 768;
    const userAgent = navigator.userAgent || navigator.vendor || window.opera;
    const mobileRegex = /android|webos|iphone|ipad|ipod|blackberry|iemobile|opera mini/i;
    return (hasTouchScreen && isSmallScreen) || mobileRegex.test(userAgent.toLowerCase());
  }, []);

  const constants = useMemo(() => ({ borderWidth: 3, cornerSize: 12 }), []);

  const moveCursor = useCallback((x, y) => {
    if (!cursorRef.current) return;
    gsap.to(cursorRef.current, { x, y, duration: 0.1, ease: 'power3.out' });
  }, []);

  useEffect(() => {
    if (isMobile || !cursorRef.current) return;
    const originalCursor = document.body.style.cursor;
    if (hideDefaultCursor) document.body.style.cursor = 'none';

    const cursor = cursorRef.current;
    cornersRef.current = cursor.querySelectorAll('.target-cursor-corner');
    let activeTarget = null;
    let currentLeaveHandler = null;
    let resumeTimeout = null;

    const cleanupTarget = target => { if (currentLeaveHandler) target.removeEventListener('mouseleave', currentLeaveHandler); currentLeaveHandler = null; };

    gsap.set(cursor, { xPercent: -50, yPercent: -50, x: window.innerWidth / 2, y: window.innerHeight / 2 });

    const createSpinTimeline = () => {
      if (spinTl.current) spinTl.current.kill();
      spinTl.current = gsap.timeline({ repeat: -1 }).to(cursor, { rotation: '+=360', duration: spinDuration, ease: 'none' });
    };
    createSpinTimeline();

    const tickerFn = () => {
      if (!targetCornerPositionsRef.current || !cursorRef.current || !cornersRef.current) return;
      const strength = activeStrengthRef.current;
      if (strength === 0) return;
      const cursorX = gsap.getProperty(cursorRef.current, 'x');
      const cursorY = gsap.getProperty(cursorRef.current, 'y');
      const corners = Array.from(cornersRef.current);
      corners.forEach((corner, i) => {
        const currentX = gsap.getProperty(corner, 'x');
        const currentY = gsap.getProperty(corner, 'y');
        const targetX = targetCornerPositionsRef.current[i].x - cursorX;
        const targetY = targetCornerPositionsRef.current[i].y - cursorY;
        const finalX = currentX + (targetX - currentX) * strength;
        const finalY = currentY + (targetY - currentY) * strength;
        const duration = strength >= 0.99 ? (parallaxOn ? 0.2 : 0) : 0.05;
        gsap.to(corner, { x: finalX, y: finalY, duration, ease: duration === 0 ? 'none' : 'power1.out', overwrite: 'auto' });
      });
    };
    tickerFnRef.current = tickerFn;

    const moveHandler = e => moveCursor(e.clientX, e.clientY);
    window.addEventListener('mousemove', moveHandler);

    const scrollHandler = () => {
      if (!activeTarget || !cursorRef.current) return;
      const mouseX = gsap.getProperty(cursorRef.current, 'x');
      const mouseY = gsap.getProperty(cursorRef.current, 'y');
      const elementUnderMouse = document.elementFromPoint(mouseX, mouseY);
      const isStillOverTarget = elementUnderMouse && (elementUnderMouse === activeTarget || elementUnderMouse.closest(targetSelector) === activeTarget);
      if (!isStillOverTarget && currentLeaveHandler) currentLeaveHandler();
    };
    window.addEventListener('scroll', scrollHandler, { passive: true });

    const mouseDownHandler = () => { if (!dotRef.current) return; gsap.to(dotRef.current, { scale: 0.7, duration: 0.3 }); gsap.to(cursorRef.current, { scale: 0.9, duration: 0.2 }); };
    const mouseUpHandler = () => { if (!dotRef.current) return; gsap.to(dotRef.current, { scale: 1, duration: 0.3 }); gsap.to(cursorRef.current, { scale: 1, duration: 0.2 }); };
    window.addEventListener('mousedown', mouseDownHandler);
    window.addEventListener('mouseup', mouseUpHandler);

    const enterHandler = e => {
      const directTarget = e.target;
      const allTargets = [];
      let current = directTarget;
      while (current && current !== document.body) {
        if (current.matches && current.matches(targetSelector)) allTargets.push(current);
        current = current.parentElement;
      }
      const target = allTargets[0] || null;
      if (!target || !cursorRef.current || !cornersRef.current) return;
      if (activeTarget === target) return;
      if (activeTarget) cleanupTarget(activeTarget);
      if (resumeTimeout) { clearTimeout(resumeTimeout); resumeTimeout = null; }

      activeTarget = target;
      const corners = Array.from(cornersRef.current);
      corners.forEach(corner => gsap.killTweensOf(corner));
      gsap.killTweensOf(cursorRef.current, 'rotation');
      spinTl.current?.pause();
      gsap.set(cursorRef.current, { rotation: 0 });

      const rect = target.getBoundingClientRect();
      const { borderWidth, cornerSize } = constants;
      const cursorX = gsap.getProperty(cursorRef.current, 'x');
      const cursorY = gsap.getProperty(cursorRef.current, 'y');

      targetCornerPositionsRef.current = [
        { x: rect.left - borderWidth, y: rect.top - borderWidth },
        { x: rect.right + borderWidth - cornerSize, y: rect.top - borderWidth },
        { x: rect.right + borderWidth - cornerSize, y: rect.bottom + borderWidth - cornerSize },
        { x: rect.left - borderWidth, y: rect.bottom + borderWidth - cornerSize }
      ];

      isActiveRef.current = true;
      gsap.ticker.add(tickerFnRef.current);
      gsap.to(activeStrengthRef, { current: 1, duration: hoverDuration, ease: 'power2.out' });

      corners.forEach((corner, i) => {
        gsap.to(corner, { x: targetCornerPositionsRef.current[i].x - cursorX, y: targetCornerPositionsRef.current[i].y - cursorY, duration: 0.2, ease: 'power2.out' });
      });

      const leaveHandler = () => {
        gsap.ticker.remove(tickerFnRef.current);
        isActiveRef.current = false;
        targetCornerPositionsRef.current = null;
        gsap.set(activeStrengthRef, { current: 0, overwrite: true });
        activeTarget = null;

        if (cornersRef.current) {
          const corners = Array.from(cornersRef.current);
          gsap.killTweensOf(corners);
          const { cornerSize } = constants;
          const positions = [
            { x: -cornerSize * 1.5, y: -cornerSize * 1.5 },
            { x: cornerSize * 0.5, y: -cornerSize * 1.5 },
            { x: cornerSize * 0.5, y: cornerSize * 0.5 },
            { x: -cornerSize * 1.5, y: cornerSize * 0.5 }
          ];
          const tl = gsap.timeline();
          corners.forEach((corner, index) => { tl.to(corner, { x: positions[index].x, y: positions[index].y, duration: 0.3, ease: 'power3.out' }, 0); });
        }

        resumeTimeout = setTimeout(() => {
          if (!activeTarget && cursorRef.current && spinTl.current) {
            const currentRotation = gsap.getProperty(cursorRef.current, 'rotation');
            const normalizedRotation = currentRotation % 360;
            spinTl.current.kill();
            spinTl.current = gsap.timeline({ repeat: -1 }).to(cursorRef.current, { rotation: '+=360', duration: spinDuration, ease: 'none' });
            gsap.to(cursorRef.current, { rotation: normalizedRotation + 360, duration: spinDuration * (1 - normalizedRotation / 360), ease: 'none', onComplete: () => { spinTl.current?.restart(); } });
          }
          resumeTimeout = null;
        }, 50);
        cleanupTarget(target);
      };

      currentLeaveHandler = leaveHandler;
      target.addEventListener('mouseleave', leaveHandler);
    };

    window.addEventListener('mouseover', enterHandler, { passive: true });

    return () => {
      if (tickerFnRef.current) gsap.ticker.remove(tickerFnRef.current);
      window.removeEventListener('mousemove', moveHandler);
      window.removeEventListener('mouseover', enterHandler);
      window.removeEventListener('scroll', scrollHandler);
      window.removeEventListener('mousedown', mouseDownHandler);
      window.removeEventListener('mouseup', mouseUpHandler);
      if (activeTarget) cleanupTarget(activeTarget);
      spinTl.current?.kill();
      document.body.style.cursor = originalCursor;
      isActiveRef.current = false;
      targetCornerPositionsRef.current = null;
      activeStrengthRef.current = 0;
    };
  }, [targetSelector, spinDuration, moveCursor, constants, hideDefaultCursor, isMobile, hoverDuration, parallaxOn]);

  if (isMobile) return null;

  return (
    <div ref={cursorRef} className="target-cursor-wrapper">
      <div ref={dotRef} className="target-cursor-dot" />
      <div className="target-cursor-corner corner-tl" />
      <div className="target-cursor-corner corner-tr" />
      <div className="target-cursor-corner corner-br" />
      <div className="target-cursor-corner corner-bl" />
    </div>
  );
};

const Hero = () => {
  const rotatingTexts = ['Real-time Threat Detection', 'AI-Powered Face Recognition', 'Multi-Camera Monitoring', 'Automated Incident Reporting', 'Intelligent Video Analysis'];
  const [idx, setIdx] = useState(0);

  useEffect(() => {
    const id = setInterval(() => setIdx(i => i === rotatingTexts.length - 1 ? 0 : i + 1), 3000);
    return () => clearInterval(id);
  }, []);

  return (
    <section className="hero-section" id="hero">

      <div className="hero-container">
        <div className="hero-grid">
          <div className="hero-content-left">
            <div className="hero-title">
              <div className="title-line title-regular">
                <TrueFocus
                  sentence="Advanced AI System for"
                  manualMode={false}
                  blurAmount={4}
                  borderColor="#3b82f6"
                  glowColor="rgba(59, 130, 246, 0.6)"
                  animationDuration={0.5}
                  pauseBetweenAnimations={0.8}
                />
              </div>
              <div className="title-line title-highlight">
                <TrueFocus
                  sentence="AI-powered surveillance"
                  manualMode={false}
                  blurAmount={4}
                  borderColor="#f63b3b"
                  glowColor="rgba(246, 59, 59, 0.6)"
                  animationDuration={0.5}
                  pauseBetweenAnimations={0.8}
                />
                <svg className="title-underline" viewBox="0 0 300 12" xmlns="http://www.w3.org/2000/svg">
                  <path d="M2 9c100-4 200-4 296 0" stroke="#fbbf24" strokeWidth="3" fill="none" strokeLinecap="round" />
                </svg>
              </div>
            </div>
            <p className="hero-subtitle">DRISHTI - Your intelligent surveillance companion that leverages cutting-edge AI to ensure comprehensive security monitoring</p>
            <div className="rotating-text-container">
              <span className="rotating-label">Featuring:</span>
              <span className="rotating-text" key={idx}>{rotatingTexts[idx]}</span>
            </div>
            <div className="hero-stats">
              <div className="stat-item"><div className="stat-number">96%</div><div className="stat-text">Accuracy</div></div>
              <div className="stat-divider" />
              <div className="stat-item"><div className="stat-number">&lt;50ms</div><div className="stat-text">Response</div></div>
              <div className="stat-divider" />
              <div className="stat-item"><div className="stat-number">24/7</div><div className="stat-text">Monitoring</div></div>
            </div>
            <div className="hero-buttons">
              <Link to="/streams" className="btn-3d btn-blue">
                <span>View Live Streams</span>
              </Link>
              <Link to="/about" className="btn-3d btn-red">
                <span>Learn More</span>
              </Link>
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