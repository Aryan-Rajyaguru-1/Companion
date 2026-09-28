package boards

import (
	"archive/zip"
	"bytes"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// A zip that expands past the limit must be refused. The limits are lowered
// here rather than shipping a real bomb: a zip writer recomputes the sizes, so
// this is the only way to exercise the real enforcement path.
func TestExtractZipRespectsSizeLimits(t *testing.T) {
	origFile, origTotal := maxArchiveFileBytes, maxArchiveTotalBytes
	maxArchiveFileBytes, maxArchiveTotalBytes = 16, 64
	defer func() { maxArchiveFileBytes, maxArchiveTotalBytes = origFile, origTotal }()

	dir := t.TempDir()
	var buf bytes.Buffer
	zw := zip.NewWriter(&buf)
	w, _ := zw.Create("lib/payload.bin")
	w.Write(bytes.Repeat([]byte("A"), 200)) // 200 bytes > both limits
	zw.Close()
	zipPath := filepath.Join(dir, "bomb.zip")
	if err := os.WriteFile(zipPath, buf.Bytes(), 0o644); err != nil {
		t.Fatal(err)
	}
	dest := filepath.Join(dir, "out")
	err := extractZip(zipPath, dest)
	if err == nil {
		t.Fatal("an archive past the size limit was accepted")
	}
	if !strings.Contains(err.Error(), "limit") {
		t.Fatalf("expected a limit error, got: %v", err)
	}
	// Nothing may be left behind from the refused extraction.
	if _, statErr := os.Stat(filepath.Join(dest, "payload.bin")); statErr == nil {
		t.Error("refused archive still wrote a file")
	}
}

// The limits must not break real installs.
func TestExtractZipStillWorksUnderLimits(t *testing.T) {
	origFile, origTotal := maxArchiveFileBytes, maxArchiveTotalBytes
	maxArchiveFileBytes, maxArchiveTotalBytes = 1024, 4096
	defer func() { maxArchiveFileBytes, maxArchiveTotalBytes = origFile, origTotal }()

	dir := t.TempDir()
	var buf bytes.Buffer
	zw := zip.NewWriter(&buf)
	w, _ := zw.Create("lib/src/sketch.cpp")
	w.Write([]byte("void setup(){}\n"))
	zw.Close()
	zipPath := filepath.Join(dir, "ok.zip")
	os.WriteFile(zipPath, buf.Bytes(), 0o644)
	dest := filepath.Join(dir, "out")
	if err := extractZip(zipPath, dest); err != nil {
		t.Fatalf("normal archive failed to extract: %v", err)
	}
	got, err := os.ReadFile(filepath.Join(dest, "src", "sketch.cpp"))
	if err != nil || string(got) != "void setup(){}\n" {
		t.Fatalf("content wrong: %q %v", got, err)
	}
}
