// The update dialog is the only place users can start a CLI install or open an
// IDE installer. These tests keep the two paths distinct: CLI updates happen
// in-app, IDE updates only open a published download/release page.
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import UpdatePanel from '../UpdatePanel.jsx';

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const status = {
  success: true,
  checkedAt: '2026-10-24T12:00:00.000Z',
  platform: 'linux',
  architecture: 'x64',
  releaseUrl: 'https://github.com/Aryan-Rajyaguru-1/Companion/releases/tag/v0.3.4-alpha',
  releaseName: 'v0.3.4-alpha',
  releaseNotes: 'Fixes and improvements.',
  cli: {
    currentVersion: '0.3.3-alpha',
    latestVersion: '0.3.4-alpha',
    updateAvailable: true,
    assetName: 'companion-linux-amd64',
    releaseUrl: 'https://github.com/Aryan-Rajyaguru-1/Companion/releases/tag/v0.3.4-alpha',
  },
  ide: {
    currentVersion: '0.3.3-alpha',
    latestVersion: '0.3.4-alpha',
    updateAvailable: true,
    installer: {
      name: 'Companion.IDE-0.3.4-alpha.AppImage',
      url: 'https://github.com/Aryan-Rajyaguru-1/Companion/releases/download/v0.3.4-alpha/Companion.IDE-0.3.4-alpha.AppImage',
      kind: 'linux-appimage',
    },
  },
};

let container;
let root;

beforeEach(() => {
  container = document.createElement('div');
  document.body.appendChild(container);
  root = createRoot(container);
});

afterEach(() => {
  act(() => root.unmount());
  container.remove();
});

function render(overrides = {}) {
  act(() => {
    root.render(
      <UpdatePanel
        status={status}
        checking={false}
        applying={false}
        error=""
        message=""
        onCheck={() => {}}
        onApplyCli={() => {}}
        onOpenIdeInstaller={() => {}}
        onOpenRelease={() => {}}
        onClose={() => {}}
        {...overrides}
      />,
    );
  });
}

function button(label) {
  return [...container.querySelectorAll('button')]
    .find(b => b.textContent.includes(label));
}

describe('UpdatePanel', () => {
  it('shows installed and latest versions for both products', () => {
    render();
    expect(container.textContent).toContain('Companion CLI');
    expect(container.textContent).toContain('v0.3.3-alpha');
    expect(container.textContent).toContain('v0.3.4-alpha');
    expect(container.textContent).toContain('linux x64');
    expect(container.textContent).toContain('Release notes');
  });

  it('starts a CLI update from the CLI card', () => {
    const onApplyCli = vi.fn();
    render({ onApplyCli });
    act(() => button('Update CLI').click());
    expect(onApplyCli).toHaveBeenCalledTimes(1);
  });

  it('disables update actions while applying', () => {
    const onApplyCli = vi.fn();
    render({ applying: true, onApplyCli });
    const apply = button('Downloading and verifying');
    expect(apply.disabled).toBe(true);
    act(() => apply.click());
    expect(onApplyCli).not.toHaveBeenCalled();
  });

  it('opens the IDE installer when one matches the host', () => {
    const onOpenIdeInstaller = vi.fn();
    render({ onOpenIdeInstaller });
    act(() => button('Download v0.3.4-alpha installer').click());
    expect(onOpenIdeInstaller).toHaveBeenCalledTimes(1);
  });

  it('degrades to the release page when no installer matches', () => {
    const onOpenRelease = vi.fn();
    render({
      status: { ...status, ide: { ...status.ide, installer: null } },
      onOpenRelease,
    });
    expect(container.textContent).toContain('No IDE installer was published');
    act(() => button('Open release page').click());
    expect(onOpenRelease).toHaveBeenCalledTimes(1);
  });

  it('reports up-to-date products without update actions', () => {
    render({
      status: {
        ...status,
        cli: { ...status.cli, updateAvailable: false },
        ide: { ...status.ide, updateAvailable: false },
      },
    });
    expect(container.textContent).toContain('Companion CLI is up to date.');
    expect(container.textContent).toContain('Companion IDE is up to date.');
    expect(button('Update CLI')).toBeUndefined();
    expect(button('Download v0.3.4-alpha installer')).toBeUndefined();
  });

  it('renders check/apply errors and informational messages', () => {
    render({ error: 'network unreachable', message: 'CLI updated.' });
    expect(container.querySelector('[role="alert"]').textContent).toContain('network unreachable');
    expect(container.querySelector('[role="status"]').textContent).toContain('CLI updated.');
  });

  it('shows a checking state before the first result', () => {
    render({ status: null, checking: true });
    expect(container.textContent).toContain('Checking the release channel');
  });
});
