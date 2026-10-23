// Smoke test for main<->renderer IPC wiring.
//
// The v0.3.1-alpha..v0.3.3-alpha IDE shipped broken in a way no test could see:
// a main-process helper threw, every caller caught and degraded, and the app
// looked healthy while doing nothing. This test guards the adjacent failure
// class — channel drift — where a preload method invoke()s a channel main.js
// no longer (or never did) register. That failure is equally silent: Electron
// rejects the invoke with "No handler registered", most callers swallow it,
// and the GUI just stops working.
//
// Both files are parsed as text (no electron runtime is loaded), and the
// renderer-reachable channel set must equal the set main.js handles.
import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const mainSrc = readFileSync(join(here, '..', 'main.js'), 'utf8');
const preloadSrc = readFileSync(join(here, '..', 'preload.js'), 'utf8');

// Collect the literal first-argument channels of the given ipc calls.
// `once` is matched before `on` implicitly: "on" requires an immediate "("
// after it, so ipcMain.once(...) can only match the `once` alternative.
function channels(src, methods, receiver) {
  const re = new RegExp(
    `ipc${receiver}\\.(?:${methods.join('|')})\\(\\s*'([^']+)'`,
    'g',
  );
  const out = new Set();
  let m;
  while ((m = re.exec(src)) !== null) out.add(m[1]);
  return out;
}

// Channels main.js registers as handlers for renderer-originated calls.
const handled = channels(mainSrc, ['handle', 'on', 'once'], 'Main');
// Channels preload.js can reach from the renderer (listeners on() and
// removeListener() are main->renderer fan-out, not calls — excluded).
const reachable = channels(preloadSrc, ['invoke', 'send'], 'Renderer');

describe('main <-> preload IPC wiring', () => {
  it('every channel the preload can call is handled by main.js', () => {
    const dangling = [...reachable].filter((c) => !handled.has(c)).sort();
    expect(
      dangling,
      `preload calls channels main.js does not handle: ${dangling.join(', ')}`,
    ).toEqual([]);
  });

  it('every channel main.js handles is reachable through the preload', () => {
    const orphaned = [...handled].filter((c) => !reachable.has(c)).sort();
    expect(
      orphaned,
      `main.js handles channels nothing in preload reaches: ${orphaned.join(', ')}`,
    ).toEqual([]);
  });

  it('exposes the core API surface the renderer depends on', () => {
    for (const fn of [
      'compile',
      'uploadBinary',
      'uploadUSB',
      'bridgeQuery',
      'otaUpload',
      'monitorTearOff',
      'saveCompleted',
      'listSerialPorts',
    ]) {
      expect(preloadSrc, `preload no longer exposes ${fn}()`).toMatch(
        new RegExp(`\\b${fn}\\s*:`),
      );
    }
  });
});
