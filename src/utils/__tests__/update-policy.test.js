import { describe, it, expect } from 'vitest';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const {
  compareVersions,
  isNewer,
  assetArchitecture,
  selectIdeInstaller,
  isTrustedReleaseUrl,
  buildIdeUpdate,
} = require('../../../electron/update-policy.js');

const releaseAssets = [
  { name: 'companion-linux-amd64', url: 'https://example.test/cli-linux-amd64' },
  { name: 'companion-linux-arm64', url: 'https://example.test/cli-linux-arm64' },
  { name: 'companion-windows-amd64.exe', url: 'https://example.test/cli-win-amd64.exe' },
  { name: 'companion-windows-arm64.exe', url: 'https://example.test/cli-win-arm64.exe' },
  { name: 'companion-darwin-amd64', url: 'https://example.test/cli-mac-amd64' },
  { name: 'companion-darwin-arm64', url: 'https://example.test/cli-mac-arm64' },
  { name: 'companion-ide_0.3.4-alpha_amd64.deb', url: 'https://example.test/companion.deb', size: 118 },
  { name: 'Companion.IDE-0.3.4-alpha-arm64.dmg', url: 'https://example.test/companion-arm64.dmg', size: 152 },
  { name: 'Companion.IDE-0.3.4-alpha.AppImage', url: 'https://example.test/companion.AppImage', size: 150 },
  { name: 'Companion.IDE.Setup.0.3.4-alpha.exe', url: 'https://example.test/companion-setup.exe', size: 129 },
  { name: 'SHA256SUMS.txt', url: 'https://example.test/SHA256SUMS.txt' },
];

const release = {
  tag_name: 'v0.3.4-alpha',
  latest_version: '0.3.4-alpha',
  release_name: 'v0.3.4-alpha',
  release_url: 'https://github.com/owner/repo/releases/tag/v0.3.4-alpha',
  published_at: '2026-10-23T13:12:37Z',
  prerelease: false,
  release_notes: 'notes',
  assets: releaseAssets,
};

describe('update policy version ordering', () => {
  it('compares releases numerically and handles prereleases', () => {
    expect(compareVersions('0.3.10-alpha', '0.3.9-alpha')).toBe(1);
    expect(compareVersions('0.4.0', '0.4.0-rc1')).toBe(1);
    expect(compareVersions('0.4.0-alpha', '0.4.0-beta')).toBe(-1);
    expect(compareVersions('0.4.0-alpha.2', '0.4.0-alpha.10')).toBe(-1);
    expect(compareVersions('1.0.0', '0.3.4-alpha')).toBe(1);
    expect(compareVersions('v0.3.4-alpha', '0.3.4-alpha')).toBe(0);
    expect(compareVersions('0.3.4-alpha+build.5', '0.3.4-alpha')).toBe(0);
  });

  it('only reports real upgrades and treats unknown current builds as older', () => {
    expect(isNewer('0.4.0', '0.3.4')).toBe(true);
    expect(isNewer('0.4.0', '0.4.0')).toBe(false);
    expect(isNewer('0.4.0', '0.5.0')).toBe(false);
    expect(isNewer('0.4.0', 'dev')).toBe(true);
    expect(isNewer('0.4.0', '')).toBe(true);
    expect(isNewer('not-a-version', '0.4.0')).toBe(false);
  });
});

