// Package compiler implements the Companion IDE build pipeline.
// Inspired by arduino-cli's internal/arduino/builder/builder.go — written from scratch.
//
// Build stages (mirrors arduino-cli's 10-stage pipeline):
//  1. ResolvePaths       — locate toolchain, core, and libraries
//  2. PreprocessSketch   — merge .ino files into a single .cpp
//  3. BuildCore          — compile core .c/.cpp → libcore.a (cached)
//  4. ResolveLibraries   — scan #include directives → library paths
//  5. BuildLibraries     — compile library sources
//  6. BuildSketch        — compile sketch .cpp/.c/.S files
//  7. Link               — link .o files + libcore.a → .elf
//  8. ExtractBinary      — objcopy .elf → .bin / .hex
//  9. PostProcess        — report binary size
//
// 10. ExportBinary       — copy binary to sketch directory
package compiler

import (
	"context"
	"crypto/md5"
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"io/fs"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"runtime"
	"sort"
	"strconv"
	"strings"
	"time"

	"github.com/companion-ide/companion-cli/internal/boards"
	"github.com/companion-ide/companion-cli/internal/config"
	"github.com/companion-ide/companion-cli/internal/plugins"
	version "github.com/companion-ide/companion-cli/internal/version"
)

// ── Options ───────────────────────────────────────────────────────

// Options controls compilation behaviour.
type Options struct {
	SketchDir    string
	FQBN         string
	BuildDir     string // empty = temp dir
	Warnings     string // none | default | more | all
	Verbose      bool
	ExportBinary bool
	LibraryDirs  []string // extra library search paths

	// CaptureCompileCommands records every translation unit's exact compile
	// command and writes a clangd-compatible compile_commands.json into the
	// build directory (closes the Arduino-cli #849 feature gap).
	CaptureCompileCommands bool
}

// Result is returned from Build().
type Result struct {
	BinaryPath string // path to .bin or .hex
	ELFPath    string // path to .elf
	BuildDir   string
	Duration   time.Duration

	// CompileCommandsPath is set when Options.CaptureCompileCommands was on.
	CompileCommandsPath string
}

// CompileCommand is one entry of a compile_commands.json export.
type CompileCommand struct {
	Directory string `json:"directory"`
	Command   string `json:"command"`
	File      string `json:"file"`
}

// ── Compiler ──────────────────────────────────────────────────────

type Compiler struct {
	cfg      *config.Config
	boards   *boards.Manager
	onOutput func(string)

	// cache is the content-addressed object cache (P2). Nil = caching off.
	cache *BuildCache

	// plugins runs pre/post-compile hooks (P5 plugin system).
	plugins *plugins.Registry

	// resolvedToolchain is set at the start of each build so cache-key
	// computation can fold toolchain-binary identity into the key.
	resolvedToolchain *Toolchain

	// curFQBN is the FQBN of the build in flight (used for per-file cache keys).
	curFQBN string

	// Compile-commands capture state (ccDir non-empty = capturing).
	ccDir string
	cc    []CompileCommand

	// ctx is bound to toolchain subprocesses via exec.CommandContext so that
	// daemon-driven cancels actually kill running gcc/ld processes instead of
	// merely abandoning their output.
	ctx context.Context
}

// Context returns the compiler's cancellation context.
func (c *Compiler) Context() context.Context {
	if c.ctx == nil {
		return context.Background()
	}
	return c.ctx
}

func New(cfg *config.Config, bm *boards.Manager, onOutput func(string)) *Compiler {
	return &Compiler{cfg: cfg, boards: bm, onOutput: onOutput, ctx: context.Background()}
}

// NewWithContext creates a Compiler whose toolchain subprocesses are killed
// when ctx is cancelled (daemon streaming compiles / compile.cancel).
func NewWithContext(ctx context.Context, cfg *config.Config, bm *boards.Manager, onOutput func(string)) *Compiler {
	return &Compiler{cfg: cfg, boards: bm, onOutput: onOutput, ctx: ctx}
}

// SetCache attaches a build cache. Passing nil disables caching.
func (c *Compiler) SetCache(bc *BuildCache) { c.cache = bc }

// SetPlugins attaches the plugin registry whose Pre/PostCompile hooks run
// around each build. Passing nil disables plugin hooks.
func (c *Compiler) SetPlugins(r *plugins.Registry) { c.plugins = r }

// runPreCompile invokes every registered PreCompile hook; the first error
// aborts the build (a plugin that returns an error says "do not compile").
func (c *Compiler) runPreCompile(opts Options) error {
	if c.plugins == nil {
		return nil
	}
	return c.plugins.RunPreCompile(c.ctx, plugins.CompileHookOptions{
		SketchDir: opts.SketchDir,
		FQBN:      opts.FQBN,
		BuildDir:  opts.BuildDir,
		Verbose:   opts.Verbose,
	})
}

// runPostCompile invokes every registered PostCompile hook with the produced
// binary path. Errors are logged but never fail a successful build.
func (c *Compiler) runPostCompile(opts Options, buildDir, binaryPath string) {
	if c.plugins == nil {
		return
	}
	if err := c.plugins.RunPostCompile(c.ctx, plugins.CompileHookOptions{
		SketchDir: opts.SketchDir,
		FQBN:      opts.FQBN,
		BuildDir:  buildDir,
		Verbose:   opts.Verbose,
	}, binaryPath); err != nil {
		c.logf("  [debug] post-compile plugin: %v", err)
	}
}

// cacheOrDefault returns the attached cache, or lazily builds one from the
// config default (cfg.Cache.Enabled honoured) so CLI paths get caching for
// free without every caller wiring it explicitly.
func (c *Compiler) cacheOrDefault() *BuildCache {
	if c.cache != nil {
		return c.cache
	}
	if c.cfg == nil || !c.cfg.Cache.Enabled {
		return nil
	}
	bc, err := NewBuildCache(DefaultCacheDir(c.cfg.Directories.Data))
	if err != nil {
		c.logf("  [debug] build cache unavailable: %v", err)
		return nil
	}
	c.cache = bc
	return c.cache
}

func (c *Compiler) log(msg string) {
	if c.onOutput != nil {
		c.onOutput(msg)
	}
}

func (c *Compiler) logf(format string, args ...interface{}) {
	c.log(fmt.Sprintf(format, args...))
}

// Build runs the full compilation pipeline and returns the binary path.
func (c *Compiler) Build(opts Options) (*Result, error) {
	return c.buildCustom(opts, time.Now())
}

// buildCustom runs the companion-cli custom build pipeline
func (c *Compiler) buildCustom(opts Options, start time.Time) (res *Result, err error) {
	var resultCCPath string
	defer func() {
		if res != nil && resultCCPath != "" {
			res.CompileCommandsPath = resultCCPath
		}
	}()

	// ── Stage 1: Resolve paths ────────────────────────────────
	c.log("» Verifying sketch…")
	c.log("")
	c.log("» Resolving board and toolchain…")

	if err := c.runPreCompile(opts); err != nil {
		return nil, fmt.Errorf("pre-compile plugin: %w", err)
	}

	rb, err := c.boards.ResolveFQBN(opts.FQBN)
	if err != nil {
		return nil, err
	}

	tc, err := c.resolveToolchain(rb)
	if err != nil {
		return nil, fmt.Errorf("toolchain: %w", err)
	}
	c.resolvedToolchain = tc

	c.logf("  Board:    %s", rb.GetProp("name"))
	c.logf("  Core:     %s", rb.GetProp("build.core"))
	c.logf("  MCU:      %s", rb.GetProp("build.mcu"))

	// ── Stage 2: Setup build directory ───────────────────────
	buildDir := opts.BuildDir
	if buildDir == "" {
		fqbnHash := fmt.Sprintf("%x", md5.Sum([]byte(opts.FQBN)))[:8]
		// Unique per invocation (pid + random): two concurrent compiles for
		// the same board must not share a temp dir — they would corrupt each
		// other's libcore.a (ar: file truncated). The persistent object/core
		// cache still provides warm rebuilds; only the disposable temp dir
		// changes.
		buildDir = filepath.Join(os.TempDir(),
			fmt.Sprintf("companion_build_%s_%d_%s", fqbnHash, os.Getpid(), randHex(4)))
	}
	if err := os.MkdirAll(buildDir, 0o755); err != nil {
		return nil, fmt.Errorf("build dir: %w", err)
	}
	coreDir := filepath.Join(buildDir, "core")
	sketchDir2 := filepath.Join(buildDir, "sketch")
	libsDir := filepath.Join(buildDir, "libraries")
	for _, d := range []string{coreDir, sketchDir2, libsDir} {
		os.MkdirAll(d, 0o755)
	}

	// Build flags from board properties
	bf := c.buildFlags(rb, tc, opts)
	bf.buildDir = buildDir

	// Compile-commands capture: activation + per-build state reset.
	if opts.CaptureCompileCommands {
		c.ccDir = buildDir
		c.cc = nil
	} else {
		c.ccDir = ""
		c.cc = nil
	}

	c.logf("  [debug] resolved sdkPath=%s", bf.sdkPath)

	// ── Prebuild: generate sdkconfig.h from Kconfig sdkconfig ─────────────
	// For ESP32 Arduino 3.x the sdk root contains a "sdkconfig" Kconfig output
	// file. We parse it and emit a proper C header so all IDF component headers
	// that do  #include "sdkconfig.h"  get the real CONFIG_* values, including
	// CONFIG_FREERTOS_NUMBER_OF_CORES which FreeRTOS.h requires via
	// FreeRTOSConfig.h.
	if bf.sdkPath != "" {
		if err := c.generateSDKConfig(bf.sdkPath, buildDir, rb.GetProp("build.mcu")); err != nil {
			// Non-fatal — log and continue; compilation may still succeed.
			c.logf("  [warn] sdkconfig generation: %v", err)
		}
	}

	// ── Stage 3: Preprocess sketch ────────────────────────────
	c.log("» Preprocessing sketch…")
	sketchCPP, err := c.preprocessSketch(opts.SketchDir, sketchDir2)
	if err != nil {
		return nil, fmt.Errorf("preprocess: %w", err)
	}

	// ── Stage 4: Build core (content-addressed cache) ─────────
	coreLib := filepath.Join(coreDir, "libcore.a")
	cache := c.cacheOrDefault()
	var coreKey string
	if cache != nil {
		// Seed the base flag list (forFile is pure computation) so the key
		// reflects the actual compile flags for this board/build dir.
		bf.preprocessorFlags = bf.forFile(filepath.Join(coreDir, "core.cpp"), "", true, tc)
		coreKey, err = c.coreCacheKey(rb, tc, bf)
		if err != nil {
			// A failed key must never block a build — compile without cache.
			c.logf("  [debug] core cache key: %v", err)
			cache = nil
		}
	}

	// Warm core: reuse the cached archive AND, when capture is on, merge the
	// core's previously captured compile commands so compile_commands.json
	// stays complete without re-walking the core.
	if cache != nil && cache.GetCore(coreKey) != "" {
		c.log("» Core: using cached libcore.a (content-verified)")
		if copied := copyFile(cache.GetCore(coreKey), coreLib); copied != nil {
			// Copy failed (disk?) — fall through and rebuild.
			c.logf("  [debug] core cache copy failed: %v", copied)
			c.log("» Compiling core…")
			if err := c.buildCore(rb, tc, bf, coreDir, coreLib); err != nil {
				return nil, fmt.Errorf("core: %w", err)
			}
			cache.PutCore(coreKey, coreLib)
			if opts.CaptureCompileCommands {
				cache.PutCoreTUs(coreKey, snapshotCC(c))
			}
		} else if opts.CaptureCompileCommands {
			if tus := cache.GetCoreTUs(coreKey); tus != nil {
				mergeCC(c, tus)
			}
		}
	} else {
		c.log("» Compiling core…")
		if err := c.buildCore(rb, tc, bf, coreDir, coreLib); err != nil {
			return nil, fmt.Errorf("core: %w", err)
		}
		// Store the freshly built core in the cache (best-effort).
		if cache != nil {
			if _, putErr := cache.PutCore(coreKey, coreLib); putErr != nil {
				c.logf("  [debug] core cache put: %v", putErr)
			}
			if opts.CaptureCompileCommands {
				if err := cache.PutCoreTUs(coreKey, snapshotCC(c)); err != nil {
					c.logf("  [debug] core TU cache put: %v", err)
				}
			}
		}
	}

	// ── Stage 5: Resolve libraries ────────────────────────────
	c.log("» Resolving libraries…")
	libPaths, err := c.resolveLibraries(sketchCPP, opts.SketchDir, opts.LibraryDirs, rb)
	if err != nil {
		return nil, fmt.Errorf("libraries: %w", err)
	}

	// ── Stage 6: Build libraries ──────────────────────────────
	var libObjs []string
	if len(libPaths) > 0 {
		c.logf("» Compiling %d libraries…", len(libPaths))
		objs, err := c.buildLibraries(libPaths, tc, bf, libsDir)
		if err != nil {
			return nil, fmt.Errorf("libraries compile: %w", err)
		}
		libObjs = objs
	}

	// ── Stage 7: Build sketch ─────────────────────────────────
	c.log("» Compiling sketch…")
	sketchObjs, err := c.buildSketch(opts.SketchDir, sketchCPP, tc, bf, sketchDir2, libPaths)
	if err != nil {
		return nil, fmt.Errorf("sketch compile: %w", err)
	}

	// ── Stage 7.5: Export compile_commands.json ───────────────
	if opts.CaptureCompileCommands {
		ccPath, ccErr := c.writeCompileCommands(buildDir)
		if ccErr != nil {
			c.logf("  [warn] compile_commands export: %v", ccErr)
		} else {
			resultCCPath = ccPath
			c.logf("» Compile commands: %s", ccPath)
		}
	}

	// ── Stage 8: Link ─────────────────────────────────────────
	c.log("» Linking…")
	sketchName := filepath.Base(opts.SketchDir)
	elfPath := filepath.Join(buildDir, sketchName+".elf")

	allObjs := append(sketchObjs, libObjs...)
	if err := c.link(rb, tc, bf, allObjs, coreLib, elfPath); err != nil {
		return nil, fmt.Errorf("link: %w", err)
	}

	// ── Stage 9: Extract binary ───────────────────────────────
	c.log("» Extracting binary…")
	binaryPath, err := c.extractBinary(rb, tc, elfPath, buildDir, sketchName)
	if err != nil {
		return nil, fmt.Errorf("objcopy: %w", err)
	}

	// ── Stage 9.5: Post-compile plugin hooks ──────────────────
	c.runPostCompile(opts, buildDir, binaryPath)

	// ── Stage 10: Report size + export ───────────────────────
	c.reportSize(rb, tc, elfPath)

	if opts.ExportBinary {
		exportPath := filepath.Join(opts.SketchDir, "build",
			strings.ReplaceAll(opts.FQBN, ":", "."),
			filepath.Base(binaryPath))
		os.MkdirAll(filepath.Dir(exportPath), 0o755)
		copyFile(binaryPath, exportPath)
		c.logf("» Binary exported: %s", exportPath)
		binaryPath = exportPath

		// Keep the IntelliSense database next to the exported binary so the
		// path is stable (unlike temp build dirs).
		if resultCCPath != "" {
			ccCopy := filepath.Join(filepath.Dir(exportPath), "compile_commands.json")
			if err := copyFile(resultCCPath, ccCopy); err == nil {
				c.logf("» Compile commands: %s", ccCopy)
			}
		}
	}

	dur := time.Since(start)
	c.logf("\n✓ Compilation complete in %.1fs", dur.Seconds())

	return &Result{
		BinaryPath:          binaryPath,
		ELFPath:             elfPath,
		BuildDir:            buildDir,
		Duration:            dur,
		CompileCommandsPath: resultCCPath,
	}, nil
}

