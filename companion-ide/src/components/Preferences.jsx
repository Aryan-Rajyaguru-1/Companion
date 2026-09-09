import { useState, useCallback } from 'react';
import { prefs } from '../utils/prefs';
import './Preferences.css';

const TABS = ['Upload', 'Compiler', 'Serial', 'Editor', 'Sketchbook', 'Performance'];

export default function Preferences({ onClose, onEvictCache, cacheStats, daemonRunning }) {
  const [tab,      setTab]      = useState('Upload');
  const [values,   setValues]   = useState(prefs.getAll());
  const [evicting, setEvicting] = useState(false);
  const [evictMsg, setEvictMsg] = useState(null);

  const set = useCallback((key, val) => setValues(p => ({ ...p, [key]: val })), []);

  const handleSave  = () => { prefs.setMany(values); onClose(values); };
  const handleReset = () => setValues(prefs.defaults);

  const handleEvict = async () => {
    setEvicting(true); setEvictMsg(null);
    const r = await onEvictCache?.();
    setEvicting(false);
    setEvictMsg(r?.success ? 'Cache cleared successfully.' : `Error: ${r?.error}`);
  };

  return (
    <div className="modal-backdrop" onClick={e => e.target === e.currentTarget && onClose(null)}>
      <div className="modal prefs-modal">
        <div className="modal-header">
          <span className="modal-title"><GearIcon /> Preferences</span>
          <button className="modal-close" onClick={() => onClose(null)}>✕</button>
        </div>

        <div className="prefs-tabs">
          {TABS.map(t => (
            <button key={t} className={`prefs-tab ${tab === t ? 'active' : ''}`}
              onClick={() => setTab(t)}>{t}</button>
          ))}
        </div>

        <div className="prefs-body">

          {tab === 'Upload' && (
            <div className="prefs-section">
              <div className="prefs-title">Upload Settings</div>
              <PrefToggle label="Auto-verify before upload"
                desc="Compile before uploading (arduino.upload.autoVerify)."
                value={values['arduino.upload.autoVerify']}
                onChange={v => set('arduino.upload.autoVerify', v)} />
              <PrefToggle label="Verbose upload output"
                desc="Show full command output during upload."
                value={values['arduino.upload.verbose']}
                onChange={v => set('arduino.upload.verbose', v)} />
              <PrefToggle label="Verify after upload"
                desc="Read back flash and compare after programming completes."
                value={values['arduino.upload.verifyAfterUpload']}
                onChange={v => set('arduino.upload.verifyAfterUpload', v)} />
            </div>
          )}

          {tab === 'Compiler' && (
            <div className="prefs-section">
              <div className="prefs-title">Compiler Settings</div>
              <PrefToggle label="Verbose compile output"
                desc="Show full gcc command lines during compilation."
                value={values['arduino.compile.verbose']}
                onChange={v => set('arduino.compile.verbose', v)} />
              <PrefSelect label="Compiler warnings"
                desc="Controls -Wall -Wextra flags (arduino.compile.warnings)."
                value={values['arduino.compile.warnings']}
                onChange={v => set('arduino.compile.warnings', v)}
                options={[
                  { value: 'none',    label: 'None — suppress all warnings' },
                  { value: 'default', label: 'Default' },
                  { value: 'more',    label: 'More  (-Wall)' },
                  { value: 'all',     label: 'All   (-Wall -Wextra)' },
                ]} />
            </div>
          )}

          {tab === 'Serial' && (
            <div className="prefs-section">
              <div className="prefs-title">Serial Monitor Defaults</div>
              <PrefSelect label="Default baud rate"
                value={String(values['arduino.serial.baud'])}
                onChange={v => set('arduino.serial.baud', Number(v))}
                options={[300,1200,2400,4800,9600,19200,38400,57600,74880,
                          115200,230400,250000,460800,921600,2000000]
                  .map(b => ({ value: String(b), label: b.toLocaleString() }))} />
              <PrefSelect label="Default line ending"
                value={values['arduino.serial.lineEnding']}
                onChange={v => set('arduino.serial.lineEnding', v)}
                options={[
                  { value: '',     label: 'No line ending' },
                  { value: '\n',   label: 'Newline (\\n)' },
                  { value: '\r',   label: 'Carriage Return (\\r)' },
                  { value: '\r\n', label: 'Both NL & CR' },
                ]} />
              <PrefToggle label="Show timestamps"
                desc="Prepend HH:MM:SS.mmm timestamp to each serial line."
                value={values['arduino.serial.timestamp']}
                onChange={v => set('arduino.serial.timestamp', v)} />
              <PrefToggle label="Auto-scroll"
                desc="Scroll to the latest output automatically."
                value={values['arduino.serial.autoscroll']}
                onChange={v => set('arduino.serial.autoscroll', v)} />
            </div>
          )}

          {tab === 'Editor' && (
            <div className="prefs-section">
              <div className="prefs-title">Editor Settings</div>
              <PrefNumber label="Font size (px)"
                desc="Editor font size in pixels."
                value={values['arduino.editor.fontSize']}
                onChange={v => set('arduino.editor.fontSize', Number(v))}
                min={8} max={32} />
              <PrefToggle label="Word wrap"
                desc="Wrap long lines instead of horizontal scrolling."
                value={values['arduino.editor.wordWrap']}
                onChange={v => set('arduino.editor.wordWrap', v)} />
              <PrefToggle label="Show minimap"
                desc="Show the code minimap scrollbar on the right."
                value={values['arduino.editor.minimap']}
                onChange={v => set('arduino.editor.minimap', v)} />
              <PrefToggle label="Bracket pair colorization"
                desc="Colorize matching brackets for easier reading."
                value={values['arduino.editor.bracketPairs']}
                onChange={v => set('arduino.editor.bracketPairs', v)} />
            </div>
          )}

          {tab === 'Sketchbook' && (
            <div className="prefs-section">
              <div className="prefs-title">Sketchbook Settings</div>
              <PrefToggle label="Show all files in sidebar"
                desc="Show non-.ino files (headers, JSON, markdown) in the sketch sidebar."
                value={values['arduino.sketchbook.showAllFiles']}
                onChange={v => set('arduino.sketchbook.showAllFiles', v)} />
              <PrefText label="Sketchbook location"
                desc="Default folder for saving sketches. Leave blank to use system default."
                value={values['arduino.sketchbook.path']}
                onChange={v => set('arduino.sketchbook.path', v)}
                placeholder="~/CompanionIDESketches" />
              <PrefToggle label="Show template picker on New Sketch"
                desc="Open the template gallery when creating a new sketch."
                value={values['companion.templates.showOnNew']}
                onChange={v => set('companion.templates.showOnNew', v)} />
            </div>
          )}

          {/* ── P2 Performance: Daemon + Cache ─────────── */}
          {tab === 'Performance' && (
            <div className="prefs-section">
              <div className="prefs-title">Performance — CLI Daemon</div>
              <div className="prefs-info-box">
                The <strong>CLI Daemon</strong> keeps the companion-cli process running
                between compiles, so the build cache stays warm in memory.
                This typically reduces compile time by <strong>~70%</strong> on 2nd+ runs.
              </div>
              <PrefToggle label="Enable CLI daemon"
                desc="Spawn a long-lived daemon when the IDE opens (companion.daemon.enabled)."
                value={values['companion.daemon.enabled']}
                onChange={v => set('companion.daemon.enabled', v)} />
              <PrefToggle label="Auto-restart daemon on crash"
                desc="Automatically restart if the daemon exits unexpectedly."
                value={values['companion.daemon.autoRestart']}
                onChange={v => set('companion.daemon.autoRestart', v)} />

              <div className="prefs-status-row">
                <span className="prefs-status-label">Current daemon status:</span>
                <span className={`prefs-status-badge ${daemonRunning ? 'running' : 'stopped'}`}>
                  <span className={`status-dot ${daemonRunning ? 'connected' : 'disconnected'}`} />
                  {daemonRunning ? 'Running' : 'Not running'}
                </span>
              </div>

              <div className="prefs-divider" />
              <div className="prefs-subtitle">Build Cache</div>
              <div className="prefs-info-box">
                Object files are cached by <em>content hash</em> — only changed source
                files are recompiled. Core libraries persist across IDE restarts.
              </div>

              <PrefToggle label="Enable build cache"
                desc="Cache compiled objects between runs (companion.cache.enabled)."
                value={values['companion.cache.enabled']}
                onChange={v => set('companion.cache.enabled', v)} />
              <PrefNumber label="Max cache size (MB)"
                desc="Oldest objects are evicted when this limit is exceeded."
                value={values['companion.cache.maxSizeMB']}
                onChange={v => set('companion.cache.maxSizeMB', Number(v))}
                min={64} max={4096} />
              <PrefNumber label="Max cache age (days)"
                desc="Objects older than this are removed on next eviction pass."
                value={values['companion.cache.maxAgeDays']}
                onChange={v => set('companion.cache.maxAgeDays', Number(v))}
                min={1} max={90} />

              {cacheStats && (
                <div className="prefs-cache-stats">
                  <div className="pcs-item"><span>Objects</span><strong>{cacheStats.ObjectCount ?? 0}</strong></div>
                  <div className="pcs-item"><span>Core libs</span><strong>{cacheStats.CoreCount ?? 0}</strong></div>
                  <div className="pcs-item"><span>Size</span><strong>{(cacheStats.TotalSizeMB ?? 0).toFixed(1)} MB</strong></div>
                </div>
              )}

              <div className="prefs-cache-actions">
                <button className="btn btn-sm" onClick={handleEvict}
                  disabled={evicting || !daemonRunning} title={!daemonRunning ? 'Daemon must be running' : ''}>
                  {evicting ? '⟳ Clearing…' : '⊘ Clear Cache Now'}
                </button>
                {evictMsg && <span className="prefs-evict-msg">{evictMsg}</span>}
                {!daemonRunning && (
                  <span className="prefs-hint">Start the daemon to manage cache</span>
                )}
              </div>
            </div>
          )}
        </div>

        <div className="prefs-footer">
          <button className="btn" onClick={handleReset}>Reset to Defaults</button>
          <div style={{ flex: 1 }} />
          <button className="btn" onClick={() => onClose(null)}>Cancel</button>
          <button className="btn btn-primary" onClick={handleSave}>Save</button>
        </div>
      </div>
    </div>
  );
}

