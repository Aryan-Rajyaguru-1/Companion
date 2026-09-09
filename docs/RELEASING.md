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

## 3. Release channel
- Tag `vX.Y.Z`; GitHub Actions builds the matrix (see `.github/`).
- Attach the four CLI binaries (`make -C companion-cli build-all`) and the IDE
  bundle. A brew tap for `companion` (macOS/Linux) should mirror those artifacts:
  `brew install companion-ide/tap/companion-ide`.

## 4. Legal hygiene (MANDATORY before every tag)
- `Arduino for refs/` (AGPL/GPL sources) and the analysis `.md` files are
  git-ignored and must never appear in any artifact, tarball, or git tag.
  `make -C companion-cli publish` in the workspace root builds a bundle that
  excludes them (see Makefile).
- If the refs tree was ever committed, purge with
  `git filter-repo --path "Arduino for refs/" --invert-paths` before pushing.
- Ship only from-scratch code. License: MIT.

## 5. Portable mode
`companion --portable` and `COMPANION_PORTABLE=1` relocate all state next to the
executable (see `internal/config/config.go`). The IDE ships the CLI binary next
to itself, so a portable IDE install = the whole toolchain on a USB stick.