/**
 * companion-cli.js
 *
 * Bug A fix: cancelCompile() now works for daemon mode by calling
 *   daemon.cancelCompile(lastStreamCallId).
 * Bug G fix: _procs is a Map<callId, proc> — no single field overwrite.
 *   Each compile gets a unique ID; cancel kills the right process.
 */

const { spawn } = require('child_process');
const path  = require('path');
const fs    = require('fs');
const os    = require('os');

const DaemonManager = require('./services/daemon-manager');

const JSON_DIAG_RE = /^\{"type":"diagnostic",.+\}$/;

class CompanionCLI {
  constructor() {
    this.binaryPath        = this._findBinary();
    this.configPath        = path.join(os.homedir(), '.companion-cli', 'config.yaml');
    this.dataDir           = path.join(os.homedir(), '.companion-cli', 'data');
    this._daemon           = new DaemonManager(this.binaryPath);
    // BUG G fix: Map<callId, proc> instead of single _currentProc field
    this._procs            = new Map();
    this._procSeq          = 0;
    // Track last streaming call for daemon cancel
    this._lastStreamCallId = null;
    this._ensureDirs();
    this._ensureConfig();
  }

  // ── Daemon ──────────────────────────────────────────────────
  async startDaemon(onOutput) {
    try   { const port = await this._daemon.start(onOutput); return { success: true, port }; }
    catch (err) { console.warn('[CLI] Daemon start failed:', err.message); return { success: false, error: err.message }; }
  }
  stopDaemon()      { this._daemon.stop(); }
  isDaemonRunning() { return this._daemon.isDaemonRunning(); }
  getDaemonPort()   { return this._daemon.getPort(); }
  async pingDaemon(){ return this._daemon.ping(); }

  // ── BUG A+G: Cancel — works for both daemon and subprocess paths ──────────

  // ── Cancel — kind-scoped so cancelling an upload doesn't kill lib installs ──
  cancelCompile(kind = 'compile') {
    let cancelled = false;

    if (kind === 'compile' && this._lastStreamCallId != null && this._daemon.isDaemonRunning()) {
      this._daemon.cancelCompile(this._lastStreamCallId);
      this._lastStreamCallId = null;
      cancelled = true;
    }

    for (const [id, entry] of this._procs.entries()) {
      if (entry.kind !== kind) continue;  // Bug-13 fix: only kill the requested job type
      try { entry.proc.kill('SIGTERM'); } catch {}
      this._procs.delete(id);
      cancelled = true;
    }

    return cancelled;
  }

  // ── Binary resolution ────────────────────────────────────────
  _findBinary() {
    const ext  = process.platform === 'win32' ? '.exe' : '';
    const name = `companion${ext}`;
    const candidates = [
      path.join(__dirname, '..', '..', 'companion-cli', name),
      path.join(__dirname, '..', 'bin', name), name,
    ];
    for (const c of candidates) { try { if (fs.existsSync(c)) return c; } catch {} }
    return name;
  }

  _ensureDirs() {
    try {
      fs.mkdirSync(path.dirname(this.configPath), { recursive: true });
      fs.mkdirSync(this.dataDir, { recursive: true });
      fs.mkdirSync(path.join(os.homedir(), 'CompanionSketches'), { recursive: true });
    } catch {}
  }

  _ensureConfig() {
    if (fs.existsSync(this.configPath)) return;
    this._run(['config', 'init']).catch(() => {});
  }

