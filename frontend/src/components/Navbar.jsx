import React, { useState, useEffect } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { Menu, X, Eye, LogOut } from 'lucide-react';
import '../styles/Navbar.css';

const Navbar = ({ admin, onLogout }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const [isVisible, setIsVisible] = useState(true);
  const [lastScrollY, setLastScrollY] = useState(0);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [scrollProgress, setScrollProgress] = useState(0);

  useEffect(() => {
    let ticking = false;
    const updateNavbar = () => {
      const currentScrollY = window.scrollY;
      if (currentScrollY > lastScrollY && currentScrollY > 100) setIsVisible(false); else setIsVisible(true);
      setLastScrollY(currentScrollY);
      const docHeight = document.documentElement.scrollHeight - window.innerHeight;
      setScrollProgress(docHeight > 0 ? (currentScrollY / docHeight) * 100 : 0);
      ticking = false;
    };
    const handleScroll = () => { if (!ticking) { window.requestAnimationFrame(updateNavbar); ticking = true; } };
    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, [lastScrollY]);

  const navLinks = [
    { name: 'Home', path: '/' },
    { name: 'Alerts', path: '/alerts' },
    { name: 'About', path: '/about' },
    { name: 'Report', path: '/report' },
    { name: 'Assistant', path: '/assistant' },
  ];

  const handleAdminClick = () => {
    if (admin) navigate('/admin'); else navigate('/admin/login');
    setIsMobileMenuOpen(false);
  };

  const isActive = (p) => (location.pathname === p) || (p !== '/' && location.pathname.startsWith(p));

  return (
    <nav className={`navbar-pimeyes ${isVisible ? 'navbar-visible' : 'navbar-hidden'}`}>

      <div className="navbar-container">
        <div className="navbar-content">
          <Link to="/" className="navbar-logo" onClick={() => setIsMobileMenuOpen(false)} aria-label="Home">
            <Eye className="logo-icon" />
            <span className="logo-text">DRISHTI</span>
          </Link>
          <div className="navbar-links">
            {navLinks.map((l, index) => {
              const colors = ['yellow', 'red', 'green'];
              const colorClass = `retro-btn-${colors[index % 3]}`;
              return (
                <Link
                  key={l.path}
                  to={l.path}
                  className={`retro-btn ${colorClass} ${isActive(l.path) ? 'active' : ''}`}
                  aria-current={isActive(l.path) ? 'page' : undefined}
                  onClick={() => setIsMobileMenuOpen(false)}
                >
                  <div className="retro-btn-text">{l.name}</div>
                  <div className="retro-btn-arrow">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M5 12h14M12 5l7 7-7 7" />
                    </svg>
                  </div>
                </Link>
              );
            })}
            <div className="nav-actions">
              <button onClick={handleAdminClick} className="retro-btn retro-btn-yellow">
                <div className="retro-btn-text">{admin ? 'Admin Panel' : 'Admin Login'}</div>
                <div className="retro-btn-arrow">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M5 12h14M12 5l7 7-7 7" />
                  </svg>
                </div>
              </button>
              {admin ? (
                <button onClick={() => { onLogout(); }} className="retro-btn retro-btn-green">
                  <div className="retro-btn-text"><LogOut size={14} /> Logout</div>
                  <div className="retro-btn-arrow">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M5 12h14M12 5l7 7-7 7" />
                    </svg>
                  </div>
                </button>
              ) : null}
            </div>
          </div>
          <button onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)} className="mobile-menu-btn" aria-label="Toggle menu">{isMobileMenuOpen ? <X size={24} /> : <Menu size={24} />}</button>
        </div>
      </div>
      {isMobileMenuOpen && (
        <div className="mobile-menu">
          <div className="mobile-menu-content">
            {navLinks.map(l => (
              <Link
                key={l.path}
                to={l.path}
                className={`mobile-nav-link ${isActive(l.path) ? 'active' : ''}`}
                aria-current={isActive(l.path) ? 'page' : undefined}
                onClick={() => setIsMobileMenuOpen(false)}
              >{l.name}</Link>
            ))}
            <div className="mobile-nav-actions">
              <button onClick={handleAdminClick} className="mobile-btn-login">{admin ? 'Admin Panel' : 'Admin Login'}</button>
              {admin ? (
                <button onClick={() => { onLogout(); setIsMobileMenuOpen(false); }} className="mobile-btn-demo" style={{ color: '#2563eb' }}>Logout</button>
              ) : null}
            </div>
          </div>
        </div>
      )}
    </nav>
  );
};
export default Navbar;
