package config

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// Audit F006: config must be owner-only — a future secret field must never
// inherit world-readable permissions.
func TestSaveIsOwnerOnly(t *testing.T) {
	path := filepath.Join(t.TempDir(), "config.yaml")
	if err := Save(testConfig(), path); err != nil {
		t.Fatalf("Save: %v", err)
	}
	fi, err := os.Stat(path)
	if err != nil {
		t.Fatalf("stat: %v", err)
	}
	if perm := fi.Mode().Perm(); perm != 0o600 {
		t.Fatalf("config perms = %o, want 600", perm)
	}
}

// Older Companion versions left config.yaml at 0644. Saving a bridge key must
// tighten the existing file, not just the mode passed to a create-only write.
func TestSaveTightensExistingConfigPermissions(t *testing.T) {
	path := filepath.Join(t.TempDir(), "config.yaml")
	if err := os.WriteFile(path, []byte("bridge:\n  host: old.example\n"), 0o644); err != nil {
		t.Fatalf("seed config: %v", err)
	}
	if err := os.Chmod(path, 0o644); err != nil {
		t.Fatalf("seed mode: %v", err)
	}

	if err := Save(testConfig(), path); err != nil {
		t.Fatalf("Save: %v", err)
	}
	fi, err := os.Stat(path)
	if err != nil {
		t.Fatalf("stat: %v", err)
	}
	if perm := fi.Mode().Perm(); perm != 0o600 {
		t.Fatalf("config perms = %o, want 600", perm)
	}
}

func testConfig() *Config {
	return &Config{
		Bridge: BridgeConfig{Host: "192.168.4.1", Port: 3333, Baud: 115200, MCU: "avr"},
		Daemon: DaemonConfig{Enabled: false, Port: 0},
		Cache:  CacheConfig{Enabled: true, MaxSizeMB: 500, MaxAgeDays: 30},
	}
}

func TestSetValueBridgePortAndBaud(t *testing.T) {
	cfg := testConfig()

	if err := SetValue(cfg, "bridge.port", "4444"); err != nil {
		t.Fatalf("bridge.port set: %v", err)
	}
	if cfg.Bridge.Port != 4444 {
		t.Errorf("Bridge.Port = %d, want 4444", cfg.Bridge.Port)
	}
	v, err := GetValue(cfg, "bridge.port")
	if err != nil || v != "4444" {
		t.Errorf("GetValue(bridge.port) = %q,%v; want 4444,nil", v, err)
	}

	if err := SetValue(cfg, "bridge.baud", "9600"); err != nil {
		t.Fatalf("bridge.baud set: %v", err)
	}
	if cfg.Bridge.Baud != 9600 {
		t.Errorf("Bridge.Baud = %d, want 9600", cfg.Bridge.Baud)
	}
}

func TestSetValueRejectsInvalidValues(t *testing.T) {
	cfg := testConfig()
	for _, c := range []struct{ key, val string }{
		{"bridge.port", "0"},
		{"bridge.port", "70000"},
		{"bridge.port", "abc"},
		{"bridge.baud", "-1"},
		{"bridge.baud", "fast"},
		{"daemon.port", "99999"},
		{"cache.max_size_mb", "-5"},
		{"compiler.warnings", "shout"},
		{"bridge.mcu", "riscv"},
	} {
		if err := SetValue(cfg, c.key, c.val); err == nil {
			t.Errorf("SetValue(%q, %q) should fail", c.key, c.val)
		}
	}
}

func TestSetValueDaemonAndCacheKeys(t *testing.T) {
	cfg := testConfig()
	if err := SetValue(cfg, "daemon.enabled", "true"); err != nil || !cfg.Daemon.Enabled {
		t.Errorf("daemon.enabled: err=%v enabled=%v", err, cfg.Daemon.Enabled)
	}
	if err := SetValue(cfg, "daemon.port", "45000"); err != nil || cfg.Daemon.Port != 45000 {
		t.Errorf("daemon.port: err=%v port=%d", err, cfg.Daemon.Port)
	}
	if err := SetValue(cfg, "cache.max_age_days", "7"); err != nil || cfg.Cache.MaxAgeDays != 7 {
		t.Errorf("cache.max_age_days: err=%v days=%d", err, cfg.Cache.MaxAgeDays)
	}
}

func TestGetValueUnknownKey(t *testing.T) {
	if _, err := GetValue(testConfig(), "no.such.key"); err == nil {
		t.Error("unknown key should error")
	}
}

func TestPackagesDirLayout(t *testing.T) {
	cfg := testConfig()
	cfg.Directories.Data = "/tmp/data"
	if got := cfg.PackagesDir(); got != filepath.Join("/tmp/data", "packages") {
		t.Errorf("PackagesDir = %q", got)
	}
}

