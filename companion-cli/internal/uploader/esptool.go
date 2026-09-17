// esptool.go — resolving the esptool invocation for USB flashing.
//
// Two things matter for reliability here:
//
//  1. WHICH esptool. The esp32 core ships its own esptool.py under
//     <packages>/<vendor>/tools/esptool_py/<ver>/. Using that means USB
//     flashing works on a machine that never ran `pip install esptool`, which
//     is the common case for someone who just installed the core from the IDE.
//     `python -m esptool` stays as the fallback.
//
//  2. HOW MANY images. An ESP chip boots from three images (bootloader,
//     partition table, OTA selector) plus the application. Writing only the
//     application works on a board that already boots, and silently fails to
//     produce a working chip on a blank one. When arduino-cli's `flash_args`
//     file sits next to the binary we flash the full set exactly as Arduino
//     would; otherwise we write the app alone and say so.
package uploader

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"

	"github.com/companion-ide/companion-cli/internal/config"
	"github.com/companion-ide/companion-cli/internal/version"
)

// resolveEsptoolPrefix returns the command that runs esptool plus the reset
// argument style it expects: esptool 5.x renamed the --before/--after values
// from default_reset/hard_reset to default-reset/hard-reset (the platform's
// own upload recipe uses the hyphenated form with its bundled 5.x tool).
func resolveEsptoolPrefix(cfg *config.Config) (cmd []string, resetStyle string, err error) {
	if py := findBundledEsptool(cfg); py != "" {
		if strings.HasSuffix(py, ".py") {
			return []string{pythonBin(), py}, resetStyleFor(py), nil
		}
		// Extensionless bundled esptool (5.x ships a PyInstaller ELF binary).
		return []string{py}, resetStyleFor(py), nil
	}
	if _, err := exec.LookPath("esptool.py"); err == nil {
		// Standalone pip entry point on PATH — run it directly.
		return []string{"esptool.py"}, "underscore", nil
	}
	if _, err := exec.LookPath("esptool"); err == nil {
		return []string{"esptool"}, "hyphen", nil
	}
	py := pythonBin()
	if _, err := exec.LookPath(py); err != nil {
		return nil, "", fmt.Errorf("esptool not found — install Python 3 (pip install esptool) or the ESP32 platform bundle")
	}
	// `python -m esptool`: the pip module. Version unknown; underscore style
	// matches every release up to 4.x, which is what pip installs today.
	return []string{py, "-m", "esptool"}, "underscore", nil
}

func pythonBin() string {
	if _, err := exec.LookPath("python3"); err == nil {
		return "python3"
	}
	return "python"
}

// resetStyleFor inspects the version directory the tool was found in:
// <...>/esptool_py/<version>/<file>. 5.x → hyphenated values, older → underscores.
func resetStyleFor(esptoolPath string) string {
	ver := filepath.Base(filepath.Dir(esptoolPath))
	major := ver
	if i := strings.IndexByte(ver, '.'); i > 0 {
		major = ver[:i]
	}
	if major >= "5" && major[0] == '5' {
		return "hyphen"
	}
	return "underscore"
}

// findBundledEsptool returns the newest esptool shipped by an installed
// platform, or "" when none is present. Both layouts are handled: the
// extensionless PyInstaller binary (esptool_py ≥ 5.x) and the classic
// esptool.py script. Search roots cover Companion's own package store and the
// standard Arduino 1.x/2.x locations, since platforms may be installed in either.
func findBundledEsptool(cfg *config.Config) string {
	var roots []string
	if cfg != nil {
		roots = append(roots, cfg.PackagesDir())
	}
	if home, err := os.UserHomeDir(); err == nil {
		roots = append(roots,
			filepath.Join(home, ".arduino15", "packages"),
			filepath.Join(home, "Library", "Arduino15", "packages"), // macOS
		)
	}
	if dir := os.Getenv("ARDUINO15_DIR"); dir != "" {
		roots = append(roots, dir)
	}

	var best string
	for _, root := range roots {
		for _, name := range []string{"esptool", "esptool.py"} {
			// <root>/<vendor>/tools/esptool_py/<version>/<file>
			matches, _ := filepath.Glob(filepath.Join(root, "*", "tools", "esptool_py", "*", name))
			for _, cand := range matches {
				if best == "" || version.Compare(filepath.Base(filepath.Dir(cand)), filepath.Base(filepath.Dir(best))) > 0 {
					best = cand
				}
			}
		}
	}
	return best
}

// readFlashArgs turns an arduino-cli `flash_args` file — written next to the
// binary by the platform's objcopy hooks — into esptool CLI arguments.
//
// Format (first line flash options, then "<offset> <file>" pairs):
//
//	--flash-mode qio --flash-freq 80m --flash-size 4MB
//	0x1000 bootloader.bin
//	0x8000 partitions.bin
//	0xe000 boot_app0.bin
//	0x10000 sketch.bin
//
// Returns ok=false when the file is absent, empty, or references a missing
// image, so callers fall back to flashing the application image alone.
func readFlashArgs(binPath string) ([]string, bool) {
	dir := filepath.Dir(binPath)
	data, err := os.ReadFile(filepath.Join(dir, "flash_args"))
	if err != nil {
		return nil, false
	}
	lines := strings.Split(strings.ReplaceAll(string(data), "\r\n", "\n"), "\n")
	if len(lines) == 0 {
		return nil, false
	}

	// First non-empty line: esptool flash options (mode / freq / size).
	var args []string
	fields := strings.Fields(lines[0])
	if len(fields) != 6 {
		return nil, false
	}
	seen := make(map[string]bool)
	for i := 0; i < len(fields); i += 2 {
		option := strings.ReplaceAll(fields[i], "-", "_")
		if (option != "__flash_mode" && option != "__flash_freq" && option != "__flash_size") ||
			seen[option] || strings.HasPrefix(fields[i+1], "-") {
			return nil, false
		}
		seen[option] = true
		args = append(args, "--"+strings.TrimPrefix(option, "__"), fields[i+1])
	}

	// Remaining lines: offset + image file, relative to the binary's directory.
	pairs := 0
	for _, line := range lines[1:] {
		fields := strings.Fields(strings.TrimSpace(line))
		if len(fields) != 2 {
			continue
		}
		img := fields[1]
		if !filepath.IsAbs(img) {
			img = filepath.Join(dir, img)
		}
		if _, err := os.Stat(img); err != nil {
			// A partial image set is worse than none: falls back to app-only.
			return nil, false
		}
		args = append(args, fields[0], img)
		pairs++
	}
	if pairs == 0 {
		return nil, false
	}
	return args, true
}

// espChipFromFQBN maps an MCU family + FQBN to an esptool --chip value.
// Empty means "let esptool auto-detect", which is safer than guessing.
func espChipFromFQBN(mcu, fqbn string) string {
	if strings.EqualFold(mcu, "esp8266") {
		return "esp8266"
	}
	f := strings.ToLower(fqbn)
	for _, chip := range []string{"esp32s3", "esp32s2", "esp32c6", "esp32c3", "esp32c2", "esp32h2", "esp32p4"} {
		if strings.Contains(f, chip) {
			return chip
		}
	}
	return ""
}
