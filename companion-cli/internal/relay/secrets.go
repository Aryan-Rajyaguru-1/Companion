package relay

// secrets.go — persistent device-id ownership for the relay hub.
//
// The hub refuses a device id that has already been bound to a different
// provisioning secret. Keeping that binding in memory alone only protects ids
// claimed since the last restart: after a hub restart, an attacker holding the
// devices token could claim an offline board's id with their own secret and
// collect its pushes. The binding is therefore written to a private JSON file
// before registration is acknowledged, and a write failure refuses the
// registration instead of silently falling back to an in-memory-only check.

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"runtime"

	"github.com/companion-ide/companion-cli/internal/atomicfile"
)

const secretsFileVersion = 1

type secretsFile struct {
	Version int               `json:"version"`
	Devices map[string]string `json:"devices"`
}

// loadSecrets reads the persisted id→secret bindings. A missing file is an
// empty store (first run); any other error is fatal to startup so an operator
// cannot accidentally run a hub that has forgotten which board owns an id.
func (h *Hub) loadSecrets() error {
	if err := ensureSecretsDir(filepath.Dir(h.secretsPath)); err != nil {
		return err
	}
	fi, err := os.Lstat(h.secretsPath)
	if os.IsNotExist(err) {
		return nil
	}
	if err != nil {
		return fmt.Errorf("inspect relay secrets file %s: %w", h.secretsPath, err)
	}
	if fi.Mode()&os.ModeSymlink != 0 {
		return fmt.Errorf("relay secrets file %s must not be a symlink", h.secretsPath)
	}
	// Windows reports synthesized permission bits; access is enforced by ACLs.
	if runtime.GOOS != "windows" && fi.Mode().Perm()&0o077 != 0 {
		return fmt.Errorf("relay secrets file %s is mode %04o; refuse to use it (chmod 600)", h.secretsPath, fi.Mode().Perm())
	}
	raw, err := os.ReadFile(h.secretsPath)
	if err != nil {
		return fmt.Errorf("read relay secrets file %s: %w", h.secretsPath, err)
	}
	var f secretsFile
	if err := json.Unmarshal(raw, &f); err != nil {
		return fmt.Errorf("parse relay secrets file %s: %w", h.secretsPath, err)
	}
	if f.Version != secretsFileVersion {
		return fmt.Errorf("unsupported relay secrets version %d in %s", f.Version, h.secretsPath)
	}
	seen := make(map[string]string, len(f.Devices))
	for id, secret := range f.Devices {
		normalized := normalizeID(id)
		if normalized == "" || secret == "" {
			return fmt.Errorf("relay secrets file %s contains an empty device id or secret", h.secretsPath)
		}
		// Device ids are case-insensitive and trimmed at registration. If a
		// hand-edited file contains both spellings, silently keeping one would
		// make ownership depend on map iteration order.
		if prior, ok := seen[normalized]; ok {
			return fmt.Errorf("relay secrets file %s contains duplicate device id %q (as %q and %q)", h.secretsPath, normalized, prior, id)
		}
		seen[normalized] = id
		h.knownSecrets[normalized] = secret
	}
	return nil
}

// rememberSecretLocked records a new binding and persists it. h.mu must be
// held. On a write failure the in-memory entry is rolled back, because the
// caller must reject the registration: an acknowledgement followed by a
// forgotten binding on restart is exactly the restart-squatting window this
// file exists to close.
func (h *Hub) rememberSecretLocked(id, secret string) error {
	h.knownSecrets[id] = secret
	if h.secretsPath == "" {
		return nil
	}
	if err := h.writeSecretsLocked(); err != nil {
		delete(h.knownSecrets, id)
		return err
	}
	return nil
}

// ensureSecretsDir creates the store directory when needed and refuses a
// world-writable one. A world-writable parent would let an attacker replace
// the binding file between restarts, either denying service or (when the hub
// runs as the same account) choosing the bindings.
func ensureSecretsDir(dir string) error {
	if err := os.MkdirAll(dir, 0o700); err != nil {
		return fmt.Errorf("create relay secrets directory %s: %w", dir, err)
	}
	fi, err := os.Stat(dir)
	if err != nil {
		return fmt.Errorf("inspect relay secrets directory %s: %w", dir, err)
	}
	if !fi.IsDir() {
		return fmt.Errorf("relay secrets parent %s is not a directory", dir)
	}
	// Windows reports synthesized permission bits, so the Unix world-write
	// check would reject every normal directory. Access there is ACL-based.
	if runtime.GOOS != "windows" {
		if perm := fi.Mode().Perm(); perm&0o002 != 0 {
			return fmt.Errorf("relay secrets directory %s is mode %04o; world-write access would let another user replace device bindings", dir, perm)
		}
	}
	return nil
}

// writeSecretsLocked atomically replaces the binding file. h.mu must be held.
func (h *Hub) writeSecretsLocked() error {
	dir := filepath.Dir(h.secretsPath)
	if err := ensureSecretsDir(dir); err != nil {
		return err
	}
	f := secretsFile{Version: secretsFileVersion, Devices: make(map[string]string, len(h.knownSecrets))}
	for id, secret := range h.knownSecrets {
		f.Devices[id] = secret
	}
	raw, err := json.MarshalIndent(f, "", "  ")
	if err != nil {
		return err
	}
	raw = append(raw, '\n')
	if err := atomicfile.WriteFile(h.secretsPath, raw, 0o600); err != nil {
		return fmt.Errorf("replace relay secrets file: %w", err)
	}
	return nil
}
