/**
 * SketchSidebar.jsx  (#2 / #10)
 * Left-side panel showing:
 *   1. Files in the current sketch directory  — via listSketchFiles IPC (#10)
 *   2. Recently opened files                  — from localStorage
 *
 * Calls window.electronAPI.listSketchFiles() which is now registered in
 * main.js under the 'file:listSketchFiles' IPC handler.
 */

import { useState, useEffect, useCallback } from 'react';
import { getRecentFiles, removeRecentFile, clearRecentFiles } from '../utils/recent-files';
import './SketchSidebar.css';

const FILE_ICONS = {
  ino:  { icon: '▶', color: 'var(--teal)' },
  cpp:  { icon: 'C', color: 'var(--yellow)' },
  c:    { icon: 'C', color: 'var(--yellow)' },
  h:    { icon: 'H', color: 'var(--blue)' },
  hpp:  { icon: 'H', color: 'var(--blue)' },
  s:    { icon: 'A', color: 'var(--text-dim)' },
  txt:  { icon: '≡', color: 'var(--text-dim)' },
  md:   { icon: '≡', color: 'var(--text-dim)' },
  json: { icon: '{}', color: 'var(--green)' },
  yaml: { icon: '≡', color: 'var(--green)' },
  yml:  { icon: '≡', color: 'var(--green)' },
};

function fileIcon(name) {
  const ext = name?.split('.').pop()?.toLowerCase() || '';
  return FILE_ICONS[ext] || { icon: '·', color: 'var(--text-dim)' };
}

export default function SketchSidebar({
  sketchDir,
  activeFile,
  onOpenFile,
  onClose,
  showAllFiles,
}) {
  const [sketchFiles,  setSketchFiles]  = useState([]);
  const [recentFiles,  setRecentFiles]  = useState([]);
  const [sketchOpen,   setSketchOpen]   = useState(true);
  const [recentOpen,   setRecentOpen]   = useState(true);
  const [loading,      setLoading]      = useState(false);
  const [error,        setError]        = useState(null);

  // ── #10 Load sketch files via listSketchFiles IPC ────────────
  const loadSketchFiles = useCallback(async () => {
    if (!sketchDir) { setSketchFiles([]); return; }
    setLoading(true);
    setError(null);
    try {
      // listSketchFiles is now exposed in preload.js and registered in main.js
      const files = await window.electronAPI?.listSketchFiles?.(sketchDir, showAllFiles);
      setSketchFiles(Array.isArray(files) ? files : []);
    } catch (e) {
      console.error('listSketchFiles error:', e);
      setError('Could not read sketch directory');
      setSketchFiles([]);
    } finally {
      setLoading(false);
    }
  }, [sketchDir, showAllFiles]);

  useEffect(() => {
    loadSketchFiles();
  }, [loadSketchFiles]);

  // ── Load recents from localStorage ──────────────────────────
  useEffect(() => {
    setRecentFiles(getRecentFiles());
  }, [activeFile]);

  const handleRemoveRecent = (e, path) => {
    e.stopPropagation();
    removeRecentFile(path);
    setRecentFiles(getRecentFiles());
  };

  const SectionHeader = ({ label, open, onToggle, count, onRefresh }) => (
    <div className="sidebar-section-header" onClick={onToggle}>
      <span className="sidebar-chevron">{open ? '▾' : '▸'}</span>
      <span className="sidebar-section-label">{label}</span>
      {count > 0 && <span className="sidebar-badge">{count}</span>}
      {onRefresh && (
        <button
          className="sidebar-refresh"
          title="Refresh"
          onClick={e => { e.stopPropagation(); onRefresh(); }}
        >
          ↺
        </button>
      )}
    </div>
  );

  return (
    <div className="sketch-sidebar">
      {/* Header */}
      <div className="sidebar-header">
        <span className="sidebar-title">
          <SketchIcon /> Explorer
        </span>
        <button className="sidebar-close" onClick={onClose} title="Close sidebar">×</button>
      </div>

      {/* ── Sketch files section ── */}
      <SectionHeader
        label={sketchDir ? sketchDir.split(/[/\\]/).pop() : 'No sketch open'}
        open={sketchOpen}
        onToggle={() => setSketchOpen(p => !p)}
        count={sketchFiles.length}
        onRefresh={sketchDir ? loadSketchFiles : null}
      />
      {sketchOpen && (
        <div className="sidebar-file-list">
          {loading && <div className="sidebar-loading">Loading…</div>}
          {error   && <div className="sidebar-error">{error}</div>}
          {!loading && !error && sketchFiles.length === 0 && (
            <div className="sidebar-empty">
              {sketchDir ? 'No source files found' : 'Open a sketch to see files'}
            </div>
          )}
          {sketchFiles.map(f => {
            const icon     = fileIcon(f.name);
            const isActive = activeFile === f.path;
            return (
              <div
                key={f.path}
                className={`sidebar-file ${isActive ? 'active' : ''}`}
                onClick={() => onOpenFile(f.path, f.name)}
                title={f.path}
              >
                <span className="sidebar-file-icon" style={{ color: icon.color }}>
                  {icon.icon}
                </span>
                <span className="sidebar-file-name">{f.name}</span>
                {f.size != null && (
                  <span className="sidebar-file-size">{formatSize(f.size)}</span>
                )}
              </div>
            );
          })}
        </div>
      )}

      <div className="sidebar-divider" />

      {/* ── Recent files section ── */}
      <SectionHeader
        label="Recent Files"
        open={recentOpen}
        onToggle={() => setRecentOpen(p => !p)}
        count={recentFiles.length}
      />
      {recentOpen && (
        <div className="sidebar-file-list">
          {recentFiles.length === 0 && (
            <div className="sidebar-empty">No recent files</div>
          )}
          {recentFiles.map(r => {
            const icon     = fileIcon(r.name);
            const isActive = activeFile === r.path;
            return (
              <div
                key={r.path}
                className={`sidebar-file ${isActive ? 'active' : ''}`}
                onClick={() => onOpenFile(r.path, r.name)}
                title={r.path}
              >
                <span className="sidebar-file-icon" style={{ color: icon.color }}>
                  {icon.icon}
                </span>
                <span className="sidebar-file-name">{r.name}</span>
                <button
                  className="sidebar-file-remove"
                  onClick={e => handleRemoveRecent(e, r.path)}
                  title="Remove from recents"
                >×</button>
              </div>
            );
          })}
          {recentFiles.length > 0 && (
            <button className="sidebar-clear-btn" onClick={() => {
              clearRecentFiles(); setRecentFiles([]);
            }}>
              Clear history
            </button>
          )}
        </div>
      )}
    </div>
  );
}

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes}B`;
  return `${(bytes / 1024).toFixed(1)}K`;
}

function SketchIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none"
         stroke="currentColor" strokeWidth="2" strokeLinecap="round">
      <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
    </svg>
  );
}