describe('installer selection', () => {
  it('recognizes architecture suffixes in release asset names', () => {
    expect(assetArchitecture('Companion.IDE-0.3.4-alpha-arm64.dmg')).toBe('arm64');
    expect(assetArchitecture('Companion.IDE-0.3.4-alpha.AppImage')).toBe('');
    expect(assetArchitecture('companion-ide_0.3.4-alpha_amd64.deb')).toBe('x64');
    expect(assetArchitecture('Companion.IDE-universal.dmg')).toBe('universal');
  });

  it('selects the x64 Linux AppImage and never a CLI binary', () => {
    const selected = selectIdeInstaller(releaseAssets, 'linux', 'x64');
    expect(selected).toMatchObject({
      name: 'Companion.IDE-0.3.4-alpha.AppImage',
      kind: 'linux-appimage',
    });
    expect(selected.url).toBe('https://example.test/companion.AppImage');
  });

  it('falls back to the matching .deb when there is no AppImage', () => {
    const selected = selectIdeInstaller(
      releaseAssets.filter(a => !a.name.endsWith('.AppImage')),
      'linux', 'x64',
    );
    expect(selected).toMatchObject({
      name: 'companion-ide_0.3.4-alpha_amd64.deb',
      kind: 'linux-deb',
    });
  });

  it('does not offer an x64 Linux installer to arm64 Linux', () => {
    expect(selectIdeInstaller(releaseAssets, 'linux', 'arm64')).toBeNull();
  });

  it('selects a matching arm64 Linux AppImage when the release publishes one', () => {
    const selected = selectIdeInstaller([
      { name: 'Companion.IDE-0.4.0-arm64.AppImage', url: 'https://example.test/arm64.AppImage' },
      { name: 'Companion.IDE-0.4.0-x64.AppImage', url: 'https://example.test/x64.AppImage' },
    ], 'linux', 'arm64');
    expect(selected?.name).toBe('Companion.IDE-0.4.0-arm64.AppImage');
  });

  it('selects the Windows NSIS installer, not the CLI .exe', () => {
    const selected = selectIdeInstaller(releaseAssets, 'win32', 'x64');
    expect(selected).toMatchObject({
      name: 'Companion.IDE.Setup.0.3.4-alpha.exe',
      kind: 'windows-installer',
    });
  });

  it('does not offer the x64 Windows installer to arm64 Windows', () => {
    expect(selectIdeInstaller(releaseAssets, 'win32', 'arm64')).toBeNull();
  });

  it('selects the macOS arm64 dmg and does not guess for x64', () => {
    expect(selectIdeInstaller(releaseAssets, 'darwin', 'arm64')).toMatchObject({
      name: 'Companion.IDE-0.3.4-alpha-arm64.dmg',
      kind: 'macos-dmg',
    });
    expect(selectIdeInstaller(releaseAssets, 'darwin', 'x64')).toBeNull();
  });

  it('returns null for an unsupported platform or empty asset list', () => {
    expect(selectIdeInstaller(releaseAssets, 'freebsd', 'x64')).toBeNull();
    expect(selectIdeInstaller([], 'linux', 'x64')).toBeNull();
    expect(selectIdeInstaller(null, 'linux', 'x64')).toBeNull();
  });
});

describe('IDE update status', () => {
  it('reports an IDE update when the release is newer', () => {
    const status = buildIdeUpdate(release, '0.3.3-alpha', 'linux', 'x64');
    expect(status.updateAvailable).toBe(true);
    expect(status.currentVersion).toBe('0.3.3-alpha');
    expect(status.latestVersion).toBe('0.3.4-alpha');
    expect(status.installer?.name).toBe('Companion.IDE-0.3.4-alpha.AppImage');
  });

  it('reports no update when the installed build is current or newer', () => {
    expect(buildIdeUpdate(release, '0.3.4-alpha', 'linux', 'x64').updateAvailable).toBe(false);
    expect(buildIdeUpdate(release, '0.4.0', 'linux', 'x64').updateAvailable).toBe(false);
  });

  it('still returns the release page when no installer matches the host', () => {
    const status = buildIdeUpdate(release, '0.3.3-alpha', 'linux', 'arm64');
    expect(status.updateAvailable).toBe(true);
    expect(status.installer).toBeNull();
    expect(status.releaseUrl).toContain('/releases/tag/');
  });
});

describe('release URL validation', () => {
  const repo = 'Aryan-Rajyaguru-1/Companion';
  it('accepts only HTTPS release URLs from this repository', () => {
    expect(isTrustedReleaseUrl(
      'https://github.com/Aryan-Rajyaguru-1/Companion/releases/tag/v0.3.4-alpha', repo, 'tag',
    )).toBe(true);
    expect(isTrustedReleaseUrl(
      'https://github.com/Aryan-Rajyaguru-1/Companion/releases/download/v0.3.4-alpha/Companion.IDE-0.3.4-alpha.AppImage', repo, 'download',
    )).toBe(true);
    expect(isTrustedReleaseUrl(
      'https://github.com/other/Companion/releases/download/v1/a.AppImage', repo, 'download',
    )).toBe(false);
    expect(isTrustedReleaseUrl(
      'http://github.com/Aryan-Rajyaguru-1/Companion/releases/tag/v0.3.4-alpha', repo, 'tag',
    )).toBe(false);
    expect(isTrustedReleaseUrl(
      'https://github.com.evil.test/Aryan-Rajyaguru-1/Companion/releases/tag/v0.3.4-alpha', repo, 'tag',
    )).toBe(false);
    expect(isTrustedReleaseUrl(
      'https://github.com/Aryan-Rajyaguru-1/Companion/issues/1', repo, 'tag',
    )).toBe(false);
    expect(isTrustedReleaseUrl('', repo, 'tag')).toBe(false);
  });
});
