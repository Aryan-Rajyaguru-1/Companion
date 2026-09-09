package cmd

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"

	"github.com/companion-ide/companion-cli/internal/boards"
	"github.com/companion-ide/companion-cli/internal/compiler"
	"github.com/companion-ide/companion-cli/internal/config"
	"github.com/companion-ide/companion-cli/internal/sketch"
	"github.com/spf13/cobra"
)

// profileLibDirs returns pinned library paths from a resolved profile.
func profileLibDirs(rp *resolvedProfile) []string {
	if rp == nil {
		return nil
	}
	return rp.LibDirs
}

// ── JSON diagnostic types (#9) ────────────────────────────────
//
// When --json is passed, companion compile emits one JSON line per diagnostic
// after the normal human-readable output.  companion-cli.js in the IDE filters
// these lines (they match JSON_DIAG_RE) and routes them to the structured error
// parser instead of the console view.
//
// Line shape:
//   {"type":"diagnostic","file":"/path/sketch.ino","line":15,"col":3,"severity":"error","message":"..."}

type DiagnosticLine struct {
	Type     string `json:"type"` // always "diagnostic"
	File     string `json:"file"`
	Line     int    `json:"line"`
	Col      int    `json:"col"`
	Severity string `json:"severity"` // "error" | "warning" | "note"
	Message  string `json:"message"`
}

// GCC regex patterns (same ones used by error-parser.js in the IDE)
var (
	gccFullRE  = regexp.MustCompile(`^(.+?):(\d+):(\d+):\s+(error|warning|note|fatal error):\s+(.+)$`)
	gccNoColRE = regexp.MustCompile(`^(.+?):(\d+):\s+(error|warning|note|fatal error):\s+(.+)$`)
	ansiRE     = regexp.MustCompile(`\x1b\[[0-9;]*m`)
)

// emitDiagnostics parses rawOutput for GCC error lines and prints one
// JSON object per unique diagnostic to stdout.
func emitDiagnostics(rawOutput string) {
	seen := map[string]bool{}
	for _, line := range splitLines(rawOutput) {
		line = ansiRE.ReplaceAllString(line, "")
		if line == "" {
			continue
		}
		var diag *DiagnosticLine
		if m := gccFullRE.FindStringSubmatch(line); m != nil {
			ln, _ := strconv.Atoi(m[2])
			col, _ := strconv.Atoi(m[3])
			diag = &DiagnosticLine{
				Type: "diagnostic", File: m[1], Line: ln, Col: col,
				Severity: normSeverity(m[4]), Message: trimSpace(m[5]),
			}
		} else if m := gccNoColRE.FindStringSubmatch(line); m != nil {
			ln, _ := strconv.Atoi(m[2])
			diag = &DiagnosticLine{
				Type: "diagnostic", File: m[1], Line: ln, Col: 1,
				Severity: normSeverity(m[3]), Message: trimSpace(m[4]),
			}
		}
		if diag == nil {
			continue
		}
		key := fmt.Sprintf("%s:%d:%d:%s:%s", diag.File, diag.Line, diag.Col, diag.Severity, diag.Message)
		if seen[key] {
			continue
		}
		seen[key] = true
		if b, err := json.Marshal(diag); err == nil {
			fmt.Println(string(b))
		}
	}
}

func normSeverity(s string) string {
	switch s {
	case "fatal error", "error":
		return "error"
	case "warning":
		return "warning"
	default:
		return "note"
	}
}

// ── newCompileCmd ─────────────────────────────────────────────

