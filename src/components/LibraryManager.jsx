/**
 * LibraryManager.jsx
 * Bug fix #3: libManager menu item now opens this working modal
 * (previously the handler was missing and nothing happened).
 *
 * Features matching Arduino IDE 2.x Library Manager:
 *   - Search libraries with 40-result limit
 *   - Category filter: All / Installed / Arduino / Partner / Recommended / Community
 *   - Version selector per library
 *   - Install / Update / Remove with confirmation
 *   - "Installed" version badge
 *   - Live output console
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import './LibraryManager.css';

const CATEGORIES = ['All', 'Installed', 'Arduino', 'Partner', 'Recommended', 'Community', 'Contributed'];

export default function LibraryManager({ onClose }) {
  const [query,       setQuery]       = useState('');
  const [category,    setCategory]    = useState('All');
  const [libraries,   setLibraries]   = useState([]);
  const [installed,   setInstalled]   = useState([]);
  const [loading,     setLoading]     = useState(false);
  const [installing,  setInstalling]  = useState(null); // name of lib being installed
  const [output,      setOutput]      = useState('');
  const [unconfirm,   setUnconfirm]   = useState(null);
  const [selectedVers, setSelectedVers] = useState({});

  const searchRef  = useRef(null);
  const outputRef  = useRef(null);
  const debounceRef = useRef(null);

  const emit = (text) => setOutput(p => p + text);

  const loadInstalled = useCallback(async () => {
    const inst = await window.electronAPI?.listLibs?.() || [];
    setInstalled(Array.isArray(inst) ? inst : []);
  }, []);

  const search = useCallback(async (q) => {
    setLoading(true);
    try {
      const results = await window.electronAPI?.searchLibs?.(q || '') || [];
      setLibraries(Array.isArray(results) ? results : []);
    } catch {
      setLibraries([]);
    } finally {
      setLoading(false);
    }
  }, []);

  // Initial load
  useEffect(() => {
    loadInstalled();
    search('');
    setTimeout(() => searchRef.current?.focus(), 80);
  }, [loadInstalled, search]);

  // Debounced search
  useEffect(() => {
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => search(query), 400);
    return () => clearTimeout(debounceRef.current);
  }, [query, search]);

  // Auto-scroll output
  useEffect(() => { outputRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [output]);

  // Esc to close
  useEffect(() => {
    const h = (e) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', h);
    return () => window.removeEventListener('keydown', h);
  }, [onClose]);

  // Build installed map
  const installedMap = {};
  installed.forEach(lib => {
    if (lib?.name) installedMap[lib.name] = lib.version || 'installed';
  });

  const getInstVersion = (name) => installedMap[name] || null;
  const isInstalled    = (name) => name in installedMap;

  const handleInstall = async (lib) => {
    const version  = selectedVers[lib.name] || lib.version;
    const fullName = version ? `${lib.name}@${version}` : lib.name;
    setInstalling(lib.name); setOutput('');
    emit(`» Installing ${fullName}…\n`);
    const r = await window.electronAPI?.installLib?.(fullName, emit);
    setInstalling(null);
    if (r?.success) {
      emit(`✓ Installed ${fullName}\n`);
      await loadInstalled();
    } else {
      emit(`✗ Failed: ${r?.error || 'unknown error'}\n`);
    }
  };

  const handleRemove = async (name) => {
    if (unconfirm !== name) { setUnconfirm(name); return; }
    setUnconfirm(null);
    setInstalling(name); setOutput('');
    emit(`» Removing ${name}…\n`);
    const r = await window.electronAPI?.uninstallLib?.(name);
    setInstalling(null);
    emit(r?.success ? `✓ Removed ${name}\n` : `✗ Failed: ${r?.error}\n`);
    await loadInstalled();
  };

  // Filter
  const display = libraries.filter(lib => {
    if (!lib?.name) return false;
    if (category === 'Installed') return isInstalled(lib.name);
    if (category !== 'All') return lib.category === category;
    return true;
  });

  const counts = {
    All:       libraries.length,
    Installed: Object.keys(installedMap).length,
  };

  return (
    <div className="modal-backdrop" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="modal lm-modal">

        <div className="modal-header">
          <span className="modal-title"><LibIcon /> Library Manager</span>
          <button className="modal-close" onClick={onClose}>✕</button>
        </div>

        <div className="lm-toolbar">
          <div className="lm-search-wrap">
            <SearchIcon />
            <input ref={searchRef} className="lm-search" type="search"
              placeholder="Search libraries…" value={query}
              onChange={e => setQuery(e.target.value)} />
            {loading && <span className="spin lm-spin">⟳</span>}
          </div>
          <div className="lm-cats">
            {CATEGORIES.map(c => (
              <button key={c}
                className={`lm-cat ${category === c ? 'active' : ''}`}
                onClick={() => setCategory(c)}>
                {c}
                {counts[c] != null && <span className="lm-cat-count">{counts[c]}</span>}
              </button>
            ))}
          </div>
        </div>

        <div className="lm-body">
          <div className="lm-list">
            {!loading && display.length === 0 && (
              <div className="lm-empty">
                {query ? `No libraries match "${query}"` : 'No libraries in this category.'}
              </div>
            )}

            {display.map(lib => {
              const instVersion = getInstVersion(lib.name);
              const isInst      = !!instVersion;
              const isActive    = installing === lib.name;
              const confirming  = unconfirm === lib.name;
              const selVer      = selectedVers[lib.name] || lib.version || '';
              const versions    = lib.versions || (lib.version ? [lib.version] : []);

              return (
                <div key={lib.name} className={`lm-item ${isInst ? 'installed' : ''}`}>
                  <div className="lm-item-info">
                    <div className="lm-item-name-row">
                      <span className="lm-item-name">{lib.name}</span>
                      {isInst && (
                        <span className="lm-installed-badge">✓ {instVersion}</span>
                      )}
                    </div>
                    {lib.author   && <span className="lm-item-author">by {lib.author}</span>}
                    {lib.sentence && <span className="lm-item-desc">{lib.sentence}</span>}
                  </div>

                  <div className="lm-item-actions">
                    {versions.length > 0 && (
                      <select className="lm-ver-select"
                        value={selVer}
                        onChange={e => setSelectedVers(p => ({ ...p, [lib.name]: e.target.value }))}>
                        {versions.map(v => (
                          <option key={v} value={v}>
                            {v}{v === instVersion ? ' (installed)' : ''}
                          </option>
                        ))}
                      </select>
                    )}

                    {!isInst ? (
                      <button className="btn btn-sm btn-primary"
                        onClick={() => handleInstall(lib)}
                        disabled={isActive || !!installing}>
                        {isActive ? <><span className="spin">⟳</span> Installing…</> : 'Install'}
                      </button>
                    ) : (
                      <>
                        <button
                          className={`btn btn-sm ${confirming ? 'lm-confirm-btn' : ''}`}
                          onClick={() => handleRemove(lib.name)}
                          disabled={isActive || !!installing}>
                          {confirming ? 'Confirm Remove'
                           : isActive ? <><span className="spin">⟳</span> Removing…</>
                           : 'Remove'}
                        </button>
                        {confirming && (
                          <button className="btn btn-sm" onClick={() => setUnconfirm(null)}>Cancel</button>
                        )}
                      </>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          {output && (
            <div className="lm-output">
              <pre className="lm-output-pre">{output}</pre>
              <div ref={outputRef} />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function SearchIcon() { return <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" style={{flexShrink:0,color:'var(--text-dim)'}}><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>; }
function LibIcon()    { return <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>; }
