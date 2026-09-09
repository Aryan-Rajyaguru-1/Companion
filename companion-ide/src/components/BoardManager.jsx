/**
 * BoardManager.jsx — reference-aligned implementation
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import './BoardManager.css';

const PLATFORM_META = {
  'arduino:avr': { maintainer: 'Arduino', official: true, docs: 'https://docs.arduino.cc/hardware/uno-rev3' },
  'arduino:samd': { maintainer: 'Arduino', official: true, docs: 'https://docs.arduino.cc/hardware/mkr-wifi-1010' },
  'arduino:megaavr': { maintainer: 'Arduino', official: true, docs: 'https://docs.arduino.cc/hardware/uno-wifi-rev2' },
  'arduino:mbed_giga': { maintainer: 'Arduino', official: true, docs: 'https://docs.arduino.cc/hardware/giga-r1-wifi' },
  'esp32:esp32': { maintainer: 'Espressif', official: false, docs: 'https://docs.espressif.com/projects/arduino-esp32' },
  'esp8266:esp8266': { maintainer: 'ESP8266 Community', official: false, docs: 'https://arduino-esp8266.readthedocs.io' },
  'stmicroelectronics:stm32': { maintainer: 'STMicroelectronics', official: false, docs: 'https://github.com/stm32duino/Arduino_Core_STM32' },
};

export default function BoardManager({ onClose }) {
  const [query, setQuery] = useState('');
  const [category, setCategory] = useState('all');
  const [packages, setPackages] = useState([]);
  const [installed, setInstalled] = useState([]);
  const [indexMissing, setIndexMissing] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [updating, setUpdating] = useState(false);
  const [output, setOutput] = useState('');
  const [activeId, setActiveId] = useState(null);
  const [selectedVers, setSelectedVers] = useState({});
  const [unconfirm, setUnconfirm] = useState(null);

  const outputRef = useRef(null);
  const searchRef = useRef(null);

  const emit = (text) => setOutput(p => p + text);

  const getVendorID = (pkg) => {
    const name = pkg?.vendorID || pkg?.VendorID || pkg?.name || '';
    return String(name).toLowerCase().trim().replace(/\s+/g, '-');
  };

  const getPlatformId = (pkg) => `${getVendorID(pkg)}:${pkg?.architecture || pkg?.Architecture || ''}`;

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    setIndexMissing(false);

    try {
      let pkgs = [];
      try {
        const result = await window.electronAPI?.searchPackages?.('');
        if (Array.isArray(result)) pkgs = result;
      } catch (e) {
        console.warn('searchPackages failed:', e);
      }

      if (pkgs.length === 0) {
        setIndexMissing(true);
        setPackages([]);
        setInstalled([]);
        setLoading(false);
        return;
      }

      const installedRaw = await window.electronAPI?.getBoards?.() || [];
      const mapped = (Array.isArray(installedRaw) ? installedRaw : []).map(c => ({
        id: c.ID || c.id || `${c.name || ''}:${c.architecture || ''}`,
        version: c.Version || c.version || '',
      })).filter(c => c.id && c.id !== ':');

      setPackages(pkgs);
      setInstalled(mapped);
      console.log(`Loaded ${pkgs.length} packages, ${mapped.length} installed`);
    } catch (e) {
      setError('Failed to load platforms. Check CLI connection.');
      console.error('loadData error:', e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
    setTimeout(() => searchRef.current?.focus(), 80);
  }, [loadData]);

  useEffect(() => { outputRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [output]);

  useEffect(() => {
    const h = (e) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', h);
    return () => window.removeEventListener('keydown', h);
  }, [onClose]);

  const installedMap = {};
  installed.forEach(i => { installedMap[i.id] = i.version; });

  const getInstalledVersion = (id) => installedMap[id] || null;
  const isInstalled = (id) => id in installedMap;

  const displayItems = packages.filter(p => {
    if (!p?.name) return false;
    const q = query.toLowerCase();
    const matchQ = !q || p.name.toLowerCase().includes(q) || p.maintainer?.toLowerCase().includes(q) || p.architecture?.toLowerCase().includes(q);
    if (!matchQ) return false;

    const platformId = getPlatformId(p);
    const meta = PLATFORM_META[platformId];

    if (category === 'installed') return isInstalled(platformId);
    if (category === 'official') return meta?.official === true;
    if (category === 'community') return meta?.official === false;
    return true;
  });

  const handleInstall = async (pkg) => {
    const platformId = getPlatformId(pkg);
    const version = selectedVers[platformId] || pkg.version || pkg.Version || '';
    const installId = version ? `${platformId}@${version}` : platformId;

    setActiveId(platformId);
    setOutput('');
    emit(`» Installing ${installId}…\n`);
    setUpdating(true);

    const r = await window.electronAPI?.installCore?.(installId, emit);
    setUpdating(false);
    setActiveId(null);

    if (r?.success) {
      emit(`✓ Installed ${installId}\n`);
      await loadData();
    } else {
      emit(`✗ Failed: ${r?.error || 'unknown error'}\n`);
    }
  };

  const handleRemove = async (platformId) => {
    if (unconfirm !== platformId) { setUnconfirm(platformId); return; }
    setUnconfirm(null);
    setActiveId(platformId);
    setOutput('');
    emit(`» Removing ${platformId}…\n`);
    setUpdating(true);

    const r = await window.electronAPI?.installCore?.(`--uninstall ${platformId}`, emit);
    setUpdating(false);
    setActiveId(null);
    emit(r?.success ? `✓ Removed ${platformId}\n` : `✗ Failed: ${r?.error}\n`);
    await loadData();
  };

  const handleUpdateIndex = async () => {
    setOutput('');
    emit('» Updating board index…\n');
    setUpdating(true);
    try {
      const r = await window.electronAPI?.updateIndex?.();
      if (r?.success === false) {
        emit(`✗ Update failed: ${r.error || 'unknown error'}\n`);
      } else {
        emit('✓ Board index updated\n');
        setIndexMissing(false);
      }
    } catch (e) {
      emit(`✗ Update failed: ${e.message}\n`);
    } finally {
      setUpdating(false);
    }
    await loadData();
  };

  const counts = {
    all: packages.length,
    installed: packages.filter(p => isInstalled(getPlatformId(p))).length,
    official: packages.filter(p => PLATFORM_META[getPlatformId(p)]?.official === true).length,
    community: packages.filter(p => PLATFORM_META[getPlatformId(p)]?.official === false).length,
  };

  const showIndexPrompt = !loading && !error && indexMissing;
  const showEmptyPrompt = !loading && !error && !indexMissing && packages.length === 0;

  return (
    <div className="modal-backdrop" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="modal bm-modal">
        <div className="modal-header">
          <span className="modal-title"><BoardsIcon /> Board Manager</span>
          <div className="bm-header-actions">
            <button className="btn btn-sm" onClick={handleUpdateIndex} disabled={updating}>
              {updating ? '⟳' : '↺'} Update Index
            </button>
            <button className="modal-close" onClick={onClose}>✕</button>
          </div>
        </div>

        <div className="bm-toolbar">
          <div className="bm-search-wrap">
            <SearchIcon />
            <input
              ref={searchRef}
              className="bm-search"
              type="search"
              placeholder="Search platforms…"
              value={query}
              onChange={e => setQuery(e.target.value)}
            />
          </div>
          <div className="bm-cats">
            {['all', 'installed', 'official', 'community'].map(c => (
              <button
                key={c}
                className={`bm-cat ${category === c ? 'active' : ''}`}
                onClick={() => setCategory(c)}
              >
                {c.charAt(0).toUpperCase() + c.slice(1)}
                <span className="bm-cat-count">{counts[c]}</span>
              </button>
            ))}
          </div>
        </div>

        <div className="bm-body">
          <div className="bm-list">
            {loading && <div className="bm-loading"><span className="spin">⟳</span> Loading platforms…</div>}
            {error && <div className="bm-error">{error}</div>}

            {showIndexPrompt && (
              <div className="bm-empty">
                <div style={{ marginBottom: '6px', fontSize: '13px', color: 'var(--text-dim)' }}>
                  Board index not downloaded yet.
                </div>
                <div style={{ marginBottom: '12px', fontSize: '12px', color: 'var(--text-dim)' }}>
                  Click Update Index to download the list of available platforms from Arduino's package registry.
                </div>
                <button className="btn btn-sm btn-primary" onClick={handleUpdateIndex} disabled={updating}>
                  {updating ? <><span className="spin">⟳</span> Downloading…</> : '↺ Update Index'}
                </button>
              </div>
            )}

            {showEmptyPrompt && (
              <div className="bm-empty">
                <div>No platforms found.</div>
                <button className="btn btn-sm" onClick={loadData} style={{ marginTop: '8px' }}>
                  Retry
                </button>
              </div>
            )}

            {!loading && !error && packages.length > 0 && displayItems.length === 0 && (
              <div className="bm-empty">
                {query ? `No platforms match "${query}"` : 'No platforms in this category.'}
                {query && (
                  <button className="btn btn-sm" onClick={() => setQuery('')} style={{ marginTop: '8px' }}>
                    Clear search
                  </button>
                )}
              </div>
            )}

            {displayItems.map(pkg => {
              const platformId = getPlatformId(pkg);
              const instVersion = getInstalledVersion(platformId);
              const isInst = !!instVersion;
              const meta = PLATFORM_META[platformId];
              const isActive = activeId === platformId;
              const confirming = unconfirm === platformId;
              const versions = pkg.versions || (pkg.version || pkg.Version ? [pkg.version || pkg.Version] : []);
              const selVer = selectedVers[platformId] || versions[0] || '';

              return (
                <div key={platformId} className={`bm-item ${isInst ? 'installed' : ''}`}>
                  <div className="bm-item-top">
                    <div className="bm-item-name-row">
                      <span className="bm-item-name">{pkg.name || platformId}</span>
                      {meta?.official && <span className="bm-official-badge">Official</span>}
                      {isInst && <span className="bm-installed-badge">✓ {instVersion}</span>}
                    </div>
                    <span className="bm-maintainer">{pkg.maintainer || pkg.Maintainer || meta?.maintainer || ''}</span>
                    <span className="bm-platform-id">{platformId}</span>
                  </div>

                  <div className="bm-item-actions">
                    {versions.length > 0 && (
                      <select
                        className="bm-ver-select"
                        value={selVer}
                        onChange={e => setSelectedVers(p => ({ ...p, [platformId]: e.target.value }))}
                      >
                        {versions.map(v => (
                          <option key={v} value={v}>
                            {v}{v === instVersion ? ' (installed)' : ''}
                          </option>
                        ))}
                      </select>
                    )}

                    {!isInst ? (
                      <button
                        className="btn btn-sm btn-primary bm-action-btn"
                        onClick={() => handleInstall(pkg)}
                        disabled={isActive || updating}
                      >
                        {isActive ? <><span className="spin">⟳</span> Installing…</> : 'Install'}
                      </button>
                    ) : (
                      <>
                        <button
                          className={`btn btn-sm bm-action-btn ${confirming ? 'bm-confirm-btn' : ''}`}
                          onClick={() => handleRemove(platformId)}
                          disabled={isActive || updating}
                        >
                          {confirming ? 'Confirm Remove' : isActive ? <><span className="spin">⟳</span> Removing…</> : 'Remove'}
                        </button>
                        {confirming && (
                          <button className="btn btn-sm" onClick={() => setUnconfirm(null)}>Cancel</button>
                        )}
                      </>
                    )}

                    {meta?.docs && (
                      <a
                        href={meta.docs}
                        target="_blank"
                        rel="noreferrer"
                        className="bm-docs-link"
                        title="Open documentation"
                      >
                        <DocsIcon />
                      </a>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          {output && (
            <div className="bm-output">
              <pre className="bm-output-pre">{output}</pre>
              <div ref={outputRef} />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function SearchIcon() { return <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" style={{flexShrink:0,color:'var(--text-dim)'}}><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>; }
function BoardsIcon() { return <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><rect x="2" y="2" width="20" height="20" rx="3"/><path d="M8 8h2M8 12h2M8 16h2M14 8h2M14 12h2M14 16h2"/></svg>; }
function DocsIcon() { return <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>; }