import { useState } from "react";
import { adminLogin } from "../api";
import "../styles/AdminLogin.css";

export default function AdminLogin({ onLogin }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleLogin = async () => {
    setLoading(true);
    setError("");
    try {
      const formData = new FormData();
      formData.append("username", username);
      formData.append("password", password);
      await adminLogin(formData);
      onLogin({ username, password });
    } catch (e) {
      setError("Login failed. Please check your credentials.");
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !loading) {
      handleLogin();
    }
  };

  return (
    <div className="admin-login-wrapper">
      <div className="admin-login-container">
        <h2>Admin Login</h2>
        <p className="admin-login-subtitle">Enter your credentials to access the dashboard</p>
        
        <div className="admin-login-form">
          {error && <div className="admin-error-message">{error}</div>}
          
          <div className="admin-input-group">
            <label className="admin-input-label">Username</label>
            <input 
              placeholder="Enter username" 
              value={username} 
              onChange={e => setUsername(e.target.value)}
              onKeyPress={handleKeyPress}
              disabled={loading}
            />
          </div>
          
          <div className="admin-input-group">
            <label className="admin-input-label">Password</label>
            <input 
              placeholder="Enter password" 
              type="password" 
              value={password} 
              onChange={e => setPassword(e.target.value)}
              onKeyPress={handleKeyPress}
              disabled={loading}
            />
          </div>
          
          <button 
            className={`admin-login-btn ${loading ? 'loading' : ''}`}
            onClick={handleLogin} 
            disabled={loading}
          >
            {loading ? "Logging in..." : "Login"}
          </button>
        </div>
      </div>
    </div>
  );
}