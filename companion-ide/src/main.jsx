import React from 'react';
import ReactDOM from 'react-dom/client';
import { loader } from '@monaco-editor/react';
import * as monaco from 'monaco-editor';
import editorWorker from 'monaco-editor/esm/vs/editor/editor.worker?worker';
import ErrorBoundary from './ErrorBoundary';
import App from './App';  // Switch back to full App
import SerialMonitor from './components/SerialMonitor';
import './index.css';

console.log('=== Companion IDE Starting ===');

// Monaco is BUNDLED, not fetched. It used to be pointed at
// cdn.jsdelivr.net, which meant the editor's JavaScript arrived at runtime
// from a third-party CDN — so the CSP had to allow that origin and
// 'unsafe-eval', and the "100% local" claim was false: whoever controlled
// that CDN response controlled the editor (and, through it, the renderer).
// Shipping the files inside the app removes the supply-chain hop, the CSP hole
// and the offline failure mode in one change.
self.MonacoEnvironment = {
  getWorker: () => new editorWorker(),
};
loader.config({ monaco });
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
