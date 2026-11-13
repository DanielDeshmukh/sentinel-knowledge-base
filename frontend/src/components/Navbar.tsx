import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

interface NavbarProps {
  mobileMenuOpen: boolean;
  onCloseMobileMenu: () => void;
}

const Navbar: React.FC<NavbarProps> = ({ mobileMenuOpen, onCloseMobileMenu }) => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const handleLogout = () => {
    logout();
    navigate('/login', { replace: true });
    onCloseMobileMenu();
  };

  if (!user) return null;

  const navItems = [
    { path: '/chat', label: 'Ask Sentinel', number: '01' },
    { path: '/documents', label: 'Knowledge base', number: '02' },
  ];

  const adminItems = user.role === 'admin' ? [
    { path: '/admin', label: 'Ingestion', number: '03' },
  ] : [];

  return (
    <>
      {mobileMenuOpen && (
        <button
          className="mobile-overlay"
          aria-label="Close navigation"
          onClick={onCloseMobileMenu}
        />
      )}
      <aside className={`sidebar ${mobileMenuOpen ? 'sidebar-open' : ''}`}>
        <div className="sidebar-top">
          <div className="brand">
            <div className="brand-mark" aria-hidden="true">
              <img src="/pwa-192x192.png" alt="" width="34" height="34" />
            </div>
            <div className="brand-words">
              <strong>SENTINEL</strong>
              <small>KNOWLEDGE SYSTEMS</small>
            </div>
          </div>
          <button className="mobile-close icon-button" onClick={onCloseMobileMenu} aria-label="Close menu">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M18 6L6 18M6 6l12 12"/></svg>
          </button>
        </div>

        <div className="nav-label">
          <span>WORKSPACE</span>
          <span>01 — {adminItems.length > 0 ? '03' : '02'}</span>
        </div>
        <nav className="nav-list" aria-label="Workspace navigation">
          {navItems.map((item) => (
            <button
              key={item.path}
              className={`nav-item ${location.pathname === item.path ? 'active' : ''}`}
              onClick={() => { navigate(item.path); onCloseMobileMenu(); }}
            >
              {item.label === 'Ask Sentinel' && (
                <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6"><path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/></svg>
              )}
              {item.label === 'Knowledge base' && (
                <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg>
              )}
              <span>{item.label}</span>
              <small>{item.number}</small>
            </button>
          ))}
          {adminItems.map((item) => (
            <button
              key={item.path}
              className={`nav-item ${location.pathname === item.path ? 'active' : ''}`}
              onClick={() => { navigate(item.path); onCloseMobileMenu(); }}
            >
              <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
              <span>{item.label}</span>
              <small>{item.number}</small>
            </button>
          ))}
        </nav>

        {user.role === 'admin' && (
          <>
            <div className="nav-label" style={{ marginTop: '30px' }}>
              <span>MANAGE</span>
              <span>04</span>
            </div>
            <nav className="nav-list" aria-label="Management navigation">
              <button
                className={`nav-item ${location.pathname === '/admin/access' ? 'active' : ''}`}
                onClick={() => { navigate('/admin/access'); onCloseMobileMenu(); }}
              >
                <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6"><path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 00-3-3.87"/><path d="M16 3.13a4 4 0 010 7.75"/></svg>
                <span>Access control</span>
                <small>04</small>
              </button>
            </nav>
          </>
        )}

        <div className="sidebar-spacer" />

        <div className="security-note">
          <div className="security-note-top">
            <div className="security-icon">
              <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="M9 12l2 2 4-4"/></svg>
            </div>
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="7" y1="17" x2="17" y2="7"/><polyline points="7 7 17 7 17 17"/></svg>
          </div>
          <strong>Knowledge stays<br/>in the right hands.</strong>
          <p>Permission-aware by design, from query to answer.</p>
          <div className="security-line">
            <span /> ACCESS ENFORCED AT RETRIEVAL
          </div>
        </div>

        <button className="sidebar-logout" type="button" onClick={handleLogout} aria-label="Log out of Sentinel">
          <span>Log out</span>
          <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M10 17l5-5-5-5" />
            <path d="M15 12H3" />
            <path d="M12 3h7a2 2 0 012 2v14a2 2 0 01-2 2h-7" />
          </svg>
        </button>

        <div className="sidebar-bottom">
          <span>© SENTINEL 2026</span>
          <span>V 1.0</span>
        </div>
      </aside>
    </>
  );
};

export default Navbar;
