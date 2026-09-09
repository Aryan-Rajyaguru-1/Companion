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

const net  = require('net');
const fs   = require('fs');
const path = require('path');
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

// ── BridgeClient class ─────────────────────────────────────────
class BridgeClient {
  constructor() {
    this._serialSock   = null;
    this._onSerialData = null;
  }

  // ══════════════════════════════════════════════════════════════
  // Serial monitor  (persistent bidirectional connection)
  // ══════════════════════════════════════════════════════════════
  async connectSerial(host, port, onData) {
    // Destroy any previous in-flight socket — re-connecting without this
    // leaked the old connection and duplicated 'data' event handlers.
    this.disconnectSerial();

    return new Promise((resolve) => {
      let settled = false;
      const settle = (result) => {
        if (settled) return;
        settled = true;
        clearTimeout(timer);
        resolve(result);
      };

      this._onSerialData = onData;
      const sock = new net.Socket();
      sock.setNoDelay(true);

      // Firewalled/dropped-SYN hosts previously left the renderer stuck in
      // "Connecting…" for the full OS TCP timeout (~2 min).
      const CONNECT_TIMEOUT_MS = 8000;
      const timer = setTimeout(() => {
        sock.destroy();
        settle({ success: false, error: `Connection timed out after ${CONNECT_TIMEOUT_MS / 1000}s` });
      }, CONNECT_TIMEOUT_MS);

      sock.connect(port, host, () => {
        this._serialSock = sock;
        settle({ success: true });
      });

      sock.on('data', (chunk) => this._onSerialData?.(chunk.toString()));

      sock.on('error', (err) => {
        this._serialSock = null;
        settle({ success: false, error: err.message });
      });

      sock.on('close', () => { this._serialSock = null; });
    });
  }

  disconnectSerial() {
    if (this._serialSock) {
      this._serialSock.destroy();
      this._serialSock = null;
    }
  }

  send(data) {
    if (this._serialSock && !this._serialSock.destroyed) {
      this._serialSock.write(typeof data === 'string' ? data : Buffer.from(data));
    }
  }

  // ══════════════════════════════════════════════════════════════
  // Query bridge status
  // ══════════════════════════════════════════════════════════════
  async query(host, port) {
    return new Promise((resolve) => {
      const sock = new net.Socket();
      let response = '';
      let settled = false;
      const settle = (result) => { if (settled) return; settled = true; resolve(result); };

      sock.setTimeout(3000);
      sock.connect(port, host, () => {
        sock.write(ctrl(CMD_QUERY));
      });

      sock.on('data', (d) => {
        response += d.toString();
        if (response.includes('\n')) { sock.destroy(); settle({ success: true, info: response.trim() }); }
      });

      sock.on('timeout', () => { sock.destroy(); settle({ success: false, error: 'Timeout — is the bridge online?' }); });
      sock.on('error', (e) => settle({ success: false, error: e.message }));
      sock.on('close', () => settle({ success: false, error: 'Bridge closed the connection' }));
    });
  }

  // ══════════════════════════════════════════════════════════════
  // Upload firmware (dispatcher)
  // ══════════════════════════════════════════════════════════════
  async uploadFirmware({ host, port, baud = 115200, mcu = 'generic', avrMcu = 'atmega328p', binaryPath, onProgress }) {
    const stat = fs.statSync(binaryPath);
    onProgress?.(`» Binary: ${path.basename(binaryPath)} (${(stat.size / 1024).toFixed(1)} KB)\n`);
    onProgress?.(`» Target MCU family: ${mcu}  Baud: ${baud}\n`);

    const key = mcu.toLowerCase();
    if (key === 'esp32' || key === 'esp8266') {
      return this._uploadESP(host, port, baud, mcu, binaryPath, onProgress);
    }
    if (key === 'stm32') {
      return this._uploadSTM32(host, port, baud, binaryPath, onProgress);
    }
    if (key === 'avr' || key === 'arduino') {
      return this._uploadAVR(host, port, baud, avrMcu, binaryPath, onProgress);
    }
    return this._uploadGeneric(host, port, baud, binaryPath, onProgress);
  }

