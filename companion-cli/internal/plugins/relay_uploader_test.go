package plugins

import (
	"context"
	"strings"
	"testing"
)

// The relay uploader must be discoverable and selectable BY ID, and it must
// never be the auto-selected uploader: UploaderFor() returns the first plugin
// claiming an FQBN, and the relay transport claims every core. If it were
// registered first it would silently shadow the LAN ArduinoOTA uploader.
func TestRelayUploaderIsOptInOnly(t *testing.T) {
	r := NewRegistry()
	for _, p := range builtins() {
		switch v := p.(type) {
		case UploaderPlugin:
			r.RegisterUploader(v)
		}
	}
	if r.UploaderByID("companion.uploader.relay") == nil {
		t.Fatal("relay uploader is not registered")
	}
	auto := r.UploaderFor("esp32:esp32:esp32")
	if auto == nil {
		t.Fatal("no auto uploader for esp32")
	}
	if auto.ID() == "companion.uploader.relay" {
		t.Fatal("the relay uploader shadowed the default LAN uploader for esp32")
	}
	if auto.ID() != "companion.uploader.ota" {
		t.Fatalf("auto-selected uploader is %q, want companion.uploader.ota", auto.ID())
	}
}

// A missing piece of configuration must fail with a message that names the
// environment variable to set — an agent or a script gets "set X", never a
// silent fallback.
func TestRelayUploaderExplainsMissingConfig(t *testing.T) {
	cases := []struct {
		name    string
		env     map[string]string
		host    string
		wantAll []string
	}{
		{"no hub", map[string]string{}, "node-01", []string{"COMPANION_RELAY_HUB"}},
		{"no device", map[string]string{"COMPANION_RELAY_HUB": "wss://x"}, "", []string{"device id"}},
		{"no token", map[string]string{"COMPANION_RELAY_HUB": "wss://x"}, "node-01", []string{"COMPANION_RELAY_AGENTS_TOKEN"}},
		{"no secret", map[string]string{
			"COMPANION_RELAY_HUB": "wss://x", "COMPANION_RELAY_AGENTS_TOKEN": "t",
		}, "node-01", []string{"COMPANION_RELAY_DEVICE_SECRET"}},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			for k, v := range tc.env {
				t.Setenv(k, v)
			}
			// Clear anything the outer environment may have set.
			for _, k := range []string{"COMPANION_RELAY_HUB", "COMPANION_RELAY_AGENTS_TOKEN", "COMPANION_RELAY_DEVICE_SECRET"} {
				if _, ok := tc.env[k]; !ok {
					t.Setenv(k, "")
				}
			}
			u := &relayUploader{}
			_ = u.Init(PluginConfig{})
			err := u.Upload(context.Background(), UploadOptions{Host: tc.host}, &strings.Builder{})
			if err == nil {
				t.Fatal("expected an error")
			}
			for _, want := range tc.wantAll {
				if !strings.Contains(err.Error(), want) {
					t.Errorf("error %q should mention %q", err.Error(), want)
				}
			}
		})
	}
}

// The secret is never accepted from a flag: UploadOptions has no field for it,
// and the error must point at the environment.
func TestRelayUploaderNeverTakesSecretFromOptions(t *testing.T) {
	t.Setenv("COMPANION_RELAY_HUB", "wss://x")
	t.Setenv("COMPANION_RELAY_AGENTS_TOKEN", "tok")
	t.Setenv("COMPANION_RELAY_DEVICE_SECRET", "")
	u := &relayUploader{}
	_ = u.Init(PluginConfig{})
	// Even if a caller smuggles one through ExtraFlags, it is not read.
	err := u.Upload(context.Background(), UploadOptions{
		Host:       "node-01",
		BinaryPath: "/tmp/fw.bin",
		ExtraFlags: []string{"relay-device-secret=leaked"},
	}, &strings.Builder{})
	if err == nil || !strings.Contains(err.Error(), "COMPANION_RELAY_DEVICE_SECRET") {
		t.Fatalf("a flag-supplied secret must be ignored; got %v", err)
	}
}
