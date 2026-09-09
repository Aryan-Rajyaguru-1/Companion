/**
 * StatusBar.jsx
 * Matches Arduino IDE 2.x status bar:
 *   Line/Column position (from editor cursor event)
 *   Board name (friendly)
 *   MCU family
 *   Daemon status
 *   Cache object count
 *   Last compile time
 *   Compile summary
 *   CLI version
 *   Bridge status
 */

import { useState, useEffect } from 'react';
import { friendlyName } from '../utils/fqbn';
import './StatusBar.css';

export default function StatusBar({
  fileName, modified, board, mcu,
  bridgeHost, bridgeStatus,
  isCompiling, isUploading,
  autoVerify, warnings, compileSummary,
  daemonRunning, cacheStats, lastCompileMs,
  cursorLine, cursorCol,        // from editor cursor event
  onShowSketchFolder,           // () => open folder in OS
  onExportBinary,               // () => run export compiled binary
}) {
  const [cliVersion, setCliVersion] = useState('');
  const [cliFound,   setCliFound]   = useState(null);

  useEffect(() => {
    window.electronAPI?.cliVersion?.()
      .then(v => {
        const found = v && !v.includes('not found');
        setCliVersion(found ? v.replace('Companion CLI ', 'CLI ') : '');
        setCliFound(found);
      })
      .catch(() => setCliFound(false));
  }, []);

  const taskText = isUploading ? '⬆ Uploading…' : isCompiling ? '⚙ Compiling…' : null;
  const boardLabel = friendlyName(board) || board?.split(':').pop() || board;

  return (
    <div className="statusbar">

      {/* ── Left ─────────────────────────────────────── */}
      <div className="sb-left">
        <span className="sb-item sb-file">
          <FileIcon />
          {fileName}{modified ? <span className="sb-modified-dot">●</span> : ''}
        </span>

        <div className="sb-sep" />

        {/* Line:Col — the most-looked-at item in any IDE */}
        <span className="sb-item sb-cursor" title="Cursor position (Ctrl+G to jump)">
          Ln {cursorLine ?? 1}, Col {cursorCol ?? 1}
        </span>

        <div className="sb-sep" />

        <span className="sb-item sb-board" title={`FQBN: ${board}`}>
          <BoardIcon />{boardLabel}
        </span>

        <div className="sb-sep" />

        <span className="sb-item sb-mcu">MCU: <strong>{mcu}</strong></span>

        {autoVerify && (
          <><div className="sb-sep" /><span className="sb-item sb-pref" title="Auto-verify before upload">AV</span></>
        )}
        {warnings && warnings !== 'none' && (
          <><div className="sb-sep" /><span className="sb-item sb-pref" title={`Warnings: ${warnings}`}>W:{warnings[0].toUpperCase()}</span></>
        )}
      </div>

      {/* ── Center ────────────────────────────────────── */}
      <div className="sb-center">
        {taskText && <span className="sb-task"><span className="spin">⟳</span>{taskText}</span>}
      </div>

      {/* ── Right ─────────────────────────────────────── */}
      <div className="sb-right">

        {/* Daemon */}
        {daemonRunning != null && (
          <>
            <span className={`sb-item sb-daemon ${daemonRunning ? 'on' : 'off'}`}
              title={daemonRunning ? 'CLI daemon running — build cache warm' : 'Daemon not running'}>
              <span className={`status-dot ${daemonRunning ? 'connected' : 'disconnected'}`} />
              {daemonRunning ? 'daemon' : 'subprocess'}
            </span>
            <div className="sb-sep" />
          </>
        )}

        {/* Cache count */}
        {cacheStats?.ObjectCount > 0 && daemonRunning && (
          <>
            <span className="sb-item sb-cache"
              title={`${cacheStats.ObjectCount} cached objects · ${(cacheStats.TotalSizeMB ?? 0).toFixed(1)} MB`}>
              <CacheIcon />{cacheStats.ObjectCount}
            </span>
            <div className="sb-sep" />
          </>
        )}

        {/* Compile time */}
        {lastCompileMs != null && !isCompiling && !isUploading && (
          <>
            <span className="sb-item sb-compile-time" title="Last compile time">
              {lastCompileMs < 1000 ? `${lastCompileMs}ms` : `${(lastCompileMs / 1000).toFixed(1)}s`}
            </span>
            <div className="sb-sep" />
          </>
        )}

        {/* Compile summary */}
        {compileSummary && !isCompiling && !isUploading && (
          <>
            {compileSummary.errors > 0
              ? <span className="sb-item sb-err">✕ {compileSummary.errors} error{compileSummary.errors > 1 ? 's' : ''}</span>
              : compileSummary.warnings > 0
              ? <span className="sb-item sb-warn">⚠ {compileSummary.warnings}</span>
              : <span className="sb-item sb-ok">✓</span>
            }
            <div className="sb-sep" />
          </>
        )}

        {/* Export binary shortcut */}
        {onExportBinary && (
          <>
            <button className="sb-item sb-action" title="Export Compiled Binary" onClick={onExportBinary}>
              <ExportIcon />
            </button>
            <div className="sb-sep" />
          </>
        )}

        {/* Show sketch folder */}
        {onShowSketchFolder && (
          <>
            <button className="sb-item sb-action" title="Show Sketch Folder" onClick={onShowSketchFolder}>
              <FolderIcon />
            </button>
            <div className="sb-sep" />
          </>
        )}

        {/* CLI version */}
        {cliVersion && (
          <span className={`sb-item sb-cli ${cliFound === false ? 'missing' : ''}`}
            title={cliFound ? 'Companion CLI active' : 'Companion CLI not found'}>
            {cliFound === false ? '⚠ ' : ''}{cliVersion}
          </span>
        )}

        <div className="sb-sep" />

        {/* Bridge */}
        <span className={`sb-item sb-bridge ${bridgeStatus}`}>
          <span className={`status-dot ${bridgeStatus}`} />
          {bridgeStatus === 'connected'    ? bridgeHost
           : bridgeStatus === 'connecting' ? 'Connecting…'
           : 'Bridge offline'}
        </span>
      </div>
    </div>
  );
}

function FileIcon()   { return <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>; }
function BoardIcon()  { return <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><rect x="2" y="2" width="20" height="20" rx="3"/><path d="M8 8h2M8 12h2M8 16h2M14 8h2M14 12h2M14 16h2"/></svg>; }
function CacheIcon()  { return <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" style={{marginRight:3,opacity:.7}}><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/></svg>; }
function ExportIcon() { return <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>; }
function FolderIcon() { return <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>; }
