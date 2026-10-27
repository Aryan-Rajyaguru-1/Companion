import { useEffect, useState } from 'react';
import './BridgeSettings.css';

const MCU_OPTIONS = [
  { value: 'esp32',   label: 'ESP32 / ESP32-S3 / ESP32-C3',  note: 'uses esptool.py' },
  { value: 'esp8266', label: 'ESP8266 / NodeMCU',             note: 'uses esptool.py' },
  { value: 'avr',     label: 'AVR — Arduino Uno/Mega/Nano',   note: 'uses avrdude' },
  { value: 'stm32',   label: 'STM32 (UART bootloader)',       note: 'built-in AN3155' },
  { value: 'generic', label: 'Generic / Custom bootloader',   note: 'raw byte stream' },
];

const BAUD_RATES = [9600, 19200, 38400, 57600, 74880, 115200, 230400,
                    250000, 460800, 500000, 921600, 1000000];

export default function BridgeSettings({
  host, port, mcu, baud,
  onHostChange, onPortChange, onMCUChange, onBaudChange,
  onPing, onClose,
  otaEnabled = false, otaPassword = '',
  onOTAToggleChange, onOTAPasswordChange, onOpen,
}) {
  const [localHost, setLocalHost] = useState(host);
  const [localPort, setLocalPort] = useState(port);
  const [localMCU,  setLocalMCU]  = useState(mcu);
  const [localBaud, setLocalBaud] = useState(baud);
  const [pinging,   setPinging]   = useState(false);
  const [pingResult,setPingResult]= useState(null);
  const [discovering,  setDiscovering]  = useState(false);
  const [discovered,   setDiscovered]   = useState([]);
  const [discoverError,setDiscoverError]= useState(null);
  // The existing key is never fetched into the renderer. We only show whether
  // one is configured; a newly typed key is written straight through the CLI.
  const [keyStatus,  setKeyStatus]  = useState('unknown');
  const [keyDraft,   setKeyDraft]   = useState('');
  const [keySaving,  setKeySaving]  = useState(false);
  const [keyError,   setKeyError]   = useState(null);

  const handleDiscover = async () => {
    setDiscovering(true);
    setDiscoverError(null);
    try {
      const r = await window.electronAPI?.otaDiscover?.(5000);
      if (r?.success) {
        // Keep only real IPs (OTA targets); use the bridge TCP port the
        // user entered for the connection (OTA port 3232 ≠ bridge 3333).
        const devs = (r.devices || []).filter(d => /^\d+\.\d+\.\d+\.\d+$/.test(d.host || ''));
        setDiscovered(devs);
        if (!devs.length) setDiscoverError('No OTA devices found — is the bridge on this network?');
      } else {
        setDiscoverError('Discovery failed');
      }
    } catch (e) {
      setDiscoverError('Discovery failed');
    } finally {
      setDiscovering(false);
    }
  };

  useEffect(() => { onOpen?.(); /* eslint-disable-line react-hooks/exhaustive-deps */ }, []);

  const loadKeyStatus = async () => {
    try {
      const value = await window.electronAPI?.companionConfigGet?.('bridge.key');
      setKeyStatus(value === '<set>' ? 'set' : value === '<unset>' ? 'unset' : 'unknown');
    } catch {
      setKeyStatus('unknown');
    }
  };

  useEffect(() => {
    loadKeyStatus(); /* eslint-disable-line react-hooks/exhaustive-deps */
  }, []);

  const saveKey = async () => {
    // Pasting a key often carries a trailing newline/space. The CLI rejects
    // surrounding whitespace in bridge.key, so trim the draft before saving.
    const value = keyDraft.trim();
    if (!value) {
      setKeyError('Enter the BRIDGE_KEY from the bridge firmware.');
      return false;
    }
    setKeySaving(true);
    setKeyError(null);
    try {
      const r = await window.electronAPI?.companionConfigSet?.('bridge.key', value);
      if (r?.success) {
        setKeyDraft('');
        // Re-read the effective value: COMPANION_BRIDGE_KEY can override the
        // file and keeps the status "set" even after the saved key is cleared.
        await loadKeyStatus();
        return true;
      }
      setKeyError(r?.error || 'Could not save the bridge key.');
    } catch (e) {
      setKeyError(e?.message || 'Could not save the bridge key.');
    } finally {
      setKeySaving(false);
    }
    return false;
  };

  const clearKey = async () => {
    setKeySaving(true);
    setKeyError(null);
    try {
      const r = await window.electronAPI?.companionConfigSet?.('bridge.key', '');
      if (r?.success) {
        setKeyDraft('');
        await loadKeyStatus();
      } else {
        setKeyError(r?.error || 'Could not clear the bridge key.');
      }
    } catch (e) {
      setKeyError(e?.message || 'Could not clear the bridge key.');
    } finally {
      setKeySaving(false);
    }
  };

  const handleSave = async () => {
    if (keyDraft.trim() && !(await saveKey())) return;
    onHostChange(localHost);
    onPortChange(Number(localPort));
    onMCUChange(localMCU);
    onBaudChange(Number(localBaud));
    onClose();
  };

  const handlePing = async () => {
    setPinging(true);
    setPingResult(null);
    // Temporarily apply values for ping
    onHostChange(localHost);
    onPortChange(Number(localPort));
    await new Promise(r => setTimeout(r, 50));
    const r = await window.electronAPI?.bridgeQuery({ host: localHost, port: Number(localPort) });
    setPinging(false);
    setPingResult(r);
  };

  const selectedMCU = MCU_OPTIONS.find(m => m.value === localMCU);

  return (
    <div className="modal-backdrop" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="modal bridge-modal">
        <div className="modal-header">
          <span className="modal-title">
            <WifiIcon /> WiFi Bridge Settings
          </span>
          <button className="modal-close" onClick={onClose}>✕</button>
        </div>

        {/* ── Connection ──────────────────────────────────────── */}
        <section className="bs-section">
          <div className="bs-section-title">Connection</div>

          <div className="bs-row">
            <div className="bs-field bs-field-grow">
              <label>Bridge Address (IP or Hostname)</label>
              <input
                type="text"
                value={localHost}
                onChange={e => setLocalHost(e.target.value)}
                placeholder="192.168.4.1"
                spellCheck={false}
              />
              <div className="bs-hint">
                Default: <code>192.168.4.1</code> when your laptop is on the bridge's own AP (the <code>AP_SSID</code>/<code>AP_PASS</code> from <code>config.local.h</code>; there is no default password) — on a router, use the board IP or <code>companion-XXXXXX.local</code>
              </div>
            </div>

            <div className="bs-field bs-field-port">
              <label>TCP Port</label>
              <input
                type="number"
                value={localPort}
                onChange={e => setLocalPort(e.target.value)}
                min={1}
                max={65535}
              />
            </div>
          </div>

          {/* Ping */}
          <div className="bs-ping-row">
            <button
              className="btn"
              onClick={handlePing}
              disabled={pinging}
            >
              {pinging ? <span className="spin">⟳</span> : <PingIcon />}
              {pinging ? 'Pinging…' : 'Test Connection'}
            </button>
            <button
              className="btn"
              onClick={handleDiscover}
              disabled={discovering}
              title="Scan the network (mDNS _arduino._tcp) for OTA devices"
            >
              {discovering ? <span className="spin">⟳</span> : <WifiIcon />}
              {discovering ? 'Discovering…' : 'Discover OTA devices'}
            </button>

            {pingResult && (
              <div className={`bs-ping-result ${pingResult.success ? 'ok' : 'fail'}`}>
                {pingResult.success
                  ? <><span className="status-dot connected" />{pingResult.info}</>
                  : <><span className="status-dot disconnected" />✗ {pingResult.error}</>}
              </div>
            )}
            {discoverError && (
              <div className="bs-ping-result fail">
                <><span className="status-dot disconnected" />✗ {discoverError}</>
              </div>
            )}
            {discovered.length > 0 && (
              <div className="bs-ota-devices">
                <div className="bs-section-title" style={{ marginTop: 8 }}>OTA devices on this network</div>
                {discovered.map((d, i) => (
                  <button key={`${d.host}:${d.port}-${i}`} className="bs-ota-device"
                    onClick={() => setLocalHost(d.host)}
                    title={`Use ${d.host} as the Bridge/OTA address`}>
                    <span className="status-dot connected" />
                    <span className="bs-ota-name">{d.name || d.host}</span>
                    <span className="bs-ota-host">{d.host}:{d.port || 3232}</span>
                    <span className="bs-ota-pick">Use</span>
                  </button>
                ))}
                <div className="bs-hint">Click a device to use its IP as the Bridge Address (also the OTA target).</div>
              </div>
            )}
          </div>
        </section>

        {/* ── Bridge authentication ───────────────────────────── */}
        <section className="bs-section">
          <div className="bs-section-title">Bridge Security — LAN Authentication</div>
          <div className="bs-row">
            <div className="bs-field bs-field-grow">
              <label>Bridge Key</label>
              <div className="bs-key-row">
                <input
                  type="password"
                  value={keyDraft}
                  onChange={e => setKeyDraft(e.target.value)}
                  placeholder={keyStatus === 'set'
                    ? 'Key is set — enter a new key to replace it'
                    : 'Paste the BRIDGE_KEY from config.local.h'}
                  autoComplete="new-password"
                  spellCheck={false}
                  onKeyDown={e => { if (e.key === 'Enter') saveKey(); }}
                />
                <button
                  className="btn"
                  onClick={saveKey}
                  disabled={keySaving || !keyDraft.trim()}
                >
                  {keySaving ? 'Saving…' : 'Save key'}
                </button>
                <button
                  className="btn"
                  onClick={clearKey}
                  disabled={keySaving || keyStatus !== 'set'}
                  title="Remove the saved bridge key from this computer"
                >
                  Clear
                </button>
              </div>
              <div className="bs-hint">
                Status:{' '}
                <span className={`bs-key-status ${keyStatus}`}>
                  {keyStatus === 'set' ? '✓ configured' : keyStatus === 'unset' ? '⚠ not configured' : 'unknown'}
                </span>
                {' '}The key must match <code>BRIDGE_KEY</code> compiled into the bridge.
                It is stored in the CLI's owner-only config; the IDE renderer never
                reads it back. A bridge without a key disables its LAN TCP server
                but keeps LAN OTA recovery available.
                <br />
                Generate one with <code>openssl rand -hex 32</code>.{' '}
                <code>COMPANION_BRIDGE_KEY</code> overrides the saved value.
              </div>
              {keyError && (
                <div className="bs-ping-result fail">
                  <><span className="status-dot disconnected" />✗ {keyError}</>
                </div>
              )}
            </div>
          </div>
        </section>

        {/* ── Target MCU ──────────────────────────────────────── */}
        <section className="bs-section">
          <div className="bs-section-title">Target MCU Family</div>
          <div className="bs-mcu-grid">
            {MCU_OPTIONS.map(opt => (
              <button
                key={opt.value}
                className={`bs-mcu-card ${localMCU === opt.value ? 'selected' : ''}`}
                onClick={() => setLocalMCU(opt.value)}
              >
                <span className="bs-mcu-label">{opt.label}</span>
                <span className="bs-mcu-note">{opt.note}</span>
              </button>
            ))}
          </div>
        </section>

        {/* ── Upload baud ─────────────────────────────────────── */}
        <section className="bs-section">
          <div className="bs-section-title">Upload Baud Rate</div>
          <div className="bs-baud-row">
            <select
              value={localBaud}
              onChange={e => setLocalBaud(e.target.value)}
              className="bs-baud-select"
            >
              {BAUD_RATES.map(b => (
                <option key={b} value={b}>{b.toLocaleString()} baud</option>
              ))}
            </select>
            <div className="bs-hint" style={{ marginTop: 6 }}>
              {localMCU === 'esp32' || localMCU === 'esp8266'
                ? 'ESP: 460800 recommended for fast flashing'
                : localMCU === 'stm32'
                ? 'STM32: 115200 is reliable; increase carefully'
                : localMCU === 'avr'
                ? 'AVR bootloader is fixed — match your board\'s bootloader baud'
                : 'Match your custom bootloader\'s expected baud rate'}
            </div>
          </div>
        </section>

        {/* ── Wireless OTA (Phase 4c) ─────────────────────────── */}
        <section className="bs-section">
          <div className="bs-section-title">Wireless OTA — ArduinoOTA</div>
          <div className="bs-row bs-ota-row">
            <label className="bs-check">
              <input
                type="checkbox"
                checked={otaEnabled}
                onChange={e => onOTAToggleChange?.(e.target.checked)}
                disabled={!onOTAToggleChange}
              />
              <span>Prefer over-the-air upload for ESP32 / ESP8266</span>
            </label>
            <div className="bs-hint">
              Flashes the sketch directly over WiFi to a device running{' '}
              <code>ArduinoOTA.begin()</code> / <code>setPassword()</code> — no bridge
              cable needed. Persisted per-sketch in <code>sketch.yaml</code> (ota: true).
              The Bridge Address above is the OTA target IP.
            </div>
          </div>
          {otaEnabled && (
            <div className="bs-row">
              <div className="bs-field bs-field-grow">
                <label>OTA Password (optional)</label>
                <input
                  type="password"
                  value={otaPassword}
                  onChange={e => onOTAPasswordChange?.(e.target.value)}
                  placeholder="Leave empty if the device has no password"
                  autoComplete="off"
                />
              </div>
            </div>
          )}
        </section>

        {/* ── Wiring guide ────────────────────────────────────── */}
        <section className="bs-section">
          <div className="bs-section-title">Wiring Guide — ESP32 bridge → target</div>
          <table className="bs-table">
            <thead>
              <tr>
                <th>ESP32 Pin</th>
                <th>{selectedMCU?.label?.split('—')[0]?.trim() || 'Target'} Pin</th>
                <th>Purpose</th>
              </tr>
            </thead>
            <tbody>
              <tr><td>GPIO17 (TX2)</td><td>RX</td><td>UART data out</td></tr>
              <tr><td>GPIO16 (RX2)</td><td>TX</td><td>UART data in</td></tr>
              <tr><td>GPIO4</td>
                  <td>{localMCU === 'stm32' ? 'NRST' : 'EN / RST'}</td>
                  <td>Reset line</td></tr>
              <tr><td>GPIO5</td>
                  <td>{localMCU === 'stm32' ? 'BOOT0' : localMCU === 'avr' ? '— (unused)' : 'GPIO0 / BOOT'}</td>
                  <td>{localMCU === 'avr' ? 'Not used for AVR' : 'Bootloader entry'}</td></tr>
              <tr><td>GND</td><td>GND</td><td>Common ground ⚠ required</td></tr>
            </tbody>
          </table>
        </section>

        {/* ── Footer ──────────────────────────────────────────── */}
        <div className="bs-footer">
          <button className="btn" onClick={onClose}>Cancel</button>
          <button className="btn primary" onClick={handleSave}>Save Settings</button>
        </div>
      </div>
    </div>
  );
}

function WifiIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M5 12.55a11 11 0 0 1 14.08 0" />
      <path d="M1.42 9a16 16 0 0 1 21.16 0" />
      <path d="M8.53 16.11a6 6 0 0 1 6.95 0" />
      <line x1="12" y1="20" x2="12.01" y2="20" strokeWidth="3" />
    </svg>
  );
}

function PingIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
      <circle cx="12" cy="12" r="2" />
      <path d="M12 2a10 10 0 0 1 0 20" opacity=".3"/>
      <path d="M12 6a6 6 0 0 1 0 12" opacity=".6"/>
    </svg>
  );
}
