package boards

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
)

// A board index is untrusted input (additional-URL indexes are user-configured
// and any index can be a hostile mirror). Every name that reaches a path must
// survive this, or a mirror can write — and on a checksum failure DELETE —
// outside the directories the install owns.
func TestSafePathSegmentRejectsTraversal(t *testing.T) {
	bad := []struct{ in, why string }{
		{"", "empty"},
		{"..", "parent"},
		{".", "current"},
		{"../../etc/cron.d/pwn", "traversal"},
		{`..\..\windows\system32\x.dll`, "windows traversal"},
		{"sub/dir.tar.gz", "forward slash"},
		{`sub\dir.tar.gz`, "backslash"},
		{"/etc/passwd", "absolute"},
		{"-rf", "option injection"},
		{"file\x00.tar.gz", "NUL"},
		{"file\nname.tar.gz", "newline"},
		{"file;rm -rf /.tar.gz", "shell metachars"},
	}
	for _, tc := range bad {
		if got, err := safePathSegment(tc.in, "archiveFileName"); err == nil {
			t.Errorf("accepted %q (%s) as %q — it must be rejected", tc.in, tc.why, got)
		}
	}
	for _, ok := range []string{
		"esp32-3.3.11.zip", "arduino-avr-1.8.6.tar.bz2", "tool-x86_64-pc-linux-gnu.tar.gz",
		"aarch64-esp-elf-gcc9_2_0.tar.gz", "avr-gcc_7.3.0_atmel3.6.1-arduino7-x86_64-pc-linux-gnu.tar.bz2",
	} {
		if _, err := safePathSegment(ok, "archiveFileName"); err != nil {
			t.Errorf("rejected a legitimate archive name %q: %v", ok, err)
		}
	}
	// Surrounding whitespace is trimmed rather than rejected — indexes in the
	// wild carry it — but the trimmed value is what gets used.
	if got, err := safePathSegment("  esp32.zip  ", "archiveFileName"); err != nil || got != "esp32.zip" {
		t.Errorf("trim: got %q, %v", got, err)
	}
}

// removeIfInside is the guard on the "checksum failed, delete the download"
// path: it must delete inside its base directory and refuse everything else.
func TestRemoveIfInside(t *testing.T) {
	base := t.TempDir()
	outside := filepath.Join(t.TempDir(), "precious.txt")
	if err := os.WriteFile(outside, []byte("do not delete"), 0o600); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(base, "download.zip"), []byte("x"), 0o600); err != nil {
		t.Fatal(err)
	}

	// Outside → refused, and the file is still there.
	if err := removeIfInside(base, outside); err == nil {
		t.Error("removeIfInside deleted a file outside the base directory")
	}
	if _, err := os.Stat(outside); err != nil {
		t.Errorf("victim file was removed anyway: %v", err)
	}
	// A traversal path that resolves back inside is fine (that is our own dir).
	if err := removeIfInside(base, filepath.Join(base, "sub", "..", "download.zip")); err != nil {
		t.Errorf("removeIfInside refused a path that resolves inside the base: %v", err)
	}
}

// The index size is attacker-controlled: a bogus or negative value must fall
// back to the hard ceiling, never to "no limit".
func TestIndexSizeBytesFallsBackToCeiling(t *testing.T) {
	for _, in := range []string{"", "abc", "-5", "0"} {
		if got := indexSizeBytes(json.Number(in)); got != maxDownloadBytes {
			t.Errorf("indexSizeBytes(%q) = %d, want the %d ceiling", in, got, maxDownloadBytes)
		}
	}
	if got := indexSizeBytes(json.Number("1000000")); got < 1000000 || got > maxDownloadBytes {
		t.Errorf("indexSizeBytes for a real size = %d, want just over 1000000", got)
	}
	// A huge published size is still clamped to the ceiling.
	if got := indexSizeBytes(json.Number("999999999999")); got != maxDownloadBytes {
		t.Errorf("indexSizeBytes(999999999999) = %d, want the ceiling", got)
	}
}
