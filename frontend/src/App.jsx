import React, { useState } from "react";
import { BrowserRouter as Router, Routes, Route, Navigate } from "react-router-dom";
import AdminLogin from "./components/AdminLogin";
import AddPerson from "./components/AddPerson";
import PersonsList from "./components/PersonsList";
import VideoUpload from "./components/VideoUpload";
import VideoFeed from "./components/VideoFeed";
// Reorganized pages
import Landing from "./pages/Landing";
import About from "./pages/About";

import Streams from "./pages/Streams";
import Navbar from "./components/Navbar";
import Footer from "./components/Footer";
import Alerts from "./pages/Alerts";

function AdminDashboard({ admin }) {
  if (!admin) return null;
  
  return (
    <div className="grid">
      <div className="layout-split">
        <div className="grid" style={{ gap: '1.5rem', margin: 0 }}>
          <AddPerson admin={admin} onAdded={() => {}} />
          <VideoUpload admin={admin} />
        </div>
        <div className="card">
          <PersonsList admin={admin} />
        </div>
      </div>
      <div className="card">
        <h2 style={{ marginTop: 0 }}>Live Cameras (inline)</h2>
        <div className="video-grid">
          {[0, 1].map(id => (
            <div key={id} className="video-tile">
              <h4>Camera {id}</h4>
              <VideoFeed camId={id} />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function AdminLoginPage({ onLogin, admin }) {
  if (admin) return <Navigate to="/admin" replace />;
  return (
    <div className="card" style={{ maxWidth: 480, margin: '60px auto' }}>
      <h2 style={{ marginTop: 0 }}>Administrator Access</h2>
      <p style={{ marginTop: 4, color: '#6b7280', fontSize: 14 }}>Authenticate to manage enrolled persons, adjust models and process offline videos.</p>
      <AdminLogin onLogin={onLogin} />
      <div style={{ marginTop: 12, fontSize: 12, color: '#9ca3af' }}>Default credentials: admin / admin123 (change in backend .env)</div>
    </div>
  );
}

function App() {
  const [admin, setAdmin] = useState(null);
  const handleLogout = () => setAdmin(null);

  return (
    <Router>
      <a href="#main-content" className="skip-link">Skip to content</a>
      <Navbar admin={admin} onLogout={handleLogout} />
      <main id="main-content" className="main-container container" tabIndex={-1}>
        <Routes>
          <Route path="/" element={<Landing />} />
          {/* Removed /features route; Streams is now the primary public page */}
          <Route path="/streams" element={<Streams admin={admin} />} />
          <Route path="/alerts" element={<Alerts admin={admin} />} />
          <Route path="/about" element={<About />} />
         
          <Route path="/admin/login" element={<AdminLoginPage onLogin={setAdmin} admin={admin} />} />
          <Route path="/admin" element={<AdminDashboard admin={admin} />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
      <Footer />
    </Router>
  );
}

export default App;
