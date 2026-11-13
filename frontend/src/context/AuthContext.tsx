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
    try {
      const userData = await getMe();
      setUser(userData);
      return userData;
    } catch {
      localStorage.removeItem('token');
      setUser(null);
      return null;
    } finally {
      setLoading(false);
    }
  };

  const login = async (email: string, password: string) => {
    const { login: apiLogin } = await import('../services/api');
    await apiLogin(email, password);
    if (!(await loadUser())) {
      throw new Error('Login succeeded, but your user session could not be loaded. Please try again.');
    }
  };

  const register = async (displayName: string, email: string, password: string, requestedRole: 'public' | 'internal' | 'restricted') => {
    const { register: apiRegister } = await import('../services/api');
    await apiRegister(displayName, email, password, requestedRole);
    if (!(await loadUser())) {
      throw new Error('Your account was created, but the user session could not be loaded. Please sign in.');
    }
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
