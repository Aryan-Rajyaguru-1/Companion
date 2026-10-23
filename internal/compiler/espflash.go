// espflash.go — ESP32 full flash artifact set (Stage 2).
//
// The compiler used to produce only the application image. An ESP chip needs
// four images to boot: second-stage bootloader, partition table, OTA selector
// (boot_app0) and the application. This file reproduces what the esp32
// platform's platform.txt hooks produce during an arduino-cli build:
//
//	bootloader  : elf2image over {sdk}/bin/bootloader_{build.boot}_{freq}.elf
//	              (prebuild.4), unless the sketch ships its own bootloader.bin
//	partitions  : gen_esp32part.py -q partitions.csv → <name>.partitions.bin
//	              (objcopy.partitions.bin), csv from source > variant > platform
//	boot_app0   : copied from tools/partitions/boot_app0.bin (postobjcopy.5)
//	flash_args  : esptool argument manifest consumed by the uploader
//	              (postobjcopy.4) — offsets 0x1000/0x8000/0xe000/0x10000
package compiler

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"github.com/companion-ide/companion-cli/internal/boards"
)

// generateESPFlashArtifacts builds the bootloader/partition/boot_app0 images
// and the flash_args manifest next to the freshly linked application image in
// buildDir. It returns the full artifact list (app image first).
func (c *Compiler) generateESPFlashArtifacts(rb *boards.ResolvedBoard, sdkPath, sketchDir, buildDir, sketchName, appBin string) ([]string, error) {
	artifacts := []string{appBin}

	// ── Bootloader (sketch-shipped wins, mirroring prebuild.4) ──────
	blBin := filepath.Join(buildDir, sketchName+".bootloader.bin")
	if fileExists(filepath.Join(sketchDir, "bootloader.bin")) {
		if err := copyFile(filepath.Join(sketchDir, "bootloader.bin"), blBin); err != nil {
			return nil, fmt.Errorf("copy sketch bootloader: %w", err)
		}
	} else if err := c.buildESPBootloader(rb, sdkPath, buildDir, blBin); err != nil {
		return nil, err
	}
	artifacts = append(artifacts, blBin)

	// ── Partition table (source > variant > platform, prebuild.1-3) ──
	csvPath := filepath.Join(buildDir, "partitions.csv")
	src := firstExisting(
		filepath.Join(sketchDir, "partitions.csv"),
		filepath.Join(rb.PlatformPath, "variants", rb.GetProp("build.variant"), "partitions.csv"),
		filepath.Join(rb.PlatformPath, "tools", "partitions", rb.GetProp("build.partitions")+".csv"),
	)
	if src == "" {
		return nil, fmt.Errorf("partition table not found for %q (looked in sketch, variant and platform tools/partitions)", rb.GetProp("build.partitions"))
	}
	if err := copyFile(src, csvPath); err != nil {
		return nil, fmt.Errorf("copy partitions.csv: %w", err)
	}
	ptBin := filepath.Join(buildDir, sketchName+".partitions.bin")
	if err := c.runTool("gen_esp32part",
		filepath.Join(rb.PlatformPath, "tools", "gen_esp32part.py"),
		[]string{"-q", csvPath, ptBin}, buildDir); err != nil {
		return nil, err
	}
	artifacts = append(artifacts, ptBin)

	// ── OTA selector (boot_app0.bin, postobjcopy.5) ─────────────────
	bootApp0 := filepath.Join(buildDir, "boot_app0.bin")
	if err := copyFile(filepath.Join(rb.PlatformPath, "tools", "partitions", "boot_app0.bin"), bootApp0); err != nil {
		return nil, fmt.Errorf("copy boot_app0.bin: %w", err)
	}
	artifacts = append(artifacts, bootApp0)

	// ── flash_args manifest (postobjcopy.4) ─────────────────────────
	flashArgs := filepath.Join(buildDir, "flash_args")
	manifest := espFlashArgsManifest(rb, sketchName)
	if err := os.WriteFile(flashArgs, []byte(manifest), 0o644); err != nil {
		return nil, fmt.Errorf("write flash_args: %w", err)
	}
	// Exported with the images so the uploader can find the full set next to
	// the exported binary.
	artifacts = append(artifacts, flashArgs)
	return artifacts, nil
}

// espFlashArgsManifest reproduces the platform's postobjcopy.4 hook output:
// one options line, then "<offset> <file>" pairs resolved relative to the
// build directory.
func espFlashArgsManifest(rb *boards.ResolvedBoard, sketchName string) string {
	mode := rb.GetProp("build.flash_mode")
	if mode == "" {
		mode = "dio"
	}
	size := rb.GetProp("build.flash_size")
	if size == "" {
		size = "4MB"
	}
	freq := espImageFreq(rb)
	blAddr := rb.GetProp("build.bootloader_addr")
	if blAddr == "" {
		blAddr = "0x1000"
	}
	return strings.Join([]string{
		fmt.Sprintf("--flash-mode %s --flash-freq %s --flash-size %s", mode, freq, size),
		fmt.Sprintf("%s %s.bootloader.bin", blAddr, sketchName),
		"0x8000 " + sketchName + ".partitions.bin",
		"0xe000 boot_app0.bin",
		"0x10000 " + sketchName + ".bin",
	}, "\n") + "\n"
}

// firstExisting returns the first path that exists on disk, or "".
func firstExisting(paths ...string) string {
	for _, p := range paths {
		if p != "" {
			if _, err := os.Stat(p); err == nil {
				return p
			}
		}
	}
	return ""
}