// ── generateSDKConfig ─────────────────────────────────────────────
// Reads the Kconfig-format "sdkconfig" file from sdkRoot and writes a
// proper C header to buildDir/sdkconfig.h.
//
// Root cause this fixes:
//
//	FreeRTOS.h (line 139) requires configNUMBER_OF_CORES to be defined
//	in FreeRTOSConfig.h.  FreeRTOSConfig.h in turn does:
//	  #define configNUMBER_OF_CORES  CONFIG_FREERTOS_NUMBER_OF_CORES
//	so CONFIG_FREERTOS_NUMBER_OF_CORES must be in sdkconfig.h before
//	FreeRTOS.h is included.  The previous stub generator only converted
//	lines that start with "CONFIG_" or "CONFIG_LIBC_NEWLIB" — it silently
//	skipped comment-annotated disabled keys and produced a header that was
//	missing most FreeRTOS config macros, causing the #error cascade.
//
// The new generator also synthesises safe defaults for mandatory FreeRTOS
// macros in case they are absent from the sdkconfig file (e.g. when the
// sdkconfig was generated for a different memory variant).
func (c *Compiler) generateSDKConfig(sdkRoot, buildDir, target string) error {
	dst := filepath.Join(buildDir, "sdkconfig.h")

	// Candidate sdkconfig locations (ordered by preference).
	// arduino-esp32 3.x puts the file directly in the sdk root.
	candidates := []string{
		filepath.Join(sdkRoot, "sdkconfig"),
		filepath.Join(sdkRoot, "qio_qspi", "sdkconfig"),
		filepath.Join(sdkRoot, "dio_qspi", "sdkconfig"),
	}

	var raw []byte
	for _, src := range candidates {
		if info, err := os.Stat(src); err == nil && !info.IsDir() {
			data, err := os.ReadFile(src)
			if err != nil {
				return fmt.Errorf("read sdkconfig: %w", err)
			}
			raw = data
			break
		}
	}

	// defined tracks every CONFIG_* key we emit so we can fill in defaults
	// for mandatory FreeRTOS macros that are absent.
	defined := make(map[string]bool)
	var lines []string
	lines = append(lines, "#ifndef SDKCONFIG_H")
	lines = append(lines, "#define SDKCONFIG_H")

	if len(raw) > 0 {
		for _, ln := range strings.Split(string(raw), "\n") {
			ln = strings.TrimSpace(ln)
			if ln == "" || strings.HasPrefix(ln, "#") {
				// Kconfig comment: "# CONFIG_FOO is not set" → the option is
				// DISABLED. IDF semantics: emit `/* #undef CONFIG_FOO */` so
				// the macro stays UNDEFINED and `#ifdef CONFIG_FOO` is FALSE.
				// We must NOT define it as 0 — a "#define X 0" still satisfies
				// #ifdef and forces the *enabled* code path, which broke lwip's
				// netdb.h (esp_getaddrinfo branch chosen, impl not compiled in).
				const notSet = "# CONFIG_"
				if strings.HasPrefix(ln, notSet) {
					rest := strings.TrimPrefix(ln, notSet)
					rest = strings.TrimSuffix(rest, " is not set")
					rest = strings.TrimSpace(rest)
					if rest != "" && !strings.Contains(rest, " ") && !defined["CONFIG_"+rest] {
						lines = append(lines, "/* #undef CONFIG_"+rest+" */")
						// Deliberately not recorded in `defined`: the
						// synthesized defaults still need to supply a real
						// value for mandatory keys (FreeRTOS array sizes…).
					}
				}
				continue
			}
			// Normal line: CONFIG_FOO=value
			if !strings.HasPrefix(ln, "CONFIG_") {
				continue
			}
			parts := strings.SplitN(ln, "=", 2)
			if len(parts) != 2 {
				continue
			}
			key := strings.TrimSpace(parts[0])
			val := strings.TrimSpace(parts[1])

			// Kconfig disabled boolean `...=n` — same as "is not set": the
			// option must stay undefined (see the comment handler above).
			if val == "n" || val == "N" {
				if !defined[key] {
					lines = append(lines, "/* #undef "+key+" */")
				}
				continue
			}

			// Kconfig boolean "y" → 1 for C preprocessor
			if val == "y" || val == "Y" {
				val = "1"
			}
			// Strip surrounding double-quotes from string values
			// (e.g. CONFIG_IDF_VER="v5.5.4") and re-quote them properly.
			// We keep them quoted so string macros work in C code.
			if len(val) >= 2 && val[0] == '"' && val[len(val)-1] == '"' {
				inner := val[1 : len(val)-1]
				// Escape any backslashes/quotes already in the inner string.
				inner = strings.ReplaceAll(inner, `\`, `\\`)
				inner = strings.ReplaceAll(inner, `"`, `\"`)
				val = `"` + inner + `"`
			}

			if !defined[key] {
				defined[key] = true
				lines = append(lines, fmt.Sprintf("#define %s %s", key, val))
			}
		}
	}

	// ── Synthesised CONFIG_* defaults ────────────────────────────────────
	//
	// When no sdkconfig file is present (the common case for pre-built
	// arduino-esp32 3.x packages), every CONFIG_* symbol used by IDF headers
	// as a compile-time array size or static-assert operand must be given a
	// safe default.  Missing values produce "not declared in this scope"
	// errors because C uses the symbol as an integer, not just an #ifdef guard.
	//
	// Sources for these values:
	//   • arduino-esp32 3.3.x sdkconfig.h reference build
	//   • IDF v5.5 Kconfig defaults for ESP32 target
	//   • esp_image_format.h / bootloader_support requirements
	type kv struct{ k, v string }
	allDefaults := []kv{
		// ── FreeRTOS (mandatory — FreeRTOS.h #error checks) ──────────────
		{"CONFIG_FREERTOS_NUMBER_OF_CORES", "2"}, // dual-core ESP32
		{"CONFIG_FREERTOS_HZ", "1000"},
		{"CONFIG_FREERTOS_MAX_PRIORITIES", "25"},
		{"CONFIG_FREERTOS_MINIMAL_STACK_SIZE", "768"},
		{"CONFIG_FREERTOS_IDLE_TASK_STACKSIZE", "1536"},
		{"CONFIG_FREERTOS_QUEUE_REGISTRY_SIZE", "0"},
		{"CONFIG_FREERTOS_USE_IDLE_HOOK", "0"},
		{"CONFIG_FREERTOS_USE_TICK_HOOK", "0"},
		{"CONFIG_FREERTOS_CHECK_STACKOVERFLOW", "2"},
		{"CONFIG_FREERTOS_THREAD_LOCAL_STORAGE_POINTERS", "1"},
		{"CONFIG_FREERTOS_ASSERT_ON_UNTESTED_FUNCTION", "1"},
		{"CONFIG_FREERTOS_TASK_NOTIFICATION_ARRAY_ENTRIES", "1"},

		// ── Bootloader / RTC retain memory ───────────────────────────────
		// esp_image_format.h uses CONFIG_BOOTLOADER_CUSTOM_RESERVE_RTC_SIZE
		// as an array size inside rtc_retain_mem_t and in ESP_STATIC_ASSERT.
		// Must be 0 (disabled) or a multiple of 4.
		{"CONFIG_BOOTLOADER_CUSTOM_RESERVE_RTC", "0"},
		{"CONFIG_BOOTLOADER_CUSTOM_RESERVE_RTC_SIZE", "0"},
		// Other bootloader keys referenced by bootloader_support headers
		{"CONFIG_BOOTLOADER_RESERVE_RTC_SIZE", "0"},
		{"CONFIG_BOOTLOADER_WDT_ENABLE", "1"},
		{"CONFIG_BOOTLOADER_WDT_TIME_MS", "9000"},
		{"CONFIG_BOOTLOADER_LOG_LEVEL", "1"},
		{"CONFIG_BOOTLOADER_VDDSDIO_BOOST_1_9V", "1"},
		{"CONFIG_BOOTLOADER_FLASH_XMC_SUPPORT", "1"},

		// ── SOC / hardware ────────────────────────────────────────────────
		{"CONFIG_SOC_CACHE_WRITEBACK_SUPPORTED", "0"},
		{"CONFIG_SOC_MODEM_CLOCK_IS_INDEPENDENT", "0"},
		{"CONFIG_SOC_PM_SUPPORT_PMU_MODEM_STATE", "0"},
		{"CONFIG_SOC_XTAL_FREQ_MHZ_DEFAULT", "40"},

		// ── MMU / flash ───────────────────────────────────────────────────
		{"CONFIG_MMU_PAGE_SIZE", "0x10000"},
		{"CONFIG_XTAL_FREQ", "40"},
		{"CONFIG_ESPTOOLPY_FLASHSIZE_DETECT", "1"},
		{"CONFIG_ESPTOOLPY_FLASHSIZE", "\"4MB\""},

		// ── Partition table ───────────────────────────────────────────────
		{"CONFIG_PARTITION_TABLE_SINGLE_APP", "1"},
		{"CONFIG_PARTITION_TABLE_OFFSET", "0x8000"},

		// ── App / OTA ─────────────────────────────────────────────────────
		{"CONFIG_APP_BUILD_USE_FLASH_SECTIONS", "1"},
		{"CONFIG_APP_COMPILE_TIME_DATE", "1"},
		{"CONFIG_APP_EXCLUDE_PROJECT_VER_VAR", "0"},
		{"CONFIG_APP_EXCLUDE_PROJECT_NAME_VAR", "0"},
		{"CONFIG_APP_PROJECT_VER_FROM_CONFIG", "0"},
		{"CONFIG_APP_RETRIEVE_LEN_ELF_SHA", "16"},

		// ── ESP-IDF version string (now generated per-target above) ───────

		// ── Log level ─────────────────────────────────────────────────────
		{"CONFIG_LOG_DEFAULT_LEVEL", "3"},
		{"CONFIG_LOG_MAXIMUM_LEVEL", "5"},
		{"CONFIG_LOG_COLORS", "1"},
		{"CONFIG_LOG_TIMESTAMP_SOURCE_RTOS", "1"},

		// ── Heap ──────────────────────────────────────────────────────────
		{"CONFIG_HEAP_POISONING_DISABLED", "1"},
		{"CONFIG_HEAP_TRACING_OFF", "1"},
		{"CONFIG_HEAP_ABORT_WHEN_ALLOCATION_FAILS", "0"},

		// ── NVS ───────────────────────────────────────────────────────────
		{"CONFIG_NVS_ASSERT_ERROR_CHECK", "0"},

		// ── Newlib reentrant allocation ───────────────────────────────────
		{"CONFIG_LIBC_NEWLIB", "1"},
		{"CONFIG_NEWLIB_STDOUT_LINE_ENDING_CRLF", "1"},

		// ── SPIRAM / PSRAM ────────────────────────────────────────────────
		{"CONFIG_SPIRAM", "0"},
		{"CONFIG_SPIRAM_SUPPORT", "0"},

		// ── Compiler / libc ───────────────────────────────────────────────
		{"CONFIG_COMPILER_OPTIMIZATION_DEFAULT", "1"},
		{"CONFIG_COMPILER_STACK_CHECK_MODE_NONE", "1"},
	}
	for _, pair := range allDefaults {
		if !defined[pair.k] {
			defined[pair.k] = true
			lines = append(lines, fmt.Sprintf("#define %s %s", pair.k, pair.v))
		}
	}

	// ── ESP-IDF target selection (per-chip) ─────────────────────────
	// The Arduino core selects chip-specific headers via these macros:
	//   #if CONFIG_IDF_TARGET_ESP32      → "esp32/rom/spi_flash.h"
	//   #elif CONFIG_IDF_TARGET_ESP32S3  → "esp32s3/rom/spi_flash.h"
	// Hardcoding esp32 here made S3/C3 builds include the wrong ROM headers.
	tgt := strings.ToLower(strings.TrimSpace(target))
	if tgt == "" || !strings.HasPrefix(tgt, "esp32") && !strings.HasPrefix(tgt, "esp32c") &&
		!strings.HasPrefix(tgt, "esp32h") && !strings.HasPrefix(tgt, "esp32p") {
		tgt = "esp32"
	}
	if !defined["CONFIG_IDF_TARGET"] {
		lines = append(lines, fmt.Sprintf("#define CONFIG_IDF_TARGET \"%s\"", tgt))
	}
	tgtUpper := strings.ToUpper(tgt)
	if !defined["CONFIG_IDF_TARGET_"+tgtUpper] {
		lines = append(lines, fmt.Sprintf("#define CONFIG_IDF_TARGET_%s 1", tgtUpper))
	}
	arch := "XTENSA"
	switch {
	case strings.Contains(tgt, "c3"), strings.Contains(tgt, "c6"),
		strings.Contains(tgt, "h2"), strings.Contains(tgt, "p4"):
		arch = "RISCV"
	}
	if !defined["CONFIG_IDF_TARGET_ARCH_"+arch] {
		lines = append(lines, fmt.Sprintf("#define CONFIG_IDF_TARGET_ARCH_%s 1", arch))
	}

	lines = append(lines, "#endif /* SDKCONFIG_H */")

	return os.WriteFile(dst, []byte(strings.Join(lines, "\n")+"\n"), 0o644)
}

// ── Stage 2: Preprocess sketch ────────────────────────────────────
// Merges all .ino files into a single .cpp — mirrors the Arduino
// preprocessor that adds forward declarations and the #line markers.
func (c *Compiler) preprocessSketch(sketchDir, outDir string) (string, error) {
	entries, err := os.ReadDir(sketchDir)
	if err != nil {
		return "", err
	}

	var inoFiles []string
	for _, e := range entries {
		if !e.IsDir() && strings.HasSuffix(e.Name(), ".ino") {
			inoFiles = append(inoFiles, filepath.Join(sketchDir, e.Name()))
		}
	}

	if len(inoFiles) == 0 {
		return "", fmt.Errorf("no .ino files found in %s", sketchDir)
	}

	sort.Strings(inoFiles)
	outPath := filepath.Join(outDir, filepath.Base(inoFiles[0])+".cpp")
	out, err := os.Create(outPath)
	if err != nil {
		return "", err
	}
	defer out.Close()

	// Arduino-compatible header
	fmt.Fprintln(out, "#include <Arduino.h>")
	fmt.Fprintln(out)

	// Collect forward declarations
	var forwardDecls []string
	for _, f := range inoFiles {
		data, _ := os.ReadFile(f)
		decls := extractForwardDeclarations(string(data))
		forwardDecls = append(forwardDecls, decls...)
	}
	for _, d := range forwardDecls {
		fmt.Fprintln(out, d)
	}
	fmt.Fprintln(out)

	// Concatenate all .ino files with #line markers
	for _, f := range inoFiles {
		data, err := os.ReadFile(f)
		if err != nil {
			return "", err
		}
		fmt.Fprintf(out, "#line 1 \"%s\"\n", filepath.ToSlash(f))
		out.Write(data)
		fmt.Fprintln(out)
	}

	return outPath, nil
}

// extractForwardDeclarations generates forward declarations for functions
// defined in .ino files. Mirrors Arduino's preprocessing step.
func extractForwardDeclarations(src string) []string {
	re := regexp.MustCompile(`(?m)^((?:unsigned\s+)?(?:void|int|long|char|bool|byte|float|double|String|uint8_t|uint16_t|uint32_t|int8_t|int16_t|int32_t)\s+\w+\s*\([^)]*\))\s*\{`)
	matches := re.FindAllStringSubmatch(src, -1)

	var decls []string
	seen := make(map[string]bool)
	for _, m := range matches {
		sig := strings.TrimSpace(m[1]) + ";"
		if !seen[sig] {
			seen[sig] = true
			decls = append(decls, sig)
		}
	}
	return decls
}

// ── Stage 3: Build core ───────────────────────────────────────────

func (c *Compiler) buildCore(rb *boards.ResolvedBoard, tc *Toolchain, bf *BuildFlags, outDir, libPath string) error {
	corePath := filepath.Join(rb.PlatformPath, "cores", rb.GetProp("build.core"))
	if _, err := os.Stat(corePath); err != nil {
		return fmt.Errorf("core not found at %s", corePath)
	}

	variantPath := filepath.Join(rb.PlatformPath, "variants", rb.GetProp("build.variant"))

	if bf.sdkPath != "" {
		c.logf("  [debug] sdkPath=%s", bf.sdkPath)
		if pflags := rb.GetProp("compiler.cpreprocessor.flags"); pflags != "" {
			c.logf("  [debug] raw compiler.cpreprocessor.flags: %s", pflags)
			toks := expandPlatformFlags(pflags, rb, bf.sdkPath)
			c.logf("  [debug] compiler.cpreprocessor.flags tokens: %v", toks)
		}
	}

	var objs []string
	err := filepath.Walk(corePath, func(path string, info os.FileInfo, err error) error {
		if err != nil || info.IsDir() {
			return err
		}
		ext := strings.ToLower(filepath.Ext(path))
		if ext != ".c" && ext != ".cpp" && ext != ".S" {
			return nil
		}

		objPath := filepath.Join(outDir, strings.ReplaceAll(path, "/", "_")+".o")
		args := bf.forFile(path, variantPath, true, tc)
		args = append(args, "-o", objPath, path)

		if err := c.runCC(tc, path, args); err != nil {
			return err
		}
		objs = append(objs, objPath)
		return nil
	})
	if err != nil {
		return err
	}

	return c.archiveObjects(tc, objs, libPath)
}

// ── Stage 5: Resolve libraries ────────────────────────────────────

var includeRE = regexp.MustCompile(`#include\s+[<"]([^>"]+\.h)[>"]`)

func (c *Compiler) resolveLibraries(sketchCPP, sketchDir string, extraDirs []string, rb *boards.ResolvedBoard) ([]string, error) {
	data, err := os.ReadFile(sketchCPP)
	if err != nil {
		return nil, err
	}

	searchPaths := []string{
		sketchDir,
		c.cfg.LibrariesDir(),
		filepath.Join(rb.PlatformPath, "libraries"),
	}
	searchPaths = append(searchPaths, extraDirs...)

	var libPaths []string
	seen := make(map[string]bool)
	scannedHeaders := make(map[string]bool)

	// scanHeaders resolves libraries for a set of headers and recurses into
	// each found library's own source files to pick up transitive dependencies
	// (e.g. WiFi.h -> WiFiGeneric.h -> Network.h -> Network library).
	var scanHeaders func(headers []string)
	scanHeaders = func(headers []string) {
		for _, headerName := range headers {
			if scannedHeaders[headerName] {
				continue
			}
			scannedHeaders[headerName] = true

			for _, sp := range searchPaths {
				libPath := c.findLibraryForHeader(headerName, sp)
				if libPath == "" || seen[libPath] {
					continue
				}
				seen[libPath] = true
				libPaths = append(libPaths, libPath)
				c.logf("  Library: %s → %s", headerName, filepath.Base(libPath))

				// Scan this library's source files for transitive #include deps
				var transitiveHeaders []string
				for _, srcDir := range []string{filepath.Join(libPath, "src"), libPath} {
					entries, err := os.ReadDir(srcDir)
					if err != nil {
						continue
					}
					for _, e := range entries {
						if e.IsDir() {
							continue
						}
						ext := strings.ToLower(filepath.Ext(e.Name()))
						if ext != ".h" && ext != ".hpp" && ext != ".cpp" && ext != ".c" {
							continue
						}
						hdata, err := os.ReadFile(filepath.Join(srcDir, e.Name()))
						if err != nil {
							continue
						}
						for _, m := range includeRE.FindAllStringSubmatch(string(hdata), -1) {
							transitiveHeaders = append(transitiveHeaders, m[1])
						}
					}
					break // only scan first found src dir
				}
				scanHeaders(transitiveHeaders)
				break
			}
		}
	}

	// Collect top-level headers from sketch and resolve transitively
	var topHeaders []string
	for _, m := range includeRE.FindAllStringSubmatch(string(data), -1) {
		topHeaders = append(topHeaders, m[1])
	}
	scanHeaders(topHeaders)

	return libPaths, nil
}

func (c *Compiler) findLibraryForHeader(header, searchPath string) string {
	entries, err := os.ReadDir(searchPath)
	if err != nil {
		return ""
	}
	for _, e := range entries {
		if !e.IsDir() {
			continue
		}
		libDir := filepath.Join(searchPath, e.Name())
		candidates := []string{
			filepath.Join(libDir, "src", header),
			filepath.Join(libDir, header),
		}
		for _, cand := range candidates {
			if _, err := os.Stat(cand); err == nil {
				return libDir
			}
		}
	}
	return ""
}

// ── Stage 6: Build libraries ──────────────────────────────────────

func (c *Compiler) buildLibraries(libPaths []string, tc *Toolchain, bf *BuildFlags, outDir string) ([]string, error) {
	var allObjs []string

	for _, libPath := range libPaths {
		libName := filepath.Base(libPath)
		libOutDir := filepath.Join(outDir, libName)
		os.MkdirAll(libOutDir, 0o755)

		srcDirs := []string{
			filepath.Join(libPath, "src"),
			libPath,
		}

		for _, srcDir := range srcDirs {
			entries, err := os.ReadDir(srcDir)
			if err != nil {
				continue
			}
			for _, e := range entries {
				if e.IsDir() {
					continue
				}
				ext := strings.ToLower(filepath.Ext(e.Name()))
				if ext != ".c" && ext != ".cpp" && ext != ".S" {
					continue
				}
				srcPath := filepath.Join(srcDir, e.Name())
				objPath := filepath.Join(libOutDir, e.Name()+".o")

				args := bf.forFile(srcPath, "", false, tc)
				// Add all resolved library src/ dirs so libraries can see each other's headers
				// (e.g. WiFi/AP.cpp needs Network/src/ on its include path for Network.h)
				for _, lp := range libPaths {
					for _, ld := range []string{filepath.Join(lp, "src"), lp} {
						if dirExists(ld) {
							args = append(args, "-I", ld)
							break
						}
					}
				}
				args = append(args, "-I", srcDir, "-o", objPath, srcPath)

				if err := c.runCC(tc, srcPath, args); err != nil {
					return nil, err
				}
				allObjs = append(allObjs, objPath)
			}
			break // Only process first found src dir
		}
	}

	return allObjs, nil
}

// ── Stage 7: Build sketch ─────────────────────────────────────────

func (c *Compiler) buildSketch(sketchDir, sketchCPP string, tc *Toolchain, bf *BuildFlags, outDir string, libPaths []string) ([]string, error) {
	// libIncDirs returns -I flags for every resolved library's src/ dir so the
	// sketch's own `#include <Lib.h>` compiles. Libraries already see each
	// other (buildLibraries), but the sketch TU was missing these paths — any
	// sketch actually using a library failed at the sketch TU.
	libIncDirs := func(out []string) []string {
		for _, lp := range libPaths {
			for _, ld := range []string{filepath.Join(lp, "src"), lp} {
				if dirExists(ld) {
					out = append(out, "-I", ld)
					break
				}
			}
		}
		return out
	}

	var objs []string

	objPath := filepath.Join(outDir, filepath.Base(sketchCPP)+".o")
	args := bf.forFile(sketchCPP, "", false, tc)
	args = append(args, libIncDirs(nil)...)
	args = append(args, "-I", sketchDir, "-o", objPath, sketchCPP)
	if err := c.runCC(tc, sketchCPP, args); err != nil {
		return nil, err
	}
	objs = append(objs, objPath)

	entries, _ := os.ReadDir(sketchDir)
	for _, e := range entries {
		ext := strings.ToLower(filepath.Ext(e.Name()))
		if ext != ".cpp" && ext != ".c" {
			continue
		}
		src := filepath.Join(sketchDir, e.Name())
		obj := filepath.Join(outDir, e.Name()+".o")
		args := bf.forFile(src, "", false, tc)
		args = append(args, libIncDirs(nil)...)
		args = append(args, "-I", sketchDir, "-o", obj, src)
		if err := c.runCC(tc, src, args); err != nil {
			return nil, err
		}
		objs = append(objs, obj)
	}

	return objs, nil
}

// archCodegenFlags returns target codegen flags (-mcpu/-mthumb/-mmcu) for
// non-x86 architectures so object files and final links are emitted for the
// MCU instead of the toolchain's host default. Derived heuristically from
// build.mcu since board packages encode the exact CPU in different props.
func archCodegenFlags(rb *boards.ResolvedBoard) []string {
	switch rb.Architecture {
	case "avr", "esp32":
		// Handled explicitly elsewhere (avr: -mmcu; esp32: xtensa flags).
		return nil
	}

	mcu := strings.ToUpper(rb.GetProp("build.mcu"))
	if mcu == "" {
		return nil
	}
	if strings.HasPrefix(mcu, "ATMEGA") || strings.HasPrefix(mcu, "ATTINY") ||
		strings.HasPrefix(mcu, "AT90") || strings.HasPrefix(mcu, "ATXMEGA") {
		return []string{fmt.Sprintf("-mmcu=%s", strings.ToLower(mcu))}
	}

	cpu := ""
	switch {
	case strings.Contains(mcu, "M0PLUS"), strings.Contains(mcu, "RP2040"):
		cpu = "cortex-m0plus"
	case strings.Contains(mcu, "SAMD21"), strings.Contains(mcu, "SAMR21"),
		strings.Contains(mcu, "STM32F0"), strings.Contains(mcu, "STM32G0"),
		strings.Contains(mcu, "STM32L0"):
		cpu = "cortex-m0"
	case strings.Contains(mcu, "STM32F1"), strings.Contains(mcu, "STM32F2"),
		strings.Contains(mcu, "STM32L1"):
		cpu = "cortex-m3"
	case strings.Contains(mcu, "SAMD51"), strings.Contains(mcu, "SAME51"),
		strings.Contains(mcu, "SAME53"), strings.Contains(mcu, "SAME54"),
		strings.Contains(mcu, "STM32F3"), strings.Contains(mcu, "STM32F4"),
		strings.Contains(mcu, "STM32L4"), strings.Contains(mcu, "STM32G4"),
		strings.Contains(mcu, "STM32WB"), strings.Contains(mcu, "NRF52"),
		strings.Contains(mcu, "MK20"), strings.Contains(mcu, "MK64"),
		strings.Contains(mcu, "MK66"):
		cpu = "cortex-m4"
	case strings.Contains(mcu, "STM32F7"), strings.Contains(mcu, "STM32H7"),
		strings.Contains(mcu, "MIMXRT"):
		cpu = "cortex-m7"
	}
	if cpu == "" {
		return nil
	}
	return []string{fmt.Sprintf("-mcpu=%s", cpu), "-mthumb"}
}

// ── Stage 8: Link ─────────────────────────────────────────────────

func (c *Compiler) link(rb *boards.ResolvedBoard, tc *Toolchain, bf *BuildFlags, objs []string, coreLib, elfPath string) error {
	buildDir := filepath.Dir(elfPath)
	projectName := strings.TrimSuffix(filepath.Base(elfPath), filepath.Ext(elfPath))

	args := []string{
		"-Os",
	}
	// Target codegen flags for ALL architectures — previously only AVR got
	// -mmcu here, so ARM/other links ran with host-arch defaults.
	if f := archCodegenFlags(rb); len(f) > 0 {
		args = append(args, f...)
	}
	if rb.Architecture == "avr" {
		args = append(args, "-Wl,--gc-sections")
		args = append(args, fmt.Sprintf("-mmcu=%s", rb.GetProp("build.mcu")))
	}

	if rb.Architecture == "esp32" {
		args = append(args, expandLinkFlags(rawProp(rb, "compiler.c.elf.flags"), rb, bf, buildDir, projectName, coreLib)...)
		args = append(args, expandLinkFlags(rawProp(rb, "compiler.c.elf.extra_flags"), rb, bf, buildDir, projectName, coreLib)...)
	} else if lflags := rb.GetProp("compiler.c.elf.extra_flags"); lflags != "" {
		args = append(args, strings.Fields(lflags)...)
	}

	if rb.Architecture == "esp32" {
		args = append(args, "-Wl,--start-group")
	}
	args = append(args, objs...)
	args = append(args, coreLib)
	if rb.Architecture == "esp32" {
		args = append(args, expandLinkFlags(rawProp(rb, "build.extra_libs"), rb, bf, buildDir, projectName, coreLib)...)
		args = append(args, expandLinkFlags(rawProp(rb, "build.zigbee_libs"), rb, bf, buildDir, projectName, coreLib)...)
		args = append(args, expandLinkFlags(rawProp(rb, "compiler.c.elf.libs"), rb, bf, buildDir, projectName, coreLib)...)
		args = append(args, expandLinkFlags(rawProp(rb, "compiler.libraries.ldflags"), rb, bf, buildDir, projectName, coreLib)...)
		args = append(args, "-Wl,--end-group", "-Wl,-EL")
	}
	args = append(args, "-o", elfPath)

	linker := tc.GCCCPP
	if linker == "" {
		linker = tc.GCC
	}
	cmd := exec.CommandContext(c.ctx, linker, args...)

	if out, err := cmd.CombinedOutput(); err != nil {
		return fmt.Errorf("link failed:\n%s", string(out))
	}
	return nil
}

func rawProp(rb *boards.ResolvedBoard, key string) string {
	if v, ok := rb.BoardProps[key]; ok {
		return v
	}
	return rb.PlatformProps[key]
}

func expandLinkFlags(flags string, rb *boards.ResolvedBoard, bf *BuildFlags, buildDir, projectName, archivePath string) []string {
	if strings.TrimSpace(flags) == "" {
		return nil
	}
	memType := rb.GetProp("build.memory_type")
	if memType == "" {
		memType = "qio_qspi"
	}
	replacements := map[string]string{
		"{build.path}":         buildDir,
		"{build.project_name}": projectName,
		"{archive_file_path}":  archivePath,
		"{compiler.sdk.path}":  bf.sdkPath,
		"{build.memory_type}":  memType,
	}
	for k, v := range replacements {
		flags = strings.ReplaceAll(flags, k, v)
	}
	return expandPlatformFlags(flags, rb, bf.sdkPath)
}

// ── Stage 9: Extract binary ───────────────────────────────────────

func (c *Compiler) extractBinary(rb *boards.ResolvedBoard, tc *Toolchain, elfPath, buildDir, name string) (string, error) {
	hexPath := filepath.Join(buildDir, name+".hex")
	binPath := filepath.Join(buildDir, name+".bin")

	// ESP chips need a real ESP app image (header with flash mode/size/freq),
	// NOT a raw objcopy binary: raw conversion pads address gaps (a 300 KB
	// sketch became a 335 MB file) and lacks the image header the ROM
	// bootloader requires. Generate it with esptool elf2image.
	if rb.Architecture == "esp32" {
		return c.extractESPImage(rb, elfPath, buildDir, name)
	}

	hexArgs := []string{"-O", "ihex", "-R", ".eeprom", elfPath, hexPath}
	if out, err := exec.CommandContext(c.ctx, tc.ObjCopy, hexArgs...).CombinedOutput(); err != nil {
		return "", fmt.Errorf("objcopy hex: %s\n%s", err, out)
	}

	binArgs := []string{"-O", "binary", elfPath, binPath}
	exec.CommandContext(c.ctx, tc.ObjCopy, binArgs...).Run() // Best-effort

	if _, err := os.Stat(binPath); err == nil {
		return binPath, nil
	}
	return hexPath, nil
}

// extractESPImage converts an ELF into a flashable ESP app image using the
// platform-bundled esptool (falls back to `python -m esptool`).
func (c *Compiler) extractESPImage(rb *boards.ResolvedBoard, elfPath, buildDir, name string) (string, error) {
	binPath := filepath.Join(buildDir, name+".bin")

	esptoolPy := latestFileUnder(filepath.Join(rb.ToolsDir, "esptool_py"), "esptool.py")

	python := "python3"
	if _, err := exec.LookPath("python3"); err != nil {
		python = "python"
	}

	var base []string
	if esptoolPy != "" {
		base = append(base, esptoolPy)
	} else if _, err := exec.LookPath(python); err == nil {
		base = append(base, "-m", "esptool")
	} else {
		return "", fmt.Errorf("esptool not found (install with: pip install esptool)")
	}

	mode := rb.GetProp("build.flash_mode")
	if mode == "" {
		mode = "dio"
	}
	size := rb.GetProp("build.flash_size")
	if size == "" {
		size = "detect"
	}
	freq := "80m"
	if ff := rb.GetProp("build.f_flash"); ff != "" {
		f := strings.TrimSuffix(ff, "L")
		if n, err := strconv.Atoi(f); err == nil && n > 0 {
			freq = fmt.Sprintf("%dm", n/1000000)
		}
	}

	args := append([]string{}, base...)
	args = append(args,
		"--chip", strings.ToLower(rb.GetProp("build.mcu")),
		"elf2image",
		"--flash_mode", mode,
		"--flash_freq", freq,
		"--flash_size", size,
		elfPath,
	)

	cmd := exec.CommandContext(c.ctx, python, args...)
	cmd.Dir = buildDir // esptool writes <elf basename>.bin here
	if out, err := cmd.CombinedOutput(); err != nil {
		return "", fmt.Errorf("elf2image failed:\n%s", out)
	}
	if _, err := os.Stat(binPath); err != nil {
		return "", fmt.Errorf("elf2image produced no output at %s", binPath)
	}
	c.logf("  ESP app image: %s (%.1f KB)", binPath, float64(fileSize(binPath))/1024)
	return binPath, nil
}

// latestFileUnder finds <root>/<version-dir>/<filename> picking the highest
// version directory (e.g. tools/esptool_py/5.3.1/esptool.py).
func latestFileUnder(root, filename string) string {
	entries, err := os.ReadDir(root)
	if err != nil {
		return ""
	}
	var latest string
	for _, e := range entries {
		if e.IsDir() && version.Compare(e.Name(), latest) > 0 {
			latest = e.Name()
		}
	}
	if latest == "" {
		return ""
	}
	p := filepath.Join(root, latest, filename)
	if info, err := os.Stat(p); err == nil && !info.IsDir() {
		return p
	}
	return ""
}

// randHex returns nBytes of cryptographically random data as hex (used to
// make temp build dirs unique per invocation).
func randHex(nBytes int) string {
	buf := make([]byte, nBytes)
	if _, err := rand.Read(buf); err != nil {
		return fmt.Sprintf("%d", time.Now().UnixNano())
	}
	return hex.EncodeToString(buf)
}

func fileSize(path string) int64 {
	info, err := os.Stat(path)
	if err != nil {
		return 0
	}
	return info.Size()
}

// ── Stage 10: Report size ─────────────────────────────────────────

// sysVSection is one row of `size -A` (SysV) output.
type sysVSection struct {
	Name string
	Size int
}

// parseSysVSize parses `size -A` output rows of the form:
//
//	section                  size         addr
//	.dram0.data           14566   1070150144
//
// The header line and any non-section lines are skipped.
func parseSysVSize(out string) []sysVSection {
	var secs []sysVSection
	for _, line := range strings.Split(out, "\n") {
		fields := strings.Fields(line)
		if len(fields) < 2 || len(fields) > 3 {
			continue
		}
		if !strings.HasPrefix(fields[0], ".") {
			continue // header line or tool noise
		}
		var sz int
		if _, err := fmt.Sscanf(fields[1], "%d", &sz); err != nil {
			continue
		}
		secs = append(secs, sysVSection{Name: fields[0], Size: sz})
	}
	return secs
}

// esp32RAMSection reports whether a section counts toward RAM ("global
// variables") on ESP32 targets. ESP-IDF linker scripts emit large NOBITS
// alignment placeholders (.dram0.dummy, .flash_rodata_dummy, .ext_ram.dummy)
// that GNU size's Berkeley mode folds into bss — inflating a trivial Blink to
// "178% of dynamic memory". Real RAM is dram0/data/bss/noinit + RTC + IRAM
// data; flash and PSRAM-resident sections never count.
func esp32RAMSection(name string) bool {
	if strings.Contains(name, "dummy") || strings.Contains(name, "ext_ram") {
		return false
	}
	switch {
	case name == ".data", name == ".bss", name == ".noinit":
		return true
	case strings.HasPrefix(name, ".dram0.data"), strings.HasPrefix(name, ".dram0.bss"):
		return true
	case strings.HasPrefix(name, ".rtc."), strings.HasPrefix(name, ".rtc_"):
		return true
	case strings.HasPrefix(name, ".iram0.data"), strings.HasPrefix(name, ".iram0.bss"):
		return true
	}
	return false
}

// esp32FlashSection reports whether a section is part of the flash-resident
// program image (used only as a fallback when the app-image .bin is absent).
func esp32FlashSection(name string) bool {
	if strings.Contains(name, "dummy") {
		return false
	}
	switch {
	case strings.HasPrefix(name, ".flash."):
		return true
	case strings.HasPrefix(name, ".iram0.text"), strings.HasPrefix(name, ".iram0.vectors"):
		return true
	case name == ".eh_frame":
		return true
	}
	return false
}

// esp32Target reports whether the board is an ESP32 family device, whose
// linker scripts make GNU size's Berkeley output unusable.
func esp32Target(rb *boards.ResolvedBoard) bool {
	return rb.Architecture == "esp32" ||
		strings.HasPrefix(strings.ToLower(rb.GetProp("build.mcu")), "esp32")
}

// computeSizeUsage returns (programBytes, dataBytes) for a linked ELF.
// ESP32 boards use section-based sums from `size -A` (Berkeley numbers are
// inflated by linker placeholders); everything else keeps the classic
// Berkeley text+data / data+bss arithmetic.
func computeSizeUsage(tc *Toolchain, elfPath string, esp32 bool) (int, int) {
	out, err := exec.Command(tc.Size, elfPath).Output()
	if err != nil || len(out) == 0 {
		return 0, 0
	}

	if !esp32 {
		lines := strings.Split(strings.TrimSpace(string(out)), "\n")
		if len(lines) < 2 {
			return 0, 0
		}
		fields := strings.Fields(lines[1])
		if len(fields) < 4 {
			return 0, 0
		}
		var text, data, bss int
		fmt.Sscanf(fields[0], "%d", &text)
		fmt.Sscanf(fields[1], "%d", &data)
		fmt.Sscanf(fields[2], "%d", &bss)
		return text + data, data + bss
	}

	out, err = exec.Command(tc.Size, "-A", elfPath).Output()
	if err != nil {
		return 0, 0
	}
	var programBytes, dataBytes int
	for _, sec := range parseSysVSize(string(out)) {
		if esp32RAMSection(sec.Name) {
			dataBytes += sec.Size
		}
		if esp32FlashSection(sec.Name) {
			programBytes += sec.Size
		}
	}
	return programBytes, dataBytes
}

func (c *Compiler) reportSize(rb *boards.ResolvedBoard, tc *Toolchain, elfPath string) {
	esp32 := esp32Target(rb)

	programBytes, dataBytes := computeSizeUsage(tc, elfPath, esp32)
	if programBytes == 0 && dataBytes == 0 {
		return
	}

	// Prefer the actual app image: it is exactly what esptool writes.
	if esp32 {
		binPath := strings.TrimSuffix(elfPath, filepath.Ext(elfPath)) + ".bin"
		if sz := fileSize(binPath); sz > 0 {
			programBytes = int(sz)
		}
	}

	maxFlash := 32256
	maxSRAM := 2048
	if v := rb.GetProp("upload.maximum_size"); v != "" {
		fmt.Sscanf(v, "%d", &maxFlash)
	}
	if v := rb.GetProp("upload.maximum_data_size"); v != "" {
		fmt.Sscanf(v, "%d", &maxSRAM)
	}
	if maxFlash <= 0 {
		maxFlash = 1
	}
	if maxSRAM <= 0 {
		maxSRAM = 1
	}

	flashPct := programBytes * 100 / maxFlash
	sramPct := dataBytes * 100 / maxSRAM

	// Arduino-canonical phrasing so the IDE's flash-parser matches.
	c.logf("\nSketch uses %d bytes (%d%%) of program storage space. Maximum is %d bytes.",
		programBytes, flashPct, maxFlash)
	c.logf("Global variables use %d bytes (%d%%) of dynamic memory, leaving %d bytes for local variables. Maximum is %d bytes.",
		dataBytes, sramPct, maxSRAM-dataBytes, maxSRAM)

	if flashPct > 95 {
		c.log("⚠ Flash usage very high!")
	}
	if sramPct > 80 {
		c.log("⚠ SRAM usage high — potential instability at runtime")
	}
}

// ── Toolchain resolution ──────────────────────────────────────────

type Toolchain struct {
	GCC         string
	GCCCPP      string
	AR          string
	ObjCopy     string
	Size        string
	Prefix      string
	SysIncludes []string
}

func (c *Compiler) resolveToolchain(rb *boards.ResolvedBoard) (*Toolchain, error) {
	ext := ""
	if runtime.GOOS == "windows" {
		ext = ".exe"
	}

	toolsDir := rb.ToolsDir
	var toolPaths []string
	seenToolPath := make(map[string]bool)
	addToolPath := func(p string) {
		p = filepath.Clean(p)
		if !seenToolPath[p] {
			seenToolPath[p] = true
			toolPaths = append(toolPaths, p)
		}
	}

	if entries, err := os.ReadDir(toolsDir); err == nil {
		for _, e := range entries {
			if !e.IsDir() {
				continue
			}
			toolRoot := filepath.Join(toolsDir, e.Name())

			if flatBin := filepath.Join(toolRoot, "bin"); dirExists(flatBin) {
				addToolPath(flatBin)
				continue
			}

			versions, _ := os.ReadDir(toolRoot)
			for _, v := range versions {
				if !v.IsDir() {
					continue
				}
				if p := filepath.Join(toolRoot, v.Name(), "bin"); dirExists(p) {
					addToolPath(p)
				}
				if p := filepath.Join(toolRoot, v.Name(), e.Name(), "bin"); dirExists(p) {
					addToolPath(p)
				}
			}
		}
	}

	if p := filepath.Join(rb.PlatformPath, "tools", "bin"); dirExists(p) {
		addToolPath(p)
	}

	resolve := func(name string) string {
		for _, dir := range toolPaths {
			p := filepath.Join(dir, name+ext)
			if _, err := os.Stat(p); err == nil {
				return p
			}
		}
		if p, err := exec.LookPath(name + ext); err == nil {
			return p
		}
		return name
	}

	compilerPath := rb.GetProp("compiler.path")
	cCmd := rb.GetProp("compiler.c.cmd")
	cppCmd := rb.GetProp("compiler.cpp.cmd")
	arCmd := rb.GetProp("compiler.ar.cmd")
	objcopyCmd := rb.GetProp("compiler.objcopy.cmd")
	sizeCmd := rb.GetProp("compiler.size.cmd")

	if strings.Contains(compilerPath, "{runtime.tools.") {
		compilerPath = c.substituteToolPath(compilerPath, toolPaths, rb)
	}

	compilerPath = strings.TrimRight(compilerPath, "/\\")

	var tc *Toolchain

	if compilerPath != "" && cCmd != "" {
		joinCmd := func(cmd string) string {
			if cmd == "" {
				return ""
			}
			p := filepath.Join(compilerPath, cmd+ext)
			if _, err := os.Stat(p); err == nil {
				return p
			}
			if _, err := os.Stat(cmd + ext); err == nil {
				return cmd + ext
			}
			return resolve(cmd)
		}
		if cppCmd == "" {
			cppCmd = strings.Replace(cCmd, "gcc", "g++", 1)
		}
		if arCmd == "" {
			arCmd = strings.Replace(cCmd, "gcc", "gcc-ar", 1)
		}
		if objcopyCmd == "" {
			objcopyCmd = strings.Replace(cCmd, "gcc", "objcopy", 1)
		}
		if sizeCmd == "" {
			sizeCmd = strings.Replace(cCmd, "gcc", "size", 1)
		}
		tc = &Toolchain{
			Prefix:  "",
			GCC:     joinCmd(cCmd),
			GCCCPP:  joinCmd(cppCmd),
			AR:      joinCmd(arCmd),
			ObjCopy: joinCmd(objcopyCmd),
			Size:    joinCmd(sizeCmd),
		}
	} else {
		tarch := rb.GetProp("build.tarch")
		target := rb.GetProp("build.target")
		var prefix string
		if tarch != "" && target != "" {
			prefix = tarch + "-" + target + "-elf-"
		} else {
			prefix = c.inferToolchainPrefix(toolPaths, ext)
		}
		tc = &Toolchain{
			Prefix:  prefix,
			GCC:     resolve(prefix + "gcc"),
			GCCCPP:  resolve(prefix + "g++"),
			AR:      resolve(prefix + "gcc-ar"),
			ObjCopy: resolve(prefix + "objcopy"),
			Size:    resolve(prefix + "size"),
		}
	}

	if _, err := os.Stat(tc.GCC); err != nil {
		if _, err2 := exec.LookPath(tc.GCC); err2 != nil {
			return nil, fmt.Errorf(
				"toolchain compiler %q not found\n"+
					"Install the platform first: companion board install %s:%s\n"+
					"Searched %d tool directories under: %s",
				tc.GCC, rb.Vendor, rb.Architecture, len(toolPaths), toolsDir,
			)
		}
	}

	// ── Collect toolchain system include directories ──────────────────────
	//
	// For ESP32 / Xtensa we need TWO distinct things from the toolchain tree:
	//
	//  a) Newlib/libc headers  (sys/reent.h, stdio.h, …)
	//     These must precede IDF wrapper headers so #include_next chains work.
	//
	//  b) Chip-specific Xtensa HAL config  (<xtensa/config/core.h>)
	//     This file defines XCHAL_HAVE_LOOPS, XCHAL_NUM_AREGS, etc. that the
	//     generic xtensa headers in esp32-libs/include/xtensa/ need.
	//     It lives under:
	//       esp-x32/xtensa-esp-elf/include/xtensa/config/
	//     and must be on the include path BEFORE esp32-libs/include/xtensa/
	//     which contains the generic xtensa/ headers that do
	//       #include <xtensa/config/core.h>
	//     If the toolchain path is absent the compiler finds no core.h and
	//     all XCHAL_* macros are undefined → compile error in xtruntime-frames.h.
	var sysincs []string
	seenInc := make(map[string]bool)

	addSysInc := func(p string) {
		p = filepath.Clean(p)
		if !seenInc[p] && dirExists(p) {
			seenInc[p] = true
			sysincs = append(sysincs, p)
		}
	}

	// Walk every tool bin/ parent for newlib/stdio headers.
	for _, tp := range toolPaths {
		root := filepath.Clean(tp)
		filepath.WalkDir(root, func(p string, d fs.DirEntry, err error) error {
			if err != nil || !d.IsDir() {
				return nil
			}
			if fileExists(filepath.Join(p, "sys", "reent.h")) || fileExists(filepath.Join(p, "stdio.h")) {
				addSysInc(p)
				return filepath.SkipDir
			}
			return nil
		})
	}

	if tc.GCC != "" {
		gccDir := filepath.Dir(tc.GCC)
		// Standard relative paths from the bin/ directory.
		stdCandidates := []string{
			filepath.Join(gccDir, "..", "xtensa-esp-elf", "include"),
			filepath.Join(gccDir, "..", "include"),
			filepath.Join(gccDir, "..", "lib", "gcc"),
		}
		for _, cand := range stdCandidates {
			cand = filepath.Clean(cand)
			if fileExists(filepath.Join(cand, "sys", "reent.h")) || fileExists(filepath.Join(cand, "stdio.h")) {
				addSysInc(cand)
			}
		}

		// ── Xtensa chip-specific config headers (XCHAL_* macros) ─────────
		// The toolchain ships <xtensa/config/core.h> under the sysroot.
		// Add the xtensa-esp-elf/include directory (which contains the
		// xtensa/config/ sub-tree) as a system include so the chip-specific
		// XCHAL definitions are visible when esp32-libs/include/xtensa/*.h
		// does  #include <xtensa/config/core.h>.
		xtensaConfigCandidates := []string{
			// Flat layout: esp-x32/xtensa-esp-elf/include
			filepath.Join(gccDir, "..", "xtensa-esp-elf", "include"),
			// Some versions: esp-x32/lib/gcc/xtensa-esp-elf/<ver>/include
			filepath.Join(gccDir, "..", "include"),
		}
		for _, cand := range xtensaConfigCandidates {
			cand = filepath.Clean(cand)
			// Confirm this dir actually has xtensa/config/core.h
			if fileExists(filepath.Join(cand, "xtensa", "config", "core.h")) {
				addSysInc(cand)
			}
		}
	}

	tc.SysIncludes = sysincs

	return tc, nil
}

func (c *Compiler) substituteToolPath(compilerPath string, toolPaths []string, rb *boards.ResolvedBoard) string {
	result := compilerPath
	start := strings.Index(result, "{runtime.tools.")
	for start >= 0 {
		end := strings.Index(result[start:], "}")
		if end < 0 {
			break
		}
		placeholder := result[start : start+end+1]
		toolName := strings.TrimPrefix(placeholder, "{runtime.tools.")
		toolName = strings.TrimSuffix(toolName, ".path}")
		toolName = strings.TrimSuffix(toolName, "-path}")

		replaced := false
		for _, tp := range toolPaths {
			toolRoot := filepath.Dir(tp)
			rootName := filepath.Base(toolRoot)
			parentName := filepath.Base(filepath.Dir(toolRoot))

			if strings.EqualFold(rootName, toolName) ||
				strings.HasPrefix(rootName, toolName) ||
				strings.EqualFold(parentName, toolName) ||
				strings.HasPrefix(parentName, toolName) {
				result = strings.Replace(result, placeholder, toolRoot, 1)
				replaced = true
				break
			}
		}

		if !replaced {
			home, _ := os.UserHomeDir()
			candidates := []string{
				filepath.Join(rb.ToolsDir, toolName),
				filepath.Join(home, ".arduino15", "packages", rb.Vendor, "tools", toolName),
			}
			for _, cand := range candidates {
				if dirExists(cand) {
					result = strings.Replace(result, placeholder, cand, 1)
					replaced = true
					break
				}
			}
		}

		if !replaced {
			result = strings.Replace(result, placeholder, "", 1)
		}
		start = strings.Index(result, "{runtime.tools.")
	}
	return filepath.FromSlash(result)
}

func (c *Compiler) inferToolchainPrefix(toolPaths []string, ext string) string {
	for _, dir := range toolPaths {
		entries, err := os.ReadDir(dir)
		if err != nil {
			continue
		}
		for _, e := range entries {
			name := e.Name()
			suffix := "gcc" + ext
			if strings.HasSuffix(name, suffix) && len(name) > len(suffix) {
				return name[:len(name)-len("gcc")]
			}
		}
	}
	return ""
}

// ── Build flags ───────────────────────────────────────────────────

// BuildFlags holds compiler flag state for a given board + build options.
type BuildFlags struct {
	rb       *boards.ResolvedBoard
	warnings string
	verbose  bool
	sdkPath  string   // ESP32: resolved esp32-libs root (provides IDF headers)
	coreInc  []string // core/ and variants/ include paths
	buildDir string   // build directory containing generated sdkconfig.h
	fqbn     string   // full FQBN (used for fallback macros)

	// preprocessorFlags caches the expanded base flag list returned by
	// forFile (used by coreCacheKey so flag changes invalidate the core).
	preprocessorFlags []string
}

func (c *Compiler) buildFlags(rb *boards.ResolvedBoard, tc *Toolchain, opts Options) *BuildFlags {
	return &BuildFlags{
		rb:       rb,
		warnings: opts.Warnings,
		verbose:  opts.Verbose,
		sdkPath:  c.resolveSDKPath(rb),
		coreInc: []string{
			filepath.Join(rb.PlatformPath, "cores", rb.GetProp("build.core")),
			filepath.Join(rb.PlatformPath, "variants", rb.GetProp("build.variant")),
		},
		fqbn: opts.FQBN,
	}
}

func (c *Compiler) resolveSDKPath(rb *boards.ResolvedBoard) string {
	if rb.Architecture != "esp32" {
		return ""
	}

	// Per-chip prebuilt SDK libraries: esp32→esp32-libs, s3→esp32s3-libs, …
	// Linking the wrong chip's SDK produces "failed to merge target
	// specific data" errors at link time.
	mcu := strings.ToLower(rb.GetProp("build.mcu"))
	libsDirName := "esp32-libs"
	switch {
	case strings.Contains(mcu, "esp32s3"):
		libsDirName = "esp32s3-libs"
	case strings.Contains(mcu, "esp32s2"):
		libsDirName = "esp32s2-libs"
	case strings.Contains(mcu, "esp32c3"):
		libsDirName = "esp32c3-libs"
	case strings.Contains(mcu, "esp32c6"):
		libsDirName = "esp32c6-libs"
	case strings.Contains(mcu, "esp32h2"):
		libsDirName = "esp32h2-libs"
	case strings.Contains(mcu, "esp32p4"):
		libsDirName = "esp32p4-libs"
	}

	sdkRootOK := func(dir string) bool {
		return fileExists(filepath.Join(dir, "flags", "includes")) &&
			dirExists(filepath.Join(dir, "include"))
	}

	isVersionDir := func(name string) bool {
		return len(name) > 0 && name[0] >= '0' && name[0] <= '9'
	}

	latestVersionIn := func(root string) string {
		entries, err := os.ReadDir(root)
		if err != nil {
			return ""
		}
		var latest string
		for _, e := range entries {
			if e.IsDir() && isVersionDir(e.Name()) && e.Name() > latest {
				latest = e.Name()
			}
		}
		return latest
	}

	// Extract platform version from PlatformPath (e.g. ".../hardware/esp32/3.3.9" -> "3.3.9")
	platformVersion := filepath.Base(rb.PlatformPath)

	tryLibsDir := func(libsDir string) string {
		// 1. Prefer versioned subdir matching the platform version exactly
		if platformVersion != "" {
			if candidate := filepath.Join(libsDir, platformVersion); sdkRootOK(candidate) {
				return candidate
			}
		}
		// 2. Fall back to latest versioned subdir
		if v := latestVersionIn(libsDir); v != "" {
			if candidate := filepath.Join(libsDir, v); sdkRootOK(candidate) {
				return candidate
			}
		}
		// 3. Last resort: bare root (only if no versioned subdir exists)
		if sdkRootOK(libsDir) {
			return libsDir
		}
		return ""
	}

	primaryLibsDir := filepath.Join(rb.ToolsDir, libsDirName)
	if result := tryLibsDir(primaryLibsDir); result != "" {
		return result
	}

	home, _ := os.UserHomeDir()
	altLibsDir := filepath.Join(home, ".arduino15", "packages", rb.Vendor, "tools", libsDirName)
	if result := tryLibsDir(altLibsDir); result != "" {
		return result
	}

	legacySDK := filepath.Join(rb.PlatformPath, "tools", "sdk")
	if dirExists(legacySDK) {
		return legacySDK
	}

	return ""
}

func dirExists(path string) bool {
	info, err := os.Stat(path)
	return err == nil && info.IsDir()
}

// forFile returns the full compiler argument list for a single source file.
//
// FIX — include path ordering for ESP32 / IDF v5.x FreeRTOS:
//
//	FreeRTOS.h validates its config at parse time via #error directives.
//	It requires FreeRTOSConfig.h to be found BEFORE FreeRTOS-Kernel headers.
//	FreeRTOSConfig.h lives in:
//	  <sdk>/include/freertos/config/include/freertos/
//	and it does:
//	  #include "sdkconfig.h"        ← must resolve to our generated header
//	  #define configNUMBER_OF_CORES  CONFIG_FREERTOS_NUMBER_OF_CORES
//
//	The flags/includes file puts FreeRTOS-Kernel headers BEFORE the config
//	directory, so by the time FreeRTOS.h checks #ifndef configNUMBER_OF_CORES
//	the value is not yet defined.
//
//	Solution: inject three -isystem entries for the FreeRTOS config dirs
//	EXPLICITLY before everything else (after newlib, before SDK includes).
//	This mirrors what arduino-esp32's platform.txt does via the ordered
//	-isystem entries in compiler.cpreprocessor.flags.
func (bf *BuildFlags) forFile(path, extraIncDir string, isCore bool, tc *Toolchain) []string {
	_ = isCore
	rb := bf.rb
	ext := strings.ToLower(filepath.Ext(path))
	mcu := rb.GetProp("build.mcu")
	fcpu := rb.GetProp("build.f_cpu")

	args := []string{"-c"}

	// ── Architecture-specific codegen flags (all non-x86 targets) ────────
	if f := archCodegenFlags(rb); len(f) > 0 {
		args = append(args, f...)
	}

	// ── Generated headers: buildDir first in search order ─────────────────
	if bf.buildDir != "" {
		args = append(args, "-I", bf.buildDir)
		if sdkHdr := filepath.Join(bf.buildDir, "sdkconfig.h"); fileExists(sdkHdr) {
			args = append(args, "-include", sdkHdr)
		}
	}

	// ── Architecture-specific flags ───────────────────────────────────────
	switch rb.Architecture {
	case "avr":
		args = append(args, fmt.Sprintf("-mmcu=%s", mcu))

	case "esp32":
		args = append(args,
			"-mlongcalls",
			"-fno-builtin-printf",
			"-Wno-error=unused-but-set-variable",
		)

		if bf.sdkPath == "" {
			if tc != nil {
				for _, si := range tc.SysIncludes {
					args = append(args, "-isystem", si)
				}
			}
			break
		}

		// Xtensa config glue is per-target (esp32 vs esp32s3 vs esp32s2).
		esp32XtensaDir := filepath.Join(bf.sdkPath, "include", "xtensa", mcu, "include")
		if dirExists(esp32XtensaDir) {
			args = append(args, "-isystem", esp32XtensaDir)
		}

		if tc != nil {
			for _, si := range tc.SysIncludes {
				args = append(args, "-isystem", si)
			}
		}

		freeRTOSConfigDirs := []string{
			filepath.Join(bf.sdkPath, "include", "freertos", "config", "include"),
			filepath.Join(bf.sdkPath, "include", "freertos", "config", "include", "freertos"),
			filepath.Join(bf.sdkPath, "include", "freertos", "config", "xtensa", "include"),
		}
		for _, d := range freeRTOSConfigDirs {
			if dirExists(d) {
				args = append(args, "-isystem", d)
			}
		}

		if data, err := os.ReadFile(filepath.Join(bf.sdkPath, "flags", "defines")); err == nil {
			rawTokens := strings.Fields(string(data))
			for _, tok := range rawTokens {
				tok = strings.ReplaceAll(tok, `\"`, `"`)
				args = append(args, tok)
			}
		}

		incPrefix := filepath.Join(bf.sdkPath, "include") + string(filepath.Separator)
		if data, err := os.ReadFile(filepath.Join(bf.sdkPath, "flags", "includes")); err == nil {
			toks := strings.Fields(string(data))
			for i := 0; i < len(toks); i++ {
				switch toks[i] {
				case "-iprefix":
					i++ // skip the prefix argument — we supply our own above
				case "-iwithprefixbefore":
					if i+1 < len(toks) {
						i++
						args = append(args, "-isystem", incPrefix+toks[i])
					}
				default:
					args = append(args, toks[i])
				}
			}
		}

		memType := rb.GetProp("build.memory_type")
		if memType == "" {
			memType = "qio_qspi"
		}
		if memInc := filepath.Join(bf.sdkPath, memType, "include"); dirExists(memInc) {
			args = append(args, "-I", memInc)
		}
		if topInc := filepath.Join(bf.sdkPath, "include"); dirExists(topInc) {
			args = append(args, "-isystem", topInc)
		}
	}

	if fcpu != "" {
		args = append(args, fmt.Sprintf("-DF_CPU=%s", fcpu))
	}

	// ── Macro definitions: ARDUINO_BOARD, ARDUINO_VARIANT, etc. ────────────
	boardMacro := rb.GetProp("build.board")
	if boardMacro == "" {
		// Fallback: extract the third part of the FQBN (e.g. "esp32:esp32:esp32" -> "ESP32")
		parts := strings.Split(bf.fqbn, ":")
		if len(parts) >= 3 {
			boardMacro = strings.ToUpper(parts[2])
		} else {
			boardMacro = "UNKNOWN_BOARD"
		}
	}
	variantMacro := rb.GetProp("build.variant")
	if variantMacro == "" {
		// Fallback: use a safe default, often "esp32" for ESP32 boards
		variantMacro = "default"
	}
	partitionMacro := rb.GetProp("build.partitions")

	args = append(args,
		"-DARDUINO=10816",
		"-DARDUINO_ARCH_"+strings.ToUpper(rb.Architecture),
	)
	if boardMacro != "" {
		args = append(args,
			"-DARDUINO_"+boardMacro,
			fmt.Sprintf(`-DARDUINO_BOARD="%s"`, boardMacro),
		)
	}
	if variantMacro != "" {
		args = append(args, fmt.Sprintf(`-DARDUINO_VARIANT="%s"`, variantMacro))
	}
	if partitionMacro != "" {
		args = append(args, "-DARDUINO_PARTITION_"+partitionMacro)
	}
	// ──────────────────────────────────────────────────────────────────────

	args = append(args,
		"-Os",
		"-ffunction-sections",
		"-fdata-sections",
	)

	// ── Warning level ─────────────────────────────────────────────────────
	switch bf.warnings {
	case "none":
		args = append(args, "-w")
	case "more":
		args = append(args, "-Wall", "-Wextra")
	case "all":
		args = append(args, "-Wall", "-Wextra", "-Wpedantic")
	default:
		args = append(args, "-Wall")
	}

	// ── Language-specific flags ───────────────────────────────────────────
	if ext == ".cpp" {
		args = append(args, "-std=gnu++17", "-fpermissive", "-fno-exceptions",
			"-fno-threadsafe-statics", "-Wno-error=narrowing")
	} else if ext == ".c" {
		args = append(args, "-std=gnu17")
	}

	// ── Core + variant include paths ──────────────────────────────────────
	for _, inc := range bf.coreInc {
		args = append(args, "-I", inc)
	}
	if extraIncDir != "" {
		args = append(args, "-I", extraIncDir)
	}

	// ── Sanitize unresolved placeholders ──────────────────────────────────
	clean := make([]string, 0, len(args))
	for i := 0; i < len(args); i++ {
		a := args[i]
		if strings.Contains(a, "libs.path") || strings.Contains(a, "{") || strings.Contains(a, "}") {
			continue
		}
		if strings.HasPrefix(a, "@") {
			f := strings.TrimPrefix(a, "@")
			if _, err := os.Stat(f); err != nil {
				continue
			}
		}
		clean = append(clean, a)
	}
	args = clean

	// ── Extra flags from platform.txt (non-ESP32 only) ────────────────────
	if rb.Architecture != "esp32" {
		if extra := rb.GetProp("compiler.c.extra_flags"); extra != "" {
			args = append(args, expandPlatformFlags(extra, rb, bf.sdkPath)...)
		}
		if ext == ".cpp" {
			if extra := rb.GetProp("compiler.cpp.extra_flags"); extra != "" {
				args = append(args, expandPlatformFlags(extra, rb, bf.sdkPath)...)
			}
		}
	}

	return args
}

// expandPlatformFlags expands a platform.txt flag string into a []string,
// substituting placeholders and stripping unresolved ones.
func expandPlatformFlags(flags string, rb *boards.ResolvedBoard, sdkPath string) []string {
	s := flags

	if sdkPath != "" {
		s = strings.ReplaceAll(s, "{compiler.sdk.path}", sdkPath)
	}
	s = strings.ReplaceAll(s, "{build.opt.flags}", rb.GetProp("build.opt.flags"))
	if rb != nil {
		s = strings.ReplaceAll(s, "{runtime.platform.path}", rb.PlatformPath)
	}

	for strings.Contains(s, "{") {
		start := strings.Index(s, "{")
		end := strings.Index(s[start:], "}")
		if end < 0 {
			break
		}
		s = s[:start] + s[start+end+1:]
	}

	splitArgs := func(input string) []string {
		var res []string
		var cur strings.Builder
		inQuote := rune(0)
		escaped := false
		for _, r := range input {
			if escaped {
				cur.WriteRune(r)
				escaped = false
				continue
			}
			if r == '\\' {
				escaped = true
				continue
			}
			if inQuote != 0 {
				if r == inQuote {
					inQuote = 0
					continue
				}
				cur.WriteRune(r)
				continue
			}
			if r == '\'' || r == '"' {
				inQuote = r
				continue
			}
			if r == ' ' || r == '\t' || r == '\n' || r == '\r' {
				if cur.Len() > 0 {
					res = append(res, cur.String())
					cur.Reset()
				}
				continue
			}
			cur.WriteRune(r)
		}
		if cur.Len() > 0 {
			res = append(res, cur.String())
		}
		return res
	}

	var out []string
	toks := splitArgs(s)
	for i := 0; i < len(toks); i++ {
		tok := toks[i]
		if strings.HasPrefix(tok, "@") {
			fpath := strings.TrimPrefix(tok, "@")
			if data, err := os.ReadFile(fpath); err == nil {
				sub := splitArgs(string(data))
				newToks := make([]string, 0, len(toks)+len(sub))
				newToks = append(newToks, toks[:i]...)
				newToks = append(newToks, sub...)
				if i+1 < len(toks) {
					newToks = append(newToks, toks[i+1:]...)
				}
				toks = newToks
				i--
				continue
			}
			continue
		}

		if tok == "-iwithprefixbefore" && i+1 < len(toks) {
			next := toks[i+1]
			if sdkPath != "" {
				out = append(out, "-isystem", filepath.Join(sdkPath, next))
			} else {
				out = append(out, "-I", next)
			}
			i++
			continue
		}

		out = append(out, tok)
	}

	return out
}

// ── runCC / helpers ───────────────────────────────────────────────

// unitKey builds a stable content-address key for one translation unit:
// source identity, flags (volatile build-dir paths normalized by the actual
// build dir), toolchain and compiler identity, and the cache schema version.
// Only inputs that would change the produced .o participate — every
// remaining flag is toolchain/SDK identity and any change there compiles
// (and caches) a fresh object instead of flashing a stale one.
func (c *Compiler) unitKey(srcPath string, args []string, compilerBin string) (string, error) {
	srcSum, err := hashFileContents(srcPath)
	if err != nil {
		return "", err
	}
	fp := sha256.New()
	fmt.Fprintf(fp, "src|%s|%s", srcPath, srcSum)
	if tc := c.resolvedToolchain; tc != nil {
		AppendFileMeta(fp, tc.GCC)
		AppendFileMeta(fp, tc.GCCCPP)
		AppendFileMeta(fp, tc.AR)
	}
	AppendFileMeta(fp, compilerBin)
	fingerprint := hex.EncodeToString(fp.Sum(nil))

	// buildDirVolatileDirs prefixes cover the stock temp-dir scheme, but a
	// stale scheduler name, a symlinked /tmp, or an unusual TEMP would break
	// the `strings.Contains` match — so also normalize the live build dir
	// itself, discovered as the directory of any "-o" output in argv.
	volatile := append([]string{}, buildDirVolatileDirs...)
	volatile = append(volatile, buildDirFromArgs(args)...)

	norm := NormalizeFlags(args, volatile...)
	sorted := make([]string, len(norm))
	copy(sorted, norm)
	sort.Strings(sorted)

	h := sha256.New()
	fmt.Fprintf(h, "unit|v%d", BuildCacheSchemaVersion)
	fmt.Fprintf(h, "|%s", fingerprint)
	for _, a := range sorted {
		h.Write([]byte("|"))
		h.Write([]byte(a))
	}
	return hex.EncodeToString(h.Sum(nil))[:40], nil
}

// buildDirFromArgs extracts the "-o <obj>" argument's parent directory from
// the compiler argv so it can be normalized out of cache keys. It returns
// the full dir path plus every ancestor down to (and including) the build
// root, so NormalizeFlags' longest-first rule collapses nested references
// (e.g. "<build>/sketch") entirely to the {BUILD_DIR} token.
func buildDirFromArgs(args []string) []string {
	for i, a := range args {
		if a == "-o" && i+1 < len(args) {
			var dirs []string
			for d := filepath.Dir(args[i+1]); d != "." && d != "/" && len(d) > 4; {
				dirs = append(dirs, d)
				parent := filepath.Dir(d)
				if parent == d || len(parent) < 4 {
					break
				}
				d = parent
			}
			return dirs
		}
	}
	return nil
}

// runCC compiles one translation unit, serving and storing the resulting
// object file through the build cache. When caching is disabled (or keying
// fails) it degrades to a plain compile.
func (c *Compiler) runCC(tc *Toolchain, srcPath string, args []string) error {
	ext := strings.ToLower(filepath.Ext(srcPath))
	compiler := tc.GCC
	if ext == ".cpp" {
		compiler = tc.GCCCPP
	}

	finalArgs := make([]string, 0, len(args))
	for _, a := range args {
		if strings.Contains(a, "libs.path") || strings.Contains(a, "@-") ||
			strings.Contains(a, "-I-libs") || strings.Contains(a, "{") ||
			strings.Contains(a, "}") {
			continue
		}
		if strings.HasPrefix(a, "@") {
			f := strings.TrimPrefix(a, "@")
			if _, err := os.Stat(f); err != nil {
				continue
			}
		}
		finalArgs = append(finalArgs, a)
	}

	// Extract "-o <obj>" so we know what the compiler will produce.
	objPath := ""
	for i, a := range finalArgs {
		if a == "-o" && i+1 < len(finalArgs) {
			objPath = finalArgs[i+1]
			break
		}
	}

	// Compile-commands capture: record the exact argv BEFORE the cache lookup
	// so a fully-cached rebuild still exports every translation unit.
	if c.ccDir != "" {
		c.cc = append(c.cc, CompileCommand{
			Directory: c.ccDir,
			Command:   compiler + " " + shellJoin(finalArgs),
			File:      srcPath,
		})
	}

	// ── Object-level cache (P4a): reuse prebuilt .o when key matches ──
	cache := c.cacheOrDefault()
	var key string
	if cache != nil && objPath != "" {
		k, err := c.unitKey(srcPath, finalArgs, compiler)
		if err != nil {
			c.logf("  [debug] cache key %s: %v", filepath.Base(srcPath), err)
		} else {
			key = k
			if hit := cache.GetObject(key); hit != "" {
				if copyErr := copyFile(hit, objPath); copyErr == nil {
					c.logf("  [cache] hit %s", filepath.Base(srcPath))
					return nil
				}
				// Copy failed — fall through to a real compile.
			}
		}
	}

	if c.onOutput != nil {
		c.logf("[debug-cmd] %s %s", compiler, strings.Join(finalArgs, " "))
	} else {
		fmt.Fprintln(os.Stderr, "[debug-cmd]", compiler, strings.Join(finalArgs, " "))
	}

	cmd := exec.CommandContext(c.ctx, compiler, finalArgs...)
	out, err := cmd.CombinedOutput()
	if err != nil {
		return fmt.Errorf("compile %s:\n%s", filepath.Base(srcPath), string(out))
	}
	if len(out) > 0 && c.onOutput != nil {
		c.log(string(out))
	}

	// Best-effort cache store.
	if cache != nil && key != "" {
		if _, putErr := cache.PutObject(key, objPath); putErr != nil {
			c.logf("  [debug] cache put %s: %v", filepath.Base(srcPath), putErr)
		}
	}
	return nil
}

// shellJoin joins argv into a single command line with POSIX-style quoting
// (compile_commands.json "command" form; "arguments" form avoids this but
// clangd handles both).
func shellJoin(args []string) string {
	quoted := make([]string, len(args))
	for i, a := range args {
		if strings.ContainsAny(a, " \t\"'\\$") {
			quoted[i] = "'" + strings.ReplaceAll(a, "'", `'\''`) + "'"
		} else {
			quoted[i] = a
		}
	}
	return strings.Join(quoted, " ")
}

// writeCompileCommands serializes the captured translation units into
// <buildDir>/compile_commands.json (clangd-compatible).
func (c *Compiler) writeCompileCommands(buildDir string) (string, error) {
	if len(c.cc) == 0 {
		return "", fmt.Errorf("no translation units captured")
	}
	data, err := json.MarshalIndent(c.cc, "", "  ")
	if err != nil {
		return "", err
	}
	out := filepath.Join(buildDir, "compile_commands.json")
	if err := os.WriteFile(out, data, 0o644); err != nil {
		return "", err
	}
	c.cc = nil
	return out, nil
}

// snapshotCC returns a copy of the captured compile commands (for persisting
// alongside a cached core archive).
func snapshotCC(c *Compiler) []CompileCommand {
	out := make([]CompileCommand, len(c.cc))
	copy(out, c.cc)
	return out
}

// mergeCC prepends persisted core translation units to the live capture so
// compile_commands.json remains complete across warm-core builds.
func mergeCC(c *Compiler, tus []CompileCommand) {
	if len(tus) == 0 {
		return
	}
	seen := make(map[string]bool)
	for _, t := range c.cc {
		seen[t.File] = true
	}
	for _, t := range tus {
		if !seen[t.File] {
			c.cc = append(c.cc, t)
		}
	}
}

// coreCacheKey builds a stable key for the compiled core archive: every core
// source file's content hash (path included so renames invalidate), the
// variant, platform.txt/boards.txt/programmers.txt metadata, and the exact
// preprocessor flag list. Replaces the old 24-hour ModTime heuristic, which
// could silently reuse a stale core after a package update.
func (c *Compiler) coreCacheKey(rb *boards.ResolvedBoard, tc *Toolchain, bf *BuildFlags) (string, error) {
	corePath := filepath.Join(rb.PlatformPath, "cores", rb.GetProp("build.core"))
	h := sha256.New()
	fmt.Fprintf(h, "core|v%d", BuildCacheSchemaVersion)
	fmt.Fprintf(h, "|arch=%s|core=%s|variant=%s", rb.Architecture, rb.GetProp("build.core"), rb.GetProp("build.variant"))

	var walkErr error
	err := filepath.Walk(corePath, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			walkErr = err
			return err
		}
		if info.IsDir() {
			return nil
		}
		ext := strings.ToLower(filepath.Ext(path))
		switch ext {
		case ".c", ".cpp", ".h", ".hpp", ".S", ".s", ".ino":
			sum, herr := hashFileContents(path)
			if herr != nil {
				walkErr = herr
				return herr
			}
			fmt.Fprintf(h, "|%s:%s", path, sum)
		}
		return nil
	})
	if walkErr != nil {
		return "", walkErr
	}
	if err != nil {
		return "", err
	}

	if vp := filepath.Join(rb.PlatformPath, "variants", rb.GetProp("build.variant")); dirExists(vp) {
		AppendFileMeta(h, vp) // pins_arduino.h lives directly in the variant dir
	}
	AppendFileMeta(h, filepath.Join(rb.PlatformPath, "platform.txt"))
	AppendFileMeta(h, filepath.Join(rb.PlatformPath, "boards.txt"))
	AppendFileMeta(h, filepath.Join(rb.PlatformPath, "programmers.txt"))
	AppendFileMeta(h, tc.GCC)
	AppendFileMeta(h, tc.GCCCPP)
	AppendFileMeta(h, tc.AR)

	// The generated sdkconfig.h feeds into every core/library compile (its
	// CONFIG_* macros gate IDF/LwIP/FreeRTOS code paths through sdkconfig.h
	// content, not its path or name), so we hash its CONTENT while ignoring
	// its volatile location/comments. Fresh temp dirs every run would
	// otherwise invalidate the core archive every single time.
	if bf.buildDir != "" {
		hashGeneratedHeader(h, filepath.Join(bf.buildDir, "sdkconfig.h"))
	}

	// Normalize EVERY volatile build-dir reference out of the preprocessor
	// flags — the prefix list alone is NOT enough: "/tmp/companion_build_"
	// replacement leaves the random per-run suffix alive in the key, which
	// invalidated the core archive on every invocation. bf.buildDir (the
	// exact directory referenced by the flags) must be in the list too.
	vol := append([]string{}, buildDirVolatileDirs...)
	if bf.buildDir != "" {
		vol = append(vol, bf.buildDir)
	}
	sorted := NormalizeFlags(bf.preprocessorFlags, vol...)
	sort.Strings(sorted)
	for _, f := range sorted {
		h.Write([]byte("|"))
		h.Write([]byte(f))
	}
	return hex.EncodeToString(h.Sum(nil))[:40], nil
}

func (c *Compiler) archiveObjects(tc *Toolchain, objs []string, libPath string) error {
	for _, obj := range objs {
		cmd := exec.CommandContext(c.ctx, tc.AR, "rcs", libPath, obj)
		if out, err := cmd.CombinedOutput(); err != nil {
			return fmt.Errorf("ar %s: %s\n%s", filepath.Base(obj), err, out)
		}
	}
	return nil
}

// ── Helpers ───────────────────────────────────────────────────────

func copyFile(src, dst string) error {
	in, err := os.Open(src)
	if err != nil {
		return err
	}
	defer in.Close()
	out, err := os.Create(dst)
	if err != nil {
		return err
	}
	defer out.Close()
	_, err = io.Copy(out, in)
	return err
}

func fileExists(path string) bool {
	if info, err := os.Stat(path); err == nil && !info.IsDir() {
		return true
	}
	return false
}
