import React from 'react';
import ReactDOM from 'react-dom/client';
import { registerSW } from 'virtual:pwa-register';
import App from './App';
import './index.css';

const SERVICE_WORKER_CLEANUP_KEY = 'sentinel-service-worker-cleanup-v1';

if ('serviceWorker' in navigator) {
  void navigator.serviceWorker.getRegistrations().then((registrations) => {
    if (registrations.length === 0 || localStorage.getItem(SERVICE_WORKER_CLEANUP_KEY)) return;

    // Replace the old Workbox worker with vite-plugin-pwa's self-destroying
    // worker once. It unregisters itself and removes its cached app shell.
    localStorage.setItem(SERVICE_WORKER_CLEANUP_KEY, 'started');
    registerSW({
      immediate: true,
      onRegisterError: () => localStorage.removeItem(SERVICE_WORKER_CLEANUP_KEY),
    });
  }).catch(() => undefined);
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
