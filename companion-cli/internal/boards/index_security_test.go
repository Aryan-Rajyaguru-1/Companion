package boards

import (
	"encoding/json"
	"fmt"
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

// TestIndexSizeBytesFitsRealESP32Toolchain is the regression test for issue #6's
// second half: `companion board install esp32:esp32` could not fetch esp-rv32.
//
// The index publishes the true size of every tool archive, but indexSizeBytes
// clamped it to maxDownloadBytes, which was 512 MiB. The real esp-rv32 archives
// are 556-673 MiB depending on host, so the download was cut off part-way and
// the reporter was told to copy the tools out of the Arduino IDE by hand.
//
// These are the exact byte counts from package_esp32_index.json, esp32 3.3.11,
// tool version 2601. They must survive the clamp.
func TestIndexSizeBytesFitsRealESP32Toolchain(t *testing.T) {
	const mib = 1 << 20
	for _, tc := range []struct {
		name  string
		bytes int64
	}{
		{"esp-x32 x86_64-mingw32", 413859845},
		{"esp-rv32 arm-linux-gnueabihf", 596288860},
		{"esp-rv32 x86_64-pc-linux-gnu", 590607738},
		{"esp-rv32 i686-mingw32", 698196605},
		{"esp-rv32 x86_64-mingw32 (largest)", 705866147},
	} {
		t.Run(tc.name, func(t *testing.T) {
			got := indexSizeBytes(json.Number(fmt.Sprintf("%d", tc.bytes)))
			if got < tc.bytes {
				t.Errorf("published size %d bytes (%.1f MiB) was clamped to %d — the download would abort part-way",
					tc.bytes, float64(tc.bytes)/mib, got)
			}
		})
	}
}

// TestMaxDownloadBytesStillBounded makes sure raising the ceiling for the
// toolchain did not turn it off. It exists to stop an untrusted index, so an
// unbounded download is a disk-fill vulnerability, not a nicety.
func TestMaxDownloadBytesStillBounded(t *testing.T) {
	const (
		mib = 1 << 20
		gib = 1 << 30
	)
	if maxDownloadBytes < 673*mib {
		t.Errorf("ceiling %d MiB is below the largest real toolchain (673 MiB)", maxDownloadBytes/mib)
	}
	if maxDownloadBytes > 2*gib {
		t.Errorf("ceiling is %d GiB — too generous to defend against a hostile index", maxDownloadBytes/gib)
	}
}
