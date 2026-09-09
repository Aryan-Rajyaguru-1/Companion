// Package plugins defines abstract interfaces for extending Companion CLI.
//
// P4 Plugin System — pattern from arduino-ide-main's contribution system.
//
// Design goals:
//   - Hard-coded features can be extracted to plugins over time
//   - Third-party tools (openocd, esptool, etc.) integrate cleanly
//   - Each plugin registers capabilities; the IDE queries them at runtime
//
// Plugin types:
//   UploaderPlugin    — custom upload strategies (OTA, JTAG, etc.)
//   CompilerPlugin    — pre/post-process hooks around compilation
//   BoardPlugin       — provides additional board definitions
//   DiagnosticPlugin  — custom lint rules on top of GCC output
//
// Plugins are discovered from ~/.companion-cli/plugins/ (Go plugin .so files)
// and from a built-in registry for first-party extensions.
//
// NOTE: Full dynamic .so loading is gated on Go build tags. The interfaces
// here are stable — first-party implementations live in this package.
package plugins

import (
	"context"
	"fmt"
	"io"
)

// ── Core plugin interface ─────────────────────────────────────────

// Plugin is the base interface every plugin must implement.
type Plugin interface {
	// ID returns a unique, stable identifier. e.g. "companion.uploader.ota"
	ID() string
	// Name returns a human-readable display name.
	Name() string
	// Version returns the plugin semver string.
	Version() string
	// Init is called once at registration time with plugin configuration.
	Init(cfg PluginConfig) error
}

// PluginConfig carries runtime configuration to plugins during Init().
type PluginConfig struct {
	// DataDir is the companion-cli data directory.
	DataDir string
	// Options contains plugin-specific key/value pairs from config.yaml.
	Options map[string]string
}

// ── Uploader plugin ───────────────────────────────────────────────

// UploaderPlugin implements a custom upload strategy.
// Pattern: OTA (ArduinoOTA), JTAG (OpenOCD), UART (avrdude), WiFi (bridge).
type UploaderPlugin interface {
	Plugin

	// SupportsFQBN reports whether this uploader can handle the given FQBN.
	SupportsFQBN(fqbn string) bool

	// Upload performs the upload and writes progress to w.
	// ctx is cancelled if the user aborts.
	Upload(ctx context.Context, opts UploadOptions, w io.Writer) error
}

// UploadOptions carries the parameters for an upload operation.
type UploadOptions struct {
	BinaryPath string
	FQBN       string
	MCU        string
	Host       string
	Port       int
	Baud       int
	Verbose    bool
	ExtraFlags []string
}

// ── Compiler plugin ───────────────────────────────────────────────

// CompilerPlugin provides hooks that run before and after compilation.
// Pattern: clang-format pre-pass, custom linker flags, size analysis post-pass.
type CompilerPlugin interface {
	Plugin

	// PreCompile runs before the compiler starts.
	// Returning an error aborts the compile.
	PreCompile(ctx context.Context, opts CompileHookOptions) error

	// PostCompile runs after a successful compilation.
	// It receives the binary path and can modify output or run analysis.
	PostCompile(ctx context.Context, opts CompileHookOptions, binaryPath string) error
}

// CompileHookOptions carries context for compiler plugin hooks.
type CompileHookOptions struct {
	SketchDir string
	FQBN      string
	BuildDir  string
	Verbose   bool
}

// ── Board plugin ──────────────────────────────────────────────────

// BoardPlugin provides additional board definitions beyond the installed cores.
// Pattern: custom hardware directories, third-party board packages.
type BoardPlugin interface {
	Plugin

	// ListBoards returns the boards provided by this plugin.
	ListBoards() []PluginBoard
}

// PluginBoard represents a board entry from a plugin.
type PluginBoard struct {
	FQBN        string
	Name        string
	Description string
	Platform    string
	MCUFamily   string
}

// ── Diagnostic plugin ─────────────────────────────────────────────

// DiagnosticPlugin adds custom lint rules on top of GCC compiler output.
// Pattern: MISRA-C checks, Arduino-specific anti-patterns, memory warnings.
type DiagnosticPlugin interface {
	Plugin

	// Analyze receives the raw compiler output and returns additional
	// diagnostics to surface in the IDE alongside GCC errors.
	Analyze(ctx context.Context, output string, fqbn string) ([]PluginDiagnostic, error)
}

// PluginDiagnostic is a diagnostic entry from a plugin.
type PluginDiagnostic struct {
	File     string
	Line     int
	Column   int
	Severity string // "error" | "warning" | "note"
	Code     string // Plugin-specific code, e.g. "MISRA-C:2004 rule 8.7"
	Message  string
	URL      string // Optional docs link
}

// ── Registry ──────────────────────────────────────────────────────

// Registry manages all registered plugins.
type Registry struct {
	uploaders   []UploaderPlugin
	compilers   []CompilerPlugin
	boards      []BoardPlugin
	diagnostics []DiagnosticPlugin
	generic     []Plugin // plugins without a capability interface
}

// NewRegistry creates an empty plugin registry.
func NewRegistry() *Registry { return &Registry{} }

// RegisterUploader registers an uploader plugin.
func (r *Registry) RegisterUploader(p UploaderPlugin) { r.uploaders = append(r.uploaders, p) }

