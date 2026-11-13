import { createContext, useContext, useState, useEffect } from 'react';
import type { ReactNode } from 'react';
import type { User } from '../types';
import { getMe, logout as apiLogout } from '../services/api';

interface AuthContextType {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (displayName: string, email: string, password: string, requestedRole: 'public' | 'internal' | 'restricted') => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider = ({ children }: { children: ReactNode }) => {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem('token');
    if (token) {
      loadUser();
    } else {
      setLoading(false);
    }
  }, []);

  const loadUser = async (): Promise<User | null> => {
    const tokenAtRequestStart = localStorage.getItem('token');
    try {
      const userData = await getMe();
      // A sign-in can replace an expired token while this restore request is in
      // flight. Ignore the old response so it cannot overwrite the new session.
      if (localStorage.getItem('token') !== tokenAtRequestStart) return null;
      setUser(userData);
      return userData;
    } catch {
      if (localStorage.getItem('token') === tokenAtRequestStart) {
        localStorage.removeItem('token');
        setUser(null);
      }
      return null;
    } finally {
      if (localStorage.getItem('token') === tokenAtRequestStart) setLoading(false);
    }
  };

  const login = async (email: string, password: string) => {
    const { login: apiLogin } = await import('../services/api');
    const response = await apiLogin(email, password);
    setUser(response.user);
    setLoading(false);
  };

  const register = async (displayName: string, email: string, password: string, requestedRole: 'public' | 'internal' | 'restricted') => {
    const { register: apiRegister } = await import('../services/api');
    const response = await apiRegister(displayName, email, password, requestedRole);
    setUser(response.user);
    setLoading(false);
  };

  const logout = () => {
    apiLogout();
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
