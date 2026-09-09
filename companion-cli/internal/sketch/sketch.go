// Package sketch manages companion sketch metadata (sketch.yaml).
//
// A sketch.yaml can pin the target board and library set so builds are
// reproducible and shareable:
//
//	default_profile: prod
//	profiles:
//	  prod:
//	    fqbn: esp32:esp32:esp32
//	    port: 192.168.4.1:3333
//	    libraries:
//	      - WiFiManager@2.0.17
//	      - ArduinoJson
//
// The format is Companion's own; it is intentionally simple YAML with no
// dependency on any other tool's sketch metadata.
package sketch

import (
	"fmt"
	"os"
	"path/filepath"

	"gopkg.in/yaml.v3"
)

const FileName = "sketch.yaml"

// Profile pins a build configuration: board + optional libraries + port.
type Profile struct {
	FQBN       string   `yaml:"fqbn,omitempty"`
	Port       string   `yaml:"port,omitempty"`
	Baud       uint32   `yaml:"baud,omitempty"`
	MCU        string   `yaml:"mcu,omitempty"`
	Programmer string   `yaml:"programmer,omitempty"`
	Libraries  []string `yaml:"libraries,omitempty"`
	OTA        bool     `yaml:"ota,omitempty"`
}

// File is the root of a sketch.yaml document.
type File struct {
	// Legacy single-board field, still honoured when no profiles exist.
	FQBN string `yaml:"fqbn,omitempty"`

	DefaultProfile string             `yaml:"default_profile,omitempty"`
	Profiles       map[string]Profile `yaml:"profiles,omitempty"`

	path string // where this was loaded from (for Save)
}

// Load reads sketchDir/sketch.yaml. A missing file yields an empty File
// (not an error) so callers can treat profiles as optional.
func Load(sketchDir string) (*File, error) {
	f := &File{path: filepath.Join(sketchDir, FileName)}
	data, err := os.ReadFile(f.path)
	if err != nil {
		if os.IsNotExist(err) {
			return f, nil
		}
		return nil, fmt.Errorf("reading %s: %w", FileName, err)
	}
	if err := yaml.Unmarshal(data, f); err != nil {
		return nil, fmt.Errorf("parsing %s: %w", FileName, err)
	}
	return f, nil
}

// Save writes the file back to its original location (or sketchDir when
// created programmatically).
func (f *File) Save() error {
	if f.path == "" {
		return fmt.Errorf("sketch file path not set")
	}
	out, err := yaml.Marshal(f)
	if err != nil {
		return err
	}
	return os.WriteFile(f.path, out, 0o644)
}

// SaveTo writes the file to sketchDir/sketch.yaml.
func (f *File) SaveTo(sketchDir string) error {
	f.path = filepath.Join(sketchDir, FileName)
	return f.Save()
}

// Resolve returns the named profile, or the default profile when name=="".
// Falls back to the legacy top-level fqbn as an anonymous profile.
func (f *File) Resolve(name string) (*Profile, error) {
	if name == "" {
		name = f.DefaultProfile
	}
	if name == "" {
		switch len(f.Profiles) {
		case 0:
			if f.FQBN != "" {
				return &Profile{FQBN: f.FQBN}, nil
			}
			return nil, nil // no profiles at all — caller uses flags/config
		case 1:
			for n := range f.Profiles { // exactly one profile: use it
				p := f.Profiles[n]
				return &p, nil
			}
		default:
			return nil, fmt.Errorf("multiple profiles defined (%s) — specify one with --profile",
				strings2Keys(f.Profiles))
		}
	}
	p, ok := f.Profiles[name]
	if !ok {
		return nil, fmt.Errorf("profile %q not found in %s (available: %s)",
			name, FileName, strings2Keys(f.Profiles))
	}
	return &p, nil
}

// SetProfile inserts or replaces a profile.
func (f *File) SetProfile(name string, p Profile) {
	if f.Profiles == nil {
		f.Profiles = map[string]Profile{}
	}
	f.Profiles[name] = p
	if f.DefaultProfile == "" && len(f.Profiles) == 1 {
		f.DefaultProfile = name
	}
}

// AddLibrary appends a pinned library if not already present.
func (p *Profile) AddLibrary(lib string) bool {
	for _, l := range p.Libraries {
		if l == lib {
			return false
		}
	}
	p.Libraries = append(p.Libraries, lib)
	return true
}

// RemoveLibrary drops a pinned library by name (ignoring @version suffix
// and letter case).
func (p *Profile) RemoveLibrary(lib string) bool {
	base := libBaseName(lib)
	out := p.Libraries[:0]
	removed := false
	for _, l := range p.Libraries {
		if equalFoldASCII(libBaseName(l), base) {
			removed = true
			continue
		}
		out = append(out, l)
	}
	p.Libraries = out
	return removed
}

func equalFoldASCII(a, b string) bool {
	if len(a) != len(b) {
		return false
	}
	for i := 0; i < len(a); i++ {
		ca, cb := a[i], b[i]
		if 'A' <= ca && ca <= 'Z' {
			ca += 32
		}
		if 'A' <= cb && cb <= 'Z' {
			cb += 32
		}
		if ca != cb {
			return false
		}
	}
	return true
}

// libBaseName strips an @version suffix.
func libBaseName(s string) string {
	if i := indexByte(s, '@'); i >= 0 {
		return s[:i]
	}
	return s
}

func indexByte(s string, c byte) int {
	for i := 0; i < len(s); i++ {
		if s[i] == c {
			return i
		}
	}
	return -1
}

// strings2Keys renders sorted-ish map keys for error messages.
func strings2Keys(m map[string]Profile) string {
	keys := make([]string, 0, len(m))
	for k := range m {
		keys = append(keys, k)
	}
	// simple insertion sort — lists are tiny
	for i := 1; i < len(keys); i++ {
		for j := i; j > 0 && keys[j] < keys[j-1]; j-- {
			keys[j], keys[j-1] = keys[j-1], keys[j]
		}
	}
	out := ""
	for i, k := range keys {
		if i > 0 {
			out += ", "
		}
		out += k
	}
	return out
}
