package compiler

import (
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/companion-ide/companion-cli/internal/boards"
)

// TestUnitKeyIgnoresBuildDir proves the per-file cache key is invariant across
// build directories: only SDK-provided flags/names are hashed, so a sketch TU
// reuses its cached object across warm rebuilds (each gets a fresh temp dir,
// companion_build_<hash>_<pid>_<rand>), instead of recompiling every time.
func TestUnitKeyIgnoresBuildDir(t *testing.T) {
	// Two distinct build dirs mimicking the real temp-dir scheme so the
	// normalization logic behaves exactly as in production.
	dirA := filepath.Join(os.TempDir(), "companion_build_testA_1_abcd")
	dirB := filepath.Join(os.TempDir(), "companion_build_testB_9_efgh")
	// One fixed source (outside both builds) — in production the sketch CPP is
	// preprocessed into the build dir, but the *identity* hashed is its content.
	srcDir := t.TempDir()
	src := filepath.Join(srcDir, "blink.cpp")
	if err := os.WriteFile(src, []byte("void setup(){} void loop(){}\n"), 0o644); err != nil {
		t.Fatal(err)
	}
	argsFor := func(build string) []string {
		return []string{"-c", "-Os", "-I", build, "-I", filepath.Join(build, "sketch"),
			"-o", filepath.Join(build, "sketch", "blink.cpp.o"), src}
	}
	c := &Compiler{}
	keyA, err := c.unitKey(src, argsFor(dirA), "/fake/xtensa-g++")
	if err != nil {
		t.Fatal(err)
	}
	keyB, err := c.unitKey(src, argsFor(dirB), "/fake/xtensa-g++")
	if err != nil {
		t.Fatal(err)
	}
	if keyA != keyB {
		t.Fatalf("cache key changed across build dirs:\nA=%s\nB=%s", keyA, keyB)
	}
}

// TestNormalizeFlagsCollapsesNestedDirs pins the longest-first invariant:
// "<build>/sketch" collapses ENTIRELY — never leaving "…/sketch" residue.
func TestNormalizeFlagsCollapsesNestedDirs(t *testing.T) {
	build := "/tmp/companion_build_abc123_99_dead"
	out := NormalizeFlags([]string{
		"-I", build,
		"-I", filepath.Join(build, "sketch"),
		"-o", filepath.Join(build, "sketch", "blink.cpp.o"),
	}, build+"/sketch", build)
	for _, f := range out {
		if strings.Contains(f, "companion_build") || strings.Contains(f, "/sketch") {
			t.Fatalf("un-normalized residue in %q (full: %v)", f, out)
		}
	}
}

// TestCoreCacheKeyStableAcrossBuildDirs pins the core-archive key invariance
// discovered in warm-build validation: the preprocessor flags embed the
// random per-run temp dir, and NormalizeFlags with prefix-only volatile dirs
// left the random suffix alive in the key — producing a NEW core key every
// invocation and recompiling all 60 core TUs every time. With bf.buildDir in
// the volatile list, the key must be byte-identical across build dirs.
func TestCoreCacheKeyStableAcrossBuildDirs(t *testing.T) {
	// Minimal platform skeleton so the core walk has something to hash.
	plat := t.TempDir()
	write := func(p, content string) {
		if err := os.MkdirAll(filepath.Dir(p), 0o755); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(p, []byte(content), 0o644); err != nil {
			t.Fatal(err)
		}
	}
	write(filepath.Join(plat, "cores", "esp32", "main.cpp"), "int main(){}")
	write(filepath.Join(plat, "variants", "esp32", "pins_arduino.h"), "#pragma once")

	// Two distinct random-suffix build dirs, as produced per invocation.
	dirA := filepath.Join(os.TempDir(), "companion_build_a1b2c3_111_feed")
	dirB := filepath.Join(os.TempDir(), "companion_build_a1b2c3_222_bead")

	c := &Compiler{}
	rb := &boards.ResolvedBoard{
		Architecture: "esp32",
		PlatformPath: plat,
		BoardProps:   map[string]string{"build.core": "esp32", "build.variant": "esp32"},
	}
	tc := &Toolchain{GCC: "/fake/xtensa-esp32s3-elf-gcc"}
	bfFor := func(build string) *BuildFlags {
		return &BuildFlags{
			buildDir: build,
			preprocessorFlags: []string{
				"-I", build,
				"-I", filepath.Join(build, "core"),
				"-I", filepath.Join(build, "sketch"),
				"-DHAVE_CONFIG_H",
			},
		}
	}
	keyA, err := c.coreCacheKey(rb, tc, bfFor(dirA))
	if err != nil {
		t.Fatal(err)
	}
	keyB, err := c.coreCacheKey(rb, tc, bfFor(dirB))
	if err != nil {
		t.Fatal(err)
	}
	if keyA != keyB {
		t.Fatalf("core cache key changed across build dirs:\nA=%s\nB=%s", keyA, keyB)
	}
}

// TestUnitKeySeesSourceChanges sanity-proves the key moves when the source or
// flags change.
func TestUnitKeySeesSourceChanges(t *testing.T) {
	dir := t.TempDir()
	src := filepath.Join(dir, "blink.cpp")
	if err := os.WriteFile(src, []byte("void setup(){} void loop(){}\n"), 0o644); err != nil {
		t.Fatal(err)
	}
	c := &Compiler{}
	args := []string{"-c", "-Os", "-o", filepath.Join(dir, "blink.cpp.o"), src}
	base, err := c.unitKey(src, args, "/fake/xtensa-g++")
	if err != nil {
		t.Fatal(err)
	}
	// Source edit → new key.
	if err := os.WriteFile(src, []byte("void setup(){} void loop(){ delay(1); }\n"), 0o644); err != nil {
		t.Fatal(err)
	}
	edited, err := c.unitKey(src, args, "/fake/xtensa-g++")
	if err != nil {
		t.Fatal(err)
	}
	if edited == base {
		t.Fatal("cache key did not change after editing the source")
	}
	// Flag change → new key.
	flagged, err := c.unitKey(src, append(args, "-O2"), "/fake/xtensa-g++")
	if err != nil {
		t.Fatal(err)
	}
	if flagged == edited {
		t.Fatal("cache key did not change after adding a flag")
	}
}