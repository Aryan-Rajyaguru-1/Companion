package cmd

import (
	"os"
	"strings"
	"testing"
)

// F002 precedence: flag > env > stdin > "".
func TestResolveOTAPasswordPrecedence(t *testing.T) {
	t.Setenv("COMPANION_OTA_PASSWORD", "env-secret")
	if got, _ := resolveOTAPassword(nil, "flag-secret", "", false); got != "flag-secret" {
		t.Fatalf("flag should win, got %q", got)
	}
	if got, _ := resolveOTAPassword(nil, "", "", false); got != "env-secret" {
		t.Fatalf("env should win over empty flag, got %q", got)
	}
	os.Unsetenv("COMPANION_OTA_PASSWORD")
	if got, _ := resolveOTAPassword(nil, "", "", false); got != "" {
		t.Fatalf("empty sources should yield empty, got %q", got)
	}
}

// F002 stdin path: reads piped secret, trims trailing newline.
func TestResolveOTAPasswordStdin(t *testing.T) {
	os.Unsetenv("COMPANION_OTA_PASSWORD")
	old := os.Stdin
	r, w, _ := os.Pipe()
	w.WriteString("stdin-secret\n")
	w.Close()
	os.Stdin = r
	defer func() { os.Stdin = old }()
	if got, err := resolveOTAPassword(nil, "", "", true); err != nil || got != "stdin-secret" {
		t.Fatalf("stdin read: got %q err %v", got, err)
	}
}

// F002 stdin empty must error, not silently proceed open.
func TestResolveOTAPasswordStdinEmpty(t *testing.T) {
	os.Unsetenv("COMPANION_OTA_PASSWORD")
	old := os.Stdin
	r, w, _ := os.Pipe()
	w.WriteString("  \n")
	w.Close()
	os.Stdin = r
	defer func() { os.Stdin = old }()
	if _, err := resolveOTAPassword(nil, "", "", true); err == nil ||
		!strings.Contains(err.Error(), "empty") {
		t.Fatalf("expected empty-stdin error, got %v", err)
	}
}
