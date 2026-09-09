package config

import (
	"os"
	"path/filepath"
	"testing"
)

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
