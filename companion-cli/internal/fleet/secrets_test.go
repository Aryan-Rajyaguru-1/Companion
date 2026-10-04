package fleet

import (
	"bytes"
	"crypto/aes"
	"crypto/cipher"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestSecretsRoundTripEncrypted(t *testing.T) {
	key := strings.Repeat("ab", 32) // 64 hex chars = 32 bytes
	t.Setenv("COMPANION_FLEET_SECRET_KEY", key)
	dir := t.TempDir()
	path := filepath.Join(dir, "devices.yaml")
	st := FileStore{Path: path}

	devs := []Device{
		{ID: "node-01", Secret: "a1b2c3d4e5f60718293a4b5c6d7e8f90"},
		{ID: "node-02", Secret: "0f1e2d3c4b5a69788796a5b4c3d2e1f0"},
	}
	if err := st.Save(devs); err != nil {
		t.Fatal(err)
	}

	// On disk the secrets must NOT be readable in plaintext.
	raw, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	for _, d := range devs {
		if strings.Contains(string(raw), d.Secret) {
			t.Fatalf("secret for %s is in the file in PLAINTEXT: %s", d.ID, raw)
		}
	}
	// The marker now depends on how the key was derived (gcm1 legacy,
	// gcm2 PBKDF2 passphrase, gcmk raw key), so assert it is one of those
	// rather than pinning the old one.
	if !bytes.Contains(raw, []byte(encPrefixKDF)) &&
		!bytes.Contains(raw, []byte(encPrefixKey)) &&
		!bytes.Contains(raw, []byte(encPrefix)) {
		t.Fatalf("expected an encrypted marker (%s / %s / %s) in the file:\n%s",
			encPrefix, encPrefixKDF, encPrefixKey, raw)
	}

	// And they must come back exactly.
	back, err := st.Load()
	if err != nil {
		t.Fatal(err)
	}
	if len(back) != 2 || back[0].Secret != devs[0].Secret || back[1].Secret != devs[1].Secret {
		t.Fatalf("round trip lost data: %+v", back)
	}
}

// A registry written before encryption existed must keep working: those values
// are plaintext and must load unchanged.
func TestSecretsPlaintextStillLoads(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "devices.yaml")
	body := "- id: node-01\n  secret: abcdef0123456789\n"
	if err := os.WriteFile(path, []byte(body), 0o600); err != nil {
		t.Fatal(err)
	}
	back, err := FileStore{Path: path}.Load()
	if err != nil {
		t.Fatal(err)
	}
	if len(back) != 1 || back[0].Secret != "abcdef0123456789" {
		t.Fatalf("plaintext secret mangled: %+v", back)
	}
}

// Loading an encrypted registry WITHOUT the key must fail loudly. Returning an
// empty secret would look like "not provisioned" and fail later, at push time,
// with a message about the wrong thing.
func TestSecretsEncryptedWithoutKeyFails(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "devices.yaml")
	t.Setenv("COMPANION_FLEET_SECRET_KEY", strings.Repeat("ab", 32))
	if err := (FileStore{Path: path}).Save([]Device{{ID: "n", Secret: "s3cret"}}); err != nil {
		t.Fatal(err)
	}
	t.Setenv("COMPANION_FLEET_SECRET_KEY", "")
	_, err := FileStore{Path: path}.Load()
	if err == nil {
		t.Fatal("expected an error when the key is missing")
	}
	if !strings.Contains(err.Error(), "COMPANION_FLEET_SECRET_KEY") {
		t.Fatalf("error should name the variable: %v", err)
	}
}

// The wrong key must fail rather than return garbage.
func TestSecretsWrongKeyFails(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "devices.yaml")
	t.Setenv("COMPANION_FLEET_SECRET_KEY", strings.Repeat("ab", 32))
	if err := (FileStore{Path: path}).Save([]Device{{ID: "n", Secret: "s3cret"}}); err != nil {
		t.Fatal(err)
	}
	t.Setenv("COMPANION_FLEET_SECRET_KEY", strings.Repeat("cd", 32))
	_, err := FileStore{Path: path}.Load()
	if err == nil || !strings.Contains(err.Error(), "did not decrypt") {
		t.Fatalf("expected a decrypt failure, got %v", err)
	}
}

// With no key configured the file stays plaintext — encryption is opt-in, and
// the operator must be able to inspect their own registry.
func TestSecretsNoKeyLeavesPlaintext(t *testing.T) {
	t.Setenv("COMPANION_FLEET_SECRET_KEY", "")
	dir := t.TempDir()
	path := filepath.Join(dir, "devices.yaml")
	if err := (FileStore{Path: path}).Save([]Device{{ID: "n", Secret: "s3cret"}}); err != nil {
		t.Fatal(err)
	}
	raw, _ := os.ReadFile(path)
	if !strings.Contains(string(raw), "s3cret") {
		t.Fatalf("without a key the value should stay plaintext:\n%s", raw)
	}
}

