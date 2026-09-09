package boards

import (
	"archive/tar"
	"archive/zip"
	"bytes"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// buildZip creates an in-memory zip with the given entries.
func buildZip(t *testing.T, entries map[string]string) string {
	t.Helper()
	var buf bytes.Buffer
	zw := zip.NewWriter(&buf)
	for name, content := range entries {
		fw, err := zw.Create(name)
		if err != nil {
			t.Fatalf("zip create %q: %v", name, err)
		}
		if _, err := fw.Write([]byte(content)); err != nil {
			t.Fatalf("zip write %q: %v", name, err)
		}
	}
	if err := zw.Close(); err != nil {
		t.Fatalf("zip close: %v", err)
	}
	p := filepath.Join(t.TempDir(), "test.zip")
	if err := os.WriteFile(p, buf.Bytes(), 0o644); err != nil {
		t.Fatal(err)
	}
	return p
}

func buildTar(t *testing.T, entries map[string]string) string {
	t.Helper()
	var buf bytes.Buffer
	tw := tar.NewWriter(&buf)
	for name, content := range entries {
		hdr := &tar.Header{Name: name, Mode: 0o644, Size: int64(len(content))}
		if strings.HasSuffix(name, "/") {
			hdr.Typeflag = tar.TypeDir
			hdr.Size = 0
		} else {
			hdr.Typeflag = tar.TypeReg
		}
		if err := tw.WriteHeader(hdr); err != nil {
			t.Fatalf("tar header %q: %v", name, err)
		}
		if hdr.Size > 0 {
			if _, err := tw.Write([]byte(content)); err != nil {
				t.Fatalf("tar body %q: %v", name, err)
			}
		}
	}
	if err := tw.Close(); err != nil {
		t.Fatal(err)
	}
	p := filepath.Join(t.TempDir(), "test.tar")
	if err := os.WriteFile(p, buf.Bytes(), 0o644); err != nil {
		t.Fatal(err)
	}
	return p
}

func TestExtractZipNormalizesTopLevelDir(t *testing.T) {
	src := buildZip(t, map[string]string{
		"mylib/src/main.cpp":       "int main(){}",
		"mylib/library.properties": "name=MyLib",
	})
	dest := t.TempDir()
	if err := extractZip(src, dest); err != nil {
		t.Fatalf("extractZip: %v", err)
	}
	for _, f := range []string{"src/main.cpp", "library.properties"} {
		if _, err := os.Stat(filepath.Join(dest, f)); err != nil {
			t.Errorf("expected %s extracted, got: %v", f, err)
		}
	}
}

func TestExtractZipRejectsTraversal(t *testing.T) {
	src := buildZip(t, map[string]string{
		"top/ok.txt":                        "fine",
		"top/../../../../tmp_zipslip_pwned": "evil",
	})
	dest := t.TempDir()
	err := extractZip(src, dest)
	if err == nil {
		t.Fatal("expected traversal entry to be rejected, got nil error")
	}
	if !strings.Contains(err.Error(), "traversal") && !strings.Contains(err.Error(), "escapes") {
		t.Errorf("error should mention traversal/escape, got: %v", err)
	}
	if _, e := os.Stat("/tmp_zipslip_pwned"); e == nil {
		t.Error("Zip Slip: file escaped destination directory!")
	}
}

func TestExtractTarRejectsTraversal(t *testing.T) {
	src := buildTar(t, map[string]string{
		"pkg/lib/x.txt":                  "ok",
		"pkg/../../../tmp_tarslip_pwned": "evil",
	})
	dest := t.TempDir()
	err := extractTar(src, dest)
	if err == nil {
		t.Fatal("expected traversal entry to be rejected, got nil error")
	}
	if _, e := os.Stat("/tmp_tarslip_pwned"); e == nil {
		t.Error("Tar Slip: file escaped destination directory!")
	}
}

func TestSanitizeRelPath(t *testing.T) {
	dest := t.TempDir()

	good := []string{"src/main.cpp", "a/b/c/d.h", "./rel.txt"}
	for _, g := range good {
		if _, err := sanitizeRelPath(dest, g); err != nil {
			t.Errorf("sanitizeRelPath(%q) should succeed, got %v", g, err)
		}
	}

	bad := []string{
		"../evil.txt",
		"a/../../evil.txt",
		"..",
		"/absolute/path.txt",
		`C:\Windows\evil.txt`,
	}
	for _, b := range bad {
		if _, err := sanitizeRelPath(dest, b); err == nil {
			t.Errorf("sanitizeRelPath(%q) should be rejected", b)
		}
	}
}

func TestExtractTarHardlinks(t *testing.T) {
	// GCC toolchain archives use hardlinks for aliased binaries
	// (e.g. bin/avr-gcc ↔ bin/avr-gcc-7.3.0). They must be materialized.
	var buf bytes.Buffer
	tw := tar.NewWriter(&buf)

	hdr := &tar.Header{Name: "tool/bin/avr-gcc-7.3.0", Typeflag: tar.TypeReg,
		Mode: 0o755, Size: 5}
	tw.WriteHeader(hdr)
	tw.Write([]byte("ELF\x7Fy"))

	lhdr := &tar.Header{Name: "tool/bin/avr-gcc", Typeflag: tar.TypeLink,
		Mode: 0o755, Linkname: "tool/bin/avr-gcc-7.3.0"}
	tw.WriteHeader(lhdr)
	tw.Close()

	p := filepath.Join(t.TempDir(), "hardlink.tar")
	os.WriteFile(p, buf.Bytes(), 0o644)

	dest := t.TempDir()
	if err := extractTar(p, dest); err != nil {
		t.Fatalf("extractTar: %v", err)
	}
	data, err := os.ReadFile(filepath.Join(dest, "bin", "avr-gcc"))
	if err != nil {
		t.Fatalf("hardlinked entry missing: %v", err)
	}
	if string(data) != "ELF\x7Fy" {
		t.Errorf("hardlink content = %q", data)
	}
}

func TestExtractZipAbsoluteEntryRejected(t *testing.T) {
	src := buildZip(t, map[string]string{"/etc/companion_pwned": "evil"})
	dest := t.TempDir()
	if err := extractZip(src, dest); err == nil {
		t.Fatal("absolute archive path should be rejected")
	}
}
