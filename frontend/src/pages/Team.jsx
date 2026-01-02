import React from 'react';
import { Github, Linkedin, Mail } from 'lucide-react';
import '../styles/Team.css';
import shreyaImg from '../assets/images/shreya.png';
import harshImg from '../assets/images/harsh.png';
import abhishekImg from '../assets/images/abhishek.png';
import adarshImg from '../assets/images/adarsh.png';
import ayazImg from '../assets/images/ayaz.png';
import arpitImg from '../assets/images/arpit.png';

const Team = () => {
  const teamMembers = [
    { name: 'SHREYA RAWAT', role: 'Team Lead & UI UX Designer', image: shreyaImg, bio: 'Expert in UI/UX design and leading cross-functional teams to deliver exceptional user experiences', github: '#', linkedin: '#', email: 'shreya@example.com' },
    { name: 'HARSH', role: 'Backend Developer', image: harshImg, bio: 'Specializes in scalable architecture and real-time data processing for high-performance systems', github: '#', linkedin: '#', email: 'harsh@example.com' },
    { name: 'ABHISHEK JAISWAL', role: 'ML Engineer', image: abhishekImg, bio: 'Focused on model optimization and deployment for production AI/ML systems', github: '#', linkedin: '#', email: 'abhishek@example.com' },
    { name: 'ADARSH SINGH', role: 'Frontend Developer', image: adarshImg, bio: 'Creates intuitive user interfaces for complex data visualization and real-time dashboards', github: '#', linkedin: '#', email: 'adarsh@example.com' },
    { name: 'AYAZ AHMED', role: 'DevOps Engineer', image: ayazImg, bio: 'Ensures smooth deployment and monitoring of AI systems with robust CI/CD pipelines', github: '#', linkedin: '#', email: 'ayaz@example.com' },
    { name: 'ARPIT SINGHAL', role: 'ML Engineer', image: arpitImg, bio: 'Specializes in computer vision and deep learning for security surveillance systems', github: '#', linkedin: '#', email: 'arpit@example.com' },
  ];
  return (
    <div className="team-page">
      <div className="container">
        <div className="team-header">
          <h1 className="team-title">Meet Our Team</h1>
          <p className="team-subtitle">The brilliant minds behind DRISHTI - bringing together expertise in AI, security, and software engineering</p>
        </div>
        <div className="team-grid">
          {teamMembers.map((m,i)=>(
            <div key={i} className="team-card">
              <div className="team-card-inner">
                <div className="team-card-front">
                  <div className="member-image-wrapper"><img src={m.image} alt={m.name} className="member-image" /></div>
                  <div className="member-info"><h3 className="member-name">{m.name}</h3><p className="member-role">{m.role}</p></div>
                </div>
                <div className="team-card-back">
                  <h3 className="member-name-back">{m.name}</h3>
                  <p className="member-role-back">{m.role}</p>
                  <p className="member-bio">{m.bio}</p>
                  <div className="social-links-team">
                    <a href={m.github} target="_blank" rel="noopener noreferrer" className="social-link-team" aria-label="GitHub"><Github size={20} /></a>
                    <a href={m.linkedin} target="_blank" rel="noopener noreferrer" className="social-link-team" aria-label="LinkedIn"><Linkedin size={20} /></a>
                    <a href={`mailto:${m.email}`} className="social-link-team" aria-label="Email"><Mail size={20} /></a>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
export default Team;