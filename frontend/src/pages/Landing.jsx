import React from 'react';
import Hero from '../components/Hero';
import ProblemSolution from '../components/ProblemSolution';
import KeyHighlights from '../components/KeyHighlights';
import CTA from '../components/CTA';

const Landing = () => {
  return (
    <div className="landing-page-full">
      <section className="hero-wrapper">
        <Hero />
      </section>
      
      <section className="problem-wrapper">
        <ProblemSolution />
      </section>
      
      <section className="highlights-wrapper">
        <KeyHighlights />
      </section>
      
      <section className="cta-wrapper">
        <CTA />
      </section>
    </div>
  );
};

export default Landing;