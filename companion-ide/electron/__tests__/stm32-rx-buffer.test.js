// Regression test: stm32RX is module-global and was never cleared between
// sessions. A session that ended (cancel, timeout, disconnect) with bytes still
// queued handed them to the NEXT session's readByte(), desynchronising the
// AN3155 handshake — and the code comment right above the buffer already warned
// about a stray byte resolving the wrong promise.
//
// The buffer and its reader are reproduced here from bridge-client.js so the
// invariant can be asserted directly.
import { describe, it, expect } from 'vitest';

function makeStm32RX() {
  let stm32RX = Buffer.alloc(0);
  const readByte = (sock, timeout = 3000) => {
    if (stm32RX.length > 0) {
      const b = stm32RX[0];
      stm32RX = stm32RX.subarray(1);
      return Promise.resolve(b);
    }
    return new Promise((resolve) => {
      const onData = (d) => {
        if (!d || d.length === 0) return;
        detach();
        stm32RX = Buffer.from(d.subarray(1));
        resolve(d[0]);
      };
      const timer = setTimeout(() => { detach(); resolve(null); }, timeout);
      function detach() { clearTimeout(timer); sock.off('data', onData); }
      sock.on('data', onData);
    });
  };
  const reset = () => { stm32RX = Buffer.alloc(0); };
  const size = () => stm32RX.length;
  return { readByte, reset, size };
}

// A one-shot socket stand-in that delivers a single chunk.
function fakeSock() {
  const handlers = [];
  return {
    on: (ev, fn) => { if (ev === 'data') handlers.push(fn); },
    off: (ev, fn) => { const i = handlers.indexOf(fn); if (i >= 0) handlers.splice(i, 1); },
    deliver: (buf) => handlers.slice().forEach((h) => h(buf)),
  };
}

describe('stm32RX session hygiene', () => {
  it('keeps the tail of one read for the next read (the original intent)', async () => {
    const { readByte, size } = makeStm32RX();
    const s = fakeSock();
    const first = readByte(s, 50);
    s.deliver(Buffer.from([0x79, 0x01, 0x02]));
    expect(await first).toBe(0x79);
    expect(size()).toBe(2); // the tail is retained, not dropped
  });

  it('does NOT leak a stale byte into a new session once reset', async () => {
    const { readByte, reset, size } = makeStm32RX();
    const s = fakeSock();
    const first = readByte(s, 50);
    // Three bytes arrive; the session ends after consuming only the first.
    s.deliver(Buffer.from([0x79, 0xAA, 0xBB]));
    expect(await first).toBe(0x79);
    expect(size()).toBe(2); // stale bytes are sitting there

    reset(); // <- what connectSerial/disconnectSerial now do
    expect(size()).toBe(0);

    // The next session must see its own bytes, not the old ones.
    const s2 = fakeSock();
    const next = readByte(s2, 50);
    s2.deliver(Buffer.from([0x1F]));
    expect(await next).toBe(0x1F); // 0x1F is this session's first byte
  });

  it('a stale byte would otherwise satisfy the next read', async () => {
    // The failure this prevents, demonstrated: with no reset, readByte returns
    // the PREVIOUS session's byte immediately and the new socket is never read.
    const { readByte, size } = makeStm32RX();
    const s = fakeSock();
    const first = readByte(s, 50);
    s.deliver(Buffer.from([0x79, 0xAA]));
    expect(await first).toBe(0x79);

    const s2 = fakeSock();
    const leaked = await readByte(s2, 50); // no reset: returns 0xAA from the old session
    expect(leaked).toBe(0xAA);
    expect(size()).toBe(0);
  });
});
