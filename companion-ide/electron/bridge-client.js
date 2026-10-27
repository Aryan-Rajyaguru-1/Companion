/**
 * bridge-client.js
 * Manages the TCP connection to the ESP32 WiFi bridge.
 *
 * Supports upload for:
 *  - ESP32 / ESP8266  → via esptool
 *  - STM32            → native AN3155 UART bootloader
 *  - AVR / Arduino    → via avrdude
 *  - Generic          → raw byte stream
 *
 * Also provides a persistent serial-monitor connection (separate session).
 */

const net    = require('net');
const fs     = require('fs');
const path   = require('path');
const crypto = require('crypto');
const { spawn } = require('child_process');

// ── Control protocol constants (must match ESP32 firmware) ────
const CTRL_A            = 0xEF;
const CTRL_B            = 0xBE;
const CMD_ENTER_BOOT    = 0x01;
const CMD_RESET         = 0x02;
const CMD_RELEASE       = 0x03;
const CMD_SET_BAUD      = 0x10;
const CMD_SET_PROFILE   = 0x11;
const CMD_QUERY         = 0x20;
const CMD_AUTH_BEGIN    = 0x30;
const CMD_AUTH_RESPONSE = 0x31;
const CMD_AUTH_CHALLENGE= 0x32;
const CMD_AUTH_OK       = 0x33;
const CMD_AUTH_FAIL     = 0x34;
const AUTH_NONCE_LEN    = 32;

const MCU_PROFILES = { generic: 0, esp32: 1, esp8266: 1, avr: 2, arduino: 2, stm32: 3 };

// avrMcuForFqbn maps an Arduino FQBN (or a bare family "avr"/"arduino") to the
// avrdude part name, mirroring companion-cli's resolveAVRMCU. Kept here so the
// wireless AVR uploader has a single source of truth and never silently
// assumes atmega328p.
const AVR_MCU_TABLE = {
  'arduino:avr:uno':      'atmega328p',
  'arduino:avr:mega':     'atmega2560',
  'arduino:avr:mega2560': 'atmega2560',
  'arduino:avr:nano':     'atmega328p',
  'arduino:avr:leonardo': 'atmega32u4',
  'arduino:avr:micro':    'atmega32u4',
  'arduino:avr:pro':      'atmega328p',
  'arduino:avr:ethernet': 'atmega328p',
};
function avrMcuForFqbn(fqbn) {
  const key = String(fqbn || '').toLowerCase();
  if (AVR_MCU_TABLE[key]) return AVR_MCU_TABLE[key];
  const parts = key.split(':');
  if (parts.length >= 3) {
    if (parts[2] === 'mega' || parts[2] === 'mega2560') return 'atmega2560';
    if (parts[2] === 'leonardo' || parts[2] === 'micro') return 'atmega32u4';
  }
  return 'atmega328p';
}

// ── Helpers ────────────────────────────────────────────────────
const delay = (ms) => new Promise((r) => setTimeout(r, ms));

function ctrl(...bytes) {
  return Buffer.from([CTRL_A, CTRL_B, ...bytes]);
}

function baudBuffer(baud) {
  const b = Buffer.alloc(4);
  b.writeUInt32BE(baud);
  return b;
}

// ── Authentication (must match esp32_bridge.ino) ──────────────
// Reads exactly N bytes from a socket without leaking listeners. The reader
// stays attached only for the handshake; callers detach (authenticateSocket
// does it in a finally block) before their own data handling starts.
function makeSocketReader(sock) {
  let buf = Buffer.alloc(0);
  let waiter = null;
  let failure = null;

  const fail = (err) => {
    if (!failure) failure = err;
    if (waiter) {
      const w = waiter;
      waiter = null;
      clearTimeout(w.timer);
      w.reject(failure);
    }
  };
  const onData = (d) => {
    buf = Buffer.concat([buf, d]);
    if (waiter && buf.length >= waiter.n) {
      const w = waiter;
      waiter = null;
      clearTimeout(w.timer);
      const out = buf.subarray(0, w.n);
      buf = buf.subarray(w.n);
      w.resolve(out);
    }
  };
  const onClose = () => fail(new Error('Bridge closed the connection during authentication'));
  const onError = (e) => fail(new Error(`Bridge connection failed during authentication: ${e.message}`));

  sock.on('data', onData);
  sock.on('close', onClose);
  sock.on('error', onError);

  return {
    readExact(n, timeoutMs) {
      if (failure) return Promise.reject(failure);
      if (buf.length >= n) {
        const out = buf.subarray(0, n);
        buf = buf.subarray(n);
        return Promise.resolve(out);
      }
      return new Promise((resolve, reject) => {
        const timer = setTimeout(() => {
          if (waiter && waiter.timer === timer) waiter = null;
          const err = new Error(`Timed out after ${timeoutMs}ms waiting for the bridge`);
          err.code = 'ETIMEDOUT';
          reject(err);
        }, timeoutMs);
        waiter = { n, resolve, reject, timer };
      });
    },
    drain() {
      const out = buf;
      buf = Buffer.alloc(0);
      return out;
    },
    detach() {
      sock.off('data', onData);
      sock.off('close', onClose);
      sock.off('error', onError);
      if (waiter) {
        const w = waiter;
        waiter = null;
        clearTimeout(w.timer);
        w.reject(failure || new Error('Authentication reader detached'));
      }
    },
  };
}

