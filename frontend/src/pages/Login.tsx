import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import toast from 'react-hot-toast';
import { FiEye, FiEyeOff } from 'react-icons/fi';
import { useSearchParams } from 'react-router-dom';
import RoleDropdown, { type AssignableRole } from '../components/RoleDropdown';

const Login: React.FC = () => {
  const { login, register } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const [isRegister, setIsRegister] = useState(searchParams.get('mode') === 'register');
  const [displayName, setDisplayName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [requestedRole, setRequestedRole] = useState<AssignableRole>('public');
  const [passwordVisible, setPasswordVisible] = useState(false);
  const [loading, setLoading] = useState(false);

  const toggleAuthMode = () => {
    const nextMode = !isRegister;
    setIsRegister(nextMode);
    setSearchParams(nextMode ? { mode: 'register' } : {}, { replace: true });
    setPasswordVisible(false);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);

    try {
      if (isRegister) {
        await register(displayName, email, password, requestedRole);
        toast.success('Account created with public access. Your role request is queued for admin review.');
        setIsRegister(false);
        setSearchParams({}, { replace: true });
      } else {
        await login(email, password);
        toast.success('Login successful!');
      }
    } catch (error: any) {
      toast.error(error.response?.data?.detail || error.message || 'Authentication failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-shell">
      <div className="auth-panel">
        <div className="auth-brand">
          <div className="auth-brand-mark">
            <img src="/pwa-192x192.png" alt="" aria-hidden="true" width="38" height="38" />
          </div>
          <div className="auth-brand-copy">
            <strong>SENTINEL</strong>
            <small>KNOWLEDGE SYSTEMS</small>
          </div>
        </div>
        <div className="auth-heading">
          <h1>{isRegister ? 'Create your account' : 'Welcome back'}</h1>
          <p>{isRegister ? 'Start with public access. An admin reviews higher access requests.' : 'Sign in to your secure knowledge workspace.'}</p>
        </div>

        <form className="auth-form" onSubmit={handleSubmit}>
          {isRegister && (
            <div className="auth-field">
              <label htmlFor="auth-name">Full name</label>
              <input
                id="auth-name"
                type="text"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                placeholder="Your name"
                autoComplete="name"
                required
              />
            </div>
          )}

          {isRegister && <div className="auth-field"><RoleDropdown value={requestedRole} onChange={setRequestedRole} /></div>}

          <div className="auth-field">
            <label htmlFor="auth-email">Email</label>
            <input
              id="auth-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              required
            />
          </div>

          <div className="auth-field">
            <label htmlFor="auth-password">Password</label>
            <div className="auth-password-wrap">
              <input
                id="auth-password"
                type={passwordVisible ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter your password"
                autoComplete={isRegister ? 'new-password' : 'current-password'}
                required
                minLength={6}
              />
              <button
                type="button"
                className="auth-password-toggle"
                aria-label={passwordVisible ? 'Hide password' : 'Show password'}
                aria-pressed={passwordVisible}
                onClick={() => setPasswordVisible((visible) => !visible)}
              >
                {passwordVisible ? <FiEyeOff aria-hidden="true" /> : <FiEye aria-hidden="true" />}
              </button>
            </div>
          </div>

          <button type="submit" className="btn-primary auth-submit" disabled={loading}>
            {loading ? 'PROCESSING...' : isRegister ? 'CREATE ACCOUNT' : 'SIGN IN'}
          </button>
        </form>

        <p className="auth-switch-copy">
          {isRegister ? 'Already have an account?' : "Don't have an account?"}{' '}
          <button
            type="button"
            className="auth-switch"
            onClick={toggleAuthMode}
          >
            {isRegister ? 'Sign in' : 'Register'}
          </button>
        </p>
      </div>
    </div>
  );
};

export default Login;