  // ── Subprocess runner: kind-tagged procs + cross-chunk diag buffering ──
  _run(args, onOutput = null, onDiag = null, kind = 'other') {
    const callId = ++this._procSeq;
    return new Promise((resolve, reject) => {
      const proc = spawn(this.binaryPath, args, { env: { ...process.env } });
      this._procs.set(callId, { proc, kind });
      let stdout = '', stderr = '';
      let diagBuf = ''; // Bug-14 fix: JSON lines split across chunks

      const handleChunk = (text) => {
        const out = [];
        const lines = (diagBuf + text).split('\n');
        diagBuf = lines.pop(); // keep incomplete tail for the next chunk
        for (const line of lines) {
          const t = line.trim();
          if (!t) continue;
          if (onDiag && JSON_DIAG_RE.test(t)) {
            try { onDiag(JSON.parse(t)); } catch {}
          } else { out.push(line); }
        }
        const s = out.join('\n'); if (s) onOutput?.(s);
      };

      proc.stdout.on('data', chunk => { const t = chunk.toString(); stdout += t; handleChunk(t); });
      proc.stderr.on('data', chunk => { const t = chunk.toString(); stderr += t; handleChunk(t); });
      proc.on('error', err => {
        this._procs.delete(callId);
        if (err.code === 'ENOENT') reject(new Error('Companion CLI binary not found.\nBuild: cd companion-cli && go build -o companion .'));
        else reject(err);
      });
      proc.on('close', (code, signal) => {
        // Flush any trailing buffered diagnostic line
        const tail = diagBuf.trim();
        diagBuf = '';
        if (tail && onDiag && JSON_DIAG_RE.test(tail)) {
          try { onDiag(JSON.parse(tail)); } catch {}
        }
        this._procs.delete(callId);
        if (signal === 'SIGTERM') reject(new Error(`Job cancelled (${kind})`));
        else if (code === 0) resolve({ stdout, stderr, code });
        else reject(new Error(stderr || stdout || `companion exited with code ${code}`));
      });
    });
  }

  // ── USB upload via local serial port ───────────────────────────
  async uploadUSB({ binaryPath, fqbn, serialPort, baud = 921600, verbose = false }, onOutput) {
    const args = ['upload', '--binary', binaryPath];
    if (fqbn)       args.push('--fqbn', fqbn);
    if (serialPort) args.push('--serial', serialPort);
    if (baud)       args.push('--baud', String(baud));
    if (verbose)    args.push('--verbose');
    try {
      await this._run(args, onOutput, null, 'upload');
      return { success: true };
    } catch (err) {
      const cancelled = err.message.startsWith('Job cancelled (upload)');
      return { success: false, cancelled, error: err.message };
    }
  }

  // ── OTA (P4c): per-sketch over-the-air switch + status ─────────
  async otaToggle(enabled, sketchDir) {
    try {
      await this._run(['ota', enabled ? 'enable' : 'disable', sketchDir || '.']);
      return { success: true };
    } catch (err) {
      return { success: false, error: err.message };
    }
  }

  async otaStatus(sketchDir) {
    try {
      const { stdout } = await this._run(['ota', 'status', sketchDir || '.']);
      const enabled = /enabled/i.test(stdout);
      return { success: true, enabled, text: stdout.trim().split('\n').pop() };
    } catch (err) {
      return { success: false, error: err.message };
    }
  }

  // OTA upload: compiles the sketch (if needed) and pushes via ArduinoOTA.
  async otaUpload({ ip, sketchDir, port = 3232, password = '' }, onOutput) {
    const args = ['ota', 'upload', ip, sketchDir || '.', '--port', String(port)];
    if (password) args.push('--auth', password);
    try {
      await this._run(args, onOutput, null, 'upload');
      return { success: true };
    } catch (err) {
      const cancelled = err.message.startsWith('Job cancelled (upload)');
      return { success: false, cancelled, error: err.message };
    }
  }

  // ── Serial port detection (board list-ports --json) ─────────────
  async listPorts() {
    try {
      const { stdout } = await this._run(['board', 'list-ports', '--json']);
      const start = stdout.indexOf('[');
      if (start < 0) return [];
      return JSON.parse(stdout.slice(start));
    } catch (err) {
      console.warn('[CLI] listPorts failed:', err.message);
      return [];
    }
  }