// Probe the bridge for HMAC authentication. A configured key is fail-closed:
// missing/unknown challenges and rejected keys are errors. Without a key,
// legacy firmware that never answers remains usable.
async function authenticateSocket(sock, bridgeKey, timeoutMs) {
  const key = String(bridgeKey || '');
  const reader = makeSocketReader(sock);
  try {
    sock.write(ctrl(CMD_AUTH_BEGIN));

    let header;
    try {
      header = await reader.readExact(3, timeoutMs);
    } catch (e) {
      // Only a timeout proves legacy firmware ignored the probe. A closed or
      // failed socket is not legacy firmware and must fail closed even when no
      // key is configured.
      if (!key && e.code === 'ETIMEDOUT') {
        return { authenticated: false, extra: reader.drain() };
      }
      if (!key) {
        throw new Error(`Bridge connection failed during authentication (${e.message}).`);
      }
      throw new Error(
        `Bridge did not answer the authentication challenge (${e.message}). ` +
        'Reflash the bridge firmware, or clear bridge.key to allow legacy unauthenticated mode.'
      );
    }

    if (header[0] !== CTRL_A || header[1] !== CTRL_B || header[2] !== CMD_AUTH_CHALLENGE) {
      const extra = Buffer.concat([header, reader.drain()]);
      if (key) {
        throw new Error(
          'Bridge did not answer the authentication challenge. ' +
          'Reflash the bridge firmware, or clear bridge.key to allow legacy unauthenticated mode.'
        );
      }
      return { authenticated: false, extra };
    }

    if (!key) {
      throw new Error(
        'The bridge requires a key, but none is configured. ' +
        'Set bridge.key (or COMPANION_BRIDGE_KEY) to the BRIDGE_KEY compiled into the firmware.'
      );
    }

    const nonce = await reader.readExact(AUTH_NONCE_LEN, timeoutMs);
    const tag = crypto.createHmac('sha256', key).update(nonce).digest();
    sock.write(Buffer.concat([ctrl(CMD_AUTH_RESPONSE), tag]));

    const status = await reader.readExact(3, timeoutMs);
    if (status[0] !== CTRL_A || status[1] !== CTRL_B) {
      throw new Error('Unexpected authentication reply from the bridge.');
    }
    if (status[2] === CMD_AUTH_FAIL) {
      throw new Error('The bridge rejected the bridge key — it must match BRIDGE_KEY in the firmware.');
    }
    if (status[2] !== CMD_AUTH_OK) {
      throw new Error(`Unexpected authentication status 0x${status[2].toString(16)}.`);
    }
    return { authenticated: true, extra: reader.drain() };
  } finally {
    reader.detach();
  }
}

// Loopback proxy for esptool (socket://) and avrdude (net:), neither of which
// can perform the HMAC handshake. Each local connection authenticates a fresh
// upstream connection and then pipes raw bytes transparently.
function startLocalProxy(host, port, key) {
  if (!String(key || '')) {
    return Promise.reject(new Error('An authenticated bridge proxy requires a bridge key.'));
  }
  return new Promise((resolve, reject) => {
    const connections = new Set();
    const server = net.createServer((local) => {
      connections.add(local);
      const remote = new net.Socket();
      remote.setNoDelay(true);
      connections.add(remote);

      const cleanup = () => { connections.delete(local); connections.delete(remote); };
      local.on('close', () => {
        cleanup();
        if (!remote.destroyed) remote.destroy();
      });
      remote.on('close', () => {
        cleanup();
        if (!local.destroyed) local.destroy();
      });
      local.on('error', () => remote.destroy());
      remote.on('error', () => local.destroy());

      remote.connect(port, host, async () => {
        try {
          await authenticateSocket(remote, key, 5000);
        } catch {
          local.destroy();
          remote.destroy();
          return;
        }
        if (local.destroyed || remote.destroyed) {
          local.destroy();
          remote.destroy();
          return;
        }
        local.pipe(remote);
        remote.pipe(local);
      });
    });

    server.on('error', reject);
    server.listen(0, '127.0.0.1', () => {
      resolve({
        port: server.address().port,
        close: () => new Promise((done) => {
          for (const s of connections) s.destroy();
          connections.clear();
          server.close(() => done());
        }),
      });
    });
  });
}

