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
	"crypto/hmac"
	"crypto/rand"
	"crypto/sha256"
	"encoding/base64"
	"encoding/binary"
	"fmt"
	"io"
	"os"
	"strings"
)

// Value prefixes in the YAML. Each records HOW the key was derived, because a
// bare "encrypted" marker cannot be decrypted correctly once more than one
// derivation exists:
//
//	encPrefix    "gcm1:" legacy  key = SHA-256(passphrase), or a raw 32-byte key
//	encPrefixKDF "gcm2:" key = PBKDF2-HMAC-SHA256(passphrase, salt, iters)
//	encPrefixKey "gcmk:" key = the configured 32 bytes, used verbatim
//
// gcm1 is read-only in practice: registries written before this change must
// keep working, and their derivation cannot be improved retroactively.
const (
	encPrefix    = "gcm1:"
	encPrefixKDF = "gcm2:"
	encPrefixKey = "gcmk:"
)

// pbkdf2Iterations is the work factor for deriving an AES key from a
// passphrase. A single unsalted SHA-256 — what this replaced — is not a
// key derivation at all: it is one hash, so anyone holding an encrypted
// registry can test billions of candidate passphrases per second on a GPU and
// recover a weak one. The cost here is paid once per CLI invocation.
const pbkdf2Iterations = 210000

// pbkdf2SaltLen is the random per-registry salt length in bytes.
const pbkdf2SaltLen = 16

// pbkdf2SHA256 is PBKDF2-HMAC-SHA256 (RFC 2898) on the standard library.
// golang.org/x/crypto is not a dependency, and crypto/pbkdf2 postdates the
// Go version this module builds with, so it is written out here.
func pbkdf2SHA256(password, salt []byte, iter, keyLen int) []byte {
	out := make([]byte, 0, keyLen)
	var counter [4]byte
	for block := 1; len(out) < keyLen; block++ {
		mac := hmac.New(sha256.New, password)
		mac.Write(salt)
		binary.BigEndian.PutUint32(counter[:], uint32(block))
		mac.Write(counter[:])
		u := mac.Sum(nil)
		t := make([]byte, len(u))
		copy(t, u)
		for i := 1; i < iter; i++ {
			mac.Reset()
			mac.Write(u)
			u = mac.Sum(nil)
			for j := range t {
				t[j] ^= u[j]
			}
		}
		out = append(out, t...)
	}
	return out[:keyLen]
}

// secretKey is the resolved encryption key plus how to re-derive it when
// decrypting: salt is set only for the PBKDF2 form, and direct marks a key the
// operator supplied already at full strength (no KDF, no salt).
type secretKey struct {
	raw    []byte
	salt   []byte
	direct bool
}

// fleetSecretKey returns the encryption key, or nil when encryption is not
// configured at all.
//
// COMPANION_FLEET_SECRET_KEY may be a 32-byte key (hex or base64), which is
// used verbatim, or a passphrase of any strength, which is stretched with
// PBKDF2-HMAC-SHA256. A passphrase is only as strong as the passphrase — but
// stretching is what makes a weak one cost an attacker real work to recover.
func fleetSecretKey() (*secretKey, error) {
	raw := strings.TrimSpace(os.Getenv("COMPANION_FLEET_SECRET_KEY"))
	if raw == "" {
		return nil, nil
	}
	if b, err := hexOrBase64(raw); err == nil && len(b) == 32 {
		return &secretKey{raw: b, direct: true}, nil
	}
	salt := make([]byte, pbkdf2SaltLen)
	if _, err := io.ReadFull(rand.Reader, salt); err != nil {
		return nil, err
	}
	return &secretKey{raw: pbkdf2SHA256([]byte(raw), salt, pbkdf2Iterations, 32), salt: salt}, nil
}

// legacyKey reproduces the original derivation, for values written before the
// KDF existed. It cannot know whether the operator supplied a 32-byte key or a
// passphrase, because the old format did not record it — so it keeps the old
// ambiguity rather than invalidating existing registries.
func legacyKey() (*secretKey, error) {
	raw := strings.TrimSpace(os.Getenv("COMPANION_FLEET_SECRET_KEY"))
	if raw == "" {
		return nil, nil
	}
	if b, err := hexOrBase64(raw); err == nil && len(b) == 32 {
		return &secretKey{raw: b, direct: true}, nil
	}
	sum := sha256.Sum256([]byte(raw))
	return &secretKey{raw: sum[:]}, nil
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
	block, err := aes.NewCipher(key.raw)
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
	if key.direct {
		// A full-strength key: no KDF was applied, so record that, or a later
		// read would try to PBKDF2 something that was never a passphrase.
		return encPrefixKey + base64.StdEncoding.EncodeToString(ct), nil
	}
	return encPrefixKDF +
		base64.StdEncoding.EncodeToString(key.salt) + ":" +
		base64.StdEncoding.EncodeToString(ct), nil
}

// isEncrypted reports whether a stored value is in any of the encrypted forms.
func isEncrypted(v string) bool {
	return strings.HasPrefix(v, encPrefix) ||
		strings.HasPrefix(v, encPrefixKDF) ||
		strings.HasPrefix(v, encPrefixKey)
}

// unprotectSecret reverses protectSecret. An encrypted value with no key
// configured is an error, never a silent empty string: a fleet that quietly
// lost its secrets would fail at push time with a confusing "secret required".
func unprotectSecret(v string) (string, error) {
	if v == "" {
		return "", nil
	}
	if !isEncrypted(v) {
		return v, nil // plaintext (file written before encryption was enabled)
	}

	// The prefix decides the derivation. For the PBKDF2 form the salt travels
	// with the ciphertext, so re-deriving needs only the passphrase.
	var key *secretKey
	var encoded string
	switch {
	case strings.HasPrefix(v, encPrefixKDF):
		rest := strings.TrimPrefix(v, encPrefixKDF)
		parts := strings.SplitN(rest, ":", 2)
		if len(parts) != 2 {
			return "", fmt.Errorf("corrupt encrypted secret: missing salt")
		}
		salt, err := base64.StdEncoding.DecodeString(parts[0])
		if err != nil {
			return "", fmt.Errorf("corrupt encrypted secret: bad salt: %w", err)
		}
		pass := os.Getenv("COMPANION_FLEET_SECRET_KEY")
		if pass == "" {
			return "", fmt.Errorf("this registry has ENCRYPTED device secrets but COMPANION_FLEET_SECRET_KEY is not set")
		}
		key = &secretKey{raw: pbkdf2SHA256([]byte(pass), salt, pbkdf2Iterations, 32), salt: salt}
		encoded = parts[1]
	default:
		// gcmk: a raw key, or gcm1: the original SHA-256 derivation.
		var err error
		key, err = legacyKey()
		if err != nil {
			return "", err
		}
		if key == nil {
			return "", fmt.Errorf("this registry has ENCRYPTED device secrets but COMPANION_FLEET_SECRET_KEY is not set")
		}
		encoded = strings.TrimPrefix(strings.TrimPrefix(v, encPrefixKey), encPrefix)
	}
	raw, err := base64.StdEncoding.DecodeString(encoded)
	if err != nil {
		return "", fmt.Errorf("corrupt encrypted secret: %w", err)
	}
	block, err := aes.NewCipher(key.raw)
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
