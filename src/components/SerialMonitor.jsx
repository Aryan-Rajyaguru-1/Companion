/**
 * SerialMonitor.jsx
 * Bug fixes applied:
 *   #7  baudBuf sent AFTER bridgeConnect resolves (was sent before connect existed)
 *   #8  `incoming` dead variable removed; only messagesToLines path kept
 *   #9  ResizeObserver drives listHeight state so FixedSizeList responds to panel resize
 */

import { useState, useEffect, useRef, useCallback, memo } from 'react';
import { FixedSizeList as List } from 'react-window';
import { CommandHistory } from '../utils/CommandHistory';
import { messagesToLines, truncateLines, formatTimestamp } from '../utils/monitor-utils';
import './SerialMonitor.css';

const ROW_HEIGHT   = 18;
const HISTORY_SIZE = 100;

const BAUD_RATES = [300,1200,2400,4800,9600,14400,19200,28800,38400,57600,
                   74880,115200,230400,250000,460800,500000,921600,1000000,2000000];

const LINE_ENDINGS = [
  { label: 'No line ending', value: '' },
  { label: 'Newline (\\n)',   value: '\n' },
  { label: 'CR (\\r)',        value: '\r' },
  { label: 'CR+NL',          value: '\r\n' },
];

const Row = memo(({ index, style, data }) => {
  const { lines, showTimestamp } = data;
  const line = lines[index];
  if (!line) return <div style={style} />;
  return (
    <div style={style} className={`sm-row${line.sent ? ' sent' : ''}${line.info ? ' info' : ''}${line.error ? ' error' : ''}`}>
      {showTimestamp && line.timestamp && (
        <span className="sm-ts">{formatTimestamp(line.timestamp)}</span>
      )}
      <span className="sm-text">{line.message}</span>
    </div>
  );
});
Row.displayName = 'SerialRow';