// ── BridgeClient class ─────────────────────────────────────────
class BridgeClient {
  constructor() {
    this._serialSock    = null;
    // A socket is pending until authentication succeeds. Keeping it separate
    // from _serialSock lets disconnect destroy an in-flight connection without
    // exposing pre-auth frames to the monitor.
    this._serialPending = null;
    this._onSerialData  = null;
  }

  // ══════════════════════════════════════════════════════════════
  // Serial monitor  (persistent bidirectional connection)
  // ══════════════════════════════════════════════════════════════
  async connectSerial(host, port, onData, bridgeKey = '') {
    // Destroy any previous in-flight socket — re-connecting without this
    // leaked the old connection and duplicated 'data' event handlers.
    this.disconnectSerial();
    // A new connection means a new STM32 session: anything still queued
    // belongs to the previous one.
    resetSTM32RX();

    return new Promise((resolve) => {
      let settled = false;
      let timer = null;
      const settle = (result) => {
        if (settled) return;
        settled = true;
        if (timer) clearTimeout(timer);
        resolve(result);
      };

      const sock = new net.Socket();
      sock.setNoDelay(true);
      const pending = {
        sock,
        cancel: () => settle({ success: false, error: 'Connection cancelled' }),
      };
      this._serialPending = pending;
      this._onSerialData = onData;

      // Firewalled/dropped-SYN hosts previously left the renderer stuck in
      // "Connecting…" for the full OS TCP timeout (~2 min).
      const CONNECT_TIMEOUT_MS = 8000;
      timer = setTimeout(() => {
        if (this._serialPending === pending) {
          this._serialPending = null;
          this._onSerialData = null;
        }
        sock.destroy();
        settle({ success: false, error: `Connection timed out after ${CONNECT_TIMEOUT_MS / 1000}s` });
      }, CONNECT_TIMEOUT_MS);

      sock.connect(port, host, async () => {
        try {
          const auth = await authenticateSocket(sock, bridgeKey, bridgeKey ? 5000 : 500);
          // A disconnect or a newer connect may have superseded this socket
          // while the handshake was in flight. Never resurrect it over the
          // current session.
          if (this._serialPending !== pending) {
            sock.destroy();
            return;
          }
          this._serialPending = null;
          this._serialSock = sock;
          settle({ success: true });
          // Legacy firmware can emit target bytes while we probe for auth.
          if (this._serialSock === sock && auth.extra && auth.extra.length > 0) {
            onData?.(auth.extra.toString());
          }
        } catch (e) {
          sock.destroy();
          if (this._serialPending === pending) {
            this._serialPending = null;
            this._onSerialData = null;
          }
          settle({ success: false, error: e.message });
        }
      });

      sock.on('data', (chunk) => {
        // A socket that was replaced by a newer connect must not feed the
        // current monitor (or the new socket's callback).
        if (this._serialSock === sock) onData?.(chunk.toString());
      });

      sock.on('error', (err) => {
        if (this._serialPending === pending) {
          this._serialPending = null;
          this._onSerialData = null;
        }
        if (this._serialSock === sock) {
          this._serialSock = null;
          this._onSerialData = null;
        }
        settle({ success: false, error: err.message });
      });

      // Only a socket that is still pending/current may clear the fields. The
      // old unconditional handler ran after a reconnect and nulled the NEW
      // socket, leaving send() silently doing nothing.
      sock.on('close', () => {
        if (this._serialPending === pending) {
          this._serialPending = null;
          this._onSerialData = null;
          settle({ success: false, error: 'Connection closed' });
        }
        if (this._serialSock === sock) {
          this._serialSock = null;
          this._onSerialData = null;
        }
      });
    });
  }

