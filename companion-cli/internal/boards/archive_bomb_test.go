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

// TestCopyBoundedBudgetAccounting is the regression test for the copyBounded
// accounting bug: the budget was decremented before the limit was checked, so
// an entry was compared against what remained AFTER itself rather than what was
// available BEFORE it. That silently halved the effective limit — a 100-byte
// budget accepted a 50-byte entry and rejected a 99-byte one — and could drive
// the running total negative.
//
// It slipped through because the existing cases used one file size against
// limits small enough that nothing landed near a boundary.
func TestCopyBoundedBudgetAccounting(t *testing.T) {
	const budget = 100
	cases := []struct {
		size      int
		wantAllow bool
	}{
		{0, true},    // empty entry
		{1, true},    //
		{49, true},   // just under half — the old code's accidental maximum
		{50, true},   // the largest the old code allowed
		{51, true},   // rejected by the old code, fits comfortably
		{99, true},   // rejected by the old code, nearly the whole budget
		{100, true},  // exactly the budget: must be allowed
		{101, false}, // one byte over: must be refused
		{500, false}, // well over
	}
	for _, tc := range cases {
		var sb strings.Builder
		rem := int64(budget)
		err := copyBounded(&sb, strings.NewReader(strings.Repeat("x", tc.size)), &rem)
		gotAllow := err == nil
		if gotAllow != tc.wantAllow {
			t.Errorf("budget=%d entry=%d: allow=%v, want %v (err=%v)",
				budget, tc.size, gotAllow, tc.wantAllow, err)
		}
		if tc.wantAllow {
			if rem != int64(budget-tc.size) {
				t.Errorf("budget=%d entry=%d: remaining=%d, want %d",
					budget, tc.size, rem, budget-tc.size)
			}
			if rem < 0 {
				t.Errorf("budget went negative: %d", rem)
			}
		}
	}
}

// The budget must also accumulate correctly across several entries, since that
// is how it is actually used — one running total for the whole archive.
func TestCopyBoundedAccumulatesAcrossEntries(t *testing.T) {
	var sb strings.Builder
	rem := int64(100)
	// 40 + 40 + 40 = 120 > 100, so the third must be refused.
	for i, size := range []int{40, 40, 40} {
		err := copyBounded(&sb, strings.NewReader(strings.Repeat("y", size)), &rem)
		if i < 2 {
			if err != nil {
				t.Fatalf("entry %d of %d unexpectedly failed: %v", i+1, 3, err)
			}
			if want := int64(100 - 40*(i+1)); rem != want {
				t.Errorf("after entry %d: remaining=%d, want %d", i+1, rem, want)
			}
		} else if err == nil {
			t.Errorf("entry 3 of 3 (total 120 > 100) was accepted; remaining=%d", rem)
		}
	}
}