export default function SerialMonitor({ host, port, onClose, onTearOff, standalone = false }) {
  const [lines,         setLines]         = useState([]);
  const [input,         setInput]         = useState('');
  const [connected,     setConnected]     = useState(false);
  const [connecting,    setConnecting]    = useState(false);
  const [autoscroll,    setAutoscroll]    = useState(true);
  const [showTimestamp, setShowTimestamp] = useState(false);
  const [lineEnd,       setLineEnd]       = useState('\n');
  const [baud,          setBaud]          = useState(115200);
  // BUG 9 FIX: listHeight is state driven by ResizeObserver
  const [listHeight,    setListHeight]    = useState(200);

  const listRef    = useRef(null);
  const outerRef   = useRef(null);
  const inputRef   = useRef(null);
  const historyRef = useRef(new CommandHistory(HISTORY_SIZE));
  const bufRef     = useRef('');
  const autoRef    = useRef(true);
  const linesRef   = useRef([]);
  const charRef    = useRef(0);
  const [isNavigating, setIsNavigating] = useState(false);

  useEffect(() => { autoRef.current = autoscroll; }, [autoscroll]);

  // BUG 9 FIX: ResizeObserver updates listHeight whenever the panel is resized
  useEffect(() => {
    const el = outerRef.current;
    if (!el) return;
    const ro = new ResizeObserver(entries => {
      for (const entry of entries) {
        setListHeight(entry.contentRect.height || 200);
      }
    });
    ro.observe(el);
    // Set initial height
    setListHeight(el.clientHeight || 200);
    return () => ro.disconnect();
  }, []);

  const scrollBottom = useCallback(() => {
    if (autoRef.current && listRef.current && linesRef.current.length > 0) {
      listRef.current.scrollToItem(linesRef.current.length - 1, 'end');
    }
  }, []);

  useEffect(() => { scrollBottom(); }, [lines, scrollBottom]);

  const appendLine = useCallback((message, type = 'info') => {
    const obj = { message, timestamp: new Date(), complete: true, lineLen: message.length, [type]: true };
    linesRef.current = [...linesRef.current, obj].slice(-3000);
    setLines([...linesRef.current]);
  }, []);

  // BUG 7 FIX: baudBuf is now sent AFTER the connection is established
  // BUG 8 FIX: `incoming` variable removed; messagesToLines is the single path
  const connect = useCallback(async () => {
    if (connecting || connected) return;
    setConnecting(true);
    const api = window.electronAPI;
    if (!api) { setConnecting(false); return; }

    api.onSerial((data) => {
      const chunk = typeof data === 'string' ? data : (data?.data || data?.text || String(data));
      // Feed RAW chunks (newlines included) to messagesToLines — it buffers
      // partial lines itself via the complete flag. Pre-splitting here made
      // every fragment take the "no newline" branch, collapsing the entire
      // session into one ever-growing row.
      if (!chunk) return;
      const [next, nextCount] = messagesToLines([chunk], linesRef.current, charRef.current);
      const [truncated, newCount] = truncateLines(next, nextCount);
      charRef.current   = newCount;
      linesRef.current  = truncated;
      setLines([...truncated]);
    });

    // BUG 7 FIX: connect first, then send baud frame
    const result = await api.bridgeConnect({ host, port });
    setConnecting(false);

    if (result?.success) {
      setConnected(true);
      // Now the TCP connection exists — safe to send the baud control frame
      const b = baud;
      const baudBuf = new Uint8Array([0xEF,0xBE,0x10,(b>>24)&0xFF,(b>>16)&0xFF,(b>>8)&0xFF,b&0xFF]);
      api.bridgeSend?.(baudBuf);
      appendLine(`● Connected to ${host}:${port} @ ${b} baud`, 'info');
    } else {
      api.offSerial?.();
      appendLine(`✗ Connection failed: ${result?.error || 'Unknown error'}`, 'error');
    }
  }, [connecting, connected, host, port, baud, appendLine]);

  const disconnect = useCallback(async () => {
    await window.electronAPI?.bridgeDisconnect?.();
    window.electronAPI?.offSerial?.();
    setConnected(false);
    appendLine('● Disconnected', 'info');
  }, [appendLine]);

  useEffect(() => () => { window.electronAPI?.bridgeDisconnect?.(); window.electronAPI?.offSerial?.(); }, []);

  const handleBaudChange = useCallback(async (newBaud) => {
    const b = Number(newBaud);
    setBaud(b);
    if (connected) {
      const baudBuf = new Uint8Array([0xEF,0xBE,0x10,(b>>24)&0xFF,(b>>16)&0xFF,(b>>8)&0xFF,b&0xFF]);
      window.electronAPI?.bridgeSend?.(baudBuf);
      appendLine(`» Baud changed to ${b}`, 'info');
    }
  }, [connected, appendLine]);

  const send = useCallback(() => {
    if (!input.trim() || !connected) return;
    const msg = input + lineEnd;
    window.electronAPI?.bridgeSend?.(msg);
    historyRef.current.addCommand(input);
    appendLine(`→ ${input}`, 'sent');
    setInput('');
    setIsNavigating(false);
  }, [input, connected, lineEnd, appendLine]);

  const handleKeyDown = useCallback((e) => {
    const hist = historyRef.current;
    if (e.key === 'Enter')     { send(); return; }
    if (e.key === 'Escape')    { setInput(hist.resetHistoryLocation()); setIsNavigating(false); return; }
    if (e.key === 'ArrowUp')   { e.preventDefault(); const v = hist.getPreviousCommand(input); if (v != null) { setInput(v); setIsNavigating(true); } return; }
    if (e.key === 'ArrowDown') { e.preventDefault(); if (!hist.hasNextCommand()) { setInput(hist.resetHistoryLocation()); setIsNavigating(false); return; } const v = hist.getNextCommand(); setInput(v ?? ''); if (!v) setIsNavigating(false); }
  }, [send, input]);

  const clearOutput = useCallback(() => {
    linesRef.current = []; charRef.current = 0;
    setLines([]);
  }, []);

  // P5 #11: detach this monitor into its own OS window.
  const popOut = useCallback(() => {
    window.electronAPI?.monitorTearOff?.({ host, port });
    onTearOff?.();
  }, [host, port, onTearOff]);

  const copyOutput = useCallback(() => {
    navigator.clipboard?.writeText(linesRef.current.map(l => l.message).join('\n'));
  }, []);

  const itemData = { lines, showTimestamp };

  return (
    <div className="serial-monitor">
      <div className="serial-header">
        <span className="serial-title">
          <SerialIcon />
          Serial Monitor
          {connected && <span className="sm-live-dot" />}
        </span>
        <div className="serial-controls">
          <div className="serial-field">
            <label>Baud</label>
            <select value={baud} onChange={e => handleBaudChange(e.target.value)} className="serial-select">
              {BAUD_RATES.map(b => <option key={b} value={b}>{b.toLocaleString()}</option>)}
            </select>
          </div>
          <div className="serial-field">
            <label>Line ending</label>
            <select value={lineEnd} onChange={e => setLineEnd(e.target.value)} className="serial-select">
              {LINE_ENDINGS.map(le => <option key={le.label} value={le.value}>{le.label}</option>)}
            </select>
          </div>
          <label className="serial-check">
            <input type="checkbox" checked={autoscroll}    onChange={e => setAutoscroll(e.target.checked)} /> Autoscroll
          </label>
          <label className="serial-check">
            <input type="checkbox" checked={showTimestamp} onChange={e => setShowTimestamp(e.target.checked)} /> Timestamp
          </label>
          {!connected
            ? <button className="btn primary sm-conn-btn" onClick={connect} disabled={connecting}>
                {connecting ? <><span className="spin">⟳</span> Connecting…</> : <><ConnectIcon /> Connect</>}
              </button>
            : <button className="btn sm-conn-btn" onClick={disconnect}>
                <DisconnectIcon /> Disconnect
              </button>
          }
          <button className="btn sm-icon-btn" onClick={copyOutput} title="Copy all"><CopyIcon /></button>
          <button className="btn sm-icon-btn" onClick={clearOutput} title="Clear"><ClearIcon /></button>
          {!standalone && (
            <button className="btn sm-icon-btn" onClick={popOut} title="Open in separate window (tear-off)"><PopoutIcon /></button>
          )}
          <button className="btn sm-icon-btn sm-close" onClick={onClose} title="Close">✕</button>
        </div>
      </div>

      {/* BUG 9 FIX: outerRef div is the ResizeObserver target; listHeight is state */}
      <div className="serial-body" ref={outerRef}>
        {lines.length === 0
          ? <div className="sm-empty">{connected ? 'Waiting for data…' : 'Press Connect to open a serial connection.'}</div>
          : <List
              ref={listRef}
              height={listHeight}
              width="100%"
              itemCount={lines.length}
              itemSize={ROW_HEIGHT}
              itemData={itemData}
              overscanCount={12}
              onScroll={({ scrollOffset, scrollUpdateWasRequested }) => {
                if (!scrollUpdateWasRequested && outerRef.current) {
                  const maxScroll = lines.length * ROW_HEIGHT - listHeight;
                  if (scrollOffset < maxScroll - ROW_HEIGHT * 3 && autoscroll) setAutoscroll(false);
                }
              }}
            >
              {Row}
            </List>
        }
      </div>

      <div className="serial-input-row">
        <div className="sm-input-wrap">
          <input ref={inputRef} type="text" className="serial-input"
            placeholder={connected ? '↑/↓ history · Enter to send · Esc resets' : 'Not connected'}
            value={input} onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown} disabled={!connected} spellCheck={false} autoComplete="off" />
          {isNavigating && <span className="sm-hist-badge" title="Press Esc to reset">hist</span>}
        </div>
        <button className="btn primary" onClick={send} disabled={!connected || !input}>Send</button>
      </div>

      <div className="sm-footer">
        <span>{lines.length.toLocaleString()} lines · {historyRef.current.size} in history</span>
        {lines.length >= 2900 && <span className="sm-footer-warn"> · buffer near limit</span>}
        {!autoscroll && (
          <button className="sm-scroll-btn" onClick={() => { setAutoscroll(true); scrollBottom(); }}>
            ↓ Resume autoscroll
          </button>
        )}
      </div>
    </div>
  );
}

function SerialIcon()     { return <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="2" y="7" width="20" height="14" rx="2"/><path d="M16 2H8l-2 5h12z"/></svg>; }
function ConnectIcon()    { return <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><path d="M5 12h14M12 5l7 7-7 7"/></svg>; }
function DisconnectIcon() { return <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>; }
function CopyIcon()       { return <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>; }
function PopoutIcon()     { return <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M15 3h6v6"/><path d="M10 14 21 3"/><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/></svg>; }
function ClearIcon()      { return <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/></svg>; }
