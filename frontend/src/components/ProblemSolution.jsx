import React from 'react';

const ProblemSolution = () => {
  const features = [
    'Face Detection',
    'Real-time Recognition',
    'Clothing Analysis',
    'clohing 2 Detection',
    'NFC Dashboard',
    'Admin Control',
    'BODY POSE'
  ];

  return (
    <section className="problem-solution-section" id="problem-solution">
      <div className="container">
        <div style={{ textAlign: 'center', marginBottom: '3rem' }}>
          <h2 className="ps-title" style={{ fontSize: '2.5rem', fontWeight: 700 }}>Key Capabilities</h2>
          <p style={{ color: '#6b7280', maxWidth: '600px', margin: '1rem auto' }}>
            Advanced security features designed for robust surveillance and real-time monitoring.
          </p>
        </div>
        <div style={{ 
          display: 'grid', 
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', 
          gap: '1.5rem',
          padding: '2rem 0'
        }}>
          {features.map((feature, index) => (
            <div key={index} style={{
              background: '#f9fafb',
              padding: '2rem',
              borderRadius: '16px',
              textAlign: 'center',
              border: '1px solid #e5e7eb',
              transition: 'transform 0.2s ease, box-shadow 0.2s ease',
              cursor: 'default'
            }}
            onMouseOver={(e) => {
              e.currentTarget.style.transform = 'translateY(-5px)';
              e.currentTarget.style.boxShadow = '0 10px 25px -5px rgba(0, 0, 0, 0.05)';
            }}
            onMouseOut={(e) => {
              e.currentTarget.style.transform = 'translateY(0)';
              e.currentTarget.style.boxShadow = 'none';
            }}
            >
              <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 600, color: '#111827' }}>{feature}</h3>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
};

export default ProblemSolution;