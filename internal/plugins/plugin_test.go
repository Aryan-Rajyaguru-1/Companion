package plugins

import (
	"context"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// fakeCompilePlugin is a first-party-style plugin used by the tests.
type fakeCompilePlugin struct{}

func (*fakeCompilePlugin) ID() string      { return "test.compiler.fake" }
func (*fakeCompilePlugin) Name() string    { return "Fake Compiler Plugin" }
func (*fakeCompilePlugin) Version() string { return "0.0.1" }
func (*fakeCompilePlugin) Init(cfg PluginConfig) error {
	return nil
}
func (*fakeCompilePlugin) PreCompile(ctx context.Context, opts CompileHookOptions) error { return nil }
func (*fakeCompilePlugin) PostCompile(ctx context.Context, opts CompileHookOptions, binaryPath string) error {
	return nil
}

// testAnalyzer implements a DiagnosticPlugin.
type testAnalyzer struct{ failure string }

func (*testAnalyzer) ID() string      { return "test.diag.analyzer" }
func (*testAnalyzer) Name() string    { return "Test Analyzer" }
func (*testAnalyzer) Version() string { return "1.0.0" }
func (*testAnalyzer) Init(cfg PluginConfig) error {
	return nil
}
func (a *testAnalyzer) Analyze(ctx context.Context, output, fqbn string) ([]PluginDiagnostic, error) {
	if a.failure == "" {
		return nil, nil
	}
	return []PluginDiagnostic{{File: "sketch.ino", Line: 1, Severity: "error", Code: a.failure, Message: "found"}}, nil
}

func TestRegisterCategorizes(t *testing.T) {
	r := NewRegistry()
	r.Register(&fakeCompilePlugin{})
	r.Register(&testAnalyzer{})

	byKind := map[string]int{}
	for _, e := range r.Entries() {
		byKind[e.Kind]++
	}
	if byKind["compiler"] != 1 {
		t.Fatalf("expected 1 compiler plugin, got %d (%v)", byKind["compiler"], byKind)
	}
	if byKind["diagnostic"] != 1 {
		t.Fatalf("expected 1 diagnostic plugin, got %d", byKind["diagnostic"])
	}

	if r.UploaderFor("arduino:avr:uno") != nil {
		t.Fatal("no uploader should be registered")
	}
	if len(r.Compilers()) != 1 {
		t.Fatal("Compilers() should expose the compiler plugin")
	}
}

func TestBuiltinsLoad(t *testing.T) {
	r, errs := LoadAll(filepath.Join(t.TempDir(), "plugins"))
	if len(errs) != 0 {
		t.Fatalf("unexpected load errors: %v", errs)
	}
	meta := r.Plugin("companion.tools.meta-export")
	if meta == nil {
		t.Fatal("meta-exporter builtin not registered")
	}
	found := false
	for _, e := range r.Entries() {
		if e.Plugin.ID() == "companion.tools.meta-export" && e.Kind == "compiler" {
			found = true
		}
	}
	if !found {
		t.Fatal("meta-exporter should be a compiler-kind entry")
	}
}

func TestRunDiagnosticsCollects(t *testing.T) {
	r := NewRegistry()
	r.Register(&testAnalyzer{failure: "BAD-CODE"})
	diags := r.RunDiagnostics(context.Background(), "x", "esp32:esp32:esp32")
	if len(diags) != 1 || diags[0].Code != "BAD-CODE" {
		t.Fatalf("expected 1 diagnostic, got %+v", diags)
	}
}

func TestLoadAllMissingDirIsNoop(t *testing.T) {
	dir := filepath.Join(os.TempDir(), "companion-no-such-plugins-dir")
	os.RemoveAll(dir)
	r, errs := LoadAll(dir)
	if len(errs) != 0 {
		t.Fatalf("missing dir must not error: %v", errs)
	}
	if len(r.Entries()) == 0 {
		t.Fatal("builtins should always be registered")
	}
}

func TestPluginMetadataSanity(t *testing.T) {
	r, _ := LoadAll(filepath.Join(t.TempDir(), "plugins"))
	for _, e := range r.Entries() {
		if strings.TrimSpace(e.Plugin.ID()) == "" {
			t.Error("plugin with empty ID")
		}
		if strings.TrimSpace(e.Plugin.Name()) == "" {
			t.Error("plugin with empty Name for", e.Plugin.ID())
		}
		if !strings.Contains(e.Plugin.Version(), ".") {
			t.Error("plugin version not semver-ish for", e.Plugin.ID())
		}
	}
}
