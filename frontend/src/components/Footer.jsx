import React from 'react';
import { Eye, Mail, Github, Linkedin, Twitter, ExternalLink } from 'lucide-react';
import { Link } from 'react-router-dom';
import '../styles/Footer.css';

const Footer = () => {
  const footerLinks = {
    product: [ { name: 'Streams', path: '/streams' }, { name: 'Tools & Tech', path: '/#cta' }, { name: 'Why DRISHTI', path: '/#key-highlights' } ],
    company: [ { name: 'About Project', path: '/about' }, { name: 'Our Team', path: '/team' }, { name: 'Problem Statement', path: '/about' } ],
    resources: [ { name: 'SIH 2025', url: 'https://www.sih.gov.in/', external: true }, { name: 'GitHub Repository', url: '#', external: true }, { name: 'Documentation', url: '#', external: false } ],
  };
  const socialLinks = [ { icon: Github, url: '#', label: 'GitHub' }, { icon: Linkedin, url: '#', label: 'LinkedIn' }, { icon: Twitter, url: '#', label: 'Twitter' }, { icon: Mail, url: 'mailto:team@drishti.ai', label: 'Email' } ];
  return (
    <footer className="footer">
      <div className="container">
        <div className="footer-content">
          <div className="footer-brand">
          <Link to="/" className="footer-logo">
              <Eye size={32} />
              <span>DRISHTI</span>
            </Link>
            <p className="footer-tagline">
              Advanced AI-powered video surveillance system for National Security Guard operations.
              Real-time threat detection, facial recognition, and automated incident reporting.
            </p>
            <div className="social-links">
              {socialLinks.map((s,i)=> { const I=s.icon; return <a key={i} href={s.url} className="social-link" aria-label={s.label} target="_blank" rel="noopener noreferrer"><I size={20} /></a>; })}
            </div>
          </div>
          <div className="footer-links">
            <div className="footer-column">
              <h4 className="footer-heading">Product</h4>
              <ul className="footer-list">{footerLinks.product.map((l,i)=>(<li key={i}><Link to={l.path} className="footer-link">{l.name}</Link></li>))}</ul>
            </div>
            <div className="footer-column">
              <h4 className="footer-heading">Project</h4>
              <ul className="footer-list">{footerLinks.company.map((l,i)=>(<li key={i}><Link to={l.path} className="footer-link">{l.name}</Link></li>))}</ul>
            </div>
            <div className="footer-column">
              <h4 className="footer-heading">Resources</h4>
              <ul className="footer-list">{footerLinks.resources.map((l,i)=>(<li key={i}>{l.external ? <a href={l.url} className="footer-link" target="_blank" rel="noopener noreferrer">{l.name}<ExternalLink size={14} className="external-icon" /></a> : <Link to={l.url} className="footer-link">{l.name}</Link>}</li>))}</ul>
            </div>
          </div>
        </div>
        <div className="footer-bottom">
          <p style={{ color:'#6b7280', fontSize:14, marginBottom:8, fontWeight:500 }}>© {new Date().getFullYear()} DRISHTI AI. All rights reserved.</p>
          <p className="footer-note">Built for Smart India Hackathon 2025 - National Security & Defense</p>
        </div>
      </div>
    </footer>
  );
};
export default Footer;