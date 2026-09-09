/**
 * CLISetup.jsx
 * First-run helper modal shown when Companion CLI binary is not found.
 * Guides the user through building and placing the CLI binary.
 */

import { useState, useEffect } from 'react';
import './CLISetup.css';

const STEPS = [
  {
    title: 'Prerequisites',
    icon: '📦',
    content: (
      <>
        <p>Install <strong>Go 1.22+</strong> from <a href="https://go.dev/dl/" target="_blank" rel="noreferrer">go.dev/dl</a></p>
        <code>go version  # should print go1.22 or higher</code>
      </>
    ),
  },
  {
    title: 'Build Companion CLI',
    icon: '🔨',
    content: (
      <>
        <p>Navigate to the <code>companion-cli/</code> folder and build:</p>
        <code>cd companion-cli</code>
        <code>go mod tidy</code>
        <code>go build -o companion .</code>
        <p className="hint">On Windows: <code>go build -o companion.exe .</code></p>
      </>
    ),
  },
  {
    title: 'Place the Binary',
    icon: '📁',
    content: (
      <>
        <p>Put the built binary in one of these locations:</p>
        <code>companion-cli/companion  ← if projects are side by side (recommended)</code>
        <code>companion-ide/bin/companion  ← bundled inside the app</code>
        <code>anywhere in your system PATH</code>
      </>
    ),
  },
  {
    title: 'Initialize',
    icon: '⚙️',
    content: (
      <>
        <p>Set up the CLI on first run:</p>
        <code>./companion config init</code>
        <code>./companion board update-index</code>
        <code>./companion lib update-index</code>
        <p className="hint">Then install your board: <code>./companion board install arduino:avr</code></p>
      </>
    ),
  },
];

export default function CLISetup({ onClose, cliFound }) {
  const [step,      setStep]      = useState(0);
  const [checking,  setChecking]  = useState(false);
  const [lastCheck, setLastCheck] = useState(null);

  const recheck = async () => {
    setChecking(true);
    const v = await window.electronAPI?.cliVersion?.();
    const found = v && !v.includes('not found');
    setLastCheck(found ? v : null);
    setChecking(false);
    if (found) setTimeout(() => onClose(), 800);
  };

  if (cliFound) return null;

  return (
    <div className="modal-backdrop">
      <div className="modal cli-setup-modal">
        <div className="modal-header">
          <span className="modal-title">
            <WrenchIcon /> Setup Companion CLI
          </span>
          <button className="modal-close" onClick={onClose}>✕</button>
        </div>

        <div className="cs-intro">
          <div className="cs-warning">
            ⚠ Companion CLI binary not found. The IDE needs it to compile and upload sketches.
          </div>
          <p className="cs-desc">
            Companion CLI is your own MIT-licensed build tool — no GPL, no restrictions.
            Follow the steps below to build and connect it.
          </p>
        </div>

        {/* Step indicators */}
        <div className="cs-steps-nav">
          {STEPS.map((s, i) => (
            <button
              key={i}
              className={`cs-step-dot ${i === step ? 'active' : ''} ${i < step ? 'done' : ''}`}
              onClick={() => setStep(i)}
            >
              {i < step ? '✓' : i + 1}
            </button>
          ))}
        </div>

        {/* Step content */}
        <div className="cs-step-content">
          <div className="cs-step-header">
            <span className="cs-step-icon">{STEPS[step].icon}</span>
            <span className="cs-step-title">Step {step + 1}: {STEPS[step].title}</span>
          </div>
          <div className="cs-step-body">
            {STEPS[step].content}
          </div>
        </div>

        {/* Navigation */}
        <div className="cs-footer">
          <button
            className="btn"
            onClick={() => setStep(s => Math.max(0, s - 1))}
            disabled={step === 0}
          >
            ← Previous
          </button>

          <button className="btn" onClick={recheck} disabled={checking}>
            {checking
              ? <><span className="spin">⟳</span> Checking…</>
              : <><RefreshIcon /> Re-check Binary</>}
          </button>

          {lastCheck && (
            <span className="cs-found">✓ Found: {lastCheck}</span>
          )}

          <div style={{ flex: 1 }} />

          {step < STEPS.length - 1
            ? <button className="btn primary" onClick={() => setStep(s => s + 1)}>
                Next →
              </button>
            : <button className="btn primary" onClick={onClose}>
                Close
              </button>
          }
        </div>
      </div>
    </div>
  );
}

function WrenchIcon() {
  return <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/></svg>;
}
function RefreshIcon() {
  return <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>;
}
