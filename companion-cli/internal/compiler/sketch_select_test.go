package compiler

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// Regression guard for the "several sketches in one folder" wall of
// "redefinition of 'void setup()'" errors: the folder must be rejected with
// the real cause before the compiler ever runs, and --main-ino must compile
// exactly one file.

func writeSketch(t *testing.T, dir, name, body string) {
	t.Helper()
	if err := os.WriteFile(filepath.Join(dir, name), []byte(body), 0o644); err != nil {
		t.Fatalf("write %s: %v", name, err)
	}
}

const fullSketch = "void setup() {\n  Serial.begin(115200);\n}\nvoid loop() {\n  delay(1000);\n}\n"
const helperIno = "// helper only — no setup()/loop()\nint addOne(int v) { return v + 1; }\n"

func TestCompleteSketchFiles(t *testing.T) {
	dir := t.TempDir()
	writeSketch(t, dir, "main.ino", fullSketch)
	writeSketch(t, dir, "helpers.ino", helperIno)
	writeSketch(t, dir, "other.ino", "void loop() { }\n")

	got := completeSketchFiles([]string{
		filepath.Join(dir, "main.ino"),
		filepath.Join(dir, "helpers.ino"),
		filepath.Join(dir, "other.ino"),
	})
	want := map[string]bool{"main.ino": true, "other.ino": true}
	if len(got) != 2 || !want[got[0]] || !want[got[1]] {
		t.Fatalf("completeSketchFiles = %v, want [main.ino other.ino]", got)
	}
}

func TestPreprocessSketchRejectsMultipleSketches(t *testing.T) {
	dir := t.TempDir()
	out := t.TempDir()
	writeSketch(t, dir, "blink.ino", fullSketch)
	writeSketch(t, dir, "serial-hello.ino", fullSketch)

	c := New(nil, nil, nil)
	_, err := c.preprocessSketch(dir, out, "")
	if err == nil {
		t.Fatal("expected an error for two complete sketches in one folder")
	}
	msg := err.Error()
	for _, want := range []string{"2 complete sketches", "blink.ino", "serial-hello.ino", "--main-ino"} {
		if !strings.Contains(msg, want) {
			t.Errorf("error %q does not mention %q", msg, want)
		}
	}
}

func TestPreprocessSketchMergesMultiFileSketch(t *testing.T) {
	// One complete sketch + a helper .ino is a legitimate multi-file sketch:
	// it must still merge (Arduino semantics), not error out.
	dir := t.TempDir()
	out := t.TempDir()
	writeSketch(t, dir, "main.ino", fullSketch)
	writeSketch(t, dir, "helpers.ino", helperIno)

	c := New(nil, nil, nil)
	cpp, err := c.preprocessSketch(dir, out, "")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	data, err := os.ReadFile(cpp)
	if err != nil {
		t.Fatalf("read merged cpp: %v", err)
	}
	if !strings.Contains(string(data), "addOne") || !strings.Contains(string(data), "setup()") {
		t.Errorf("merged cpp is missing sketch or helper content:\n%s", data)
	}
}

func TestPreprocessSketchMainInoSelectsOneFile(t *testing.T) {
	dir := t.TempDir()
	out := t.TempDir()
	writeSketch(t, dir, "blink.ino", fullSketch)
	writeSketch(t, dir, "serial-hello.ino", "void setup(){}\nvoid loop(){ Serial.println(\"hello\"); }\n")

	c := New(nil, nil, nil)
	cpp, err := c.preprocessSketch(dir, out, "serial-hello.ino")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	data, err := os.ReadFile(cpp)
	if err != nil {
		t.Fatalf("read merged cpp: %v", err)
	}
	if strings.Contains(string(data), "LED") || strings.Contains(string(data), "delay(1000)") {
		t.Errorf("blink.ino content leaked into the compiled unit:\n%s", data)
	}
	if !strings.Contains(string(data), "hello") {
		t.Errorf("selected sketch content missing:\n%s", data)
	}
	if filepath.Base(cpp) != "serial-hello.ino.cpp" {
		t.Errorf("output name = %s, want serial-hello.ino.cpp", filepath.Base(cpp))
	}
}

func TestPreprocessSketchMainInoMissing(t *testing.T) {
	dir := t.TempDir()
	out := t.TempDir()
	writeSketch(t, dir, "blink.ino", fullSketch)

	c := New(nil, nil, nil)
	_, err := c.preprocessSketch(dir, out, "nope.ino")
	if err == nil {
		t.Fatal("expected an error for a missing --main-ino file")
	}
	if !strings.Contains(err.Error(), "blink.ino") {
		t.Errorf("error should list the available .ino files, got: %v", err)
	}
}

func TestBaseNamesHelpers(t *testing.T) {
	paths := []string{"/a/x.ino", "/a/y.ino"}
	if got := baseNames(paths); len(got) != 2 || got[0] != "x.ino" || got[1] != "y.ino" {
		t.Errorf("baseNames = %v", got)
	}
	if got := baseNamesExcept(paths, "/a/x.ino"); len(got) != 1 || got[0] != "y.ino" {
		t.Errorf("baseNamesExcept = %v", got)
	}
}
