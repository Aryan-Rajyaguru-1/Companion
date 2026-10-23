package boards

import (
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestDownloadFileReplacesOnlyCompleteBody(t *testing.T) {
	const body = "complete archive bytes"
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Length", "22")
		w.Write([]byte(body))
	}))
	defer srv.Close()

	dest := filepath.Join(t.TempDir(), "archive.zip")
	if err := downloadFile(srv.URL, dest, 1024, nil); err != nil {
		t.Fatalf("downloadFile: %v", err)
	}
	got, err := os.ReadFile(dest)
	if err != nil {
		t.Fatal(err)
	}
	if string(got) != body {
		t.Fatalf("downloaded body = %q, want %q", got, body)
	}
}

// A truncated response must not destroy a previously cached archive: the next
// checksum verify would see corruption, but a crash mid-write used to leave a
// short file that the "bigger than 1 KiB" cache hit accepted.
func TestDownloadFileFailureLeavesDestinationUntouched(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Length", "100")
		w.Write([]byte("short"))
	}))
	defer srv.Close()

	dir := t.TempDir()
	dest := filepath.Join(dir, "archive.zip")
	if err := os.WriteFile(dest, []byte("previous complete archive"), 0o600); err != nil {
		t.Fatal(err)
	}
	if err := downloadFile(srv.URL, dest, 1024, nil); err == nil {
		t.Fatal("downloadFile accepted a truncated response")
	}
	got, err := os.ReadFile(dest)
	if err != nil {
		t.Fatal(err)
	}
	if string(got) != "previous complete archive" {
		t.Fatalf("failed download replaced the previous archive with %q", got)
	}
	entries, err := os.ReadDir(dir)
	if err != nil {
		t.Fatal(err)
	}
	for _, e := range entries {
		if strings.HasPrefix(e.Name(), ".archive.zip-") {
			t.Errorf("temporary download %q was left behind", e.Name())
		}
	}
}

func TestDownloadFileRejectsOversizedContentLength(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Length", "2048")
		w.Write(make([]byte, 2048))
	}))
	defer srv.Close()

	dest := filepath.Join(t.TempDir(), "archive.zip")
	if err := downloadFile(srv.URL, dest, 1024, nil); err == nil {
		t.Fatal("downloadFile accepted an archive over the limit")
	}
	if _, err := os.Stat(dest); !os.IsNotExist(err) {
		t.Fatalf("oversized download wrote the destination: %v", err)
	}
}