  // ── Compile (daemon streaming → subprocess fallback) ──────────
  async compile(sketchDir, fqbn, onOutput, exportBin = false, verbose = false, warnings = 'default', json = false) {
    if (this._daemon.isDaemonRunning()) {
      return this._compileDaemonStream(sketchDir, fqbn, onOutput, exportBin, verbose, warnings);
    }
    return this._compileSubprocess(sketchDir, fqbn, onOutput, exportBin, verbose, warnings, json);
  }

  async _compileDaemonStream(sketchDir, fqbn, onOutput, exportBin, verbose, warnings) {
    try {
      // BUG A: use streaming path so output arrives in real time
      const streamPromise = this._daemon.callStreaming(
        { sketchDir, fqbn, exportBin, verbose, warnings: warnings || 'default' },
        onOutput
      );
      // BUG A: track the call ID for cancellation
      this._lastStreamCallId = this._daemon.getLastStreamCallId();

      const result = await streamPromise;
      this._lastStreamCallId = null;
      return result;
    } catch (err) {
      this._lastStreamCallId = null;
      const cancelled = err.message === 'Compile cancelled';
      if (cancelled) return { success: false, cancelled: true, error: 'Compile cancelled', diagnostics: [], fromDaemon: true };
      // Daemon failure → fall back to subprocess
      console.warn('[CLI] Daemon stream failed, falling back:', err.message);
      this._daemon.stop();
      return this._compileSubprocess(sketchDir, fqbn, onOutput, exportBin, verbose, warnings, true);
    }
  }

  async _compileSubprocess(sketchDir, fqbn, onOutput, exportBin, verbose, warnings, json = false) {
    try {
      const args = ['compile', sketchDir, '--fqbn', fqbn, '--warnings', warnings || 'default'];
      if (exportBin) args.push('--export-binaries');
      if (verbose)   args.push('--verbose');
      if (json)      args.push('--json');
      const diagnostics = [];
      await this._run(args, onOutput, d => diagnostics.push(d), 'compile');
      return { success: true, binaryPath: this._findExportedBinary(sketchDir, fqbn), diagnostics, fromDaemon: false };
    } catch (err) {
      const cancelled = err.message.startsWith('Job cancelled (compile)') || err.message === 'Compile cancelled';
      return { success: false, cancelled, error: err.message, binaryPath: null, diagnostics: [], fromDaemon: false };
    }
  }

