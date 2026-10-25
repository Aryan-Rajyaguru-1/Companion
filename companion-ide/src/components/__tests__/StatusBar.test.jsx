import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import StatusBar from '../StatusBar.jsx';

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

let container;
let root;
let cliVersion;

beforeEach(() => {
  container = document.createElement('div');
  document.body.appendChild(container);
  root = createRoot(container);
  cliVersion = vi.fn().mockResolvedValue('Companion CLI v0.3.4-alpha');
  window.electronAPI = { cliVersion };
});

afterEach(() => {
  act(() => root.unmount());
  container.remove();
  delete window.electronAPI;
});

const props = {
  fileName: 'sketch.ino',
  modified: false,
  board: 'arduino:avr:uno',
  mcu: 'avr',
  bridgeHost: '192.168.4.1',
  bridgeStatus: 'disconnected',
  isCompiling: false,
  isUploading: false,
  autoVerify: false,
  warnings: 'none',
  compileSummary: null,
  daemonRunning: false,
  cacheStats: null,
  lastCompileMs: null,
  cursorLine: 1,
  cursorCol: 1,
  cliVersionRefresh: 0,
};

async function render(overrides = {}) {
  await act(async () => {
    root.render(<StatusBar {...props} {...overrides} />);
  });
}

describe('StatusBar updates', () => {
  it('shows the CLI version reported by the main process', async () => {
    await render();
    expect(container.textContent).toContain('CLI v0.3.4-alpha');
    expect(cliVersion).toHaveBeenCalledTimes(1);
  });

  it('refreshes the CLI version after an update', async () => {
    await render();
    cliVersion.mockResolvedValue('Companion CLI v0.3.5-alpha');
    await render({ cliVersionRefresh: 1 });
    expect(container.textContent).toContain('CLI v0.3.5-alpha');
    expect(cliVersion).toHaveBeenCalledTimes(2);
  });

  it('shows a clickable update badge only when an update exists', async () => {
    const onShowUpdates = vi.fn();
    await render({ updateAvailable: false, onShowUpdates });
    expect(container.textContent).not.toContain('Update');

    await render({
      updateAvailable: true,
      updateLabel: 'CLI v0.3.5-alpha',
      onShowUpdates,
    });
    const badge = [...container.querySelectorAll('button')]
      .find(b => b.textContent.includes('Update'));
    expect(badge).toBeTruthy();
    expect(badge.title).toContain('CLI v0.3.5-alpha');
    act(() => badge.click());
    expect(onShowUpdates).toHaveBeenCalledTimes(1);
  });
});
