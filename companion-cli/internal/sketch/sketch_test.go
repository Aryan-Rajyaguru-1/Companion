package sketch

import (
	"os"
	"path/filepath"
	"testing"
)

func writeSketchYAML(t *testing.T, content string) string {
	t.Helper()
	dir := t.TempDir()
	if err := os.WriteFile(filepath.Join(dir, FileName), []byte(content), 0o644); err != nil {
		t.Fatal(err)
	}
	return dir
}

func TestLoadAndResolveNamedProfile(t *testing.T) {
	dir := writeSketchYAML(t, `
default_profile: prod
profiles:
  dev:
    fqbn: arduino:avr:uno
  prod:
    fqbn: esp32:esp32:esp32
    port: 192.168.4.1:3333
    libraries:
      - WiFiManager@2.0.17
      - ArduinoJson
`)
	f, err := Load(dir)
	if err != nil {
		t.Fatal(err)
	}
	p, err := f.Resolve("prod")
	if err != nil {
		t.Fatal(err)
	}
	if p.FQBN != "esp32:esp32:esp32" || p.Port != "192.168.4.1:3333" {
		t.Errorf("prod profile = %+v", p)
	}
	if len(p.Libraries) != 2 || p.Libraries[0] != "WiFiManager@2.0.17" {
		t.Errorf("libraries = %v", p.Libraries)
	}

	// Default profile resolves without a name
	dp, err := f.Resolve("")
	if err != nil || dp.FQBN != "esp32:esp32:esp32" {
		t.Errorf("default resolve = %+v, %v", dp, err)
	}
}

func TestResolveSingleProfileWithoutDefault(t *testing.T) {
	dir := writeSketchYAML(t, `
profiles:
  only:
    fqbn: esp8266:esp8266:nodemcuv2
`)
	f, _ := Load(dir)
	p, err := f.Resolve("")
	if err != nil || p.FQBN != "esp8266:esp8266:nodemcuv2" {
		t.Errorf("single-profile auto-select failed: %+v, %v", p, err)
	}
}

func TestResolveAmbiguousProfilesErrors(t *testing.T) {
	dir := writeSketchYAML(t, `
profiles:
  a: {fqbn: x:x:x}
  b: {fqbn: y:y:y}
`)
	f, _ := Load(dir)
	if _, err := f.Resolve(""); err == nil {
		t.Error("expected error when multiple profiles and no default")
	}
}

func TestLegacyFQBNStillWorks(t *testing.T) {
	dir := writeSketchYAML(t, "fqbn: arduino:avr:mega\n")
	f, _ := Load(dir)
	p, err := f.Resolve("")
	if err != nil || p.FQBN != "arduino:avr:mega" {
		t.Errorf("legacy fqbn = %+v, %v", p, err)
	}
}

func TestAddRemoveLibrary(t *testing.T) {
	dir := t.TempDir()
	f := &File{}
	f.SetProfile("main", Profile{FQBN: "a:b:c"})
	p, _ := f.Resolve("main")

	if !p.AddLibrary("LibA@1.0") {
		t.Error("first add should report true")
	}
	if p.AddLibrary("LibA@1.0") {
		t.Error("duplicate add should report false")
	}
	if p.AddLibrary("LibB") == false {
		t.Error("second distinct add should report true")
	}
	if !p.RemoveLibrary("liba") {
		t.Error("remove should match ignoring version suffix")
	}
	f.SetProfile("main", *p)
	if err := f.SaveTo(dir); err != nil {
		t.Fatal(err)
	}

	rf, err := Load(dir)
	if err != nil {
		t.Fatal(err)
	}
	rp, _ := rf.Resolve("main")
	if len(rp.Libraries) != 1 || rp.Libraries[0] != "LibB" {
		t.Errorf("after save/load libraries = %v", rp.Libraries)
	}
}