  disconnectSerial() {
    // Drop queued bytes on the way out too, so a later connect cannot inherit
    // them even if it skips its own reset.
    resetSTM32RX();
    const pending = this._serialPending;
    this._serialPending = null;
    if (pending) {
      pending.sock.destroy();
      pending.cancel();
    }
    if (this._serialSock) {
      this._serialSock.destroy();
      this._serialSock = null;
    }
    this._onSerialData = null;
  }

  send(data) {
    if (this._serialSock && !this._serialSock.destroyed) {
      this._serialSock.write(typeof data === 'string' ? data : Buffer.from(data));
    }
  }

  // ══════════════════════════════════════════════════════════════
  // Query bridge status
  // ══════════════════════════════════════════════════════════════
  async query(host, port, bridgeKey = '') {
    return new Promise((resolve) => {
      const sock = new net.Socket();
      let response = '';
      let settled = false;
      let authenticated = false;
      const settle = (result) => { if (settled) return; settled = true; sock.destroy(); resolve(result); };
      // Keep a listener attached for the whole session so bytes cannot be
      // dropped between the auth reader detaching and the query starting,
      // but ignore handshake frames. Also ignore bytes captured during the
      // legacy probe: they are target UART output, not a status reply, and
      // treating a boot log as the answer skipped CMD_QUERY entirely.
      const onData = (d) => {
        if (!authenticated) return;
        response += d.toString();
        if (response.includes('\n')) settle({ success: true, info: response.trim() });
      };
      sock.on('data', onData);

      sock.connect(port, host, async () => {
        try {
          await authenticateSocket(sock, bridgeKey, bridgeKey ? 5000 : 500);
          authenticated = true;
        } catch (e) {
          settle({ success: false, error: e.message });
          return;
        }
        sock.setTimeout(3000);
        sock.write(ctrl(CMD_QUERY));
      });

      sock.on('timeout', () => settle({ success: false, error: 'Timeout — is the bridge online?' }));
      sock.on('error', (e) => settle({ success: false, error: e.message }));
      sock.on('close', () => settle({ success: false, error: 'Bridge closed the connection' }));
    });
  }

  // ══════════════════════════════════════════════════════════════
  // Upload firmware (dispatcher)
  // ══════════════════════════════════════════════════════════════
  async uploadFirmware({ host, port, baud = 115200, mcu = 'generic', avrMcu = 'atmega328p', binaryPath, bridgeKey = '', onProgress }) {
    let stat;
    try {
      stat = await fs.promises.stat(binaryPath);
    } catch (e) {
      return { success: false, error: `Binary not found: ${binaryPath} (${e?.message || e})` };
    }
    // Wrap the progress-stream write so a broken/closed stream surfaces as a
    // returned error instead of an uncaught exception.
    const safeProgress = (msg) => {
      try { onProgress?.(msg); } catch (e) { throw new Error(`Progress stream failed: ${e?.message || e}`); }
    };
    try {
      safeProgress(`» Binary: ${path.basename(binaryPath)} (${(stat.size / 1024).toFixed(1)} KB)\n`);
      safeProgress(`» Target MCU family: ${mcu}  Baud: ${baud}\n`);
    } catch (e) {
      return { success: false, error: e?.message || String(e) };
    }
    // From here on, forward safeProgress (guarded) instead of raw onProgress.

    const guardedProgress = (msg) => { try { onProgress?.(msg); } catch (e) { throw new Error(`Progress stream failed: ${e?.message || e}`); } };
    const key = String(mcu || 'generic').toLowerCase();
    try {
      if (key === 'esp32' || key === 'esp8266') {
        return await this._uploadESP(host, port, baud, mcu, binaryPath, guardedProgress, bridgeKey);
      }
      if (key === 'stm32') {
        return await this._uploadSTM32(host, port, baud, binaryPath, guardedProgress, bridgeKey);
      }
      if (key === 'avr' || key === 'arduino') {
        return await this._uploadAVR(host, port, baud, avrMcu, binaryPath, guardedProgress, bridgeKey);
      }
      return await this._uploadGeneric(host, port, baud, binaryPath, guardedProgress, bridgeKey);
    } catch (e) {
      return { success: false, error: e?.message || String(e) };
    }
  }

