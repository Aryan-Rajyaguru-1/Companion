/**
 * BoardAutoDetect.jsx
 * UI/UX improvement from analysis: auto-detect connected boards.
 *
 * Queries `companion board list` to find installed platforms,
 * then cross-references with well-known boards to offer a fast-select.
 * Also shows a "Refresh" action to re-scan after installing a new core.
 */

import { useState, useEffect, useCallback } from 'react';
import { ALL_BOARDS, friendlyName, mcuFromFQBN } from '../utils/fqbn';
import './BoardAutoDetect.css';

export default function BoardAutoDetect({ currentFQBN, onSelect, onClose }) {
  const [installedPlatforms, setInstalledPlatforms] = useState([]);
  const [loading,  setLoading]  = useState(true);
  const [error,    setError]    = useState(null);

  const loadInstalled = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // Fetch installed platform list from CLI
      const platforms = await window.electronAPI?.getBoards?.() || [];
      setInstalledPlatforms(platforms.map(p => p.id || '').filter(Boolean));
    } catch (e) {
      setError('Could not fetch installed platforms');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadInstalled(); }, [loadInstalled]);

  // Build list of boards that are actually installable (platform is installed)
  const installedSet = new Set(installedPlatforms);

  const installedBoards = ALL_BOARDS.filter(b => {
    const parts = b.fqbn.split(':');
    const platform = parts.slice(0, 2).join(':');
    return installedSet.has(platform);
  });

  const notInstalledBoards = ALL_BOARDS.filter(b => {
    const parts = b.fqbn.split(':');
    const platform = parts.slice(0, 2).join(':');
    return !installedSet.has(platform);
  });

  const BoardRow = ({ board, installed }) => {
    const isActive = board.fqbn === currentFQBN;
    return (
      <div
        className={`bad-board-row ${isActive ? 'active' : ''} ${!installed ? 'dimmed' : ''}`}
        onClick={() => installed && onSelect(board.fqbn, board.mcu)}
        title={installed ? board.fqbn : `Install platform: ${board.fqbn.split(':').slice(0,2).join(':')}`}
      >
        <div className="bad-board-icon">
          <ChipIcon />
        </div>
        <div className="bad-board-info">
          <span className="bad-board-label">{board.label}</span>
          <span className="bad-board-fqbn">{board.fqbn}</span>
        </div>
        <div className="bad-board-status">
          {isActive
            ? <span className="bad-active-badge">selected</span>
            : installed
            ? <span className="bad-installed-badge">✓</span>
            : <span className="bad-need-badge">install needed</span>
          }
        </div>
      </div>
    );
  };

  return (
    <div className="modal-backdrop" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="modal bad-modal">
        <div className="modal-header">
          <span className="modal-title"><ChipIcon /> Board Selector</span>
          <button className="modal-close" onClick={onClose}>✕</button>
        </div>

        <div className="bad-toolbar">
          <span className="bad-subtitle">
            {loading ? 'Scanning installed platforms…'
              : `${installedBoards.length} boards ready · ${notInstalledBoards.length} need install`}
          </span>
          <button className="btn btn-sm" onClick={loadInstalled} disabled={loading}>
            {loading ? '⟳' : '↺ Refresh'}
          </button>
        </div>

        <div className="bad-body">
          {error && <div className="bad-error">{error}</div>}

          {loading ? (
            <div className="bad-loading">
              <span className="spin">⟳</span> Loading installed platforms…
            </div>
          ) : (
            <>
              {installedBoards.length > 0 && (
                <>
                  <div className="bad-section-label">Installed Platforms</div>
                  {installedBoards.map(b => (
                    <BoardRow key={b.fqbn} board={b} installed={true} />
                  ))}
                </>
              )}

              {notInstalledBoards.length > 0 && (
                <>
                  <div className="bad-section-label dimmed">Other Boards (platform not installed)</div>
                  {notInstalledBoards.slice(0, 8).map(b => (
                    <BoardRow key={b.fqbn} board={b} installed={false} />
                  ))}
                </>
              )}
            </>
          )}
        </div>

        <div className="bad-footer">
          <span className="bad-hint">
            Install platforms via Sketch → Board Manager
          </span>
          <button className="btn" onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  );
}

function ChipIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none"
         stroke="currentColor" strokeWidth="2" strokeLinecap="round">
      <rect x="9" y="9" width="6" height="6"/>
      <path d="M3 9h2M3 15h2M19 9h2M19 15h2M9 3v2M15 3v2M9 19v2M15 19v2"/>
      <rect x="5" y="5" width="14" height="14" rx="2"/>
    </svg>
  );
}