// TestPBKDF2SHA256Vectors checks the hand-written KDF against the published
// PBKDF2-HMAC-SHA256 test vectors. It is written out rather than imported
// because golang.org/x/crypto is not a dependency and crypto/pbkdf2 postdates
// this module's Go version — so "we wrote the KDF ourselves" is only safe if
// something proves it agrees with everyone else.
func TestPBKDF2SHA256Vectors(t *testing.T) {
	cases := []struct {
		pass, salt string
		iter, size int
		want       string
	}{
		{"password", "salt", 1, 32,
			"120fb6cffcf8b32c43e7225256c4f837a86548c92ccc35480805987cb70be17b"},
		{"password", "salt", 2, 32,
			"ae4d0c95af6b46d32d0adff928f06dd02a303f8ef3c251dfd6e2d85a95474c43"},
		{"password", "salt", 4096, 32,
			"c5e478d59288c841aa530db6845c4c8d962893a001ce4e11a4963873aa98134a"},
		// dkLen spanning more than one HMAC block.
		{"passwordPASSWORDpassword", "saltSALTsaltSALTsaltSALTsaltSALTsalt", 4096, 40,
			"348c89dbcbd32b2f32d814b8116e84cf2b17347ebc1800181c4e2a1fb8dd53e1c635518c7dac47e9"},
	}
	for _, tc := range cases {
		got := pbkdf2SHA256([]byte(tc.pass), []byte(tc.salt), tc.iter, tc.size)
		if hex.EncodeToString(got) != tc.want {
			t.Errorf("pbkdf2(%q,%q,%d,%d)\n got %s\nwant %s",
				tc.pass, tc.salt, tc.iter, tc.size, hex.EncodeToString(got), tc.want)
		}
	}
}

// A passphrase must be stretched, and each encryption must use a fresh salt:
// identical plaintext under one passphrase must not produce identical
// ciphertext, or an observer learns how many secrets share a value.
func TestSecretKeyUsesPBKDF2AndFreshSalt(t *testing.T) {
	t.Setenv("COMPANION_FLEET_SECRET_KEY", "correct horse battery staple")
	a, err := protectSecret("device-secret-one")
	if err != nil {
		t.Fatal(err)
	}
	b, err := protectSecret("device-secret-one")
	if err != nil {
		t.Fatal(err)
	}
	if a == b {
		t.Error("two encryptions of the same secret are identical — salt or nonce is not random")
	}
	if !strings.HasPrefix(a, encPrefixKDF) {
		t.Errorf("a passphrase must produce the %s format, got %q", encPrefixKDF, a[:8])
	}
	// Not a single unsalted hash of the passphrase.
	sum := sha256.Sum256([]byte("correct horse battery staple"))
	if strings.Contains(a, base64.StdEncoding.EncodeToString(sum[:8])) {
		t.Error("ciphertext appears to embed a raw SHA-256 of the passphrase")
	}
}

// Legacy gcm1 registries must still decrypt, or enabling the KDF would strand
// every operator who already encrypted their file.
func TestLegacyGCM1StillDecrypts(t *testing.T) {
	const pass = "legacy-passphrase"
	t.Setenv("COMPANION_FLEET_SECRET_KEY", pass)

	sum := sha256.Sum256([]byte(pass))
	block, _ := aes.NewCipher(sum[:])
	gcm, _ := cipher.NewGCM(block)
	nonce := make([]byte, gcm.NonceSize())
	for i := range nonce {
		nonce[i] = byte(i)
	}
	ct := gcm.Seal(nonce, nonce, []byte("old-secret"), nil)
	stored := encPrefix + base64.StdEncoding.EncodeToString(ct)

	got, err := unprotectSecret(stored)
	if err != nil {
		t.Fatalf("a legacy gcm1 value failed to decrypt: %v", err)
	}
	if got != "old-secret" {
		t.Errorf("legacy decrypt returned %q, want %q", got, "old-secret")
	}
}

// A 32-byte key supplied by the operator is used verbatim, and is marked as
// such so a later read does not try to stretch something that is not a
// passphrase.
func TestRawKeyIsUsedVerbatim(t *testing.T) {
	key := make([]byte, 32)
	for i := range key {
		key[i] = byte(i + 1)
	}
	t.Setenv("COMPANION_FLEET_SECRET_KEY", hex.EncodeToString(key))

	enc, err := protectSecret("device-secret")
	if err != nil {
		t.Fatal(err)
	}
	if !strings.HasPrefix(enc, encPrefixKey) {
		t.Errorf("a raw 32-byte key must use %s, got %q", encPrefixKey, enc[:8])
	}
	got, err := unprotectSecret(enc)
	if err != nil || got != "device-secret" {
		t.Errorf("raw-key round trip failed: %q %v", got, err)
	}
}
