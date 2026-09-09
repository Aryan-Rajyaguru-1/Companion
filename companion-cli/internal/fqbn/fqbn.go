// Package fqbn implements parsing and validation of Arduino Fully Qualified
// Board Names (FQBNs).
//
// Pattern adopted from: arduino-cli/pkg/fqbn
//
// Format:  vendor:architecture:board[:menu_key=value,menu_key=value,...]
//
// Examples:
//   arduino:avr:uno
//   arduino:avr:mega:cpu=atmega2560
//   esp32:esp32:esp32:freq=240,psram=enabled
//   STMicroelectronics:stm32:Nucleo_64:pnum=NUCLEO_F103RB
//
// Benefits over ad-hoc string handling:
//   - Validation catches typos early
//   - Menu options round-trip cleanly
//   - Portable: FQBNs are universally understood across all Arduino tooling
//   - Sketch files can embed the exact board config (sketch.yaml)
package fqbn

import (
	"fmt"
	"regexp"
	"sort"
	"strings"
)

// ── Types ──────────────────────────────────────────────────────────

// FQBN represents a parsed Fully Qualified Board Name.
type FQBN struct {
	Vendor       string            // e.g. "arduino"
	Architecture string            // e.g. "avr"
	Board        string            // e.g. "uno"
	Options      map[string]string // e.g. {"cpu":"atmega2560","clock":"16MHz"}
}

// ── Validation regex ───────────────────────────────────────────────

// Component names: alphanumeric + underscore + hyphen + dot, 1+ chars
var componentRE = regexp.MustCompile(`^[a-zA-Z0-9_\-\.]+$`)

// ── Parse ──────────────────────────────────────────────────────────

// Parse validates and parses an FQBN string.
// Returns an error with a suggestion if the format is invalid.
func Parse(raw string) (*FQBN, error) {
	if raw == "" {
		return nil, fmt.Errorf("FQBN cannot be empty (expected: vendor:architecture:board)")
	}

	// Split off options: everything after the third colon
	// e.g. "arduino:avr:mega:cpu=atmega2560,clock=16MHz"
	//       [------core------][-----options-----------]
	parts := strings.SplitN(raw, ":", 4)
	if len(parts) < 3 {
		return nil, fmt.Errorf(
			"invalid FQBN %q: expected at least vendor:architecture:board, got %d component(s)",
			raw, len(parts),
		)
	}

	f := &FQBN{
		Vendor:       parts[0],
		Architecture: parts[1],
		Board:        parts[2],
		Options:      map[string]string{},
	}

	// Validate core components
	for _, pair := range []struct{ label, val string }{
		{"vendor", f.Vendor},
		{"architecture", f.Architecture},
		{"board", f.Board},
	} {
		if !componentRE.MatchString(pair.val) {
			return nil, fmt.Errorf(
				"invalid FQBN %q: %s component %q contains illegal characters",
				raw, pair.label, pair.val,
			)
		}
	}

	// Parse menu options (4th segment, comma-separated key=value pairs)
	if len(parts) == 4 && parts[3] != "" {
		optStr := parts[3]
		for _, kv := range strings.Split(optStr, ",") {
			kv = strings.TrimSpace(kv)
			if kv == "" {
				continue
			}
			idx := strings.IndexByte(kv, '=')
			if idx <= 0 {
				return nil, fmt.Errorf(
					"invalid FQBN option %q in %q: expected key=value format",
					kv, raw,
				)
			}
			key := strings.TrimSpace(kv[:idx])
			val := strings.TrimSpace(kv[idx+1:])
			if key == "" {
				return nil, fmt.Errorf("invalid FQBN option in %q: empty key", raw)
			}
			f.Options[key] = val
		}
	}

	return f, nil
}

// MustParse parses an FQBN and panics on error. Use only for known-valid constants.
func MustParse(raw string) *FQBN {
	f, err := Parse(raw)
	if err != nil {
		panic(err)
	}
	return f
}

// ── String / Serialize ─────────────────────────────────────────────

// String returns the canonical FQBN string representation.
// Options are sorted alphabetically for determinism.
func (f *FQBN) String() string {
	core := f.Vendor + ":" + f.Architecture + ":" + f.Board
	if len(f.Options) == 0 {
		return core
	}

	// Sort option keys for deterministic output
	keys := make([]string, 0, len(f.Options))
	for k := range f.Options {
		keys = append(keys, k)
	}
	sort.Strings(keys)

	pairs := make([]string, 0, len(keys))
	for _, k := range keys {
		pairs = append(pairs, k+"="+f.Options[k])
	}
	return core + ":" + strings.Join(pairs, ",")
}

