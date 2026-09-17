package uploader

import (
	"os"
	"path/filepath"
	"reflect"
	"testing"

	"github.com/companion-ide/companion-cli/internal/config"
)

func TestFindBundledEsptoolPrefersNewest(t *testing.T) {
	// Discovery also searches the user's Arduino installations. Keep the
	// fixture independent of tools installed on the developer's machine.
	home := t.TempDir()
	t.Setenv("HOME", home)
	t.Setenv("USERPROFILE", home)
	t.Setenv("home", home)
	root := t.TempDir()
	t.Setenv("ARDUINO15_DIR", root)
	mk := func(rel string) string {
		p := filepath.Join(root, filepath.FromSlash(rel))
		if err := os.MkdirAll(filepath.Dir(p), 0o755); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(p, []byte("#!/bin/sh\n"), 0o755); err != nil {
			t.Fatal(err)
		}
		return p
	}
	oldPy := mk("esp8266/tools/esptool_py/4.4/esptool.py")
	newBin := mk("esp32/tools/esptool_py/5.3.1/esptool")

	got := findBundledEsptool(nil)
	if got != newBin {
		t.Fatalf("findBundledEsptool() = %q; want newest %q (over %q)", got, newBin, oldPy)
	}
}

func TestFindBundledEsptoolUsesConfigPackagesDir(t *testing.T) {
	home := t.TempDir()
	t.Setenv("HOME", home)
	t.Setenv("USERPROFILE", home)
	t.Setenv("home", home)
	t.Setenv("ARDUINO15_DIR", "")
	data := t.TempDir()
	cfg := &config.Config{}
	cfg.Directories.Data = data
	want := filepath.Join(data, "packages", "esp32", "tools", "esptool_py", "5.3.1", "esptool")
	if err := os.MkdirAll(filepath.Dir(want), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(want, []byte("x"), 0o755); err != nil {
		t.Fatal(err)
	}
	if got := findBundledEsptool(cfg); got != want {
		t.Fatalf("findBundledEsptool() = %q; want %q", got, want)
	}
}

func TestResetStyleForVersion(t *testing.T) {
	cases := map[string]string{
		filepath.Join("x", "esptool_py", "5.3.1", "esptool"):    "hyphen",
		filepath.Join("x", "esptool_py", "4.8.1", "esptool.py"): "underscore",
		filepath.Join("x", "esptool_py", "5.0", "esptool"):      "hyphen",
	}
	for path, want := range cases {
		if got := resetStyleFor(path); got != want {
			t.Errorf("resetStyleFor(%q) = %q, want %q", path, got, want)
		}
	}
}

func TestReadFlashArgsPreservesOptionValues(t *testing.T) {
	dir := t.TempDir()
	manifest := "--flash-mode qio --flash-freq 80m --flash-size 4MB\n" +
		"0x1000 bootloader.bin\n0x8000 partitions.bin\n0xe000 boot_app0.bin\n0x10000 sketch.bin\n"
	if err := os.WriteFile(filepath.Join(dir, "flash_args"), []byte(manifest), 0o644); err != nil {
		t.Fatal(err)
	}
	for _, name := range []string{"bootloader.bin", "partitions.bin", "boot_app0.bin", "sketch.bin"} {
		if err := os.WriteFile(filepath.Join(dir, name), []byte{0xe9}, 0o644); err != nil {
			t.Fatal(err)
		}
	}
	got, ok := readFlashArgs(filepath.Join(dir, "sketch.bin"))
	want := []string{
		"--flash_mode", "qio", "--flash_freq", "80m", "--flash_size", "4MB",
		"0x1000", filepath.Join(dir, "bootloader.bin"),
		"0x8000", filepath.Join(dir, "partitions.bin"),
		"0xe000", filepath.Join(dir, "boot_app0.bin"),
		"0x10000", filepath.Join(dir, "sketch.bin"),
	}
	if !ok || !reflect.DeepEqual(got, want) {
		t.Fatalf("readFlashArgs() = %q, %v; want %q, true", got, ok, want)
	}
}