  // ── Board management ──────────────────────────────────────────
  async updateIndex(onOutput) {
    if (this._daemon.isDaemonRunning()) {
      try {
        const r = await this._daemon.call('board.update-index', {}, 60_000);
        if (r?.lines && onOutput) r.lines.forEach(l => onOutput(l + '\n'));
        if (r?.ok) return { success: true };
      } catch (e) {
        console.warn('[CLI] daemon board.update-index failed, falling back:', e.message);
      }
    }
    try { await this._run(['board', 'update-index'], onOutput); return { success: true }; }
    catch (err) { return { success: false, error: err.message }; }
  }
  async searchBoards(q = '') {
    if (this._daemon.isDaemonRunning()) {
      try {
        const r = await this._daemon.call('board.search', { query: q }, 10_000);
        if (Array.isArray(r)) return r;
      } catch {}
    }
    try { const { stdout } = await this._run(['board', 'search', '--all', ...(q ? [q] : [])]); return this._parseBoardSearch(stdout); }
    catch { return []; }
  }
  async searchBoardPackages(q = '') {
    if (this._daemon.isDaemonRunning()) {
      try {
        const r = await this._daemon.call('board.search-packages', { query: q }, 10_000);
        if (Array.isArray(r)) {
          return r.map(p => ({
            name:         p.Name         || p.name         || '',
            vendorID:     p.VendorID     || p.vendorID     || '',
            maintainer:   p.Maintainer   || p.maintainer   || '',
            description:  p.Description  || p.description  || '',
            version:      p.Version      || p.version      || '',
            architecture: p.Architecture || p.architecture || '',
            installed:    p.Installed    || p.installed    || false,
          }));
        }
      } catch (e) {
        console.warn('[CLI] daemon board.search-packages failed, falling back:', e.message);
      }
    }
    // Fallback: CLI subprocess + text parsing
    try {
      const { stdout } = await this._run(['board', 'packages', ...(q ? [q] : [])]);
      const parsed = this._parseBoardPackages(stdout);
      if (parsed.length > 0) return parsed;
      // If parsing returned nothing but there was output, log it for debugging
      if (stdout.trim() && !stdout.includes('No packages found')) {
        console.warn('[CLI] board packages parse returned empty from:', stdout.slice(0, 200));
      }
      return parsed;
    } catch (err) {
      console.warn('[CLI] board packages error:', err.message);
      return [];
    }
  }
  async listBoards() {
    if (this._daemon.isDaemonRunning()) {
      try { const r = await this._daemon.call('board.list', {}, 10_000); if (Array.isArray(r)) return r; } catch {}
    }
    try { const { stdout } = await this._run(['board', 'list']); return this._parseBoardList(stdout); }
    catch { return []; }
  }
  // Every board across all installed platforms (like Arduino IDE's "Select
  // other board and port" dialog). Prefers the daemon RPC, falls back to
  // `board listall --json`.
  async listAllBoards() {
    if (this._daemon.isDaemonRunning()) {
      try {
        const r = await this._daemon.call('board.listAll', {}, 10_000);
        if (Array.isArray(r)) return r.map(c => ({
          fqbn: c.fqbn || c.FQBN || '',
          name: c.name || c.Name || '',
          platform: c.platform || c.Platform || String(c.fqbn || '').split(':').slice(0, 2).join(':'),
          version: c.version || c.Version || '',
        })).filter(c => c.fqbn);
      } catch {}
    }
    try {
      const { stdout } = await this._run(['board', 'listall', '--json']);
      const data = JSON.parse(stdout);
      if (Array.isArray(data)) return data.map(c => ({
        fqbn: c.fqbn || c.FQBN || '',
        name: c.name || c.Name || '',
        platform: c.platform || c.Platform || String(c.fqbn || '').split(':').slice(0, 2).join(':'),
        version: c.version || c.Version || '',
      })).filter(c => c.fqbn);
    } catch {}
    return [];
  }
  async installCore(platformId, onOutput) {
    try { await this._run(['board', 'install', platformId], onOutput); return { success: true }; }
    catch (err) { return { success: false, error: err.message }; }
  }

  // ── Library management ────────────────────────────────────────
  async updateLibIndex(onOutput) {
    try { await this._run(['lib', 'update-index'], onOutput); return { success: true }; }
    catch (err) { return { success: false, error: err.message }; }
  }
  async searchLibraries(q) {
    try { const { stdout } = await this._run(['lib', 'search', q, '--limit', '40']); return this._parseLibSearch(stdout); }
    catch { return []; }
  }
  async listLibraries() {
    try { const { stdout } = await this._run(['lib', 'list']); return this._parseLibSearch(stdout); }
    catch { return []; }
  }
  async installLibrary(name, onOutput) {
    try { await this._run(['lib', 'install', name], onOutput); return { success: true }; }
    catch (err) { return { success: false, error: err.message }; }
  }
  async uninstallLibrary(name) {
    try { await this._run(['lib', 'uninstall', name]); return { success: true }; }
    catch (err) { return { success: false, error: err.message }; }
  }

  // ── Config ────────────────────────────────────────────────────
  async getConfig(key) {
    try { const { stdout } = await this._run(['config', 'get', key]); const p = stdout.trim().split('='); return p.length > 1 ? p.slice(1).join('=').trim() : stdout.trim(); }
    catch { return null; }
  }
  async setConfig(key, value) {
    try { await this._run(['config', 'set', key, value]); return { success: true }; }
    catch (err) { return { success: false, error: err.message }; }
  }

