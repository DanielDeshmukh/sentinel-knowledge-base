import React from 'react';
import ReactDOM from 'react-dom/client';
import { registerSW } from 'virtual:pwa-register';
import App from './App';
import './index.css';

const SERVICE_WORKER_UPDATE_INTERVAL_MS = 5 * 60 * 1000;

registerSW({
  immediate: true,
  onRegisteredSW: (_serviceWorkerUrl, registration) => {
    if (!registration) return;
    window.setInterval(() => {
      void registration.update().catch(() => undefined);
    }, SERVICE_WORKER_UPDATE_INTERVAL_MS);
  },
});

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