func TestEnsureDirsCreatesTree(t *testing.T) {
	root := t.TempDir()
	cfg := testConfig()
	cfg.Directories.Data = filepath.Join(root, "data")
	cfg.Directories.Downloads = filepath.Join(root, "staging")
	cfg.Directories.User = filepath.Join(root, "sketches")
	if err := EnsureDirs(cfg); err != nil {
		t.Fatalf("EnsureDirs: %v", err)
	}
	for _, d := range []string{cfg.Directories.Data, cfg.Directories.Downloads, cfg.Directories.User} {
		info, err := os.Stat(d)
		if err != nil || !info.IsDir() {
			t.Errorf("expected directory %s to exist", d)
		}
	}
}

func TestBridgeKeyRedactionAndEnvOverride(t *testing.T) {
	cfg := testConfig()
	cfg.Bridge.Key = "saved-bridge-key"

	got, err := GetValue(cfg, "bridge.key")
	if err != nil {
		t.Fatalf("GetValue(bridge.key): %v", err)
	}
	if got != "<set>" {
		t.Fatalf("GetValue(bridge.key) = %q, want <set>", got)
	}
	if BridgeKey(cfg) != "saved-bridge-key" {
		t.Fatalf("BridgeKey = %q, want stored key", BridgeKey(cfg))
	}

	t.Setenv("COMPANION_BRIDGE_KEY", "env-bridge-key")
	if got := BridgeKey(cfg); got != "env-bridge-key" {
		t.Fatalf("BridgeKey with env = %q, want env-bridge-key", got)
	}
	if got, _ := GetValue(cfg, "bridge.key"); got != "<set>" {
		t.Fatalf("GetValue must stay redacted with env override, got %q", got)
	}

	// A blank environment variable must not hide a stored key.
	t.Setenv("COMPANION_BRIDGE_KEY", "   ")
	if got := BridgeKey(cfg); got != "saved-bridge-key" {
		t.Fatalf("blank env BridgeKey = %q, want stored key", got)
	}

	cfg.Bridge.Key = ""
	if got, _ := GetValue(cfg, "bridge.key"); got != "<unset>" {
		t.Fatalf("GetValue with empty key = %q, want <unset>", got)
	}
	if BridgeKey(nil) != "" {
		t.Fatalf("BridgeKey(nil) = %q, want empty", BridgeKey(nil))
	}
}

func TestSetValueBridgeKeyValidation(t *testing.T) {
	for _, value := range []string{
		"short",
		" leading-space",
		"trailing-space ",
		"CHANGE_ME",
		"CHANGE_ME_please",
		"YOUR_KEY_HERE",
		"flashme!",
		"line\nbreak",
		"carriage\rreturn",
		"nul\x00byte",
		strings.Repeat("a", 4097),
	} {
		cfg := testConfig()
		if err := SetValue(cfg, "bridge.key", value); err == nil {
			t.Errorf("SetValue(bridge.key, %q) should fail", value)
		}
		if cfg.Bridge.Key != "" {
			t.Errorf("rejected key %q mutated config to %q", value, cfg.Bridge.Key)
		}
	}

	cfg := testConfig()
	for _, value := range []string{"12345678", "0123456789abcdef0123456789abcdef"} {
		if err := SetValue(cfg, "bridge.key", value); err != nil {
			t.Errorf("SetValue(bridge.key, %q): %v", value, err)
		}
		if cfg.Bridge.Key != value {
			t.Errorf("Bridge.Key = %q, want %q", cfg.Bridge.Key, value)
		}
	}

	// Empty is the explicit clear/legacy path.
	if err := SetValue(cfg, "bridge.key", ""); err != nil {
		t.Fatalf("clearing bridge.key: %v", err)
	}
	if cfg.Bridge.Key != "" {
		t.Fatalf("Bridge.Key = %q after clear", cfg.Bridge.Key)
	}
}

func TestBridgeKeyRoundTripsThroughOwnerOnlyConfig(t *testing.T) {
	path := filepath.Join(t.TempDir(), "config.yaml")
	cfg := testConfig()
	cfg.Bridge.Key = "round-trip-bridge-key"
	if err := Save(cfg, path); err != nil {
		t.Fatalf("Save: %v", err)
	}
	loaded, _, err := Load(path)
	if err != nil {
		t.Fatalf("Load: %v", err)
	}
	if got := loaded.Bridge.Key; got != cfg.Bridge.Key {
		t.Fatalf("loaded bridge key = %q, want %q", got, cfg.Bridge.Key)
	}
	fi, err := os.Stat(path)
	if err != nil {
		t.Fatalf("stat: %v", err)
	}
	if perm := fi.Mode().Perm(); perm != 0o600 {
		t.Fatalf("config perms = %o, want 600", perm)
	}
}
