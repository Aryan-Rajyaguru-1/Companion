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

  useEffect(() => { onOpen?.(); /* eslint-disable-line react-hooks/exhaustive-deps */ }, []);

  const handleSave = () => {
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
                placeholder="esp32-bridge.local"
                spellCheck={false}
              />
              <div className="bs-hint">
                Default: <code>esp32-bridge.local</code> (auto-discovers ESP32) — or enter IP like <code>192.168.1.100</code>
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

            {pingResult && (
              <div className={`bs-ping-result ${pingResult.success ? 'ok' : 'fail'}`}>
                {pingResult.success
                  ? <><span className="status-dot connected" />{pingResult.info}</>
                  : <><span className="status-dot disconnected" />✗ {pingResult.error}</>}
              </div>
            )}
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
