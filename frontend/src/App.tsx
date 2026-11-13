import React, { useState } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import { AuthProvider, useAuth } from './context/AuthContext';
import Login from './pages/Login';
import Chat from './pages/Chat';
import Documents from './pages/Documents';
import Admin from './pages/Admin';
import AccessControl from './pages/AccessControl';
import Navbar from './components/Navbar';
import Landing from './pages/Landing';
import PageSkeleton, { type SkeletonPage } from './components/PageSkeleton';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 5 * 60 * 1000,
    },
  },
});

function ProtectedRoute({ children, page }: { children: React.ReactNode; page: SkeletonPage }) {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return <PageSkeleton page={page} />;
  }

  if (!user) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  return <>{children}</>;
}

function AdminRoute({ children, page }: { children: React.ReactNode; page: SkeletonPage }) {
  const { user, loading } = useAuth();

  if (loading) {
    return <PageSkeleton page={page} />;
  }

  if (!user || user.role !== 'admin') {
    return <Navigate to="/chat" replace />;
  }

  return <>{children}</>;
}

function LoginRoute() {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return <PageSkeleton page="login" />;
  }

  if (!user) {
    return <Login />;
  }

  const from = (
    location.state as {
      from?: { pathname?: string; search?: string; hash?: string };
    } | null
  )?.from;
  const destination = from?.pathname?.startsWith('/') && !from.pathname.startsWith('//')
    ? `${from.pathname}${from.search ?? ''}${from.hash ?? ''}`
    : '/chat';

  return <Navigate to={destination === '/login' ? '/chat' : destination} replace />;
}

function HomeRoute() {
  const { user, loading } = useAuth();

  if (loading) {
    return <PageSkeleton page="landing" />;
  }

  return user ? <Navigate to="/chat" replace /> : <Landing />;
}

function PageHeader({ onOpenNavigation }: { onOpenNavigation: () => void }) {
  const location = useLocation();
  const { user, loading } = useAuth();

  const pageMap: Record<string, string> = {
    '/chat': 'ASK SENTINEL',
    '/documents': 'KNOWLEDGE BASE',
    '/admin': 'INGESTION',
    '/admin/access': 'ACCESS CONTROL',
  };

  const pageTitle = pageMap[location.pathname] || 'WORKSPACE';

  return (
    <header className="topbar">
      <div className="topbar-left">
        <button className="mobile-menu-button icon-button" onClick={onOpenNavigation} aria-label="Open navigation">
          <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="18" x2="21" y2="18"/></svg>
        </button>
        <span className="topbar-root">WORKSPACE</span>
        <span className="slash">/</span>
        <span>{pageTitle}</span>
      </div>
      <div className="topbar-right">
        {loading ? (
          <span className="topbar-status skeleton-topbar-status" aria-hidden="true"><i className="skeleton-shape" /><span className="skeleton-shape" /></span>
        ) : (
          <span className="topbar-status"><i /> WORKSPACE ONLINE</span>
        )}
        <span className="topbar-divider" />
        {loading ? (
          <span className="topbar-account skeleton-topbar-account" aria-hidden="true"><span className="skeleton-shape" /><span className="skeleton-shape" /></span>
        ) : (
          <span className="topbar-account">
            <span className="tiny-avatar">{user?.email?.[0]?.toUpperCase() || 'S'}</span>
            <span>{user?.role?.toUpperCase() || 'SIGN IN'}</span>
          </span>
        )}
      </div>
    </header>
  );
}

function AppLayout({ children }: { children: React.ReactNode }) {
  const location = useLocation();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const hasWorkspaceChrome = location.pathname !== '/' && location.pathname !== '/login';

  return (
    <div className="app-shell">
      {hasWorkspaceChrome && (
        <Navbar
          mobileMenuOpen={mobileMenuOpen}
          onCloseMobileMenu={() => setMobileMenuOpen(false)}
        />
      )}
      {hasWorkspaceChrome && (
        <PageHeader onOpenNavigation={() => setMobileMenuOpen(true)} />
      )}
      <main className={hasWorkspaceChrome ? 'main-area' : ''}>
        {hasWorkspaceChrome ? (
          <div className={location.pathname === '/chat' ? 'main-inner main-inner-chat' : 'main-inner'}>
            {children}
          </div>
        ) : (
          children
        )}
      </main>
    </div>
  );
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<HomeRoute />} />
      <Route path="/login" element={<LoginRoute />} />
      <Route
        path="/chat"
        element={
          <ProtectedRoute page="chat">
            <Chat />
          </ProtectedRoute>
        }
      />
      <Route
        path="/documents"
        element={
          <ProtectedRoute page="documents">
            <Documents />
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin"
        element={
          <AdminRoute page="ingestion">
            <Admin />
          </AdminRoute>
        }
      />
      <Route path="/admin/access" element={<AdminRoute page="access"><AccessControl /></AdminRoute>} />
    </Routes>
  );
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BrowserRouter>
          <AppLayout>
            <AppRoutes />
          </AppLayout>
          <Toaster position="top-right" />
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  );
}

export default App;
