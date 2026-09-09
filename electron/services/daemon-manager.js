/**
 * daemon-manager.js
 *
 * Bug A fix: cancelCompile() now:
 *   1. Destroys the in-flight HTTP request via stored req reference
 *   2. Sends daemon:cancel RPC so the server kills its subprocess
 *
 * Streaming compile: callStreaming() uses Transfer-Encoding: chunked
 * to receive JSON output lines in real time, eliminating the batch-at-end UX.
 */

const { spawn } = require('child_process');
const http      = require('http');
const os        = require('os');

const STARTUP_TIMEOUT_MS = 12_000;
const PING_TIMEOUT_MS    =  3_000;
const PORT_RE            = /COMPANION_DAEMON_PORT=(\d+)/;
const TOKEN_RE           = /COMPANION_DAEMON_TOKEN=(\S+)/;

class DaemonManager {
  constructor(binaryPath) {
    this._binary       = binaryPath;
    this._proc         = null;
    this._port         = null;
    this._token        = null; // bearer token from COMPANION_DAEMON_TOKEN
    this._ready        = false;
    this._starting     = false;
    this._startPromise = null;
    this._onOutput     = null;
    // BUG A: track in-flight request per call-id so we can abort exactly one
    this._inFlightReqs = new Map(); // callId → http.ClientRequest
    this._callSeq      = 0;
  }

  // ── Public lifecycle ──────────────────────────────────────────

  async start(onOutput = null) {
    if (this._ready && this._port) return this._port;
    if (this._starting) return this._startPromise;
    this._starting    = true;
    this._onOutput    = onOutput;
    this._startPromise = this._doStart();
    try {
      this._port  = await this._startPromise;
      this._ready = true;
      return this._port;
    } catch (err) {
      this._ready = false; this._port = null;
      throw err;
    } finally {
      this._starting = false;
    }
  }

  stop() {
    // Abort all in-flight requests
    for (const req of this._inFlightReqs.values()) {
      try { req.destroy(); } catch {}
    }
    this._inFlightReqs.clear();
    if (this._proc) { try { this._proc.kill('SIGTERM'); } catch {} }
    this._proc = null; this._port = null; this._ready = false;
  }

  isDaemonRunning() { return this._ready && this._port != null; }
  getPort()         { return this._port; }

  // ── BUG A: cancel the in-flight compile ──────────────────────

  /**
   * Cancels a streaming compile by:
   *   1. Aborting the HTTP chunked request (stops receiving new output)
   *   2. Sending a cancel RPC to the daemon (kills the subprocess)
   */
  async cancelCompile(streamCallId) {
    // Abort the streaming HTTP connection
    const req = this._inFlightReqs.get(streamCallId);
    if (req) { try { req.destroy(); } catch {} this._inFlightReqs.delete(streamCallId); }
    // Tell the daemon to kill its subprocess
    if (this._ready && this._port) {
      try { await this.call('compile.cancel', {}, 5_000); } catch {}
    }
  }

  // ── Standard JSON-RPC call ────────────────────────────────────

  call(method, params = {}, timeoutMs = 90_000) {
    if (!this._ready || !this._port) return Promise.reject(new Error('Daemon not running'));
    const id = ++this._callSeq;
    return this._jsonRpc(id, this._port, method, params, timeoutMs);
  }

  // ── Streaming compile (real-time output) ─────────────────────

  /**
   * Calls /stream-compile with chunked Transfer-Encoding.
   * Each chunk is one newline-terminated JSON line:
   *   {"type":"output","text":"..."}
   *   {"type":"done","success":true,"binaryPath":"...","output":["..."]}
   *   {"type":"error","message":"..."}
   *
   * @param {object} params     compile params
   * @param {Function} onOutput called for each output line as it arrives
   * @returns {Promise<{success, binaryPath, diagnostics, output}>}
   */
  callStreaming(params, onOutput) {
    if (!this._ready || !this._port) return Promise.reject(new Error('Daemon not running'));
    const callId = ++this._callSeq;

    return new Promise((resolve, reject) => {
      const body = JSON.stringify(params);

      const req = http.request({
        hostname:  '127.0.0.1',
        port:       this._port,
        path:      '/stream-compile',
        method:    'POST',
        headers:   {
          'Content-Type':   'application/json',
          'Content-Length': Buffer.byteLength(body),
          ...this._authHeaders(),
        },
        timeout: 300_000, // 5 min max for large sketches
      }, (res) => {
        let buf = '';
        let resolved = false;

        res.on('data', chunk => {
          buf += chunk.toString();
          const lines = buf.split('\n');
          buf = lines.pop(); // keep incomplete last line

          for (const line of lines) {
            const trimmed = line.trim();
            if (!trimmed) continue;
            let msg;
            try { msg = JSON.parse(trimmed); } catch { continue; }

            if (msg.type === 'output') {
              onOutput?.(msg.text || '');
            } else if (msg.type === 'done' || msg.type === 'error') {
              resolved = true;
              this._inFlightReqs.delete(callId);
              if (msg.type === 'done') {
                resolve({ success: msg.success, binaryPath: msg.binaryPath || null,
                          diagnostics: msg.diagnostics || [], output: msg.output || [], fromDaemon: true,
                          error: msg.error });
              } else {
                reject(new Error(msg.message || 'Stream compile error'));
              }
            }
          }
        });

        res.on('end', () => {
          this._inFlightReqs.delete(callId);
          if (!resolved) reject(new Error('Stream ended without result'));
        });
        res.on('error', err => { this._inFlightReqs.delete(callId); reject(err); });
      });

      // BUG A: store req so cancelCompile() can destroy it
      this._inFlightReqs.set(callId, req);

      req.on('timeout', () => { req.destroy(); reject(new Error('Stream compile timeout')); });
      req.on('error', err => {
        this._inFlightReqs.delete(callId);
        if (err.code === 'ECONNRESET' || err.message.includes('socket hang up')) {
          // Connection destroyed by cancel — not an error
          reject(new Error('Compile cancelled'));
        } else {
          reject(err);
        }
      });

      req.write(body);
      req.end();

      // Return the callId so the caller can pass it back to cancelCompile()
      req._companionCallId = callId;
    });
  }

