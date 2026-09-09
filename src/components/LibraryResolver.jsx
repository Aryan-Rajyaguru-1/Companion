/**
 * LibraryResolver.jsx
 * P1 — Structured errors: surfaces missing library suggestions inline
 * after compile fails, with one-click install.
 *
 * Pattern from arduino-ide-main's library-service-impl.ts which parses
 * compile errors to generate actionable install suggestions.
 */

import { useState, useCallback } from 'react';
import { detectMissingLibraries, guessLibraryName } from '../utils/library-resolver';
import './LibraryResolver.css';

export default function LibraryResolver({ errors, sourceCode, onInstallComplete, onDismiss }) {
  const [installing, setInstalling] = useState(new Set());
  const [installed,  setInstalled]  = useState(new Set());
  const [failed,     setFailed]     = useState(new Map());
  const [customName, setCustomName] = useState({});

  const missing = detectMissingLibraries(errors, sourceCode);

  // Hooks must run on every render — moving the early return below them.
  // (Returning before useCallback threw "Rendered more hooks than during
  // the previous render" when library detection appeared mid-session.)
  const handleInstall = useCallback(async (header, libraryName) => {
    if (!libraryName) return;
    setInstalling(prev => new Set([...prev, header]));
    setFailed(prev => { const n = new Map(prev); n.delete(header); return n; });

    const result = await window.electronAPI?.installLib?.(libraryName);

    setInstalling(prev => { const n = new Set(prev); n.delete(header); return n; });

    if (result?.success) {
      setInstalled(prev => new Set([...prev, header]));
      // If all are installed, notify parent to re-compile
      if (installed.size + 1 >= missing.length) {
        setTimeout(() => onInstallComplete?.(), 400);
      }
    } else {
      setFailed(prev => new Map([...prev, [header, result?.error || 'Installation failed']]));
    }
  }, [missing.length, installed.size, onInstallComplete]);

  if (missing.length === 0) return null;

  const allInstalled = missing.every(m => installed.has(m.header));

  return (
    <div className="lib-resolver">
      <div className="lr-header">
        <LibIcon />
        <span className="lr-title">Missing Libraries Detected</span>
        <span className="lr-count">{missing.length - installed.size} needed</span>
        <button className="lr-dismiss" onClick={onDismiss} title="Dismiss">×</button>
      </div>

      <div className="lr-list">
        {missing.map(m => {
          const isInstalling = installing.has(m.header);
          const isInstalled  = installed.has(m.header);
          const error        = failed.get(m.header);
          const libName      = m.library || customName[m.header] || guessLibraryName(m.header);

          return (
            <div key={m.header} className={`lr-item ${isInstalled ? 'installed' : ''}`}>
              <div className="lr-item-left">
                <code className="lr-header-file">#{m.header}</code>
                {m.file && (
                  <span className="lr-location">
                    {m.file.split(/[/\\]/).pop()}{m.line ? `:${m.line}` : ''}
                  </span>
                )}
              </div>

              <div className="lr-item-right">
                {isInstalled ? (
                  <span className="lr-done">✓ Installed</span>
                ) : (
                  <>
                    {!m.known && (
                      <input
                        className="lr-custom-input"
                        type="text"
                        placeholder="Library name…"
                        value={customName[m.header] || ''}
                        onChange={e => setCustomName(prev => ({ ...prev, [m.header]: e.target.value }))}
                        title="Enter the exact library name from the Library Manager"
                      />
                    )}
                    {m.known && (
                      <span className="lr-lib-name" title="Library to install">{m.library}</span>
                    )}
                    <button
                      className="btn btn-sm btn-primary lr-install-btn"
                      disabled={isInstalling || !libName}
                      onClick={() => handleInstall(m.header, libName)}
                    >
                      {isInstalling ? <><span className="spin-sm">⟳</span> Installing…</> : 'Install'}
                    </button>
                  </>
                )}
              </div>

              {error && (
                <div className="lr-error">{error}</div>
              )}
            </div>
          );
        })}
      </div>

      {allInstalled && (
        <div className="lr-footer">
          <span className="lr-success">✓ All libraries installed</span>
          <button className="btn btn-sm btn-primary" onClick={() => onInstallComplete?.()}>
            Re-compile
          </button>
        </div>
      )}
    </div>
  );
}

function LibIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none"
         stroke="currentColor" strokeWidth="2" strokeLinecap="round">
      <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/>
      <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>
    </svg>
  );
}
