package uploader

import "testing"

func TestResolveAVRMCUKnownBoards(t *testing.T) {
	cases := map[string]string{
		"arduino:avr:uno":      "atmega328p",
		"arduino:avr:mega":     "atmega2560",
		"ARDUINO:AVR:NANO":     "atmega328p", // case-insensitive
		"arduino:avr:leonardo": "atmega32u4",
	}
	for fqbn, want := range cases {
		got, err := resolveAVRMCU(fqbn)
		if err != nil {
			t.Errorf("resolveAVRMCU(%q) unexpected error: %v", fqbn, err)
			continue
		}
		if got != want {
			t.Errorf("resolveAVRMCU(%q) = %q, want %q", fqbn, got, want)
		}
	}
}

func TestResolveAVRMCUThirdComponentGuesses(t *testing.T) {
	if got, err := resolveAVRMCU("vendor:avr:mega"); err != nil || got != "atmega2560" {
		t.Errorf("board-id guess for mega = %q, err %v, want atmega2560", got, err)
	}
	if got, err := resolveAVRMCU("vendor:avr:leonardo"); err != nil || got != "atmega32u4" {
		t.Errorf("board-id guess for leonardo = %q, err %v, want atmega32u4", got, err)
	}
}

func TestResolveAVRMCUUnknownReturnsError(t *testing.T) {
	if _, err := resolveAVRMCU("unknown:thing:whatever"); err == nil {
		t.Error("unknown FQBN should return an error, not default silently")
	}
}