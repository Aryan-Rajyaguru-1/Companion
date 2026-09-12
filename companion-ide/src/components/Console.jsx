/**
 * Console.jsx
 * Structural fix: classifyLine() now imported from error-parser.js.
 * Previously had an independent regex implementation — now there is one JS parser.
 */

import { useEffect, useRef, useCallback, useState, useMemo } from 'react';
import { classifyLine } from '../utils/error-parser';
import './Console.css';

const TYPE_COLOR = {
  output:  'var(--text-muted)',
  info:    'var(--blue,#58a6ff)',
  success: 'var(--green,#3fb950)',
  error:   'var(--red,#f85149)',
  warning: 'var(--yellow,#d29922)',
  note:    'var(--text-dim)',
  muted:   'var(--text-dim)',
};

export default function Console({ lines, onClear, compileSummary, compileStatus = 'idle', onJumpToLine, missingPlatform, installingPlatform, onInstallPlatform }) {
  const [filter,    setFilter]    = useState('all');
  const [search,    setSearch]    = useState('');
  const [searching, setSearching] = useState(false);
  const [wordWrap,  setWordWrap]  = useState(true);
  const [autoscroll,setAutoscroll]= useState(true);

  const bodyRef    = useRef(null);
  const bottomRef  = useRef(null);
  const searchRef  = useRef(null);
  const autoRef    = useRef(true);
  useEffect(() => { autoRef.current = autoscroll; }, [autoscroll]);

  useEffect(() => {
    if (!autoRef.current) return;
    bottomRef.current?.scrollIntoView({ behavior: 'auto' });
  }, [lines]);

  const handleScroll = useCallback(() => {
    const el = bodyRef.current; if (!el) return;
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
    if (!atBottom && autoRef.current) setAutoscroll(false);
  }, []);

  useEffect(() => {
    const handler = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'f' && bodyRef.current?.contains(document.activeElement)) {
        e.preventDefault(); setSearching(true); setTimeout(() => searchRef.current?.focus(), 50);
      }
      if (e.key === 'Escape' && searching) { setSearching(false); setSearch(''); }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [searching]);

  // Annotate — use unified classifyLine from error-parser.js
  const annotated = useMemo(() =>
    lines.map((l, i) => ({ ...l, ...classifyLine(l.text || ''), idx: i })),
    [lines]);

  const filtered = useMemo(() => {
    let out = annotated;
    if (filter === 'errors')   out = out.filter(l => l.type === 'error');
    if (filter === 'warnings') out = out.filter(l => l.type === 'warning');
    if (filter === 'info')     out = out.filter(l => ['info','success','muted'].includes(l.type));
    if (search) { const q = search.toLowerCase(); out = out.filter(l => l.text?.toLowerCase().includes(q)); }
    return out;
  }, [annotated, filter, search]);

  const counts = useMemo(() => ({
    errors:   annotated.filter(l => l.type === 'error').length,
    warnings: annotated.filter(l => l.type === 'warning').length,
  }), [annotated]);

  const handleCopy = () => navigator.clipboard?.writeText(filtered.map(l => l.text || '').join('\n'));

  const handleLineClick = (l) => {
    if (l.line && onJumpToLine) onJumpToLine(l.line, l.file);
  };

  const totalChars = useMemo(() => lines.reduce((s, l) => s + (l.text?.length || 0), 0), [lines]);

  return (
    <div className="console-pane">
      <div className="console-header">
        <div className="console-header-left">
          <span className="console-title"><ConsoleIcon /> Output</span>
          <div className="console-filters">
            {['all','errors','warnings','info'].map(f => (
              <button key={f} className={`cf-btn ${filter === f ? 'active' : ''}`} onClick={() => setFilter(f)}>
                {f.charAt(0).toUpperCase() + f.slice(1)}
                {f === 'errors'   && counts.errors   > 0 && <span className="cf-count err">{counts.errors}</span>}
                {f === 'warnings' && counts.warnings  > 0 && <span className="cf-count warn">{counts.warnings}</span>}
              </button>
            ))}
          </div>
        </div>
        <div className="console-header-right">
          <button className={`console-icon-btn ${searching ? 'active' : ''}`} title="Search  Ctrl+F"
            onClick={() => { setSearching(p => !p); setTimeout(() => searchRef.current?.focus(), 50); }}>
            <SearchIcon />
          </button>
          <button className={`console-icon-btn ${wordWrap ? 'active' : ''}`} title="Word wrap" onClick={() => setWordWrap(p => !p)}>
            <WrapIcon />
          </button>
          <button className="console-icon-btn" title="Copy" onClick={handleCopy}><CopyIcon /></button>
          <button className="console-icon-btn" title="Clear" onClick={onClear}><ClearIcon /></button>
        </div>
      </div>

      {searching && (
        <div className="console-search-bar">
          <SearchIcon />
          <input ref={searchRef} className="console-search-input" type="text"
            placeholder="Filter output…" value={search}
            onChange={e => setSearch(e.target.value)}
            onKeyDown={e => e.key === 'Escape' && (setSearching(false), setSearch(''))} />
          {search && <span className="console-search-count">{filtered.length} match{filtered.length !== 1 ? 'es' : ''}</span>}
          <button className="console-icon-btn" onClick={() => { setSearching(false); setSearch(''); }}>✕</button>
        </div>
      )}

      <div className={`console-body ${wordWrap ? 'wrap' : 'nowrap'}`} ref={bodyRef} onScroll={handleScroll} tabIndex={0}>
        {filtered.length === 0 && (
          <div className="console-empty">
            {lines.length === 0 ? 'Output will appear here when you compile or upload.' : 'No matches.'}
          </div>
        )}
        {filtered.map((l) => {
          const clickable = l.line != null && onJumpToLine;
          return (
            <div key={l.idx}
              className={`console-line ${l.type} ${clickable ? 'clickable' : ''}`}
              style={{ color: TYPE_COLOR[l.type] || TYPE_COLOR.output }}
              onClick={clickable ? () => handleLineClick(l) : undefined}
              title={clickable ? `Jump to line ${l.line}` : undefined}>
              {search ? highlightSearch(l.text || '', search) : (l.text || '')}
              {clickable && <span className="console-jump-hint">→ :{l.line}</span>}
            </div>
          );
        })}
        <div ref={bottomRef} />
      </div>

      <div className="console-footer">
        <span>{filtered.length.toLocaleString()} line{filtered.length !== 1 ? 's' : ''}</span>
        {totalChars > 0 && <span>{formatBytes(totalChars)}</span>}
        {compileStatus === 'ok' && (
          <span className="cf-ok">✓ Compiled OK</span>
        )}
        {compileStatus === 'failed' && (
          <span className="cf-fail">✗ Compile failed</span>
        )}
        {compileStatus === 'failed' && missingPlatform && onInstallPlatform && (
          <button className="cf-install-btn" onClick={onInstallPlatform} disabled={installingPlatform}>
            {installingPlatform ? `⟳ Installing ${missingPlatform}…` : `Install ${missingPlatform}`}
          </button>
        )}
        {!autoscroll && (
          <button className="console-resume-btn"
            onClick={() => { setAutoscroll(true); bottomRef.current?.scrollIntoView({ behavior: 'smooth' }); }}>
            ↓ Resume autoscroll
          </button>
        )}
      </div>
    </div>
  );
}

function highlightSearch(text, query) {
  const parts = text.split(new RegExp(`(${query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi'));
  return parts.map((p, i) =>
    p.toLowerCase() === query.toLowerCase() ? <mark key={i} className="console-highlight">{p}</mark> : p
  );
}

function formatBytes(n) { if (n < 1024) return `${n}B`; return `${(n / 1024).toFixed(1)}KB`; }

function ConsoleIcon() { return <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/></svg>; }
function SearchIcon()  { return <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>; }
function WrapIcon()    { return <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M3 6h18M3 12h12a3 3 0 0 1 0 6h-3m-3 0 3-3-3-3M3 18h6"/></svg>; }
function CopyIcon()    { return <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>; }
function ClearIcon()   { return <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/></svg>; }
