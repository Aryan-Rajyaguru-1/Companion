/**
 * SerialPlotter.jsx — full rewrite
 *
 * Matches Arduino IDE 2.x Serial Plotter + adds:
 *   - Auto-detects labeled channels from "label:value" format
 *   - Legend with per-channel colour toggle
 *   - Pause / Resume button
 *   - Y-axis auto-scale or fixed ±range
 *   - Adjustable time window (100–2000 points)
 *   - CSV export of current buffer
 *   - FPS / sample-rate counter
 *   - Canvas 2D rendering (no library needed)
 */

import { useEffect, useRef, useState, useCallback } from 'react';
import './SerialPlotter.css';

const COLORS = ['#00979D','#f85149','#3fb950','#d29922','#58a6ff','#bc8cff','#ff7b72','#79c0ff'];
const MAX_PTS = 2000;

function parseLine(text) {
  if (!text || typeof text !== 'string') return null;
  const line = text.trim();
  if (!line) return null;

  const channels = {};

  // Format 1: "Label:Value Label2:Value2"  (Arduino IDE default)
  if (line.includes(':')) {
    const pairs = line.split(/\s+/);
    let valid = 0;
    for (const p of pairs) {
      const idx = p.lastIndexOf(':');
      if (idx > 0) {
        const label = p.slice(0, idx);
        const val   = parseFloat(p.slice(idx + 1));
        if (!isNaN(val)) { channels[label] = val; valid++; }
      }
    }
    if (valid > 0) return channels;
  }

  // Format 2: comma-separated numbers
  const parts = line.split(/[,\t ]+/).map(Number);
  if (parts.length >= 1 && parts.every(v => !isNaN(v))) {
    parts.forEach((v, i) => { channels[`Ch${i + 1}`] = v; });
    return channels;
  }

  return null;
}

