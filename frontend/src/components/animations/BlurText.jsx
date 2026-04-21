import React, { useRef, useEffect } from 'react';
import { gsap } from 'gsap';
import './BlurText.css';

/**
 * BlurText - GSAP-powered blur reveal animation
 * Text starts blurred and fades into focus with stagger
 */
export default function BlurText({
    children,
    delay = 0,
    duration = 0.8,
    staggerAmount = 0.05,
    blurAmount = 20,
    className = ''
}) {
    const containerRef = useRef(null);
    const hasAnimated = useRef(false);

    useEffect(() => {
        if (!containerRef.current || hasAnimated.current) return;
        hasAnimated.current = true;

        const chars = containerRef.current.querySelectorAll('.blur-char');

        gsap.set(chars, {
            opacity: 0,
            filter: `blur(${blurAmount}px)`,
            y: 15
        });

        gsap.to(chars, {
            opacity: 1,
            filter: 'blur(0px)',
            y: 0,
            duration: duration,
            stagger: staggerAmount,
            delay: delay,
            ease: 'power3.out'
        });
    }, [delay, duration, staggerAmount, blurAmount]);

    // Split text into characters
    const text = typeof children === 'string' ? children : '';
    const chars = text.split('').map((char, i) => (
        <span key={i} className="blur-char" style={{ display: 'inline-block' }}>
            {char === ' ' ? '\u00A0' : char}
        </span>
    ));

    return (
        <span ref={containerRef} className={`blur-text ${className}`}>
            {chars}
        </span>
    );
}
