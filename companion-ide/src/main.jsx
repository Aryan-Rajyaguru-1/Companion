// FIRST import: it must evaluate before App/Editor, which call loader.init()
// at module scope. See src/monacoSetup.js for why that matters.
import './monacoSetup';
import React from 'react';
import ReactDOM from 'react-dom/client';
import ErrorBoundary from './ErrorBoundary';
import App from './App';  // Switch back to full App
import SerialMonitor from './components/SerialMonitor';
import './index.css';

console.log('=== Companion IDE Starting ===');

console.log('✓ Monaco bundled locally (no CDN)');

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
