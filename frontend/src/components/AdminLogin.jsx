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
    } catch {
      setError("Invalid username or password.");
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === "Enter" && !loading) handleLogin();
  };

  return (
    <div className="auth-wrapper">
      <div className="auth-card">
        <h1 className="auth-title">Admin Access</h1>
        <p className="auth-subtitle">
          Secure access to DRISHTI control panel
        </p>

        {error && <div className="auth-error">{error}</div>}

        <div className="auth-field">
          <label>Username</label>
          <input
            placeholder="Enter username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            onKeyDown={handleKeyPress}
            disabled={loading}
          />
        </div>

        <div className="auth-field">
          <label>Password</label>
          <input
            type="password"
            placeholder="Enter password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            onKeyDown={handleKeyPress}
            disabled={loading}
          />
        </div>

        <button
          className={`auth-btn ${loading ? "loading" : ""}`}
          onClick={handleLogin}
          disabled={loading}
        >
          {loading ? "Authenticating…" : "Sign in"}
        </button>
      </div>
    </div>
  );
}
