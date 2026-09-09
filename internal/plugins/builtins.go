// Package plugins defines abstract interfaces for extending Companion CLI.
//
// Built-in plugin: the meta exporter (companion.tools.meta-export) writes a
// companion-meta.json next to every compiled binary so builds are reproducible
// and tooling (IDE, CI) can correlate artifacts with their source/config.
package plugins

import (
	"context"
	"encoding/json"
	"os"
	"path/filepath"
	"time"
)

// builtins returns the first-party plugins shipped with Companion.
func builtins() []Plugin {
	return []Plugin{
		&metaExporter{},
		&otaUploader{},
	}
}

// metaExporter is a first-party CompilerPlugin that records build metadata
// (fqbn, build dir, binary, timestamp) in the build directory.
type metaExporter struct{}

func (*metaExporter) ID() string                  { return "companion.tools.meta-export" }
func (*metaExporter) Name() string                { return "Build Metadata Exporter" }
func (*metaExporter) Version() string             { return "1.0.0" }
func (*metaExporter) Init(cfg PluginConfig) error { return nil }

// PreCompile is a no-op — metadata is written post-build.
func (*metaExporter) PreCompile(ctx context.Context, opts CompileHookOptions) error {
	return nil
}

// PostCompile writes companion-meta.json next to the binary.
func (*metaExporter) PostCompile(ctx context.Context, opts CompileHookOptions, binaryPath string) error {
	if opts.BuildDir == "" {
		return nil
	}
	meta := map[string]string{
		"fqbn":      opts.FQBN,
		"sketch":    opts.SketchDir,
		"build_dir": opts.BuildDir,
		"binary":    binaryPath,
		"timestamp": time.Now().UTC().Format(time.RFC3339),
	}
	data, err := json.MarshalIndent(meta, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(filepath.Join(opts.BuildDir, "companion-meta.json"), data, 0o644)
}
