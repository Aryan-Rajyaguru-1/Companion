// The IDE's bridge client is a second implementation of the ESP32 wire
// protocol, independent of the Go CLI. These tests drive real loopback sockets
// so they exercise the same bytes the firmware sees: challenge, HMAC response,
// status, then the original control/raw stream.
import { describe, it, expect } from 'vitest';
import net from 'node:net';
import crypto from 'node:crypto';
import { once } from 'node:events';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const BridgeClient = require('../bridge-client.js');
const { startLocalProxy } = BridgeClient;

const A = 0xEF;
const B = 0xBE;
const CMD_AUTH_BEGIN = 0x30;
const CMD_AUTH_RESPONSE = 0x31;
const CMD_AUTH_CHALLENGE = 0x32;
const CMD_AUTH_OK = 0x33;
const CMD_AUTH_FAIL = 0x34;
const CMD_QUERY = 0x20;
const NONCE = Buffer.alloc(32, 0x5a);
const KEY = 'ide-bridge-test-key';

function makeReader(sock) {
  let buf = Buffer.alloc(0);
  let waiter = null;
  let failure = null;

  const fail = (err) => {
    failure = failure || err;
    if (waiter) {
      clearTimeout(waiter.timer);
      const w = waiter;
      waiter = null;
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

  sock.on('data', onData);
  sock.on('error', fail);
  sock.on('close', () => fail(new Error('closed')));

  return {
    read(n, timeoutMs = 2000) {
      if (failure) return Promise.reject(failure);
      if (buf.length >= n) {
        const out = buf.subarray(0, n);
        buf = buf.subarray(n);
        return Promise.resolve(out);
      }
      return new Promise((resolve, reject) => {
        const timer = setTimeout(() => {
          if (waiter && waiter.timer === timer) waiter = null;
          reject(new Error(`read ${n} bytes timed out`));
        }, timeoutMs);
        waiter = { n, resolve, reject, timer };
      });
    },
    detach() {
      sock.off('data', onData);
      sock.off('error', fail);
      if (waiter) {
        clearTimeout(waiter.timer);
        waiter = null;
      }
    },
  };
}

function startServer(handler) {
  const sockets = new Set();
  let handlerError = null;

  const server = net.createServer((sock) => {
    sockets.add(sock);
    sock.on('close', () => sockets.delete(sock));
    Promise.resolve()
      .then(() => handler(sock))
      .catch((e) => { handlerError = handlerError || e; });
  });

  return new Promise((resolve, reject) => {
    server.once('error', reject);
    server.listen(0, '127.0.0.1', () => {
      resolve({
        host: '127.0.0.1',
        port: server.address().port,
        error: () => handlerError,
        async close() {
          for (const s of sockets) s.destroy();
          await new Promise((r) => server.close(r));
        },
      });
    });
  });
}

async function serverAuth(reader, sock, key, nonce) {
  const begin = await reader.read(3);
  expect(begin).toEqual(Buffer.from([A, B, CMD_AUTH_BEGIN]));
  sock.write(Buffer.concat([Buffer.from([A, B, CMD_AUTH_CHALLENGE]), nonce]));

  const response = await reader.read(35);
  expect(response.subarray(0, 3)).toEqual(Buffer.from([A, B, CMD_AUTH_RESPONSE]));
  const expected = crypto.createHmac('sha256', key).update(nonce).digest();
  expect(response.subarray(3).equals(expected)).toBe(true);
  sock.write(Buffer.from([A, B, CMD_AUTH_OK]));
}

describe('IDE bridge authentication', () => {
  it('authenticates a query and returns the status line', async () => {
    const srv = await startServer(async (sock) => {
      const r = makeReader(sock);
      await serverAuth(r, sock, KEY, NONCE);
      const query = await r.read(3);
      expect(query).toEqual(Buffer.from([A, B, CMD_QUERY]));
      sock.write('Companion Bridge v1\n');
    });

    const client = new BridgeClient();
    const res = await client.query(srv.host, srv.port, KEY);
    await srv.close();

    expect(res).toEqual({ success: true, info: 'Companion Bridge v1' });
    expect(srv.error()).toBeNull();
  });

  it('fails closed when the bridge rejects the key', async () => {
    const srv = await startServer(async (sock) => {
      const r = makeReader(sock);
      expect(await r.read(3)).toEqual(Buffer.from([A, B, CMD_AUTH_BEGIN]));
      sock.write(Buffer.concat([Buffer.from([A, B, CMD_AUTH_CHALLENGE]), NONCE]));
      const response = await r.read(35);
      expect(response.subarray(0, 3)).toEqual(Buffer.from([A, B, CMD_AUTH_RESPONSE]));
      sock.write(Buffer.from([A, B, CMD_AUTH_FAIL]));
    });

    const client = new BridgeClient();
    const res = await client.query(srv.host, srv.port, 'wrong-key');
    await srv.close();

    expect(res.success).toBe(false);
    expect(res.error).toMatch(/rejected the bridge key/);
    expect(srv.error()).toBeNull();
  });

  it('refuses a keyed bridge when no key is configured', async () => {
    const srv = await startServer(async (sock) => {
      const r = makeReader(sock);
      expect(await r.read(3)).toEqual(Buffer.from([A, B, CMD_AUTH_BEGIN]));
      sock.write(Buffer.concat([Buffer.from([A, B, CMD_AUTH_CHALLENGE]), NONCE]));
    });

    const client = new BridgeClient();
    const res = await client.query(srv.host, srv.port, '');
    await srv.close();

    expect(res.success).toBe(false);
    expect(res.error).toMatch(/requires a key/);
    expect(srv.error()).toBeNull();
  });

  it('fails closed when a configured key meets non-challenge bytes', async () => {
    const srv = await startServer(async (sock) => {
      const r = makeReader(sock);
      expect(await r.read(3)).toEqual(Buffer.from([A, B, CMD_AUTH_BEGIN]));
      sock.write('OK\n'); // e.g. old firmware forwarding target output
    });

    const client = new BridgeClient();
    const res = await client.query(srv.host, srv.port, KEY);
    await srv.close();

    expect(res.success).toBe(false);
    expect(res.error).toMatch(/did not answer the authentication challenge/);
    expect(srv.error()).toBeNull();
  });

  it('does not let a late serial auth callback replace a newer connection', async () => {
    let firstAcceptedResolve;
    const firstAccepted = new Promise((resolve) => { firstAcceptedResolve = resolve; });
    let connection = 0;

    const srv = await startServer(async (sock) => {
      const n = ++connection;
      const r = makeReader(sock);
      if (n === 1) {
        firstAcceptedResolve();
        try {
          // Delay the first challenge so disconnect/reconnect happens while
          // its authentication is still in flight.
          await new Promise((resolve) => setTimeout(resolve, 80));
          await serverAuth(r, sock, KEY, NONCE);
        } catch {
          // The first socket is expected to be destroyed by disconnect.
        }
        return;
      }
      await serverAuth(r, sock, KEY, NONCE);
      r.detach();
      sock.on('data', (d) => sock.write(d));
    });

    const client = new BridgeClient();
    const received = [];
    const first = client.connectSerial(srv.host, srv.port, () => {}, KEY);
    await firstAccepted;
    client.disconnectSerial();
    expect(await first).toMatchObject({ success: false });

    const second = await client.connectSerial(
      srv.host, srv.port, (d) => received.push(d), KEY,
    );
    expect(second.success).toBe(true);

    // Let the first connection's delayed auth completion run.
    await new Promise((resolve) => setTimeout(resolve, 150));
    expect(client._serialSock).not.toBeNull();

    client.send('after-reconnect');
    await new Promise((resolve) => setTimeout(resolve, 100));
    expect(received.join('')).toContain('after-reconnect');

    client.disconnectSerial();
    await srv.close();
    expect(srv.error()).toBeNull();
  });

  it('does not treat a closed socket as legacy firmware', async () => {
    const srv = await startServer(async (sock) => {
      const r = makeReader(sock);
      expect(await r.read(3)).toEqual(Buffer.from([A, B, CMD_AUTH_BEGIN]));
      r.detach();
      sock.destroy(); // closed, not merely silent
    });

    const client = new BridgeClient();
    const res = await client.query(srv.host, srv.port, '');
    await srv.close();

    expect(res.success).toBe(false);
    expect(res.error).toMatch(/closed the connection|connection failed during authentication/i);
  });

  it('falls back to legacy firmware only when no key is configured', async () => {
    const srv = await startServer(async (sock) => {
      const r = makeReader(sock);
      expect(await r.read(3)).toEqual(Buffer.from([A, B, CMD_AUTH_BEGIN]));
      // Old firmware ignores the probe. Wait past the 500 ms legacy window.
      await new Promise((resolve) => setTimeout(resolve, 700));
      const query = await r.read(3);
      expect(query).toEqual(Buffer.from([A, B, CMD_QUERY]));
      sock.write('legacy bridge\n');
    });

    const client = new BridgeClient();
    const res = await client.query(srv.host, srv.port, '');
    await srv.close();

    expect(res).toEqual({ success: true, info: 'legacy bridge' });
    expect(srv.error()).toBeNull();
  });

  it('ignores legacy UART output captured during the probe and still sends CMD_QUERY', async () => {
    const srv = await startServer(async (sock) => {
      const r = makeReader(sock);
      expect(await r.read(3)).toEqual(Buffer.from([A, B, CMD_AUTH_BEGIN]));
      sock.write('hi\n'); // target boot output, exactly the probe length
      const query = await r.read(3);
      expect(query).toEqual(Buffer.from([A, B, CMD_QUERY]));
      sock.write('Companion Bridge v1\n');
    });

    const client = new BridgeClient();
    const res = await client.query(srv.host, srv.port, '');
    await srv.close();

    expect(res).toEqual({ success: true, info: 'Companion Bridge v1' });
    expect(srv.error()).toBeNull();
  });
});

describe('IDE authenticated loopback proxy', () => {
  it('requires a key before listening', async () => {
    await expect(startLocalProxy('127.0.0.1', 1, '')).rejects.toThrow(/requires a bridge key/);
  });

  it('authenticates upstream and pipes raw bytes both ways', async () => {
    const srv = await startServer(async (sock) => {
      const r = makeReader(sock);
      await serverAuth(r, sock, KEY, NONCE);
      r.detach();
      sock.on('data', (d) => sock.write(d));
      await new Promise((resolve) => sock.on('close', resolve));
    });

    const proxy = await startLocalProxy(srv.host, srv.port, KEY);
    const local = net.connect(proxy.port, '127.0.0.1');
    await once(local, 'connect');

    const payload = Buffer.from('raw-uart-payload');
    local.write(payload);
    const got = await makeReader(local).read(payload.length);
    expect(got.equals(payload)).toBe(true);

    local.destroy();
    await proxy.close();
    await srv.close();
    expect(srv.error()).toBeNull();
  });
});