  // ══════════════════════════════════════════════════════════════
  // ESP32 / ESP8266  — delegates to esptool
  // ══════════════════════════════════════════════════════════════
  async _uploadESP(host, port, baud, chip, binaryPath, onProgress) {
    // Step 1: open a control socket, assert bootloader, then keep it open
    // until esptool has fully connected and is running.  Closing it too
    // early (the old bug) means the bridge accepts esptool as a brand-new
    // client with no bootloader sequence, and the ESP32 ROM times out.
    let ctrlSock = null;
    const ctrlReady = await new Promise((resolve) => {
      const sock = new net.Socket();
      ctrlSock = sock;
      sock.setNoDelay(true);

      sock.connect(port, host, async () => {
        sock.write(ctrl(CMD_SET_PROFILE, MCU_PROFILES[chip.toLowerCase()] || 1));
        await delay(50);
        sock.write(Buffer.concat([ctrl(CMD_SET_BAUD), baudBuffer(baud)]));
        await delay(100);
        sock.write(ctrl(CMD_ENTER_BOOT));
        // Give the target's ROM time to enter bootloader (GPIO0/BOOT0 must
        // be stable before EN rises; 200 ms is the safe minimum for ESP32).
        await delay(200);
        resolve(true);
      });
      sock.on('error', () => { ctrlSock = null; resolve(false); });
      sock.on('close', () => { ctrlSock = null; resolve(false); });
    });

    if (!ctrlReady) {
      onProgress?.('⚠ Could not reach bridge for bootloader entry — attempting upload anyway\n');
    }

    // Step 2: spawn esptool.  The bridge firmware serves one client at a
    // time: esptool will queue behind our still-open control socket until
    // we release it, so we destroy it as soon as esptool has started and
    // the output indicates it is connecting.
    return new Promise((resolve) => {
      const python  = process.platform === 'win32' ? 'python' : 'python3';
      const sockUrl = `socket://${host}:${port}`;
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
        // Always clean up control socket on exit
        if (ctrlSock) { ctrlSock.destroy(); ctrlSock = null; }
        resolve(code === 0
          ? { success: true }
          : { success: false, error: 'esptool exited with errors. See output above.' });
      });

      proc.on('error', () => {
        if (ctrlSock) { ctrlSock.destroy(); ctrlSock = null; }
        resolve({
          success: false,
          error: 'esptool not found. Install it with:\n  pip install esptool',
        });
      });
    });
  }

  // ══════════════════════════════════════════════════════════════
  // STM32  — native UART bootloader (AN3155)
  // ══════════════════════════════════════════════════════════════
  async _uploadSTM32(host, port, baud, binaryPath, onProgress) {
    const fw = fs.readFileSync(binaryPath);

    return new Promise((resolve) => {
      let settled = false;
      const done = (result) => { if (settled) return; settled = true; resolve(result); };
      const sock = new net.Socket();
      sock.setNoDelay(true);

      sock.connect(port, host, async () => {
        try {
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
  async _uploadAVR(host, port, baud, avrMcu, binaryPath, onProgress) {
    // Enter bootloader via bridge, then release for avrdude
    await new Promise((resolve) => {
      let settled = false;
      const settle = () => { if (settled) return; settled = true; resolve(); };
      const sock = new net.Socket();
      sock.connect(port, host, async () => {
        sock.write(ctrl(CMD_SET_PROFILE, MCU_PROFILES.avr));
        await delay(50);
        sock.write(ctrl(CMD_ENTER_BOOT));
        await delay(200);
        sock.destroy();
        settle();
      });
      sock.on('error', settle);
      sock.on('close', settle);
    });

    return new Promise((resolve) => {
      const ext = path.extname(binaryPath).toLowerCase();
      const fmt = ext === '.hex' ? 'i' : 'r';
      // avrdude network protocol syntax is "net:host:port" — "socket://" is
      // esptool-only and made avrdude fail with "can't open device".
      const sockUrl = `net:${host}:${port}`;
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
        resolve(code === 0
          ? { success: true }
          : { success: false, error: 'avrdude failed. See output above.' });
      });

      proc.on('error', () => {
        resolve({ success: false, error: 'avrdude not found. Install Arduino IDE to get avrdude in PATH.' });
      });
    });
  }

  // ══════════════════════════════════════════════════════════════
  // Generic  — raw binary stream for custom bootloaders
  // ══════════════════════════════════════════════════════════════
  async _uploadGeneric(host, port, baud, binaryPath, onProgress) {
    const fw = fs.readFileSync(binaryPath);

    return new Promise((resolve) => {
      const sock = new net.Socket();
      sock.setNoDelay(true);

      sock.connect(port, host, async () => {
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
        resolve({ success: true });
      });

      sock.on('error', (e) => resolve({ success: false, error: e.message }));
      sock.on('close', () => resolve({ success: false, error: 'Bridge closed the connection' }));
    });
  }
}

// ══════════════════════════════════════════════════════════════
// STM32 low-level helpers
// ══════════════════════════════════════════════════════════════
function readByte(sock, timeout = 3000) {
  return new Promise((resolve) => {
    const timer = setTimeout(() => { resolve(null); }, timeout);
    sock.once('data', (d) => { clearTimeout(timer); resolve(d[0]); });
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