// RegisterCompiler registers a compiler hook plugin.
func (r *Registry) RegisterCompiler(p CompilerPlugin) { r.compilers = append(r.compilers, p) }

// RegisterBoard registers a board provider plugin.
func (r *Registry) RegisterBoard(p BoardPlugin) { r.boards = append(r.boards, p) }

// RegisterDiagnostic registers a diagnostic plugin.
func (r *Registry) RegisterDiagnostic(p DiagnosticPlugin) { r.diagnostics = append(r.diagnostics, p) }

// UploaderFor returns the first uploader that supports the given FQBN,
// or nil if none is registered.
func (r *Registry) UploaderFor(fqbn string) UploaderPlugin {
	for _, u := range r.uploaders {
		if u.SupportsFQBN(fqbn) {
			return u
		}
	}
	return nil
}

// AllBoards returns all boards from all registered board plugins.
func (r *Registry) AllBoards() []PluginBoard {
	var all []PluginBoard
	for _, bp := range r.boards {
		all = append(all, bp.ListBoards()...)
	}
	return all
}

// RunPreCompile calls PreCompile on all compiler plugins in registration order.
func (r *Registry) RunPreCompile(ctx context.Context, opts CompileHookOptions) error {
	for _, cp := range r.compilers {
		if err := cp.PreCompile(ctx, opts); err != nil {
			return err
		}
	}
	return nil
}

// RunPostCompile calls PostCompile on all compiler plugins in registration order.
func (r *Registry) RunPostCompile(ctx context.Context, opts CompileHookOptions, binaryPath string) error {
	for _, cp := range r.compilers {
		if err := cp.PostCompile(ctx, opts, binaryPath); err != nil {
			return err
		}
	}
	return nil
}

// RunDiagnostics collects diagnostics from all registered diagnostic plugins.
func (r *Registry) RunDiagnostics(ctx context.Context, output, fqbn string) []PluginDiagnostic {
	var all []PluginDiagnostic
	for _, dp := range r.diagnostics {
		diags, _ := dp.Analyze(ctx, output, fqbn)
		all = append(all, diags...)
	}
	return all
}

// Global is the default plugin registry used by the CLI.
var Global = NewRegistry()

// ── Discovery / loading ───────────────────────────────────────────

// LoadAll builds a fresh registry containing first-party builtins plus any
// dynamic plugins (.so files) found under pluginDir. It returns the registry
// and any non-fatal load errors (a bad .so must never break the CLI).
func LoadAll(pluginDir string) (*Registry, []error) {
	r := NewRegistry()
	var errs []error

	for _, b := range builtins() {
		if err := b.Init(PluginConfig{DataDir: pluginDir}); err != nil {
			errs = append(errs, fmt.Errorf("init builtin %s: %w", b.ID(), err))
			continue
		}
		r.Register(b)
	}

	dyn, derrs := loadDynamic(pluginDir)
	errs = append(errs, derrs...)
	for _, p := range dyn {
		if err := p.Init(PluginConfig{DataDir: pluginDir}); err != nil {
			errs = append(errs, fmt.Errorf("init %s: %w", p.ID(), err))
			continue
		}
		r.Register(p)
	}
	return r, errs
}

// Register type-switches a plugin into the matching capability slots.
// A plugin implementing several interfaces is registered into each.
func (r *Registry) Register(p Plugin) {
	matched := false
	if u, ok := p.(UploaderPlugin); ok {
		r.RegisterUploader(u)
		matched = true
	}
	if c, ok := p.(CompilerPlugin); ok {
		r.RegisterCompiler(c)
		matched = true
	}
	if b, ok := p.(BoardPlugin); ok {
		r.RegisterBoard(b)
		matched = true
	}
	if d, ok := p.(DiagnosticPlugin); ok {
		r.RegisterDiagnostic(d)
		matched = true
	}
	if !matched {
		r.generic = append(r.generic, p)
	}
}

// Entry pairs a plugin with its kind label for listing.
type Entry struct {
	Kind   string // "uploader" | "compiler" | "board" | "diagnostic" | "plugin"
	Plugin Plugin
}

// Entries returns every registered plugin with its capability label.
func (r *Registry) Entries() []Entry {
	var out []Entry
	for _, p := range r.uploaders {
		out = append(out, Entry{"uploader", p})
	}
	for _, p := range r.compilers {
		out = append(out, Entry{"compiler", p})
	}
	for _, p := range r.boards {
		out = append(out, Entry{"board", p})
	}
	for _, p := range r.diagnostics {
		out = append(out, Entry{"diagnostic", p})
	}
	for _, p := range r.generic {
		out = append(out, Entry{"plugin", p})
	}
	return out
}

// Plugin returns the registered plugin with the given ID, or nil.
func (r *Registry) Plugin(id string) Plugin {
	for _, e := range r.Entries() {
		if e.Plugin.ID() == id {
			return e.Plugin
		}
	}
	return nil
}

// Compilers exposes compiler-hook plugins (used by the build pipeline).
func (r *Registry) Compilers() []CompilerPlugin {
	return r.compilers
}

// Diagnostics exposes diagnostic plugins (used by the JSON output path).
func (r *Registry) Diagnostics() []DiagnosticPlugin {
	return r.diagnostics
}

// Boards exposes board-provider plugins.
func (r *Registry) Boards() []BoardPlugin {
	return r.boards
}
