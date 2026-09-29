package fleet

// secrets.go — optional encryption of the per-device provisioning secrets in the
// fleet registry.
//
// The registry is one YAML file holding a secret for every board. That is fine
// for two boards on a workstation, and a liability at fifty: 0600 protects
// against other local users, but not against a synced folder, a backup, or a
// stolen disk. Set COMPANION_FLEET_SECRET_KEY to encrypt the secrets at rest.
//
// Design notes:
//   - AES-GCM with a FRESH random nonce per secret. The per-device secret is
//     what the hub checks, so it must be recoverable exactly — GCM is
//     authenticated, so a tampered file fails loudly instead of decrypting to
//     garbage.
//   - Encrypted values are tagged with a prefix, so a file written before
//     encryption was enabled still loads (its values are plaintext), and a
//     file written WITH encryption fails with a clear message when the key is
//     missing — never silently skipped, which would look like "no secret".
//   - The key is never written anywhere: it is read from the environment.

import (
	"crypto/aes"
	"crypto/cipher"
	"crypto/rand"
	"crypto/sha256"
	"encoding/base64"
	"fmt"
	"io"
	"os"
	"strings"
)

// encPrefix marks a value in the YAML as encrypted by this package.
const encPrefix = "gcm1:"

// fleetSecretKey returns the AES key, or nil when encryption is not configured.
func fleetSecretKey() ([]byte, error) {
	raw := strings.TrimSpace(os.Getenv("COMPANION_FLEET_SECRET_KEY"))
	if raw == "" {
		return nil, nil
	}
	// A 32-byte key may be given as hex or base64; anything else is treated
	// as a passphrase and stretched with SHA-256 (documented: a passphrase is
	// only as strong as the passphrase, it is not stretched on purpose).
	if b, err := hexOrBase64(raw); err == nil && len(b) == 32 {
		return b, nil
	}
	sum := sha256.Sum256([]byte(raw))
	return sum[:], nil
}

func hexOrBase64(s string) ([]byte, error) {
	if len(s) == 64 {
		if b, err := hexDecode(s); err == nil {
			return b, nil
		}
	}
	return base64.StdEncoding.DecodeString(s)
}

func hexDecode(s string) ([]byte, error) {
	out := make([]byte, len(s)/2)
	for i := 0; i < len(out); i++ {
		var v int
		for j := 0; j < 2; j++ {
			c := s[i*2+j]
			switch {
			case c >= '0' && c <= '9':
				v = v<<4 | int(c-'0')
			case c >= 'a' && c <= 'f':
				v = v<<4 | int(c-'a'+10)
			case c >= 'A' && c <= 'F':
				v = v<<4 | int(c-'A'+10)
			default:
				return nil, fmt.Errorf("not hex")
			}
		}
		out[i] = byte(v)
	}
	return out, nil
}

// protectSecret encrypts v when a key is configured, and returns it unchanged
// otherwise (so the file stays plaintext until the operator opts in).
func protectSecret(v string) (string, error) {
	if v == "" {
		return "", nil
	}
	key, err := fleetSecretKey()
	if err != nil {
		return "", err
	}
	if key == nil {
		return v, nil
	}
	block, err := aes.NewCipher(key)
	if err != nil {
		return "", err
	}
	gcm, err := cipher.NewGCM(block)
	if err != nil {
		return "", err
	}
	nonce := make([]byte, gcm.NonceSize())
	if _, err := io.ReadFull(rand.Reader, nonce); err != nil {
		return "", err
	}
	ct := gcm.Seal(nonce, nonce, []byte(v), nil)
	return encPrefix + base64.StdEncoding.EncodeToString(ct), nil
}

// unprotectSecret reverses protectSecret. An encrypted value with no key
// configured is an error, never a silent empty string: a fleet that quietly
// lost its secrets would fail at push time with a confusing "secret required".
func unprotectSecret(v string) (string, error) {
	if v == "" {
		return "", nil
	}
	if !strings.HasPrefix(v, encPrefix) {
		return v, nil // plaintext (file written before encryption was enabled)
	}
	key, err := fleetSecretKey()
	if err != nil {
		return "", err
	}
	if key == nil {
		return "", fmt.Errorf("this registry has ENCRYPTED device secrets but COMPANION_FLEET_SECRET_KEY is not set")
	}
	raw, err := base64.StdEncoding.DecodeString(strings.TrimPrefix(v, encPrefix))
	if err != nil {
		return "", fmt.Errorf("corrupt encrypted secret: %w", err)
	}
	block, err := aes.NewCipher(key)
	if err != nil {
		return "", err
	}
	gcm, err := cipher.NewGCM(block)
	if err != nil {
		return "", err
	}
	if len(raw) < gcm.NonceSize() {
		return "", fmt.Errorf("corrupt encrypted secret: too short")
	}
	nonce, ct := raw[:gcm.NonceSize()], raw[gcm.NonceSize():]
	pt, err := gcm.Open(nil, nonce, ct, nil)
	if err != nil {
		return "", fmt.Errorf("device secret did not decrypt — wrong COMPANION_FLEET_SECRET_KEY")
	}
	return string(pt), nil
}
