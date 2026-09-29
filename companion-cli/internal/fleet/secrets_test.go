package fleet

import (
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
	if !strings.Contains(string(raw), encPrefix) {
		t.Fatalf("expected the %s marker in the file:\n%s", encPrefix, raw)
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
