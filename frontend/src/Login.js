import React, { useState } from 'react';
import axios from 'axios';
import './Login.css';

const AUTH_URL = 'http://localhost:8081/auth';

function Login({ onLogin }) {
  const [mode, setMode] = useState('login');
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [code, setCode] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [info, setInfo] = useState('');
  const [loading, setLoading] = useState(false);

  const switchMode = (m) => {
    setMode(m);
    setError('');
    setInfo('');
    setCode('');
  };

  const handleLogin = async () => {
    try {
      const res = await axios.post(`${AUTH_URL}/login`, { username, password });
      localStorage.setItem('token', res.data.token);
      localStorage.setItem('username', res.data.username);
      localStorage.setItem('role', res.data.role || 'USER');
      onLogin(res.data.username);
    } catch (err) {
      const data = err.response?.data;
      if (data?.requiresVerification) {
        setUsername(data.username || username);
        setMode('verify');
        setInfo('Contul nu este verificat. Am retrimis codul pe email.');
        try { await axios.post(`${AUTH_URL}/resend`, { username: data.username || username }); } catch (_) {}
      } else {
        setError(data?.error || 'A aparut o eroare. Incearca din nou.');
      }
    }
  };

  const handleRegister = async () => {
    try {
      await axios.post(`${AUTH_URL}/register`, { username, email, password });
      setMode('verify');
      setInfo(`Codul a fost trimis la ${email}. Verifica-ti inbox-ul.`);
    } catch (err) {
      setError(err.response?.data?.error || 'A aparut o eroare. Incearca din nou.');
    }
  };

  const handleVerify = async () => {
    try {
      const res = await axios.post(`${AUTH_URL}/verify`, { username, code });
      localStorage.setItem('token', res.data.token);
      localStorage.setItem('username', res.data.username);
      localStorage.setItem('role', res.data.role || 'USER');
      onLogin(res.data.username);
    } catch (err) {
      setError(err.response?.data?.error || 'Cod invalid.');
    }
  };

  const handleResend = async () => {
    setError('');
    setInfo('');
    try {
      await axios.post(`${AUTH_URL}/resend`, { username });
      setInfo('Un cod nou a fost trimis pe email.');
    } catch (err) {
      setError(err.response?.data?.error || 'Nu s-a putut retrimite codul.');
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setInfo('');
    setLoading(true);
    try {
      if (mode === 'login') await handleLogin();
      else if (mode === 'register') await handleRegister();
      else if (mode === 'verify') await handleVerify();
    } finally {
      setLoading(false);
    }
  };

  const eyeIcon = showPassword ? (
    <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"/>
      <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"/>
      <line x1="1" y1="1" x2="23" y2="23"/>
    </svg>
  ) : (
    <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
      <circle cx="12" cy="12" r="3"/>
    </svg>
  );

  return (
    <div className="login-page">
      <div className="login-shell">
        <aside className="login-showcase">
          <div className="showcase-bg" aria-hidden="true">
            <div className="orb orb-gold" />
            <div className="orb orb-blue" />
            <div className="grid-overlay" />
          </div>
          <div className="showcase-content">
            <div className="showcase-brand">
              <div className="showcase-logo">UT</div>
              <div className="showcase-brand-text">
                <span className="showcase-brand-title">Asistent UTCN</span>
                <span className="showcase-brand-sub">Universitatea Tehnica din Cluj-Napoca</span>
              </div>
            </div>

            <div className="showcase-hero">
              <h2>Asistentul tau academic.</h2>
              <p>Raspunsuri rapide despre UTCN — admitere, orare, regulamente.</p>
            </div>

            <ul className="showcase-features">
              <li>
                <div>
                  <strong>Surse verificate</strong>
                  <span>Direct din documentele oficiale ale facultatii</span>
                </div>
              </li>
              <li>
                <div>
                  <strong>Mereu disponibil</strong>
                  <span>Intreaba orice, oricand</span>
                </div>
              </li>
              <li>
                <div>
                  <strong>Acces securizat</strong>
                  <span>Conturi verificate prin email</span>
                </div>
              </li>
            </ul>

            <div className="showcase-footer">
              © {new Date().getFullYear()} · UTCN · Lucrare de licenta
            </div>
          </div>
        </aside>

        <div className="login-card">
        <div className="login-header">
          <div className="login-logo">UT</div>
          <h1>Chatbot Facultate</h1>
          <p>Universitatea Tehnica din Cluj-Napoca</p>
        </div>

        {mode !== 'verify' && (
          <div className="login-tabs">
            <button
              className={mode === 'login' ? 'active' : ''}
              onClick={() => switchMode('login')}
            >
              Autentificare
            </button>
            <button
              className={mode === 'register' ? 'active' : ''}
              onClick={() => switchMode('register')}
            >
              Inregistrare
            </button>
          </div>
        )}

        <form onSubmit={handleSubmit} className="login-form">
          {mode === 'verify' ? (
            <>
              <div className="verify-info">
                Am trimis un cod de 6 cifre pe email.
                <br />Introdu-l mai jos pentru a-ti activa contul.
              </div>
              <div className="form-group">
                <label>Cod de verificare</label>
                <input
                  type="text"
                  value={code}
                  onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                  placeholder="123456"
                  className="code-input"
                  inputMode="numeric"
                  maxLength={6}
                  required
                  disabled={loading}
                />
              </div>
            </>
          ) : (
            <>
              <div className="form-group">
                <label>Nume utilizator</label>
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="Introdu numele de utilizator"
                  required
                  disabled={loading}
                />
              </div>

              {mode === 'register' && (
                <div className="form-group">
                  <label>Email</label>
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="exemplu@gmail.com"
                    required
                    disabled={loading}
                  />
                </div>
              )}

              <div className="form-group">
                <label>Parola</label>
                <div className="password-wrapper">
                  <input
                    type={showPassword ? 'text' : 'password'}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Introdu parola"
                    required
                    disabled={loading}
                  />
                  <button
                    type="button"
                    className="eye-btn"
                    onClick={() => setShowPassword(v => !v)}
                    tabIndex={-1}
                  >
                    {eyeIcon}
                  </button>
                </div>
              </div>
            </>
          )}

          {info && <div className="info-msg">{info}</div>}
          {error && <div className="error-msg">{error}</div>}

          <button type="submit" className="submit-btn" disabled={loading}>
            {loading
              ? 'Se proceseaza...'
              : mode === 'login'
                ? 'Autentificare'
                : mode === 'register'
                  ? 'Inregistrare'
                  : 'Verifica codul'}
          </button>

          {mode === 'verify' && (
            <div className="verify-actions">
              <button type="button" className="link-btn" onClick={handleResend} disabled={loading}>
                Retrimite codul
              </button>
              <button type="button" className="link-btn" onClick={() => switchMode('login')} disabled={loading}>
                Inapoi la autentificare
              </button>
            </div>
          )}
        </form>
        </div>
      </div>
    </div>
  );
}

export default Login;
