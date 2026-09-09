/**
 * BoardDropdown.jsx
 * P1 FQBN Standardization: uses fqbn.js utilities for normalization + display.
 *
 * New features:
 *   - "Recent" section showing last 5 FQBNs (from prefs.getRecentFQBNs)
 *   - ✓ badge on boards whose platform is installed
 *   - "Detect boards…" entry opens BoardAutoDetect modal
 *   - FQBN normalized through normalizeFQBN() on every select
 */

import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { createPortal } from 'react-dom';
import { BOARD_GROUPS, ALL_BOARDS, friendlyName, mcuFromFQBN, normalizeFQBN } from '../utils/fqbn';
import { prefs } from '../utils/prefs';
import './BoardDropdown.css';

function getPortalContainer() {
  let el = document.getElementById('boards-dropdown-container');
  if (!el) {
    el = document.createElement('div');
    el.id = 'boards-dropdown-container';
    el.style.cssText = 'position:fixed;top:0;left:0;z-index:9999;pointer-events:none;';
    document.body.appendChild(el);
  }
  return el;
}

export default function BoardDropdown({
  selectedFqbn, selectedMCU,
  onSelect,          // (fqbn, mcu) => void
  onEditConfig,      // () => void — opens BridgeSettings
  onDetectBoards,    // () => void — opens BoardAutoDetect
  installedPlatforms = [],  // string[] e.g. ['arduino:avr', 'esp32:esp32']
}) {
  const [open,    setOpen]    = useState(false);
  const [query,   setQuery]   = useState('');
  const [pos,     setPos]     = useState({ top: 0, left: 0, width: 280 });
  const [recents, setRecents] = useState([]);
  // Full board list from every installed platform (Arduino-IDE-style).
  const [available, setAvailable] = useState([]);

  const triggerRef = useRef(null);
  const dropRef    = useRef(null);
  const searchRef  = useRef(null);

  // Load recent FQBNs on open
  useEffect(() => {
    if (open) setRecents(prefs.getRecentFQBNs().slice(0, 5));
  }, [open]);

  // Load every board provided by installed platforms on open
  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    (async () => {
      try {
        const all = await window.electronAPI?.getAllBoards?.();
        if (!cancelled && Array.isArray(all)) setAvailable(all);
      } catch { /* keep previous list */ }
    })();
    return () => { cancelled = true; };
  }, [open]);

  const shortLabel = friendlyName(selectedFqbn) || selectedFqbn?.split(':').pop() || 'Select Board';

  const updatePos = useCallback(() => {
    if (!triggerRef.current) return;
    const rect = triggerRef.current.getBoundingClientRect();
    setPos({ top: rect.bottom + 4, left: rect.left, width: Math.max(300, rect.width) });
  }, []);

  const handleOpen  = () => { updatePos(); setOpen(true); setQuery(''); };
  const handleClose = () => { setOpen(false); setQuery(''); };

  useEffect(() => {
    if (!open) return;
    const handler = (e) => {
      if (triggerRef.current?.contains(e.target) || dropRef.current?.contains(e.target)) return;
      handleClose();
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  useEffect(() => {
    if (open) setTimeout(() => searchRef.current?.focus(), 50);
  }, [open]);

  const handleSelect = (fqbn, mcu) => {
    // P1 FQBN: normalize before bubbling up
    const normalized = normalizeFQBN(fqbn);
    const resolvedMcu = mcu || mcuFromFQBN(normalized);
    onSelect(normalized, resolvedMcu);
    handleClose();
  };

  const installedSet = new Set(installedPlatforms);
  const isInstalled = (fqbn) => {
    const platform = fqbn.split(':').slice(0, 2).join(':');
    return installedSet.has(platform);
  };

  // ── Installed-platform board groups (Arduino-IDE-style full list) ──
  const dynamicGroups = useMemo(() => {
    if (!available.length) return [];
    const byPlatform = new Map();
    for (const b of available) {
      const plat = b.platform || b.fqbn.split(':').slice(0, 2).join(':');
      if (!byPlatform.has(plat)) byPlatform.set(plat, []);
      byPlatform.get(plat).push({
        label: b.name || friendlyName(b.fqbn),
        fqbn:  b.fqbn,
        mcu:   mcuFromFQBN(b.fqbn),
        group: plat,
        version: b.version || '',
      });
    }
    return Array.from(byPlatform.entries())
      .sort((a, b) => a[0].localeCompare(b[0]))
      .map(([plat, items]) => ({
        group: plat,
        version: items[0]?.version || '',
        items: items.sort((a, b) => a.label.localeCompare(b.label)),
      }));
  }, [available]);

  // Search covers both installed boards and the curated fallback list
  const searchUniverse = useMemo(() => {
    const seen = new Set();
    const out = [];
    for (const g of dynamicGroups) {
      for (const b of g.items) {
        if (!seen.has(b.fqbn)) { seen.add(b.fqbn); out.push({ ...b, group: g.group }); }
      }
    }
    for (const g of BOARD_GROUPS) {
      for (const b of g.items) {
        if (!seen.has(b.fqbn)) { seen.add(b.fqbn); out.push({ ...b, group: g.group }); }
      }
    }
    return out;
  }, [dynamicGroups]);

  // Build filtered list
  const filtered = query.trim()
    ? searchUniverse.filter(b =>
        b.label.toLowerCase().includes(query.toLowerCase()) ||
        b.fqbn.toLowerCase().includes(query.toLowerCase()) ||
        b.group.toLowerCase().includes(query.toLowerCase())
      )
    : null;

  // Recent boards not in main list
  const recentBoards = recents
    .filter(fqbn => fqbn !== selectedFqbn)
    .map(fqbn => {
      const found = searchUniverse.find(b => b.fqbn === fqbn);
      return found || { fqbn, label: friendlyName(fqbn), mcu: mcuFromFQBN(fqbn), group: 'Recent' };
    })
    .slice(0, 4);

  const portalContent = open ? (
    <div
      ref={dropRef}
      className="bd-portal"
      style={{ top: pos.top, left: pos.left, width: pos.width, pointerEvents: 'all' }}
    >
      {/* Search */}
      <div className="bd-search-wrap">
        <SearchIcon />
        <input
          ref={searchRef}
          type="text"
          className="bd-search"
          placeholder="Search boards…"
          value={query}
          onChange={e => setQuery(e.target.value)}
          onKeyDown={e => e.key === 'Escape' && handleClose()}
        />
      </div>

      <div className="bd-list">
        {filtered ? (
          /* Search results */
          filtered.length === 0
            ? <div className="bd-empty">No boards match "{query}"</div>
            : filtered.map(b => (
                <BoardItem key={b.fqbn} board={b}
                  selected={b.fqbn === selectedFqbn}
                  installed={isInstalled(b.fqbn)}
                  onSelect={handleSelect} />
              ))
        ) : (
          <>
            {/* Recent section */}
            {recentBoards.length > 0 && (
              <div className="bd-group">
                <div className="bd-group-label">Recent</div>
                {recentBoards.map(b => (
                  <BoardItem key={b.fqbn} board={b}
                    selected={b.fqbn === selectedFqbn}
                    installed={isInstalled(b.fqbn)}
                    onSelect={handleSelect} />
                ))}
                <div className="bd-group-sep" />
              </div>
            )}

            {/* Grouped boards — every board of every installed platform,
                grouped vendor → architecture (Arduino-IDE-style).
                Falls back to the curated list if the CLI returned nothing. */}
            {(dynamicGroups.length > 0 ? dynamicGroups : BOARD_GROUPS).map(g => (
              <div key={g.group} className="bd-group">
                <div className="bd-group-label">
                  <span className="bd-group-name">{g.group}</span>
                  {g.version && <span className="bd-group-ver">v{g.version}</span>}
                  <span className="bd-group-count">{g.items.length}</span>
                </div>
                {g.items.map(b => (
                  <BoardItem key={b.fqbn} board={b}
                    selected={b.fqbn === selectedFqbn}
                    installed={isInstalled(b.fqbn)}
                    onSelect={handleSelect} />
                ))}
              </div>
            ))}
          </>
        )}
      </div>

      {/* Footer */}
      <div className="bd-footer">
        {onDetectBoards && (
          <button className="bd-edit-btn" onClick={() => { handleClose(); onDetectBoards(); }}>
            <ChipIcon /> Detect installed boards…
          </button>
        )}
        <button className="bd-edit-btn" onClick={() => { handleClose(); onEditConfig(); }}>
          <GearIcon /> Configure bridge & settings…
        </button>
      </div>
    </div>
  ) : null;

  return (
    <>
      <button
        ref={triggerRef}
        className={`tb-board-btn ${open ? 'active' : ''}`}
        onClick={open ? handleClose : handleOpen}
        title={`Board: ${friendlyName(selectedFqbn) || selectedFqbn}\nFQBN: ${selectedFqbn}\nMCU: ${selectedMCU}`}
      >
        <BoardChipIcon />
        <span className="tb-board-label">{shortLabel}</span>
        <span className="tb-board-mcu">{selectedMCU}</span>
        <ChevronIcon open={open} />
      </button>

      {createPortal(portalContent, getPortalContainer())}
    </>
  );
}

// ── BoardItem ─────────────────────────────────────────────────────

function BoardItem({ board, selected, installed, onSelect }) {
  return (
    <button
      className={`bd-item ${selected ? 'selected' : ''} ${!installed && installed !== undefined ? 'not-installed' : ''}`}
      onClick={() => onSelect(board.fqbn, board.mcu)}
      title={`${board.fqbn}${!installed && installed !== undefined ? '\n(platform not installed)' : ''}`}
    >
      <span className="bd-item-label">{board.label}</span>
      <span className="bd-item-fqbn">{board.fqbn.split(':').pop()}</span>
      <span className="bd-item-right">
        {installed && !selected && <span className="bd-installed-dot" title="Platform installed" />}
        {selected && <CheckIcon />}
      </span>
    </button>
  );
}

// ── Icons ─────────────────────────────────────────────────────────
function BoardChipIcon() { return <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><rect x="5" y="5" width="14" height="14" rx="2"/><path d="M9 9h6M9 12h6M9 15h6"/></svg>; }
function ChevronIcon({ open }) { return <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" style={{ transform: open ? 'rotate(180deg)' : 'none', transition: 'transform 0.15s' }}><polyline points="6 9 12 15 18 9"/></svg>; }
function SearchIcon() { return <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" style={{flexShrink:0,color:'var(--text-dim)'}}><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>; }
function GearIcon() { return <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>; }
function ChipIcon() { return <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><rect x="9" y="9" width="6" height="6"/><path d="M3 9h2M3 15h2M19 9h2M19 15h2M9 3v2M15 3v2M9 19v2M15 19v2"/><rect x="5" y="5" width="14" height="14" rx="2"/></svg>; }
function CheckIcon() { return <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" style={{color:'var(--teal)',flexShrink:0}}><polyline points="20 6 9 17 4 12"/></svg>; }
