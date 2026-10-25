# Companion — Release & Distribution Policy

Phase 6 of ROADMAP.md. This is the policy that prevents the class of issues
Arduino IDE/CLI users keep hitting (#2424 Electron EOL drift, #1127 "no bottle
available", #122 no portable mode).

## 1. Electron upgrade cadence
- Track all Electron major releases; upgrade within **two majors** of the
  latest stable, and never run an EOL Electron in a shipped release.
- Pin exact Electron versions in `companion-ide/package.json` (no `^`).
- Since this project ships its own CLI daemon (not an external arduino-cli),
  there is no bundling fragility — the risk window is the Electron runtime only.

## 2. Signing
- macOS: notarize + staple every dmg (Apple notarytool; Developer ID).
- Windows: Authenticode sign the NSIS installer (signtool + EV cert).
- Linux: no universal signing — publish `.deb`/`.AppImage`; verify artifact
  SHA-256 in the release notes (matches the CLI's own checksum-verify story).
- The IDE update panel opens installers; it does not silently apply them until
  signed installer/updater metadata (for example `electron-updater`) exists.
  Do not add an unsigned auto-replacement path.

## 3. Release channel
- Tag `vX.Y.Z`; GitHub Actions builds the matrix (see `.github/`).
- Attach the six CLI binaries (`make -C companion-cli build-all`) and the IDE
  bundle. A brew tap for `companion` (macOS/Linux) should mirror those artifacts:
  `brew install companion-ide/tap/companion-ide`.

## 4. Application update contract

`companion --update` / `companion self-update` and the IDE's
**Help → Check for Updates…** read the same GitHub release metadata.

Every release must publish:

- `SHA256SUMS.txt` covering every asset;
- one CLI binary per target: `companion-linux-amd64`,
  `companion-linux-arm64`, `companion-windows-amd64.exe`,
  `companion-windows-arm64.exe`, `companion-darwin-amd64`,
  `companion-darwin-arm64`.

The CLI updater is fail-closed: it selects the asset for the host platform and
architecture, requires a matching SHA-256 entry, stages the download beside the
target, and replaces it atomically. It considers the newest published release,
including prereleases, because this project currently ships alpha tags.

The IDE uses the CLI's `self-update --check --json` result as the release
source of truth. It compares `app.getVersion()` with the release tag and picks
an installer only when the asset name and architecture match:

- Linux: `Companion.IDE-<version>.AppImage` or
  `companion-ide_<version>_amd64.deb` (x64), and arm64-suffixed variants;
- Windows: `Companion.IDE.Setup.<version>.exe` (x64);
- macOS: `Companion.IDE-<version>-arm64.dmg`.

If no compatible installer exists, the IDE opens the release page. It does not
silently replace its own installation.

Platform gaps in the current release workflow: Linux arm64 and macOS x64 IDE
installers are not built, so those hosts fall back to the release page. Add
matrix entries before advertising those installers. Un-suffixed AppImage and
NSIS assets are x64 and are deliberately rejected for arm64 hosts.

## 5. Legal hygiene (MANDATORY before every tag)
- `Arduino for refs/` (AGPL/GPL sources) and the analysis `.md` files are
  git-ignored and must never appear in any artifact, tarball, or git tag.
  `make -C companion-cli publish` in the workspace root builds a bundle that
  excludes them (see Makefile).
- If the refs tree was ever committed, purge with
  `git filter-repo --path "Arduino for refs/" --invert-paths` before pushing.
- Ship only from-scratch code. License: MIT.

## 6. Portable mode
`companion --portable` and `COMPANION_PORTABLE=1` relocate all state next to the
executable (see `internal/config/config.go`). The IDE ships the CLI binary next
to itself, so a portable IDE install = the whole toolchain on a USB stick.