func newCompileCmd() *cobra.Command {
	var (
		fqbn       string
		warnings   string
		exportBin  bool
		buildDir   string
		clean      bool
		jsonOut    bool // #9
		profileNam string
		exportCC   bool
	)

	cmd := &cobra.Command{
		Use:   "compile [sketch-dir]",
		Short: "Compile an Arduino sketch",
		Long: `Compile an Arduino sketch for the specified board (FQBN).

The Fully Qualified Board Name (FQBN) format is:
  vendor:architecture:board_id

Examples:
  arduino:avr:uno
  esp32:esp32:esp32
  STMicroelectronics:stm32:Nucleo_64`,

		Args: cobra.MaximumNArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			sketchDir := "."
			if len(args) > 0 {
				sketchDir = args[0]
			}
			sketchDir, _ = filepath.Abs(sketchDir)

			if _, err := os.Stat(sketchDir); err != nil {
				return fmt.Errorf("sketch directory not found: %s", sketchDir)
			}

			cfg, cfgPath, err := config.Load(globalFlags.ConfigFile)
			if err != nil {
				return fmt.Errorf("config: %w", err)
			}
			_ = cfgPath

			if err := config.EnsureDirs(cfg); err != nil {
				return err
			}

			// ── Profile resolution: --profile > default profile > legacy fqbn
			rp, profErr := applyProfile(cfg, sketchDir, profileNam)
			if profErr != nil {
				return profErr
			}
			if rp != nil && rp.FQBN != "" && !cmd.Flags().Changed("fqbn") {
				fqbn = rp.FQBN
			}

			if fqbn == "" {
				fqbn = cfg.Bridge.MCU
				if f := readSketchFQBN(sketchDir); f != "" {
					fqbn = f
				}
			}
			if fqbn == "" {
				return fmt.Errorf("FQBN required — use --fqbn flag or set in sketch.yaml\n" +
					"Example: companion compile --fqbn arduino:avr:uno")
			}

			if warnings == "" {
				warnings = cfg.Compiler.Warnings
			}

			if clean && buildDir != "" {
				printInfo(fmt.Sprintf("Cleaning build dir: %s", buildDir))
				os.RemoveAll(buildDir)
			}

			printInfo(fmt.Sprintf("Compiling %s for %s",
				colorBold(filepath.Base(sketchDir)), colorTeal(fqbn)))

			// Capture all output so we can run the JSON diagnostic pass over it
			var rawOutput string

			bm := boards.NewManager(cfg)
			cmp := compiler.New(cfg, bm, func(s string) {
				fmt.Println(s)
				rawOutput += s + "\n"
			})
			cmp.SetPlugins(pluginRegistry(cfg))
			if cfg.Cache.Enabled {
				if bc, err := compiler.NewBuildCache(compiler.DefaultCacheDir(cfg.Directories.Data)); err == nil {
					cmp.SetCache(bc)
					defer bc.Evict()
				}
			}

			result, buildErr := cmp.Build(compiler.Options{
				SketchDir:              sketchDir,
				FQBN:                   fqbn,
				BuildDir:               buildDir,
				Warnings:               warnings,
				Verbose:                globalFlags.Verbose || cfg.Compiler.Verbose,
				ExportBinary:           exportBin,
				LibraryDirs:            profileLibDirs(rp),
				CaptureCompileCommands: exportCC,
			})

			// #9 — emit structured JSON diagnostics after human-readable output.
			// companion-cli.js in the IDE recognises these lines via JSON_DIAG_RE
			// and routes them to parseJsonDiagnostics() instead of the console.
			if jsonOut {
				emitDiagnostics(rawOutput)
			}

			if buildErr != nil {
				printError(buildErr.Error())
				return fmt.Errorf("compilation failed")
			}

			printSuccess(fmt.Sprintf("Compiled in %.1fs → %s",
				result.Duration.Seconds(), colorCyan(result.BinaryPath)))
			return nil
		},
	}

	cmd.Flags().StringVar(&fqbn, "fqbn", "",
		"Fully Qualified Board Name (e.g. arduino:avr:uno)")
	cmd.Flags().StringVar(&warnings, "warnings", "",
		"Compiler warnings: none | default | more | all (default from config)")
	cmd.Flags().BoolVar(&exportBin, "export-binaries", false,
		"Copy binary to <sketch>/build/<fqbn>/ after compilation")
	cmd.Flags().StringVar(&buildDir, "build-dir", "",
		"Custom build directory (default: system temp)")
	cmd.Flags().BoolVar(&clean, "clean", false,
		"Clean build directory before compiling")
	// Profile support: board + pinned libraries from sketch.yaml
	cmd.Flags().StringVar(&profileNam, "profile", "",
		"Build profile from sketch.yaml (board + pinned libraries)")
	// #9 JSON diagnostic output
	cmd.Flags().BoolVar(&jsonOut, "json", false,
		"Emit structured JSON diagnostic lines (used by Companion IDE for red squiggles)")
	// compile_commands.json export (Arduino-cli #849 parity)
	cmd.Flags().BoolVar(&exportCC, "export-compile-commands", false,
		"Write clangd-compatible compile_commands.json into the build directory")

	return cmd
}

