package fqbn_test

import (
	"testing"

	"github.com/companion-ide/companion-cli/internal/fqbn"
)

// ── Parse ──────────────────────────────────────────────────────

func TestParse_Basic(t *testing.T) {
	f, err := fqbn.Parse("arduino:avr:uno")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if f.Vendor != "arduino" || f.Architecture != "avr" || f.Board != "uno" {
		t.Errorf("got %+v", f)
	}
	if len(f.Options) != 0 {
		t.Errorf("expected no options, got %v", f.Options)
	}
}

func TestParse_WithOptions(t *testing.T) {
	f, err := fqbn.Parse("arduino:avr:mega:cpu=atmega2560")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if f.Options["cpu"] != "atmega2560" {
		t.Errorf("expected cpu=atmega2560, got %v", f.Options)
	}
}

func TestParse_MultipleOptions(t *testing.T) {
	f, err := fqbn.Parse("esp32:esp32:esp32:freq=240,psram=enabled")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if f.Options["freq"] != "240" || f.Options["psram"] != "enabled" {
		t.Errorf("got options: %v", f.Options)
	}
}

func TestParse_Empty(t *testing.T) {
	if _, err := fqbn.Parse(""); err == nil {
		t.Error("expected error for empty string")
	}
}

func TestParse_TwoSegments(t *testing.T) {
	if _, err := fqbn.Parse("arduino:avr"); err == nil {
		t.Error("expected error for 2-segment FQBN")
	}
}

func TestParse_OneSegment(t *testing.T) {
	if _, err := fqbn.Parse("arduino"); err == nil {
		t.Error("expected error for 1-segment FQBN")
	}
}

func TestParse_STMicro(t *testing.T) {
	f, err := fqbn.Parse("STMicroelectronics:stm32:Nucleo_64")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if f.Vendor != "STMicroelectronics" || f.Board != "Nucleo_64" {
		t.Errorf("got %+v", f)
	}
}

// ── String / Serialize ─────────────────────────────────────────

func TestString_NoOptions(t *testing.T) {
	f := fqbn.MustParse("arduino:avr:uno")
	if got := f.String(); got != "arduino:avr:uno" {
		t.Errorf("expected arduino:avr:uno, got %q", got)
	}
}

func TestString_OptionsAreSorted(t *testing.T) {
	// Options should be alphabetically sorted regardless of parse order
	f, _ := fqbn.Parse("esp32:esp32:esp32:psram=enabled,freq=240")
	got := f.String()
	want := "esp32:esp32:esp32:freq=240,psram=enabled"
	if got != want {
		t.Errorf("expected %q, got %q", want, got)
	}
}

// ── PlatformID ─────────────────────────────────────────────────

func TestPlatformID(t *testing.T) {
	f := fqbn.MustParse("arduino:avr:uno")
	if got := f.PlatformID(); got != "arduino:avr" {
		t.Errorf("expected arduino:avr, got %q", got)
	}
}

// ── Equal / EqualCore ─────────────────────────────────────────

func TestEqual(t *testing.T) {
	a := fqbn.MustParse("arduino:avr:mega:cpu=atmega2560")
	b := fqbn.MustParse("arduino:avr:mega:cpu=atmega2560")
	c := fqbn.MustParse("arduino:avr:mega:cpu=atmega1280")
	if !a.Equal(b) {
		t.Error("equal FQBNs should be equal")
	}
	if a.Equal(c) {
		t.Error("different option FQBNs should not be equal")
	}
}

func TestEqualCore(t *testing.T) {
	a := fqbn.MustParse("arduino:avr:mega:cpu=atmega2560")
	b := fqbn.MustParse("arduino:avr:mega:cpu=atmega1280")
	if !a.EqualCore(b) {
		t.Error("same board different options should be EqualCore")
	}
}

// ── IsValid ────────────────────────────────────────────────────

func TestIsValid(t *testing.T) {
	cases := []struct {
		raw  string
		want bool
	}{
		{"arduino:avr:uno", true},
		{"esp32:esp32:esp32:freq=240", true},
		{"STMicroelectronics:stm32:Nucleo_64", true},
		{"arduino:avr", false},
		{"", false},
		{"bad", false},
	}
	for _, tc := range cases {
		got := fqbn.IsValid(tc.raw)
		if got != tc.want {
			t.Errorf("IsValid(%q) = %v, want %v", tc.raw, got, tc.want)
		}
	}
}

// ── Normalize ──────────────────────────────────────────────────

func TestNormalize_SortsOptions(t *testing.T) {
	in := "esp32:esp32:esp32:psram=enabled,freq=240"
	want := "esp32:esp32:esp32:freq=240,psram=enabled"
	if got := fqbn.Normalize(in); got != want {
		t.Errorf("expected %q, got %q", want, got)
	}
}

func TestNormalize_PassthroughInvalid(t *testing.T) {
	in := "not-an-fqbn"
	if got := fqbn.Normalize(in); got != in {
		t.Errorf("expected passthrough of invalid FQBN, got %q", got)
	}
}

// ── FriendlyName ──────────────────────────────────────────────

func TestFriendlyName(t *testing.T) {
	cases := []struct {
		raw  string
		want string
	}{
		{"arduino:avr:uno", "Arduino Uno"},
		{"esp32:esp32:esp32", "ESP32 Dev Module"},
		{"custom:hw:myboard", "myboard"},
	}
	for _, tc := range cases {
		if got := fqbn.FriendlyName(tc.raw); got != tc.want {
			t.Errorf("FriendlyName(%q) = %q, want %q", tc.raw, got, tc.want)
		}
	}
}

// ── MCUFromFQBN ───────────────────────────────────────────────

func TestMCUFromFQBN(t *testing.T) {
	cases := []struct{ raw, want string }{
		{"arduino:avr:uno", "avr"},
		{"esp32:esp32:esp32", "esp32"},
		{"esp8266:esp8266:nodemcuv2", "esp8266"},
		{"STMicroelectronics:stm32:Nucleo_64", "stm32"},
		{"custom:hw:board", "generic"},
	}
	for _, tc := range cases {
		if got := fqbn.MCUFromFQBN(tc.raw); got != tc.want {
			t.Errorf("MCUFromFQBN(%q) = %q, want %q", tc.raw, got, tc.want)
		}
	}
}