  // ══════════════════════════════════════════════════════════════
  // ESP32 / ESP8266  — delegates to esptool
  // ══════════════════════════════════════════════════════════════
  async _uploadESP(host, port, baud, chip, binaryPath, onProgress, bridgeKey = '') {
    try { await fs.promises.access(binaryPath, fs.constants.R_OK); } catch (e) { return { success: false, error: `Cannot read binary: ${e?.message || e}` }; }
    // Step 1: open a control socket, authenticate, assert bootloader, then
    // keep it open until esptool has fully connected and is running. Closing
    // it too early (the old bug) means the bridge accepts esptool as a
    // brand-new client with no bootloader sequence, and the ESP32 ROM times
    // out.
    let ctrlSock = null;
    let ctrlError = null;
    const ctrlReady = await new Promise((resolve) => {
      let settled = false;
      const finish = (ok, err) => {
        if (settled) return;
        settled = true;
        if (err) ctrlError = err;
        resolve(ok);
      };
      const sock = new net.Socket();
      ctrlSock = sock;
      sock.setNoDelay(true);

      sock.connect(port, host, async () => {
        try {
          await authenticateSocket(sock, bridgeKey, bridgeKey ? 5000 : 500);
        } catch (e) {
          sock.destroy();
          ctrlSock = null;
          finish(false, e.message);
          return;
        }
        sock.write(ctrl(CMD_SET_PROFILE, MCU_PROFILES[chip.toLowerCase()] || 1));
        await delay(50);
        sock.write(Buffer.concat([ctrl(CMD_SET_BAUD), baudBuffer(baud)]));
        await delay(100);
        sock.write(ctrl(CMD_ENTER_BOOT));
        // Give the target's ROM time to enter bootloader (GPIO0/BOOT0 must
        // be stable before EN rises; 200 ms is the safe minimum for ESP32).
        await delay(200);
        finish(true);
      });
      sock.on('error', (e) => { ctrlSock = null; finish(false, `Bridge: ${e.message}`); });
      sock.on('close', () => { ctrlSock = null; finish(false, 'Bridge closed the connection'); });
    });

    if (!ctrlReady) {
      onProgress?.(`⚠ ${ctrlError}\n`);
      return { success: false, error: ctrlError };
    }

    // esptool cannot perform the HMAC handshake, so a keyed bridge is exposed
    // as a loopback socket. The proxy authenticates each upstream connection.
    let proxy = null;
    if (bridgeKey) {
      try {
        proxy = await startLocalProxy(host, port, bridgeKey);
        onProgress?.(`» Authenticated bridge proxy on 127.0.0.1:${proxy.port}\n`);
      } catch (e) {
        if (ctrlSock) { ctrlSock.destroy(); ctrlSock = null; }
        return { success: false, error: `Could not start authenticated bridge proxy: ${e.message}` };
      }
    }

    // Step 2: spawn esptool.  The bridge firmware serves one client at a
    // time: esptool will queue behind our still-open control socket until
    // we release it, so we destroy it as soon as esptool has started and
    // the output indicates it is connecting.
    return new Promise((resolve) => {
      let settled = false;
      const finish = async (result) => {
        if (settled) return;
        settled = true;
        if (ctrlSock) { ctrlSock.destroy(); ctrlSock = null; }
        if (proxy) {
          try { await proxy.close(); } catch {}
          proxy = null;
        }
        resolve(result);
      };

      const python  = process.platform === 'win32' ? 'python' : 'python3';
      const sockUrl = proxy
        ? `socket://127.0.0.1:${proxy.port}`
        : `socket://${host}:${port}`;
      const args = [
        '-m', 'esptool',
        '--chip',   chip,
        '--port',   sockUrl,
        '--baud',   String(baud),
        '--before', 'no_reset',   // We already pulsed EN/BOOT via bridge
        '--after',  'hard_reset',
        'write_flash',
        '--flash_mode', 'dio',
        '--flash_size', 'detect',
        '--compress',             // Faster transfers over TCP
        '0x0', binaryPath,
      ];

      onProgress?.('» Launching esptool.py...\n');
      const proc = spawn(python, args);

      let esptoolConnecting = false;

      const handleOutput = (d) => {
        const text = d.toString();
        onProgress?.(text);

        // Release the control socket the moment esptool is actively
        // trying to connect — this hands the TCP port over to esptool.
        if (!esptoolConnecting && (
          text.includes('Connecting') ||
          text.includes('Serial port')
        )) {
          esptoolConnecting = true;
          if (ctrlSock) {
            ctrlSock.destroy();
            ctrlSock = null;
          }
        }
      };

      proc.stdout.on('data', handleOutput);
      proc.stderr.on('data', handleOutput);

      proc.on('close', (code) => {
        finish(code === 0
          ? { success: true }
          : { success: false, error: 'esptool exited with errors. See output above.' });
      });

      proc.on('error', () => {
        // Platform-correct hint: Windows has no python3, and testers were
        // being told to run a command their machine cannot execute.
        const hint = process.platform === 'win32'
          ? 'py -m pip install esptool'
          : 'python3 -m pip install esptool';
        finish({
          success: false,
          error: `esptool not found. Install it with:\n  ${hint}`,
        });
      });
    });
  }

