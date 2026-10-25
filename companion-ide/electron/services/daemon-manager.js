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
const fs        = require('fs');
const os        = require('os');
const path      = require('path');

const STARTUP_TIMEOUT_MS = 12_000;
const PING_TIMEOUT_MS    =  3_000;
const PORT_RE            = /COMPANION_DAEMON_PORT=(\d+)/;
const TOKEN_FILE_ENV     = 'COMPANION_DAEMON_TOKEN_FILE';

class DaemonManager {
  constructor(binaryPath) {
    this._binary       = binaryPath;
    this._proc         = null;
    this._port         = null;
    this._token        = null; // bearer token read from the private token file
    this._tokenDir     = null;
    this._tokenFile    = null;
    this._ready        = false;
    this._starting     = false;
    this._startPromise = null;
    this._onOutput     = null;
    // BUG A: track in-flight request per call-id so we can abort exactly one
    this._inFlightReqs = new Map(); // callId → http.ClientRequest
    this._callSeq      = 0;
  }

  // ── Public lifecycle ──────────────────────────────────────────

  start(onOutput = null) {
    if (this._ready && this._port) return Promise.resolve(this._port);
    if (this._starting) return this._startPromise;
    this._starting = true;
    this._onOutput = onOutput;
    // Resolve this promise only after _ready is set. Returning the raw
    // _doStart() promise let a concurrent caller observe a port while the
    // first caller had not yet marked the manager ready.
    this._startPromise = this._startOnce().finally(() => {
      this._starting = false;
    });
    return this._startPromise;
  }

  async _startOnce() {
    try {
      const port = await this._doStart();
      if (!this._proc || this._proc.exitCode !== null) {
        throw new Error('Daemon exited before it became ready');
      }
      this._port = port;
      this._ready = true;
      return port;
    } catch (err) {
      this._ready = false;
      this._port = null;
      this._token = null;
      this._cleanupTokenFile();
      throw err;
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
    this._token = null;
    this._cleanupTokenFile();
  }

  /**
   * Stop the daemon and wait for the child to exit. Windows cannot replace a
   * binary that is still mapped, so a self-update must not race teardown of a
   * daemon that is running the file being replaced. The timeout bounds the
   * wait; callers still fail closed if the replacement itself cannot complete.
   */
  async stopAndWait(timeoutMs = 5000) {
    const proc = this._proc;
    this.stop();
    if (!proc || proc.exitCode !== null) return true;

    return new Promise((resolve) => {
      let settled = false;
      let timer = null;
      const finish = (exited) => {
        if (settled) return;
        settled = true;
        if (timer) clearTimeout(timer);
        proc.removeListener('exit', onExit);
        resolve(exited);
      };
      const onExit = () => finish(true);
      proc.once('exit', onExit);
      timer = setTimeout(() => finish(false), timeoutMs);
      // The child may have exited between the exitCode check and listener
      // registration, in which case the exit event has already fired.
      if (proc.exitCode !== null) finish(true);
    });
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

      req.on('timeout', () => {
        this._inFlightReqs.delete(callId);
        req.destroy();
        reject(new Error('Stream compile timeout'));
      });
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

  /** Bearer token read from the private token file written by the daemon. */
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
      let tokenDir;
      let tokenFile;
      try {
        // A private 0700 directory keeps the token off stdout and away from
        // other users. The daemon writes the file before announcing its port,
        // so the IDE can read it as soon as the port line arrives.
        tokenDir  = fs.mkdtempSync(path.join(os.tmpdir(), 'companion-daemon-'));
        tokenFile = path.join(tokenDir, 'auth-token');
      } catch (err) {
        return reject(new Error(`Failed to create daemon token directory: ${err.message}`));
      }
      this._tokenDir  = tokenDir;
      this._tokenFile = tokenFile;
      this._token     = null;

      try {
        proc = spawn(this._binary, ['daemon', '--port', '0'], {
          env: { ...process.env, [TOKEN_FILE_ENV]: tokenFile },
          stdio: ['ignore', 'pipe', 'pipe'],
        });
      } catch (err) {
        this._cleanupTokenFile();
        return reject(new Error(`Failed to spawn daemon: ${err.message}`));
      }

      this._proc = proc;
      let startupBuf = '';
      let settled = false;

      const fail = (err) => {
        if (settled) return;
        settled = true;
        clearTimeout(timer);
        this._token = null;
        this._cleanupTokenFile();
        reject(err);
      };
      const succeed = (port) => {
        if (settled) return;
        settled = true;
        clearTimeout(timer);
        resolve(port);
      };

      const timer = setTimeout(() => {
        try { proc.kill(); } catch {}
        fail(new Error('Daemon startup timed out'));
      }, STARTUP_TIMEOUT_MS);

      proc.stdout.on('data', chunk => {
        const text = chunk.toString();
        this._onOutput?.(`[daemon] ${text}`);
        // Port and token can arrive in separate chunks, so match against the
        // accumulated buffer rather than this chunk alone.
        startupBuf += text;
        const m = PORT_RE.exec(startupBuf);
        if (!m || this._token) return;

        try {
          const token = fs.readFileSync(tokenFile, 'utf8').trim();
          if (!token) throw new Error('token file was empty');
          this._token = token;
          succeed(parseInt(m[1], 10));
        } catch (err) {
          try { proc.kill(); } catch {}
          fail(new Error(
            `Daemon reported a port but did not write ${tokenFile} (${err.message}). ` +
            'Rebuild companion-cli so it supports COMPANION_DAEMON_TOKEN_FILE.'));
        }
      });

      proc.stderr.on('data', chunk => { this._onOutput?.(`[daemon] ${chunk.toString()}`); });
      proc.on('error', err => {
        // A process from a previous start must not clear the state of the
        // daemon that replaced it (stop() → start() can overlap the old
        // process's exit event).
        if (this._proc === proc) {
          this._ready = false;
          this._port = null;
          this._proc = null;
        }
        fail(err);
      });
      proc.on('close', code => {
        const current = this._proc === proc;
        if (current) {
          this._ready = false;
          this._port = null;
          this._proc = null;
        }
        if (!settled) {
          fail(new Error(`Daemon exited (code ${code}) before reporting port`));
        } else if (current) {
          // A daemon that exits after startup is no longer usable.
          this._token = null;
          this._cleanupTokenFile();
        }
      });
    });
  }

  _cleanupTokenFile() {
    const dir = this._tokenDir;
    this._tokenDir = null;
    this._tokenFile = null;
    if (dir) {
      try { fs.rmSync(dir, { recursive: true, force: true }); } catch {}
    }
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
      req.on('timeout', () => {
        this._inFlightReqs.delete(id);
        req.destroy();
        reject(new Error('Daemon RPC timeout'));
      });
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