  async version() {
    try { const { stdout } = await this._run(['version']); const m = stdout.match(/Version:\s+(\S+)/); return m ? `Companion CLI v${m[1]}` : stdout.trim().split('\n')[0]; }
    catch { return 'Companion CLI (not found)'; }
  }
  async ping(host, port) {
    try { const { stdout } = await this._run(['version', 'ping', '--host', host, '--port', String(port)]); return { success: true, info: stdout.trim() }; }
    catch (err) { return { success: false, error: err.message }; }
  }

  async cacheStats() {
    if (!this._daemon.isDaemonRunning()) return null;
    try { return await this._daemon.call('cache.stats', {}, 5_000); } catch { return null; }
  }
  async evictCache() {
    if (!this._daemon.isDaemonRunning()) return { success: false, error: 'Daemon not running' };
    try { await this._daemon.call('cache.evict', {}, 30_000); return { success: true }; }
    catch (err) { return { success: false, error: err.message }; }
  }

  // ── Parsers ───────────────────────────────────────────────────
  _sa(s) { return s.replace(/\x1b\[[0-9;]*m/g, '').trim(); }
  _isSep(l) { return /^[\s──\-─]+$/.test(l); }

  _parseBoardSearch(stdout) {
    const lines = stdout.split('\n'); const boards = []; let header = true;
    for (const line of lines) {
      if (!line.trim() || this._isSep(line)) continue;
      const c = this._sa(line); if (!c) continue;
      if (header) { if (c.includes('FQBN')) header = false; continue; }
      const p = c.split(/\s{2,}/);
      if (p.length >= 2 && !c.startsWith('─'))
        boards.push({ name: p[0].trim(), fqbn: p[1].trim(), installed: p[2]?.trim()?.includes('install') });
    }
    return boards;
  }
  _parseBoardList(stdout) {
    const lines = stdout.split('\n'); const plats = []; let header = true;
    for (const line of lines) {
      if (!line.trim() || this._isSep(line)) continue;
      const c = this._sa(line); if (!c) continue;
      if (header) { if (c.includes('Version')) header = false; continue; }
      const p = c.split(/\s{2,}/);
      if (p.length >= 2 && !c.startsWith('─'))
        plats.push({ id: p[0].trim(), version: p[1].trim(), fqbn: p[0].trim() });
    }
    return plats;
  }
  _parseBoardPackages(stdout) {
    const lines = stdout.split('\n'); const pkgs = []; let header = true;
    for (const line of lines) {
      if (!line.trim() || this._isSep(line)) continue;
      const c = this._sa(line); if (!c || c.includes('package(s) shown')) continue;
      if (header) { if (c.includes('Architecture')) header = false; continue; }
      const p = c.split(/\s{2,}/);
      if (p.length >= 3 && !c.startsWith('─'))
        pkgs.push({
          name: p[0].trim(),
          vendorID: p[0].trim().toLowerCase().replace(/\s+/g, '-'),
          maintainer: p[1].trim(),
          architecture: p[2].trim(),
          installed: p[3]?.trim()?.includes('install'),
        });
    }
    return pkgs;
  }
  _parseLibSearch(stdout) {
    const lines = stdout.split('\n'); const libs = []; let header = true;
    for (const line of lines) {
      if (!line.trim() || this._isSep(line)) continue;
      const c = this._sa(line); if (!c || c.startsWith('result')) continue;
      if (header) { if (c.includes('Version')) header = false; continue; }
      const p = c.split(/\s{2,}/);
      if (p.length >= 2 && !c.startsWith('─'))
        libs.push({ name: p[0].trim(), version: p[1].trim(), author: p[2]?.trim() || '', sentence: p[3]?.trim() || '' });
    }
    return libs;
  }
  _findExportedBinary(sketchDir, fqbn) {
    const n = path.basename(sketchDir);
    const d = path.join(sketchDir, 'build', fqbn.replace(/:/g, '.'));
    return [`${n}.ino.bin`,`${n}.ino.hex`,`${n}.bin`,`${n}.hex`,`${n}.ino.merged.bin`]
      .map(f => path.join(d, f)).find(p => fs.existsSync(p)) || null;
  }
}

module.exports = CompanionCLI;