// StringCore returns just vendor:architecture:board without options.
func (f *FQBN) StringCore() string {
	return f.Vendor + ":" + f.Architecture + ":" + f.Board
}

// PlatformID returns the platform identifier (vendor:architecture).
// This is what you pass to `companion board install`.
func (f *FQBN) PlatformID() string {
	return f.Vendor + ":" + f.Architecture
}

// ── Comparison ─────────────────────────────────────────────────────

// Equal reports whether two FQBNs refer to the same board and options.
func (f *FQBN) Equal(other *FQBN) bool {
	if other == nil {
		return false
	}
	return f.String() == other.String()
}

// EqualCore reports whether two FQBNs refer to the same board
// ignoring menu options.
func (f *FQBN) EqualCore(other *FQBN) bool {
	if other == nil {
		return false
	}
	return f.StringCore() == other.StringCore()
}

// ── Mutation ───────────────────────────────────────────────────────

// WithOption returns a new FQBN with the given menu option set.
func (f *FQBN) WithOption(key, value string) *FQBN {
	opts := make(map[string]string, len(f.Options)+1)
	for k, v := range f.Options {
		opts[k] = v
	}
	opts[key] = value
	return &FQBN{
		Vendor:       f.Vendor,
		Architecture: f.Architecture,
		Board:        f.Board,
		Options:      opts,
	}
}

// ── Helpers ────────────────────────────────────────────────────────

// IsValid reports whether a raw FQBN string is syntactically valid.
func IsValid(raw string) bool {
	_, err := Parse(raw)
	return err == nil
}

// Normalize parses and re-serializes a raw FQBN string, canonicalizing it.
// Returns the original string if parsing fails.
func Normalize(raw string) string {
	f, err := Parse(raw)
	if err != nil {
		return raw
	}
	return f.String()
}

// FriendlyName returns a human-readable board name from a known FQBN.
// Returns the board component of the FQBN if not in the known list.
func FriendlyName(raw string) string {
	// Well-known boards — mirrors BoardDropdown.jsx BOARDS list
	names := map[string]string{
		"arduino:avr:uno":                    "Arduino Uno",
		"arduino:avr:mega":                   "Arduino Mega 2560",
		"arduino:avr:nano":                   "Arduino Nano",
		"arduino:avr:leonardo":               "Arduino Leonardo",
		"arduino:avr:pro":                    "Arduino Pro Mini",
		"arduino:avr:micro":                  "Arduino Micro",
		"arduino:avr:diecimila":              "Arduino Diecimila",
		"esp32:esp32:esp32":                  "ESP32 Dev Module",
		"esp32:esp32:esp32s3":                "ESP32-S3 Dev",
		"esp32:esp32:esp32s2":                "ESP32-S2 Dev",
		"esp32:esp32:esp32c3":                "ESP32-C3 Dev",
		"esp32:esp32:esp32c6":                "ESP32-C6 Dev",
		"esp8266:esp8266:nodemcuv2":          "NodeMCU 1.0 (ESP-12E)",
		"esp8266:esp8266:d1_mini":            "Wemos D1 Mini",
		"STMicroelectronics:stm32:Nucleo_64": "STM32 Nucleo-64",
		"STMicroelectronics:stm32:GenF1":     "STM32 Generic F1 (BluePill)",
		"STMicroelectronics:stm32:GenF4":     "STM32 Generic F4 (BlackPill)",
		"arduino:samd:arduino_zero_edbg":     "Arduino Zero",
		"arduino:samd:mkr1000":               "Arduino MKR1000",
	}

	f, err := Parse(raw)
	if err != nil {
		return raw
	}
	core := f.StringCore()
	if name, ok := names[core]; ok {
		if len(f.Options) > 0 {
			return name + " (custom)"
		}
		return name
	}
	return f.Board
}

// MCUFromFQBN infers the MCU family from a well-known FQBN.
// Used to determine the upload protocol.
func MCUFromFQBN(raw string) string {
	f, err := Parse(raw)
	if err != nil {
		return "generic"
	}
	switch f.Vendor + ":" + f.Architecture {
	case "arduino:avr":
		return "avr"
	case "esp32:esp32":
		return "esp32"
	case "esp8266:esp8266":
		return "esp8266"
	case "STMicroelectronics:stm32":
		return "stm32"
	case "arduino:samd":
		return "samd"
	case "arduino:megaavr":
		return "megaavr"
	case "arduino:mbed", "arduino:mbed_giga":
		return "mbed"
	default:
		return "generic"
	}
}