// readSketchFQBN reads the FQBN from a sketch.yaml file if present.
func readSketchFQBN(sketchDir string) string {
	data, err := os.ReadFile(filepath.Join(sketchDir, "sketch.yaml"))
	if err != nil {
		return ""
	}
	for _, line := range splitLines(string(data)) {
		if len(line) > 5 && line[:5] == "fqbn:" {
			return trimSpace(line[5:])
		}
	}
	return ""
}

// resolvedProfile carries everything a profile contributes to compile/upload.
type resolvedProfile struct {
	FQBN    string
	Port    string
	Baud    uint32
	MCU     string
	LibDirs []string // absolute paths of pinned installed libraries
	OTA     bool     // sketch.ota — prefer ArduinoOTA push over bridge
}

// applyProfile loads sketch.yaml, resolves the requested profile, verifies
// that every pinned library is actually installed, and returns what the
// build should use. Returns nil when no profile applies.
func applyProfile(cfg *config.Config, sketchDir, profileName string) (*resolvedProfile, error) {
	sf, err := sketch.Load(sketchDir)
	if err != nil {
		return nil, err
	}
	p, err := sf.Resolve(profileName)
	if err != nil {
		return nil, err
	}
	if p == nil {
		return nil, nil
	}

	rp := &resolvedProfile{FQBN: p.FQBN, Port: p.Port, Baud: p.Baud, MCU: p.MCU, OTA: p.OTA}

	// Resolve pinned libraries against the user libraries directory
	// (case-insensitive match on directory name).
	for _, lib := range p.Libraries {
		name := lib
		if i := strings.IndexByte(lib, '@'); i >= 0 {
			name = lib[:i]
		}
		dir, err := findInstalledLibrary(cfg.LibrariesDir(), name)
		if err != nil {
			return nil, fmt.Errorf("profile library %s is not installed — run: companion lib install %q",
				colorTeal(lib), name)
		}
		rp.LibDirs = append(rp.LibDirs, dir)
	}
	return rp, nil
}

// findInstalledLibrary locates an installed library directory by name,
// falling back to a case-insensitive match.
func findInstalledLibrary(libRoot, name string) (string, error) {
	direct := filepath.Join(libRoot, name)
	if info, err := os.Stat(direct); err == nil && info.IsDir() {
		return direct, nil
	}
	entries, err := os.ReadDir(libRoot)
	if err != nil {
		return "", fmt.Errorf("libraries dir not readable")
	}
	for _, e := range entries {
		if e.IsDir() && strings.EqualFold(e.Name(), name) {
			return filepath.Join(libRoot, e.Name()), nil
		}
	}
	return "", fmt.Errorf("library not found")
}

func splitLines(s string) []string {
	var lines []string
	start := 0
	for i, c := range s {
		if c == '\n' {
			lines = append(lines, s[start:i])
			start = i + 1
		}
	}
	if start < len(s) {
		lines = append(lines, s[start:])
	}
	return lines
}

func trimSpace(s string) string {
	i, j := 0, len(s)-1
	for i <= j && (s[i] == ' ' || s[i] == '\t' || s[i] == '\r') {
		i++
	}
	for j >= i && (s[j] == ' ' || s[j] == '\t' || s[j] == '\r') {
		j--
	}
	return s[i : j+1]
}
