import React from 'react';
import ReactDOM from 'react-dom/client';
import ErrorBoundary from './ErrorBoundary';
import AppTest from './AppTest';
import './index.css';

console.log('=== TEST: Companion IDE Starting ===');

const rootElement = document.getElementById('root');
if (!rootElement) {
  throw new Error('Root element not found');
}

console.log('✓ Root element found, mounting React test app...');

ReactDOM.createRoot(rootElement).render(
  <React.StrictMode>
    <ErrorBoundary>
      <AppTest />
    </ErrorBoundary>
  </React.StrictMode>
);

console.log('✓ React test app mounted');
