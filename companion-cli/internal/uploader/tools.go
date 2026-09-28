// tools.go — external-tool detection for `companion doctor`.
//
// The upload paths shell out to esptool and avrdude, and to Python when
// esptool comes from pip. A missing tool surfaces deep inside an upload as an
// opaque error ("executable file not found"), which is exactly the class of
// problem a new user cannot diagnose. doctor asks THIS package instead: the
// detection below is the same resolution an upload performs, which is what
// keeps the diagnosis from drifting away from the behaviour it describes.
package uploader

import (
	"context"
	"os/exec"
	"runtime"
	"strings"
	"time"

	"github.com/companion-ide/companion-cli/internal/config"
)

// ToolStatus is one external tool's detection result.
type ToolStatus struct {
	Name   string // "esptool", "avrdude", "python3"
	Needed string // which targets need it — a missing AVR-only tool is not scary
	Found  bool   // resolved AND runs
	Detail string // how it resolved ("bundled with the ESP32 core: …"), or why not
	Hint   string // platform-correct fix
}

// Tools probes every external tool the upload paths can shell out to.
func Tools(cfg *config.Config) []ToolStatus {
	return []ToolStatus{probeEsptool(cfg), probeAvrdude(), probePython()}
}

// probeEsptool checks the same chain an upload uses — core-bundled esptool,
// then esptool.py, then esptool, then `python -m esptool` — but then RUNS it.
// Resolving is not running: `python -m esptool` resolves whenever Python
// exists, even when the module was never installed, and that difference is
// invisible until an upload fails.
func probeEsptool(cfg *config.Config) ToolStatus {
	st := ToolStatus{Name: "esptool", Needed: "ESP32 / ESP8266 targets"}
	prefix, _, err := resolveEsptoolPrefix(cfg)
	if err != nil {
		st.Detail = "not found"
		st.Hint = toolInstallHint("esptool")
		return st
	}
	resolved := strings.Join(prefix, " ")
	args := append(append([]string{}, prefix...), "version")
	out, rerr := probeOutput(args...)
	if rerr != nil {
		st.Detail = resolved + " — resolved, but running it failed"
		if line := firstLine(out); line != "" {
			st.Detail += ": " + line
		}
		st.Hint = toolInstallHint("esptool")
		return st
	}
	st.Found = true
	st.Detail = resolved
	if line := firstLine(out); line != "" {
		st.Detail += "  →  " + line
	}
	return st
}

// probeAvrdude checks PATH only: avrdude has no side-effect-free version flag
// (every invocation wants a port and a part), and the uploader invokes it as a
// bare `avrdude`, so PATH is the whole contract.
func probeAvrdude() ToolStatus {
	st := ToolStatus{Name: "avrdude", Needed: "AVR targets (Uno / Nano / Mega)"}
	path, err := exec.LookPath("avrdude")
	if err != nil {
		st.Detail = "not found on PATH"
		st.Hint = toolInstallHint("avrdude")
		return st
	}
	st.Found = true
	st.Detail = path
	return st
}

// probePython reports the interpreter the pip form of esptool would run on.
func probePython() ToolStatus {
	bin := pythonBin()
	st := ToolStatus{Name: bin, Needed: "esptool from pip (not needed when the core bundles it)"}
	path, err := exec.LookPath(bin)
	if err != nil {
		st.Detail = "not found on PATH"
		st.Hint = pythonInstallHint()
		return st
	}
	st.Found = true
	st.Detail = path
	if out, err := probeOutput(bin, "--version"); err == nil {
		if line := firstLine(out); line != "" {
			st.Detail += "  →  " + line
		}
	}
	return st
}

// probeOutput runs a resolved tool with a bounded timeout and returns its
// combined output — several of these print version banners to stderr.
func probeOutput(args ...string) (string, error) {
	ctx, cancel := context.WithTimeout(context.Background(), 20*time.Second)
	defer cancel()
	out, err := exec.CommandContext(ctx, args[0], args[1:]...).CombinedOutput()
	return string(out), err
}

func firstLine(s string) string {
	s = strings.TrimSpace(s)
	if i := strings.IndexByte(s, '\n'); i >= 0 {
		s = s[:i]
	}
	return strings.TrimSpace(s)
}

func pythonInstallHint() string {
	switch runtime.GOOS {
	case "windows":
		return "winget install Python.Python.3.12   (or python.org — tick \"Add python.exe to PATH\")"
	case "darwin":
		return "brew install python3"
	default:
		return "sudo apt install python3   (or your distro's package manager)"
	}
}
