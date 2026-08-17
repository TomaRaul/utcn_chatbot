import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import './App.css';
import Login from './Login';
import AdminPanel from './AdminPanel';

const API = 'http://localhost:8080/api/chat';

const authHeader = () => ({
  headers: { Authorization: `Bearer ${localStorage.getItem('token')}` }
});

const GREETING = 'Salut! Sunt asistentul virtual al facultatii. Cu ce te pot ajuta?';

function App() {
  const [user, setUser] = useState(localStorage.getItem('username'));
  const [role, setRole] = useState(localStorage.getItem('role') || 'USER');
  const [theme, setTheme] = useState(localStorage.getItem('theme') || 'light');
  const [conversations, setConversations] = useState([]);
  const [activeConversationId, setActiveConversationId] = useState(null);
  const [messages, setMessages] = useState([
    { sender: 'bot', text: GREETING, messageId: null, animated: false }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [adminOpen, setAdminOpen] = useState(false);
  const [feedbackState, setFeedbackState] = useState({});
  const [correctionDraft, setCorrectionDraft] = useState({});
  const [typingText, setTypingText] = useState({});
  const [menuOpenId, setMenuOpenId] = useState(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState(null);
  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);
  const menuRef = useRef(null);
  const abortRef = useRef(null);
  const typingEpochRef = useRef(0);

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
  }, [theme]);

  useEffect(() => {
    if (user) loadConversations();
  }, [user]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, typingText]);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 140) + 'px';
    }
  }, [input]);

  useEffect(() => {
    if (menuOpenId === null) return;
    const onClick = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setMenuOpenId(null);
      }
    };
    document.addEventListener('mousedown', onClick);
    return () => document.removeEventListener('mousedown', onClick);
  }, [menuOpenId]);

  if (!user) {
    return <Login onLogin={(username) => {
      setUser(username);
      setRole(localStorage.getItem('role') || 'USER');
    }} />;
  }

  const cancelPendingRequest = () => {
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
    typingEpochRef.current++;
  };

  const handleLogout = () => {
    cancelPendingRequest();
    localStorage.removeItem('token');
    localStorage.removeItem('username');
    localStorage.removeItem('role');
    setUser(null);
  };

  const loadConversations = async () => {
    try {
      const res = await axios.get(`${API}/conversations`, authHeader());
      setConversations(Array.isArray(res.data) ? res.data : []);
    } catch (e) {
      setConversations([]);
    }
  };

  const loadConversation = async (id) => {
    cancelPendingRequest();
    try {
      const res = await axios.get(`${API}/conversations/${id}/messages`, authHeader());
      const msgs = res.data.map(m => ({
        sender: m.role === 'user' ? 'user' : 'bot',
        text: m.content,
        messageId: m.id,
        animated: false
      }));
      setMessages(msgs);
      setActiveConversationId(id);
      setFeedbackState({});
      setCorrectionDraft({});
      setTypingText({});
    } catch (e) {}
  };

  const togglePin = async (id, currentlyPinned) => {
    setMenuOpenId(null);
    try {
      await axios.patch(`${API}/conversations/${id}/pin`, { pinned: !currentlyPinned }, authHeader());
      loadConversations();
    } catch (e) {}
  };

  const deleteConversation = async (id) => {
    setConfirmDeleteId(null);
    setMenuOpenId(null);
    try {
      await axios.delete(`${API}/conversations/${id}`, authHeader());
      if (id === activeConversationId) {
        startNewConversation();
      }
      loadConversations();
    } catch (e) {}
  };

  const startNewConversation = () => {
    cancelPendingRequest();
    setActiveConversationId(null);
    setMessages([
      { sender: 'bot', text: GREETING, messageId: null, animated: false }
    ]);
    setFeedbackState({});
    setCorrectionDraft({});
    setTypingText({});
  };

  const animateTypewriter = (index, fullText) => {
    const speed = Math.max(8, Math.min(20, 600 / Math.max(fullText.length, 1)));
    const epoch = typingEpochRef.current;
    let i = 0;
    const tick = () => {
      if (typingEpochRef.current !== epoch) return;
      i = Math.min(i + 2, fullText.length);
      setTypingText(prev => ({ ...prev, [index]: fullText.slice(0, i) }));
      if (i < fullText.length) {
        setTimeout(tick, speed);
      } else {
        setTypingText(prev => {
          const { [index]: _, ...rest } = prev;
          return rest;
        });
        setMessages(prev => prev.map((m, idx) => idx === index ? { ...m, animated: true } : m));
      }
    };
    tick();
  };

  const sendMessage = async () => {
    if (!input.trim() || loading) return;

    const userText = input;
    setMessages(prev => [...prev, { sender: 'user', text: userText, messageId: null, animated: true }]);
    setInput('');
    setLoading(true);

    const controller = new AbortController();
    abortRef.current = controller;
    const epochAtSend = typingEpochRef.current;

    try {
      const res = await axios.post(API, {
        message: userText,
        conversationId: activeConversationId
      }, { ...authHeader(), signal: controller.signal });
      if (typingEpochRef.current !== epochAtSend) return;
      const botText = res.data.message;
      setMessages(prev => {
        const next = [...prev, { sender: 'bot', text: botText, messageId: res.data.messageId, animated: false }];
        const newIndex = next.length - 1;
        setTimeout(() => {
          if (typingEpochRef.current === epochAtSend) animateTypewriter(newIndex, botText);
        }, 80);
        return next;
      });
      setActiveConversationId(res.data.conversationId);
      loadConversations();
    } catch (e) {
      if (axios.isCancel(e)) return;
      let errorText;
      if (e.response) {
        const status = e.response.status;
        const serverMsg = e.response.data?.error || e.response.data?.message;
        if (status === 401 || status === 403) {
          errorText = 'Sesiunea ta a expirat. Te rugam sa te autentifici din nou.';
          handleLogout();
        } else if (status >= 500) {
          errorText = `Eroare de server (${status})${serverMsg ? `: ${serverMsg}` : '. Verifica daca Ollama si baza de date ruleaza.'}`;
        } else {
          errorText = serverMsg ? `Eroare (${status}): ${serverMsg}` : `Eroare (${status}).`;
        }
      } else if (e.request) {
        errorText = 'Nu s-a putut contacta serverul. Verifica daca backend-ul ruleaza pe portul 8080.';
      } else {
        errorText = `Eroare neasteptata: ${e.message}`;
      }
      setMessages(prev => [...prev, { sender: 'bot', text: errorText, messageId: null, animated: true }]);
    } finally {
      setLoading(false);
      if (abortRef.current === controller) {
        abortRef.current = null;
      }
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const submitFeedback = async (messageId, rating, correction = null) => {
    if (!messageId) return;
    setFeedbackState(s => ({ ...s, [messageId]: 'submitting' }));
    try {
      await axios.post(`${API}/feedback`, { messageId, rating, correction }, authHeader());
      setFeedbackState(s => ({ ...s, [messageId]: rating }));
      if (correction !== null) {
        setCorrectionDraft(d => {
          const { [messageId]: _, ...rest } = d;
          return rest;
        });
      }
    } catch (e) {
      setFeedbackState(s => ({ ...s, [messageId]: undefined }));
    }
  };

  const formatDate = (dateStr) => {
    const d = new Date(dateStr);
    return d.toLocaleDateString('ro-RO', { day: '2-digit', month: 'short' });
  };

  const initialsOf = (name) => (name || '?').trim().slice(0, 2).toUpperCase();

  return (
    <div className="app">
      <aside className="sidebar" style={{ width: sidebarOpen ? '270px' : '0' }}>
        <div className="sidebar-brand">
          <div className="brand-mark">UT</div>
          <div className="brand-text">
            <span className="brand-title">Asistent UTCN</span>
            <span className="brand-sub">Facultate</span>
          </div>
        </div>
        <div className="sidebar-header">
          <button className="new-chat-btn" onClick={startNewConversation}>
            <span className="plus">+</span> Conversatie noua
          </button>
        </div>
        <div className="conversations-list">
          {(() => {
            const pinned = conversations.filter(c => c.pinned);
            const rest = conversations.filter(c => !c.pinned);
            const renderItem = (conv) => (
              <div
                key={conv.id}
                className={`conversation-item ${conv.id === activeConversationId ? 'active' : ''} ${conv.pinned ? 'is-pinned' : ''}`}
                onClick={() => loadConversation(conv.id)}
              >
                <div className="conv-main">
                  <div className="conv-title">
                    {conv.pinned && <span className="pin-icon" title="Fixata">&#9670;</span>}
                    {conv.title || 'Conversatie noua'}
                  </div>
                  <div className="conv-date">{formatDate(conv.createdAt)}</div>
                </div>
                <button
                  className="conv-menu-btn"
                  title="Optiuni"
                  onClick={(e) => {
                    e.stopPropagation();
                    setMenuOpenId(menuOpenId === conv.id ? null : conv.id);
                  }}
                >
                  ...
                </button>
                {menuOpenId === conv.id && (
                  <div className="conv-menu" ref={menuRef} onClick={(e) => e.stopPropagation()}>
                    <button
                      className="conv-menu-item"
                      onClick={() => togglePin(conv.id, conv.pinned)}
                    >
                      {conv.pinned ? 'Anuleaza fixarea' : 'Fixeaza'}
                    </button>
                    <button
                      className="conv-menu-item danger"
                      onClick={() => setConfirmDeleteId(conv.id)}
                    >
                      Sterge
                    </button>
                  </div>
                )}
              </div>
            );
            return (
              <>
                {pinned.length > 0 && (
                  <>
                    <div className="conv-section-label">Fixate</div>
                    {pinned.map(renderItem)}
                  </>
                )}
                {rest.length > 0 && (
                  <>
                    <div className="conv-section-label">Istoric</div>
                    {rest.map(renderItem)}
                  </>
                )}
              </>
            );
          })()}
        </div>
        <div className="sidebar-footer">v1.0 · Lucrare de licenta 2026</div>
      </aside>

      <div className="main">
        <header className="header">
          <button className="toggle-sidebar" onClick={() => setSidebarOpen(o => !o)} title="Afiseaza/ascunde meniul">
            Meniu
          </button>
          <div className="header-title">
            <h1>Chatbot Facultate</h1>
            <p>Universitatea Tehnica din Cluj-Napoca</p>
          </div>
          <div className="header-user">
            <button
              className="icon-btn"
              onClick={() => setTheme(t => t === 'dark' ? 'light' : 'dark')}
              title={theme === 'dark' ? 'Mod luminos' : 'Mod intunecat'}
            >
              {theme === 'dark' ? 'Luminos' : 'Intunecat'}
            </button>
            <div className="user-chip">
              <div className="avatar">{initialsOf(user)}</div>
              <span>{user}</span>
            </div>
            {role === 'ADMIN' && (
              <button className="admin-btn" onClick={() => setAdminOpen(true)}>Panou admin</button>
            )}
            <button className="logout-btn" onClick={handleLogout}>Deconectare</button>
          </div>
        </header>

        <div className="chat-container">
          <div className="messages">
            {messages.map((msg, index) => {
              const fb = msg.messageId ? feedbackState[msg.messageId] : null;
              const isTyping = typingText[index] !== undefined;
              const displayText = isTyping ? typingText[index] : msg.text;
              const showFeedback = msg.sender === 'bot' && msg.messageId && !isTyping;
              return (
                <div key={index} className={`message ${msg.sender}`}>
                  <div className="msg-avatar">
                    {msg.sender === 'bot' ? 'UT' : initialsOf(user)}
                  </div>
                  <div className="bubble-wrap">
                    <div className="bubble">
                      {msg.sender === 'bot' ? (
                        <div className="md">
                          <ReactMarkdown remarkPlugins={[remarkGfm]}>
                            {displayText}
                          </ReactMarkdown>
                          {isTyping && <span className="typing-caret" />}
                        </div>
                      ) : (
                        <div style={{ whiteSpace: 'pre-wrap' }}>{displayText}</div>
                      )}
                      {showFeedback && (
                        <div className="feedback-row">
                          <button
                            className={`fb-btn ${fb === 'up' ? 'sent' : ''}`}
                            disabled={!!fb && fb !== undefined}
                            title="Raspuns util"
                            onClick={() => submitFeedback(msg.messageId, 'up')}
                          >Util</button>
                          <button
                            className={`fb-btn ${fb === 'down' ? 'sent' : ''}`}
                            disabled={fb === 'up' || fb === 'submitting'}
                            title="Raspuns gresit"
                            onClick={() => {
                              setCorrectionDraft(d => ({ ...d, [msg.messageId]: d[msg.messageId] ?? '' }));
                            }}
                          >Gresit</button>
                          {fb === 'up' && <span className="fb-thanks">Multumim!</span>}
                        </div>
                      )}
                      {showFeedback && correctionDraft[msg.messageId] !== undefined && fb !== 'down' && (
                        <div className="correction-box">
                          <textarea
                            value={correctionDraft[msg.messageId]}
                            onChange={(e) => setCorrectionDraft(d => ({ ...d, [msg.messageId]: e.target.value }))}
                            placeholder="Care era raspunsul corect? (optional, dar util)"
                            rows={2}
                          />
                          <div className="correction-actions">
                            <button
                              className="link-btn"
                              onClick={() => setCorrectionDraft(d => {
                                const { [msg.messageId]: _, ...rest } = d;
                                return rest;
                              })}
                            >Anuleaza</button>
                            <button
                              className="submit-correction-btn"
                              onClick={() => submitFeedback(msg.messageId, 'down', correctionDraft[msg.messageId] || null)}
                            >Trimite</button>
                          </div>
                        </div>
                      )}
                      {fb === 'down' && (
                        <div className="fb-thanks">Multumim, o vom analiza.</div>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
            {loading && (
              <div className="message bot">
                <div className="msg-avatar">UT</div>
                <div className="bubble-wrap">
                  <div className="bubble typing">
                    <span></span><span></span><span></span>
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          <div className="input-wrap">
            <div className="input-area">
              <textarea
                ref={textareaRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Scrie un mesaj... (Shift+Enter pentru rand nou)"
                rows={1}
                disabled={loading}
              />
              <button className="send-btn" onClick={sendMessage} disabled={loading || !input.trim()}>
                Trimite
              </button>
            </div>
            <div className="input-hint">Apasa Enter pentru a trimite · Shift+Enter pentru rand nou</div>
          </div>
        </div>
      </div>

      {adminOpen && <AdminPanel onClose={() => setAdminOpen(false)} />}

      {confirmDeleteId !== null && (
        <div className="modal-overlay" onClick={() => setConfirmDeleteId(null)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <h3>Stergi conversatia?</h3>
            <p>Aceasta actiune este permanenta. Toate mesajele vor fi sterse.</p>
            <div className="modal-actions">
              <button className="modal-cancel" onClick={() => setConfirmDeleteId(null)}>Anuleaza</button>
              <button className="modal-confirm" onClick={() => deleteConversation(confirmDeleteId)}>Sterge</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