  // ══════════════════════════════════════════════════════════════
  // STM32  — native UART bootloader (AN3155)
  // ══════════════════════════════════════════════════════════════
  async _uploadSTM32(host, port, baud, binaryPath, onProgress, bridgeKey = '') {
    let fw;
    try { fw = await fs.promises.readFile(binaryPath); } catch (e) { return { success: false, error: `Cannot read binary: ${e?.message || e}` }; }
    resetSTM32RX();

    return new Promise((resolve) => {
      let settled = false;
      const done = (result) => { if (settled) return; settled = true; resolve(result); };
      const sock = new net.Socket();
      sock.setNoDelay(true);

      sock.connect(port, host, async () => {
        try {
          const auth = await authenticateSocket(sock, bridgeKey, bridgeKey ? 5000 : 500);
          if (auth.extra && auth.extra.length > 0) {
            stm32RX = Buffer.concat([auth.extra, stm32RX]);
          }

          // Configure bridge
          sock.write(ctrl(CMD_SET_PROFILE, MCU_PROFILES.stm32));
          await delay(50);
          sock.write(Buffer.concat([ctrl(CMD_SET_BAUD), baudBuffer(baud)]));
          await delay(100);
          sock.write(ctrl(CMD_ENTER_BOOT));
          await delay(500);

          // Sync
          onProgress?.('» Syncing with STM32 bootloader...\n');
          if (!await stm32Sync(sock)) {
            sock.destroy();
            return done({ success: false, error: 'STM32 sync failed. Check BOOT0 pin and NRST wiring.' });
          }

          // Get bootloader info
          await stm32GetInfo(sock, onProgress);

          // Mass erase
          onProgress?.('» Erasing flash...\n');
          if (!await stm32MassErase(sock)) {
            sock.destroy();
            return done({ success: false, error: 'STM32 flash erase failed.' });
          }

          // Write
          onProgress?.(`» Writing ${fw.length} bytes to 0x08000000...\n`);
          const FLASH_BASE = 0x08000000;
          const CHUNK = 256;
          for (let i = 0; i < fw.length; i += CHUNK) {
            const chunk = fw.slice(i, Math.min(i + CHUNK, fw.length));
            if (!await stm32WriteMemory(sock, FLASH_BASE + i, chunk)) {
              sock.destroy();
              return done({ success: false, error: `Write failed at 0x${(FLASH_BASE + i).toString(16).toUpperCase()}` });
            }
            const pct = Math.round((i + chunk.length) * 100 / fw.length);
            onProgress?.(`\r  ${String(pct).padStart(3)}%  [${i + chunk.length}/${fw.length} B]`);
          }
          onProgress?.('\n');

          // Release and run
          sock.write(ctrl(CMD_RELEASE));
          await delay(100);
          sock.write(ctrl(CMD_RESET));
          await delay(200);
          sock.destroy();
          done({ success: true });

        } catch (err) {
          sock.destroy();
          done({ success: false, error: err.message });
        }
      });

      sock.on('error', (e) => done({ success: false, error: `Bridge: ${e.message}` }));
      sock.on('close', () => done({ success: false, error: 'Bridge closed the connection' }));
    });
  }