// ── Pref field primitives ────────────────────────────────────────

function PrefToggle({ label, desc, value, onChange }) {
  return (
    <div className="pref-row">
      <div className="pref-label-col">
        <span className="pref-label">{label}</span>
        {desc && <span className="pref-desc">{desc}</span>}
      </div>
      <div className="pref-control">
        <button className={`toggle ${value ? 'on' : 'off'}`}
          onClick={() => onChange(!value)} role="switch" aria-checked={value}>
          <span className="toggle-knob" />
        </button>
      </div>
    </div>
  );
}

function PrefSelect({ label, desc, value, onChange, options }) {
  return (
    <div className="pref-row">
      <div className="pref-label-col">
        <span className="pref-label">{label}</span>
        {desc && <span className="pref-desc">{desc}</span>}
      </div>
      <div className="pref-control">
        <select className="pref-select" value={value} onChange={e => onChange(e.target.value)}>
          {options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
      </div>
    </div>
  );
}

function PrefNumber({ label, desc, value, onChange, min, max }) {
  return (
    <div className="pref-row">
      <div className="pref-label-col">
        <span className="pref-label">{label}</span>
        {desc && <span className="pref-desc">{desc}</span>}
      </div>
      <div className="pref-control">
        <input type="number" className="pref-input" value={value}
          min={min} max={max} onChange={e => onChange(e.target.value)} />
      </div>
    </div>
  );
}

function PrefText({ label, desc, value, onChange, placeholder }) {
  return (
    <div className="pref-row">
      <div className="pref-label-col">
        <span className="pref-label">{label}</span>
        {desc && <span className="pref-desc">{desc}</span>}
      </div>
      <div className="pref-control pref-control-wide">
        <input type="text" className="pref-input pref-input-wide"
          value={value} onChange={e => onChange(e.target.value)} placeholder={placeholder} />
      </div>
    </div>
  );
}

function GearIcon() {
  return <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
    stroke="currentColor" strokeWidth="2" strokeLinecap="round">
    <circle cx="12" cy="12" r="3"/>
    <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>
  </svg>;
}
