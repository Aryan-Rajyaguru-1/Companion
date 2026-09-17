// esptools.go — process helpers for the ESP flash artifact pipeline.
package compiler

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"

	"github.com/companion-ide/companion-cli/internal/boards"
)

// buildESPBootloader converts the SDK's prebuilt bootloader ELF into a
// flashable image with esptool elf2image (platform prebuild.4).
func (c *Compiler) buildESPBootloader(rb *boards.ResolvedBoard, sdkPath, buildDir, outPath string) error {
	boot := rb.GetProp("build.boot")
	if boot == "" {
		boot = "dio"
	}
	freq := rb.GetProp("build.boot_freq")
	if freq == "" {
		freq = espImageFreq(rb)
	}
	sdkBin := filepath.Join(sdkPath, "bin")
	elfPath := firstExisting(filepath.Join(sdkBin, fmt.Sprintf("bootloader_%s_%s.elf", boot, freq)))
	if elfPath == "" {
		return fmt.Errorf("prebuilt bootloader ELF not found under %s — reinstall the ESP32 platform", sdkBin)
	}

	args := []string{"--chip", strings.ToLower(rb.GetProp("build.mcu")), "elf2image",
		"--flash_mode", rb.GetProp("build.flash_mode"),
		"--flash_freq", espImageFreq(rb),
		"--flash_size", rb.GetProp("build.flash_size"),
		"-o", outPath, elfPath}
	if err := c.runEsptool(rb, args); err != nil {
		return fmt.Errorf("bootloader elf2image: %w", err)
	}
	if !fileExists(outPath) {
		return fmt.Errorf("bootloader image not produced at %s", outPath)
	}
	c.logf("  [debug] bootloader image: %s", outPath)
	return nil
}

// runEsptool executes esptool with a version-appropriate invocation. The 5.x
// platform bundle ships an extensionless PyInstaller binary (executed
// directly); older bundles and pip installs provide esptool.py or the
// `esptool` python module.
func (c *Compiler) runEsptool(rb *boards.ResolvedBoard, args []string) error {
	esptoolRoot := filepath.Join(rb.ToolsDir, "esptool_py")
	bundled := latestFileUnder(esptoolRoot, "esptool")
	if bundled == "" {
		bundled = latestFileUnder(esptoolRoot, "esptool.py")
	}

	var cmd *exec.Cmd
	switch {
	case bundled != "" && strings.HasSuffix(bundled, ".py"):
		cmd = exec.CommandContext(c.ctx, pythonBinName(), append([]string{bundled}, args...)...)
	case bundled != "":
		cmd = exec.CommandContext(c.ctx, bundled, args...)
	default:
		cmd = exec.CommandContext(c.ctx, pythonBinName(), append([]string{"-m", "esptool"}, args...)...)
	}
	out, err := cmd.CombinedOutput()
	if err != nil {
		return fmt.Errorf("%s\n%s", err, out)
	}
	return nil
}

func pythonBinName() string {
	if _, err := exec.LookPath("python3"); err == nil {
		return "python3"
	}
	return "python"
}

// runTool runs a platform python script (e.g. gen_esp32part.py), cwd=dir.
func (c *Compiler) runTool(name, script string, args []string, dir string) error {
	if _, err := os.Stat(script); err != nil {
		return fmt.Errorf("%s not found at %s", name, script)
	}
	cmd := exec.CommandContext(c.ctx, pythonBinName(), append([]string{script}, args...)...)
	cmd.Dir = dir
	if out, err := cmd.CombinedOutput(); err != nil {
		return fmt.Errorf("%s: %s\n%s", name, err, out)
	}
	return nil
}

// espImageFreq returns the flash frequency in esptool notation ("40m", "80m").
// build.img_freq aliases build.flash_freq on this platform.
func espImageFreq(rb *boards.ResolvedBoard) string {
	if f := rb.GetProp("build.img_freq"); f != "" {
		return f
	}
	if f := rb.GetProp("build.flash_freq"); f != "" {
		return strings.TrimSuffix(f, "L")
	}
	return "40m"
}

// exportArtifacts copies each produced artifact into exportDir (base names
// preserved, duplicates skipped). Only files this build created are touched —
// nothing pre-existing in the export directory is deleted.
func exportArtifacts(artifacts []string, exportDir string) error {
	if err := os.MkdirAll(exportDir, 0o755); err != nil {
		return err
	}
	seen := make(map[string]bool)
	for _, src := range artifacts {
		if src == "" {
			continue
		}
		dst := filepath.Join(exportDir, filepath.Base(src))
		if seen[dst] {
			continue
		}
		seen[dst] = true
		if filepath.Clean(src) == filepath.Clean(dst) {
			continue
		}
		if err := copyFile(src, dst); err != nil {
			return fmt.Errorf("copy %s: %w", filepath.Base(src), err)
		}
	}
	return nil
}