  /** Returns the callId of the last started streaming call */
  getLastStreamCallId() { return this._callSeq; }

  /** Bearer token captured from daemon startup output. */
  _authHeaders() {
    return this._token ? { Authorization: `Bearer ${this._token}` } : {};
  }

  // ── Ping ─────────────────────────────────────────────────────

  async ping() {
    if (!this._port) return false;
    try {
      const result = await this._get(this._port, '/ping', PING_TIMEOUT_MS);
      return result?.status === 'ok';
    } catch { return false; }
  }

  // ── Internal ──────────────────────────────────────────────────

  _doStart() {
    return new Promise((resolve, reject) => {
      let proc;
      try {
        proc = spawn(this._binary, ['daemon', '--port', '0'], {
          env: { ...process.env },
          stdio: ['ignore', 'pipe', 'pipe'],
        });
      } catch (err) { return reject(new Error(`Failed to spawn daemon: ${err.message}`)); }

      this._proc = proc;
      const timer = setTimeout(() => { proc.kill(); reject(new Error('Daemon startup timed out')); }, STARTUP_TIMEOUT_MS);
      let found = false;

      proc.stdout.on('data', chunk => {
        const text = chunk.toString();
        this._onOutput?.(`[daemon] ${text}`);
        if (!this._token) {
          const tm = TOKEN_RE.exec(text);
          if (tm) this._token = tm[1];
        }
        if (!found) {
          const m = PORT_RE.exec(text);
          if (m && this._token) { found = true; clearTimeout(timer); resolve(parseInt(m[1], 10)); }
        }
      });

      proc.stderr.on('data',   chunk => { this._onOutput?.(`[daemon] ${chunk.toString()}`); });
      proc.on('error', err  => { clearTimeout(timer); this._ready = false; this._port = null; if (!found) reject(err); });
      proc.on('close', code => { clearTimeout(timer); this._ready = false; this._port = null; this._proc = null; if (!found) reject(new Error(`Daemon exited (code ${code}) before reporting port`)); });
    });
  }

  _jsonRpc(id, port, method, params, timeoutMs) {
    return new Promise((resolve, reject) => {
      const body = JSON.stringify({ id, method, params });

      const req = http.request({
        hostname: '127.0.0.1', port, path: '/rpc', method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Content-Length': Buffer.byteLength(body),
          ...this._authHeaders(),
        },
        timeout: timeoutMs,
      }, res => {
        let data = '';
        res.on('data', c => { data += c; });
        res.on('end', () => {
          this._inFlightReqs.delete(id);
          try {
            const json = JSON.parse(data);
            if (json.error) reject(new Error(json.error.message));
            else resolve(json.result);
          } catch (e) { reject(new Error('Invalid JSON from daemon: ' + data.slice(0, 200))); }
        });
      });

      this._inFlightReqs.set(id, req);
      req.on('timeout', () => { req.destroy(); reject(new Error('Daemon RPC timeout')); });
      req.on('error', err => { this._inFlightReqs.delete(id); reject(err); });
      req.write(body); req.end();
    });
  }

  _get(port, path, timeoutMs) {
    return new Promise((resolve, reject) => {
      const req = http.request({ hostname: '127.0.0.1', port, path, method: 'GET', timeout: timeoutMs }, res => {
        let data = '';
        res.on('data', c => { data += c; });
        res.on('end', () => { try { resolve(JSON.parse(data)); } catch { resolve(null); } });
      });
      req.on('timeout', () => { req.destroy(); reject(new Error('ping timeout')); });
      req.on('error', reject);
      req.end();
    });
  }
}

module.exports = DaemonManager;