  // ══════════════════════════════════════════════════════════════
  // AVR / Arduino  — delegates to avrdude
  // ══════════════════════════════════════════════════════════════
  async _uploadAVR(host, port, baud, avrMcu, binaryPath, onProgress, bridgeKey = '') {
    try { await fs.promises.access(binaryPath, fs.constants.R_OK); } catch (e) { return { success: false, error: `Cannot read binary: ${e?.message || e}` }; }
    // Enter bootloader via bridge, then release for avrdude.
    let ctrlError = null;
    const ctrlReady = await new Promise((resolve) => {
      let settled = false;
      const finish = (ok, err) => {
        if (settled) return;
        settled = true;
        if (err) ctrlError = err;
        resolve(ok);
      };
      const sock = new net.Socket();
      sock.connect(port, host, async () => {
        try {
          await authenticateSocket(sock, bridgeKey, bridgeKey ? 5000 : 500);
        } catch (e) {
          sock.destroy();
          finish(false, e.message);
          return;
        }
        sock.write(ctrl(CMD_SET_PROFILE, MCU_PROFILES.avr));
        await delay(50);
        sock.write(ctrl(CMD_ENTER_BOOT));
        await delay(200);
        sock.destroy();
        finish(true);
      });
      sock.on('error', (e) => finish(false, `Bridge: ${e.message}`));
      sock.on('close', () => finish(false, 'Bridge closed the connection'));
    });
    if (!ctrlReady) {
      onProgress?.(`⚠ ${ctrlError}\n`);
      return { success: false, error: ctrlError };
    }

    // avrdude cannot perform the HMAC handshake; the loopback proxy does it.
    let proxy = null;
    if (bridgeKey) {
      try {
        proxy = await startLocalProxy(host, port, bridgeKey);
        onProgress?.(`» Authenticated bridge proxy on 127.0.0.1:${proxy.port}\n`);
      } catch (e) {
        return { success: false, error: `Could not start authenticated bridge proxy: ${e.message}` };
      }
    }

    return new Promise((resolve) => {
      let settled = false;
      const finish = async (result) => {
        if (settled) return;
        settled = true;
        if (proxy) {
          try { await proxy.close(); } catch {}
          proxy = null;
        }
        resolve(result);
      };

      const ext = path.extname(binaryPath).toLowerCase();
      const fmt = ext === '.hex' ? 'i' : 'r';
      // avrdude network protocol syntax is "net:host:port" — "socket://" is
      // esptool-only and made avrdude fail with "can't open device".
      const sockUrl = proxy
        ? `net:127.0.0.1:${proxy.port}`
        : `net:${host}:${port}`;
      const args = [
        '-p', avrMcu,
        '-c', 'arduino',
        '-P', sockUrl,
        '-b', String(baud),
        '-D',
        '-U', `flash:w:${binaryPath}:${fmt}`,
      ];

      onProgress?.('» Launching avrdude...\n');
      const proc = spawn('avrdude', args);

      proc.stdout.on('data', (d) => onProgress?.(d.toString()));
      proc.stderr.on('data', (d) => onProgress?.(d.toString()));

      proc.on('close', (code) => {
        finish(code === 0
          ? { success: true }
          : { success: false, error: 'avrdude failed. See output above.' });
      });

      proc.on('error', () => {
        finish({ success: false, error: 'avrdude not found. Install Arduino IDE to get avrdude in PATH.' });
      });
    });
  }

  // ══════════════════════════════════════════════════════════════
  // Generic  — raw binary stream for custom bootloaders
  // ══════════════════════════════════════════════════════════════
  async _uploadGeneric(host, port, baud, binaryPath, onProgress, bridgeKey = '') {
    let fw;
    try { fw = await fs.promises.readFile(binaryPath); } catch (e) { return { success: false, error: `Cannot read binary: ${e?.message || e}` }; }

    return new Promise((resolve) => {
      let settled = false;
      const finish = (result) => {
        if (settled) return;
        settled = true;
        resolve(result);
      };
      const sock = new net.Socket();
      sock.setNoDelay(true);

      sock.connect(port, host, async () => {
        try {
          await authenticateSocket(sock, bridgeKey, bridgeKey ? 5000 : 500);
        } catch (e) {
          sock.destroy();
          finish({ success: false, error: e.message });
          return;
        }

        sock.write(Buffer.concat([ctrl(CMD_SET_BAUD), baudBuffer(baud)]));
        await delay(100);
        sock.write(ctrl(CMD_ENTER_BOOT));
        await delay(500);

        onProgress?.(`» Streaming ${fw.length} bytes (raw)...\n`);
        const CHUNK = 256;
        for (let i = 0; i < fw.length; i += CHUNK) {
          sock.write(fw.slice(i, Math.min(i + CHUNK, fw.length)));
          await delay(8);
          const pct = Math.round(Math.min(i + CHUNK, fw.length) * 100 / fw.length);
          onProgress?.(`\r  ${String(pct).padStart(3)}%`);
        }
        onProgress?.('\n');

        sock.write(ctrl(CMD_RELEASE));
        await delay(100);
        sock.write(ctrl(CMD_RESET));
        await delay(200);
        sock.destroy();
        finish({ success: true });
      });

      sock.on('error', (e) => finish({ success: false, error: e.message }));
      sock.on('close', () => finish({ success: false, error: 'Bridge closed the connection' }));
    });
  }
}

