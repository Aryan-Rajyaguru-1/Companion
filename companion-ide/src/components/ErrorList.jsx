/**
 * ErrorList.jsx — Problems panel
 * Bug fixes:
 *   #1  All hooks called unconditionally before any early return (React rules of hooks)
 *   #14 Keyboard navigation uses same sorted order as the displayed rows
 */

import { useState, useCallback, useEffect, useRef, useMemo } from 'react';
import './ErrorList.css';

const SEV_ORDER = { error: 0, warning: 1, note: 2 };

export default function ErrorList({ errors = [], onJumpToLine, onDismiss }) {
  // ── All hooks first — unconditionally ────────────────────────
  const [collapsed, setCollapsed] = useState({});
  const [selected,  setSelected]  = useState(null);
  const listRef = useRef(null);

  // BUG 14 FIX: flat uses the same sorted order as display, so ↑↓ moves
  // through the visually adjacent row, not the original arrival order.
  const sorted = useMemo(() =>
    [...errors].sort(
      (a, b) => (SEV_ORDER[a.severity] ?? 9) - (SEV_ORDER[b.severity] ?? 9) || a.line - b.line
    ),
    [errors]
  );

  // Group by file basename (using the already-sorted array)
  const byFile = useMemo(() => {
    const map = {};
    sorted.forEach(e => {
      const key = e.file ? e.file.split(/[/\\]/).pop() : 'unknown';
      if (!map[key]) map[key] = { path: e.file, items: [] };
      map[key].items.push(e);
    });
    return map;
  }, [sorted]);

  const handleClick = useCallback((e) => {
    setSelected(`${e.file}:${e.line}:${e.col}`);
    onJumpToLine?.(e.line, e.file);
  }, [onJumpToLine]);

  // BUG 14 FIX: navigate within `sorted` (display order)
  useEffect(() => {
    if (!sorted.length) return;
    const handler = (ev) => {
      if (!listRef.current?.contains(document.activeElement)) return;
      if (ev.key !== 'ArrowDown' && ev.key !== 'ArrowUp' && ev.key !== 'Enter') return;
      ev.preventDefault();

      const idx = sorted.findIndex(e => `${e.file}:${e.line}:${e.col}` === selected);
      if (ev.key === 'ArrowDown' || ev.key === 'ArrowUp') {
        const next = ev.key === 'ArrowDown'
          ? Math.min(idx + 1, sorted.length - 1)
          : Math.max(idx - 1, 0);
        setSelected(`${sorted[next].file}:${sorted[next].line}:${sorted[next].col}`);
      }
      if (ev.key === 'Enter' && selected) {
        const e = sorted.find(e => `${e.file}:${e.line}:${e.col}` === selected);
        if (e) onJumpToLine?.(e.line, e.file);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [selected, sorted, onJumpToLine]);

  // BUG 1 FIX: early return AFTER all hooks
  if (errors.length === 0) return null;

  const groups   = Object.entries(byFile);
  const errCount = errors.filter(e => e.severity === 'error').length;
  const wrnCount = errors.filter(e => e.severity === 'warning').length;

  return (
    <div className="error-list" ref={listRef} tabIndex={0}>
      <div className="el-header">
        <div className="el-header-left">
          <ProblemsIcon />
          <span className="el-title">Problems</span>
          {errCount > 0 && <span className="el-badge el-badge-err">{errCount} error{errCount > 1 ? 's' : ''}</span>}
          {wrnCount > 0 && <span className="el-badge el-badge-warn">{wrnCount} warning{wrnCount > 1 ? 's' : ''}</span>}
        </div>
        {onDismiss && (
          <button className="el-close" onClick={onDismiss} title="Close">✕</button>
        )}
      </div>

      <div className="el-body">
        {groups.map(([key, group]) => {
          const isOpen     = !collapsed[key];
          const fileErrors = group.items.filter(i => i.severity === 'error').length;
          const fileWarns  = group.items.filter(i => i.severity === 'warning').length;

          return (
            <div key={key} className="el-group">
              <div className="el-group-header"
                onClick={() => setCollapsed(p => ({ ...p, [key]: !p[key] }))}>
                <span className="el-chevron">{isOpen ? '▾' : '▸'}</span>
                <FileIcon />
                <span className="el-group-name" title={group.path}>{key}</span>
                <span className="el-group-path">{group.path}</span>
                <div className="el-group-counts">
                  {fileErrors > 0 && <span className="el-mini err">{fileErrors}</span>}
                  {fileWarns  > 0 && <span className="el-mini warn">{fileWarns}</span>}
                </div>
              </div>

              {isOpen && group.items.map((item, i) => {
                const rowKey    = `${item.file}:${item.line}:${item.col}`;
                const isSelected = selected === rowKey;
                return (
                  <div key={i}
                    className={`el-row ${item.severity} ${isSelected ? 'selected' : ''}`}
                    onClick={() => handleClick(item)}
                    title={`${item.file}:${item.line} — click to jump`}>
                    <SevIcon sev={item.severity} />
                    <span className="el-message">{item.message}</span>
                    <span className="el-location">:{item.line}{item.col > 1 ? `:${item.col}` : ''}</span>
                  </div>
                );
              })}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function SevIcon({ sev }) {
  if (sev === 'error')   return <span className="el-sev-dot err"  title="Error">✕</span>;
  if (sev === 'warning') return <span className="el-sev-dot warn" title="Warning">⚠</span>;
  return                        <span className="el-sev-dot note" title="Note">ℹ</span>;
}

function ProblemsIcon() { return <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>; }
function FileIcon()     { return <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" style={{flexShrink:0,color:'var(--text-dim)'}}><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>; }
