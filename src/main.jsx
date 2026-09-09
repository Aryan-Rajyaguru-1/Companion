import React from 'react';
import ReactDOM from 'react-dom/client';
import { loader } from '@monaco-editor/react';
import ErrorBoundary from './ErrorBoundary';
import App from './App';  // Switch back to full App
import SerialMonitor from './components/SerialMonitor';
import './index.css';

console.log('=== Companion IDE Starting ===');

// Configure Monaco Editor with robust CDN setup
try {
  loader.config({
    paths: {
      vs: 'https://cdn.jsdelivr.net/npm/monaco-editor@0.50.0/min/vs'
    },
    trustedTypes: false
  });
  console.log('✓ Monaco loader configured');
} catch (e) {
  console.warn('Monaco config warning (non-critical):', e);
}

// Ensure root element exists
const rootElement = document.getElementById('root');
if (!rootElement) {
  throw new Error('Root element not found');
}

console.log('✓ Root element found, mounting React app...');

try {
  // P5 #11: standalone serial-monitor window (opened via monitor:tear-off).
  const params = new URLSearchParams(window.location.search);
  if (params.get('view') === 'serial-monitor') {
    const host = params.get('host') || '';
    const port = Number(params.get('port')) || 3333;
    document.title = `Serial Monitor — ${host}:${port}`;
    ReactDOM.createRoot(rootElement).render(
      <SerialMonitor
        host={host}
        port={port}
        standalone
        onClose={() => window.close()}
      />
    );
    console.log('✓ Tear-off serial monitor mounted');
  } else {
    ReactDOM.createRoot(rootElement).render(
      <React.StrictMode>
        <ErrorBoundary>
          <App />
        </ErrorBoundary>
      </React.StrictMode>
    );
    console.log('✓ React app mounted successfully');
  }
} catch (e) {
  console.error('FATAL: Failed to mount React app:', e);
  rootElement.innerHTML = `<div style="color: red; padding: 20px; font-family: monospace;">FATAL ERROR: ${e.message}</div>`;
}