export default function SerialPlotter({ host, port, onClose }) {
  const canvasRef   = useRef(null);
  const animRef     = useRef(null);
  const bufferRef   = useRef({});      // channelName → number[]
  const colorsRef   = useRef({});      // channelName → color string
  const colorIdxRef = useRef(0);
  const sampleCountRef = useRef(0);
  const lastFpsTimeRef = useRef(Date.now());
  const fpsCountRef    = useRef(0);

  const [channels,    setChannels]    = useState([]);
  const [hidden,      setHidden]      = useState(new Set());
  const [paused,      setPaused]      = useState(false);
  const [maxPoints,   setMaxPoints]   = useState(500);
  const [yMin,        setYMin]        = useState('auto');
  const [yMax,        setYMax]        = useState('auto');
  const [fps,         setFps]         = useState(0);
  const [sampleRate,  setSampleRate]  = useState(0);

  const pausedRef = useRef(false);
  useEffect(() => { pausedRef.current = paused; }, [paused]);

  // Serial data handler
  const handleData = useCallback((raw) => {
    if (pausedRef.current) return;
    const line = typeof raw === 'string' ? raw : raw?.data || raw?.text || String(raw);
    const parsed = parseLine(line);
    if (!parsed) return;

    sampleCountRef.current++;
    fpsCountRef.current++;

    // Update buffers
    const newChannels = [];
    for (const [name, val] of Object.entries(parsed)) {
      if (!bufferRef.current[name]) {
        bufferRef.current[name] = [];
        colorsRef.current[name] = COLORS[colorIdxRef.current % COLORS.length];
        colorIdxRef.current++;
      }
      bufferRef.current[name].push(val);
      if (bufferRef.current[name].length > MAX_PTS) bufferRef.current[name].shift();
      newChannels.push(name);
    }

    // Sync channel list (only update state when channels change)
    const all = Object.keys(bufferRef.current);
    setChannels(prev => {
      if (JSON.stringify(prev) === JSON.stringify(all)) return prev;
      return all;
    });
  }, []);

  useEffect(() => {
    window.electronAPI?.onSerial?.(handleData);
    return () => window.electronAPI?.offSerial?.();
  }, [handleData]);

  // FPS + sample-rate counter
  useEffect(() => {
    const id = setInterval(() => {
      const now  = Date.now();
      const dt   = (now - lastFpsTimeRef.current) / 1000;
      setFps(Math.round(fpsCountRef.current / dt));
      setSampleRate(Math.round(sampleCountRef.current / dt));
      fpsCountRef.current    = 0;
      sampleCountRef.current = 0;
      lastFpsTimeRef.current = now;
    }, 1000);
    return () => clearInterval(id);
  }, []);

  // Canvas render loop
  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const W = canvas.width, H = canvas.height;

    // Background
    ctx.fillStyle = '#0d1117';
    ctx.fillRect(0, 0, W, H);

    const visChannels = channels.filter(c => !hidden.has(c));
    if (visChannels.length === 0) {
      ctx.fillStyle = 'rgba(255,255,255,.3)';
      ctx.font = '13px system-ui';
      ctx.textAlign = 'center';
      ctx.fillText('Waiting for serial data…', W / 2, H / 2);
      return;
    }

    // Collect all visible values for Y-axis scaling
    const allVals = visChannels.flatMap(c => bufferRef.current[c] || []);
    let minV = yMin === 'auto' ? Math.min(...allVals) : parseFloat(yMin) || 0;
    let maxV = yMax === 'auto' ? Math.max(...allVals) : parseFloat(yMax) || 1;
    if (!isFinite(minV)) minV = 0;
    if (!isFinite(maxV)) maxV = 1;
    if (minV === maxV) { minV -= 1; maxV += 1; }
    const pad = (maxV - minV) * 0.08;
    minV -= pad; maxV += pad;

    const MARGIN_L = 52, MARGIN_R = 12, MARGIN_T = 16, MARGIN_B = 28;
    const plotW = W - MARGIN_L - MARGIN_R;
    const plotH = H - MARGIN_T - MARGIN_B;

    const toX = (i, len) => MARGIN_L + (i / (maxPoints - 1)) * plotW;
    const toY = (v)       => MARGIN_T + plotH - ((v - minV) / (maxV - minV)) * plotH;

    // Grid lines
    ctx.strokeStyle = 'rgba(255,255,255,.07)';
    ctx.lineWidth = 1;
    const gridLines = 5;
    for (let i = 0; i <= gridLines; i++) {
      const y = MARGIN_T + (i / gridLines) * plotH;
      ctx.beginPath(); ctx.moveTo(MARGIN_L, y); ctx.lineTo(W - MARGIN_R, y); ctx.stroke();

      const v = maxV - (i / gridLines) * (maxV - minV);
      ctx.fillStyle = 'rgba(255,255,255,.35)';
      ctx.font = '9px "JetBrains Mono",monospace';
      ctx.textAlign = 'right';
      ctx.fillText(v.toFixed(Math.abs(v) < 10 ? 2 : 0), MARGIN_L - 4, y + 3);
    }

    // X-axis labels
    ctx.fillStyle = 'rgba(255,255,255,.3)';
    ctx.font = '9px "JetBrains Mono",monospace';
    ctx.textAlign = 'center';
    for (let i = 0; i <= 4; i++) {
      const x = MARGIN_L + (i / 4) * plotW;
      const val = Math.round(i / 4 * maxPoints);
      ctx.fillText(val, x, H - 8);
    }

    // Plot each channel
    for (const name of visChannels) {
      const data = bufferRef.current[name] || [];
      if (data.length < 2) continue;

      const slice = data.slice(-maxPoints);
      ctx.strokeStyle = colorsRef.current[name];
      ctx.lineWidth = 1.5;
      ctx.lineJoin = 'round';
      ctx.beginPath();
      slice.forEach((v, i) => {
        const x = toX(i, slice.length);
        const y = toY(v);
        i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
      });
      ctx.stroke();
    }

    // Axes
    ctx.strokeStyle = 'rgba(255,255,255,.2)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(MARGIN_L, MARGIN_T); ctx.lineTo(MARGIN_L, MARGIN_T + plotH);
    ctx.moveTo(MARGIN_L, MARGIN_T + plotH); ctx.lineTo(W - MARGIN_R, MARGIN_T + plotH);
    ctx.stroke();
  }, [channels, hidden, maxPoints, yMin, yMax]);

  // Animate
  useEffect(() => {
    let raf;
    const loop = () => { draw(); raf = requestAnimationFrame(loop); };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, [draw]);

  // Resize canvas to container
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ro = new ResizeObserver(() => {
      canvas.width  = canvas.offsetWidth;
      canvas.height = canvas.offsetHeight;
    });
    ro.observe(canvas.parentElement);
    return () => ro.disconnect();
  }, []);

  const toggleChannel = (name) => setHidden(prev => {
    const n = new Set(prev);
    n.has(name) ? n.delete(name) : n.add(name);
    return n;
  });

  const handleClear = () => {
    bufferRef.current   = {};
    colorIdxRef.current = 0;
    setChannels([]);
  };

  const handleExportCSV = () => {
    const names = Object.keys(bufferRef.current);
    if (!names.length) return;
    const maxLen = Math.max(...names.map(n => bufferRef.current[n].length));
    const rows = [names.join(',')];
    for (let i = 0; i < maxLen; i++) {
      rows.push(names.map(n => bufferRef.current[n][i] ?? '').join(','));
    }
    const blob = new Blob([rows.join('\n')], { type: 'text/csv' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `serial_plotter_${Date.now()}.csv`;
    a.click();
  };

  return (
    <div className="serial-plotter">
      {/* Header */}
      <div className="sp-header">
        <span className="sp-title"><PlotIcon /> Serial Plotter</span>
        <div className="sp-controls">
          {/* Pause */}
          <button className={`sp-btn ${paused ? 'paused' : ''}`}
            onClick={() => setPaused(p => !p)}
            title={paused ? 'Resume' : 'Pause'}>
            {paused ? <PlayIcon /> : <PauseIcon />}
            {paused ? 'Resume' : 'Pause'}
          </button>
          {/* Window size */}
          <label className="sp-label">Points:
            <select className="sp-select" value={maxPoints}
              onChange={e => setMaxPoints(Number(e.target.value))}>
              {[100,250,500,1000,2000].map(v => <option key={v} value={v}>{v}</option>)}
            </select>
          </label>
          {/* Y-axis */}
          <label className="sp-label">Y:
            <input className="sp-yinput" type="text" value={yMin}
              onChange={e => setYMin(e.target.value)} placeholder="auto" title="Y min" />
            <span>–</span>
            <input className="sp-yinput" type="text" value={yMax}
              onChange={e => setYMax(e.target.value)} placeholder="auto" title="Y max" />
          </label>
          <button className="sp-btn" onClick={handleClear} title="Clear data">Clear</button>
          <button className="sp-btn" onClick={handleExportCSV} title="Export CSV">CSV</button>
          <button className="sp-btn sp-close" onClick={onClose} title="Close plotter">✕</button>
        </div>
      </div>

      <div className="sp-body">
        {/* Canvas */}
        <div className="sp-canvas-wrap">
          <canvas ref={canvasRef} className="sp-canvas" />
          {paused && <div className="sp-paused-overlay">⏸ Paused</div>}
        </div>

        {/* Legend sidebar */}
        <div className="sp-legend">
          <div className="sp-legend-title">Channels</div>
          {channels.length === 0 && (
            <div className="sp-legend-empty">No data yet</div>
          )}
          {channels.map(name => (
            <button key={name}
              className={`sp-legend-item ${hidden.has(name) ? 'hidden' : ''}`}
              onClick={() => toggleChannel(name)}>
              <span className="sp-legend-dot" style={{ background: colorsRef.current[name] }} />
              <span className="sp-legend-name">{name}</span>
              {!hidden.has(name) && (
                <span className="sp-legend-val">
                  {(bufferRef.current[name]?.at(-1) ?? 0).toFixed(2)}
                </span>
              )}
            </button>
          ))}
          <div className="sp-stats">
            <div>{sampleRate} sps</div>
            <div>{fps} fps</div>
          </div>
        </div>
      </div>
    </div>
  );
}

function PlotIcon()  { return <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>; }
function PauseIcon() { return <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor" stroke="none"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg>; }
function PlayIcon()  { return <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor" stroke="none"><polygon points="5 3 19 12 5 21 5 3"/></svg>; }