// ══════════════════════════════════════════════════════════════
// STM32 low-level helpers
// ══════════════════════════════════════════════════════════════
// stm32RX buffers bytes that arrived but were not consumed yet. A single TCP
// read can carry several protocol bytes; dropping the tail desynchronises the
// AN3155 handshake (and a leaked listener from a timed-out read would later
// resolve the WRONG promise with a stray byte).
let stm32RX = Buffer.alloc(0);

// resetSTM32RX drops bytes left over from a previous session. The buffer
// outlives the socket on purpose — that is what stops one TCP read's tail being
// dropped mid-handshake — but nothing ever cleared it between sessions, so a
// session that was cancelled or timed out with bytes still queued handed them
// to the NEXT session's readByte(). That desynchronises the AN3155 handshake,
// and a stray byte from the old run can resolve a fresh read with the wrong
// value. Any session boundary must call this.
function resetSTM32RX() {
  stm32RX = Buffer.alloc(0);
}

function readByte(sock, timeout = 3000) {
  if (stm32RX.length > 0) {
    const b = stm32RX[0];
    stm32RX = stm32RX.subarray(1);
    return Promise.resolve(b);
  }
  return new Promise((resolve) => {
    const onData = (d) => {
      if (!d || d.length === 0) return;
      detach();
      stm32RX = Buffer.from(d.subarray(1)); // keep the rest for the next read
      resolve(d[0]);
    };
    const timer = setTimeout(() => { detach(); resolve(null); }, timeout);
    function detach() {
      clearTimeout(timer);
      sock.off('data', onData); // never leave a listener behind
    }
    sock.on('data', onData);
  });
}

async function stm32Sync(sock) {
  for (let i = 0; i < 5; i++) {
    sock.write(Buffer.from([0x7F]));
    const b = await readByte(sock, 800);
    if (b === 0x79) return true;
    await delay(200);
  }
  return false;
}

async function stm32Cmd(sock, opcode) {
  sock.write(Buffer.from([opcode, opcode ^ 0xFF]));
  const b = await readByte(sock);
  return b === 0x79;
}

async function stm32GetInfo(sock, onProgress) {
  if (!await stm32Cmd(sock, 0x00)) return;
  const n = await readByte(sock);
  if (n === null) return;
  const data = [];
  for (let i = 0; i <= n; i++) {
    const b = await readByte(sock);
    if (b !== null) data.push(b);
  }
  await readByte(sock); // final ACK
  onProgress?.(`» BL version 0x${data[0]?.toString(16).toUpperCase()} — ${data.length - 1} commands\n`);
}

async function stm32MassErase(sock) {
  if (!await stm32Cmd(sock, 0x44)) return false;
  sock.write(Buffer.from([0xFF, 0xFF, 0x00]));
  const b = await readByte(sock, 30000); // mass erase can take a while
  return b === 0x79;
}

async function stm32WriteMemory(sock, address, data) {
  if (!await stm32Cmd(sock, 0x31)) return false;

  // Pad to 4-byte boundary (fresh buffer; do not mutate the caller's slice)
  const padded = Buffer.alloc(Math.ceil(data.length / 4) * 4, 0xFF);
  data.copy(padded);

  // Address + checksum
  const ab = Buffer.alloc(4);
  ab.writeUInt32BE(address);
  const addrCs = ab[0] ^ ab[1] ^ ab[2] ^ ab[3];
  sock.write(Buffer.concat([ab, Buffer.from([addrCs])]));
  if (await readByte(sock) !== 0x79) return false;

  // (N-1) + data + XOR checksum
  let xor = padded.length - 1;
  for (const byte of padded) xor ^= byte;
  sock.write(Buffer.concat([Buffer.from([padded.length - 1]), padded, Buffer.from([xor])]));
  const ack = await readByte(sock, 5000);
  return ack === 0x79;
}

module.exports = BridgeClient;
module.exports.avrMcuForFqbn = avrMcuForFqbn;
// Test hook only: the upload paths use this internally, but exporting it lets
// the protocol suite exercise the loopback auth/pipe without esptool/avrdude.
module.exports.startLocalProxy = startLocalProxy;