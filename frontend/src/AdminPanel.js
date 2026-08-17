import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './AdminPanel.css';

const ADMIN_API = 'http://localhost:8080/api/admin';

const authHeader = () => ({
  headers: { Authorization: `Bearer ${localStorage.getItem('token')}` }
});

function AdminPanel({ onClose }) {
  const [pending, setPending] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [edits, setEdits] = useState({});

  useEffect(() => {
    load();
  }, []);

  const load = async () => {
    setLoading(true);
    setError('');
    try {
      const res = await axios.get(`${ADMIN_API}/pending`, authHeader());
      setPending(Array.isArray(res.data) ? res.data : []);
    } catch (e) {
      setError(e.response?.data?.error || 'Nu s-au putut incarca intrarile.');
    } finally {
      setLoading(false);
    }
  };

  const approve = async (id) => {
    const edit = edits[id] || {};
    try {
      await axios.post(`${ADMIN_API}/pending/${id}/approve`, edit, authHeader());
      setPending(p => p.filter(e => e.id !== id));
    } catch (e) {
      setError(e.response?.data?.error || 'Aprobarea a esuat.');
    }
  };

  const reject = async (id) => {
    try {
      await axios.post(`${ADMIN_API}/pending/${id}/reject`, {}, authHeader());
      setPending(p => p.filter(e => e.id !== id));
    } catch (e) {
      setError(e.response?.data?.error || 'Respingerea a esuat.');
    }
  };

  const updateEdit = (id, field, value) => {
    setEdits(prev => ({
      ...prev,
      [id]: { ...prev[id], [field]: value }
    }));
  };

  return (
    <div className="admin-overlay" onClick={onClose}>
      <div className="admin-modal" onClick={(e) => e.stopPropagation()}>
        <div className="admin-header">
          <h2>Coada de corecturi de la utilizatori</h2>
          <button className="admin-close" onClick={onClose}>×</button>
        </div>
        {error && <div className="admin-error">{error}</div>}
        {loading ? (
          <div className="admin-loading">Se incarca...</div>
        ) : pending.length === 0 ? (
          <div className="admin-empty">Nicio corectura in asteptare.</div>
        ) : (
          <div className="admin-list">
            {pending.map(e => (
              <div key={e.id} className="admin-item">
                <div className="admin-meta">
                  <span>#{e.id}</span>
                  <span>{new Date(e.createdAt).toLocaleString('ro-RO')}</span>
                </div>
                <label>Intrebarea utilizatorului</label>
                <textarea
                  rows={2}
                  defaultValue={e.question}
                  onChange={(ev) => updateEdit(e.id, 'question', ev.target.value)}
                />
                <label>Raspunsul corect</label>
                <textarea
                  rows={4}
                  defaultValue={e.answer}
                  onChange={(ev) => updateEdit(e.id, 'answer', ev.target.value)}
                />
                <div className="admin-actions">
                  <button className="reject-btn" onClick={() => reject(e.id)}>Respinge</button>
                  <button className="approve-btn" onClick={() => approve(e.id)}>Aproba</button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default AdminPanel;
