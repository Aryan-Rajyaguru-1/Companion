package selfupdate_test

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"testing"

	"github.com/companion-ide/companion-cli/internal/selfupdate"
)

type testRelease struct {
	tag        string
	draft      bool
	prerelease bool
	assets     []string
}

func testReleaseServer(t *testing.T, releases []testRelease, files map[string][]byte) *httptest.Server {
	t.Helper()
	var srv *httptest.Server
	mux := http.NewServeMux()
	mux.HandleFunc("/repos/o/r/releases", func(w http.ResponseWriter, r *http.Request) {
		out := make([]map[string]interface{}, 0, len(releases))
		for _, rel := range releases {
			assets := make([]map[string]interface{}, 0, len(rel.assets))
			for _, name := range rel.assets {
				assets = append(assets, map[string]interface{}{
					"name":                 name,
					"browser_download_url": srv.URL + "/download/" + name,
					"size":                 len(files[name]),
				})
			}
			out = append(out, map[string]interface{}{
				"tag_name":     rel.tag,
				"name":         rel.tag,
				"html_url":     "https://example.test/releases/" + rel.tag,
				"published_at": "2026-01-02T03:04:05Z",
				"draft":        rel.draft,
				"prerelease":   rel.prerelease,
				"body":         "release notes",
				"assets":       assets,
			})
		}
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(out)
	})
	mux.HandleFunc("/download/", func(w http.ResponseWriter, r *http.Request) {
		name := strings.TrimPrefix(r.URL.Path, "/download/")
		data, ok := files[name]
		if !ok {
			http.NotFound(w, r)
			return
		}
		_, _ = w.Write(data)
	})
	srv = httptest.NewServer(mux)
	t.Cleanup(srv.Close)
	return srv
}

func newTestUpdater(t *testing.T, srv *httptest.Server, current, goos, goarch string) *selfupdate.Updater {
	t.Helper()
	u, err := selfupdate.New(selfupdate.Options{
		Repo:           "o/r",
		APIBaseURL:     srv.URL,
		CurrentVersion: current,
		GOOS:           goos,
		GOARCH:         goarch,
	})
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	return u
}

func checksums(name string, data []byte) []byte {
	sum := sha256.Sum256(data)
	return []byte(fmt.Sprintf("%s  %s\n", hex.EncodeToString(sum[:]), name))
}

func TestAssetName(t *testing.T) {
	tests := []struct {
		goos, goarch, want string
	}{
		{"linux", "amd64", "companion-linux-amd64"},
		{"linux", "arm64", "companion-linux-arm64"},
		{"darwin", "amd64", "companion-darwin-amd64"},
		{"darwin", "arm64", "companion-darwin-arm64"},
		{"windows", "amd64", "companion-windows-amd64.exe"},
		{"windows", "arm64", "companion-windows-arm64.exe"},
	}
	for _, tt := range tests {
		got, err := selfupdate.AssetName(tt.goos, tt.goarch)
		if err != nil {
			t.Fatalf("AssetName(%s, %s): %v", tt.goos, tt.goarch, err)
		}
		if got != tt.want {
			t.Errorf("AssetName(%s, %s) = %q, want %q", tt.goos, tt.goarch, got, tt.want)
		}
	}
	for _, pair := range [][2]string{{"freebsd", "amd64"}, {"linux", "386"}, {"", ""}} {
		if _, err := selfupdate.AssetName(pair[0], pair[1]); err == nil {
			t.Errorf("AssetName(%q, %q) unexpectedly succeeded", pair[0], pair[1])
		}
	}
}

func TestCheckSelectsNewestCompatibleReleaseBySemver(t *testing.T) {
	files := map[string][]byte{
		"companion-linux-amd64": []byte("new binary"),
		"SHA256SUMS.txt":        checksums("companion-linux-amd64", []byte("new binary")),
	}
	srv := testReleaseServer(t, []testRelease{
		{tag: "v0.3.9-alpha", assets: []string{"companion-linux-amd64", "SHA256SUMS.txt"}},
		{tag: "v0.3.10-alpha", assets: []string{"companion-linux-amd64", "SHA256SUMS.txt"}},
		{tag: "v0.4.0-beta", assets: []string{"companion-darwin-arm64"}},
		{tag: "v9.0.0", draft: true, assets: []string{"companion-linux-amd64", "SHA256SUMS.txt"}},
	}, files)

	check, err := newTestUpdater(t, srv, "0.3.9-alpha", "linux", "amd64").Check(context.Background())
	if err != nil {
		t.Fatalf("Check: %v", err)
	}
	if check.LatestVersion != "0.3.10-alpha" {
		t.Fatalf("LatestVersion = %q, want 0.3.10-alpha", check.LatestVersion)
	}
	if !check.UpdateAvailable {
		t.Error("UpdateAvailable = false, want true")
	}
	if check.AssetName != "companion-linux-amd64" {
		t.Errorf("AssetName = %q", check.AssetName)
	}
	if check.ChecksumsURL == "" {
		t.Error("ChecksumsURL is empty")
	}
}

func TestCheckSkipsReleaseWithoutChecksums(t *testing.T) {
	files := map[string][]byte{
		"companion-linux-amd64": []byte("verified"),
		"SHA256SUMS.txt":        checksums("companion-linux-amd64", []byte("verified")),
	}
	// v0.4.0 is newer but has no SHA256SUMS.txt. Offering it would make every
	// install attempt fail, so the updater must fall back to v0.3.10 instead.
	srv := testReleaseServer(t, []testRelease{
		{tag: "v0.4.0", assets: []string{"companion-linux-amd64"}},
		{tag: "v0.3.10", assets: []string{"companion-linux-amd64", "SHA256SUMS.txt"}},
	}, files)

	check, err := newTestUpdater(t, srv, "0.3.9", "linux", "amd64").Check(context.Background())
	if err != nil {
		t.Fatalf("Check: %v", err)
	}
	if check.LatestVersion != "0.3.10" {
		t.Fatalf("LatestVersion = %q, want 0.3.10", check.LatestVersion)
	}
}

func TestCheckErrorsWithoutCompatibleRelease(t *testing.T) {
	srv := testReleaseServer(t, []testRelease{
		{tag: "v1.0.0", assets: []string{"companion-darwin-arm64", "SHA256SUMS.txt"}},
	}, map[string][]byte{})
	if _, err := newTestUpdater(t, srv, "0.9.0", "linux", "amd64").Check(context.Background()); err == nil {
		t.Fatal("Check unexpectedly selected an incompatible release")
	}
}

func TestCheckReportsNoUpdateForCurrentRelease(t *testing.T) {
	data := []byte("current")
	srv := testReleaseServer(t, []testRelease{
		{tag: "v0.3.4-alpha", assets: []string{"companion-linux-amd64", "SHA256SUMS.txt"}},
	}, map[string][]byte{
		"companion-linux-amd64": data,
		"SHA256SUMS.txt":        checksums("companion-linux-amd64", data),
	})
	check, err := newTestUpdater(t, srv, "v0.3.4-alpha", "linux", "amd64").Check(context.Background())
	if err != nil {
		t.Fatalf("Check: %v", err)
	}
	if check.UpdateAvailable {
		t.Error("UpdateAvailable = true, want false")
	}
}

func TestInstallReplacesTargetAndVerifiesChecksum(t *testing.T) {
	data := []byte("new executable contents")
	srv := testReleaseServer(t, []testRelease{
		{tag: "v0.4.0", assets: []string{"companion-linux-amd64", "SHA256SUMS.txt"}},
	}, map[string][]byte{
		"companion-linux-amd64": data,
		"SHA256SUMS.txt":        checksums("companion-linux-amd64", data),
	})
	u := newTestUpdater(t, srv, "0.3.4", "linux", "amd64")
	check, err := u.Check(context.Background())
	if err != nil {
		t.Fatalf("Check: %v", err)
	}

	dir := t.TempDir()
	target := filepath.Join(dir, "companion")
	if err := os.WriteFile(target, []byte("old executable"), 0o700); err != nil {
		t.Fatal(err)
	}
	installed, err := u.Install(context.Background(), check, target, false)
	if err != nil {
		t.Fatalf("Install: %v", err)
	}
	if !installed.Updated || !installed.ChecksumVerified {
		t.Fatalf("Install result = %+v", installed)
	}
	if installed.InstallPath != target {
		t.Errorf("InstallPath = %q, want %q", installed.InstallPath, target)
	}
	got, err := os.ReadFile(target)
	if err != nil {
		t.Fatal(err)
	}
	if string(got) != string(data) {
		t.Errorf("target contents = %q, want %q", got, data)
	}
	fi, err := os.Stat(target)
	if err != nil {
		t.Fatal(err)
	}
	if fi.Mode().Perm() != 0o700 {
		t.Errorf("mode = %o, want 700 (executable permissions preserved)", fi.Mode().Perm())
	}
	entries, err := os.ReadDir(dir)
	if err != nil {
		t.Fatal(err)
	}
	if len(entries) != 1 || entries[0].Name() != "companion" {
		t.Errorf("temporary files left behind: %v", entries)
	}
}

func TestInstallRefusesChecksumMismatch(t *testing.T) {
	data := []byte("attacker-controlled")
	srv := testReleaseServer(t, []testRelease{
		{tag: "v0.4.0", assets: []string{"companion-linux-amd64", "SHA256SUMS.txt"}},
	}, map[string][]byte{
		"companion-linux-amd64": data,
		"SHA256SUMS.txt":        checksums("companion-linux-amd64", []byte("expected different bytes")),
	})
	u := newTestUpdater(t, srv, "0.3.4", "linux", "amd64")
	check, err := u.Check(context.Background())
	if err != nil {
		t.Fatalf("Check: %v", err)
	}

	dir := t.TempDir()
	target := filepath.Join(dir, "companion")
	original := []byte("known good binary")
	if err := os.WriteFile(target, original, 0o755); err != nil {
		t.Fatal(err)
	}
	if _, err := u.Install(context.Background(), check, target, false); err == nil {
		t.Fatal("Install accepted a mismatched checksum")
	}
	got, err := os.ReadFile(target)
	if err != nil {
		t.Fatal(err)
	}
	if string(got) != string(original) {
		t.Errorf("target was modified after checksum failure: %q", got)
	}
	entries, _ := os.ReadDir(dir)
	if len(entries) != 1 {
		t.Errorf("temporary files left behind after failure: %v", entries)
	}
}

func TestInstallNoopAndForce(t *testing.T) {
	data := []byte("release binary")
	srv := testReleaseServer(t, []testRelease{
		{tag: "v0.4.0", assets: []string{"companion-linux-amd64", "SHA256SUMS.txt"}},
	}, map[string][]byte{
		"companion-linux-amd64": data,
		"SHA256SUMS.txt":        checksums("companion-linux-amd64", data),
	})
	u := newTestUpdater(t, srv, "0.4.0", "linux", "amd64")
	check, err := u.Check(context.Background())
	if err != nil {
		t.Fatalf("Check: %v", err)
	}
	target := filepath.Join(t.TempDir(), "companion")
	noop, err := u.Install(context.Background(), check, target, false)
	if err != nil {
		t.Fatalf("Install no-op: %v", err)
	}
	if noop.Updated {
		t.Error("no-op install reported Updated = true")
	}
	if _, err := os.Stat(target); !os.IsNotExist(err) {
		t.Errorf("no-op install touched target: %v", err)
	}

	forced, err := u.Install(context.Background(), check, target, true)
	if err != nil {
		t.Fatalf("forced Install: %v", err)
	}
	if !forced.Updated {
		t.Error("forced install reported Updated = false")
	}
}

func TestInstallWithoutChecksumsFailsClosed(t *testing.T) {
	u := newTestUpdater(t, httptest.NewServer(http.NotFoundHandler()), "0.3.0", "linux", "amd64")
	check := &selfupdate.CheckResult{
		CurrentVersion:  "0.3.0",
		LatestVersion:   "0.4.0",
		UpdateAvailable: true,
		AssetName:       "companion-linux-amd64",
		AssetURL:        "https://example.test/companion",
	}
	target := filepath.Join(t.TempDir(), "companion")
	if _, err := u.Install(context.Background(), check, target, false); err == nil {
		t.Fatal("Install accepted a release without checksums")
	}
}

func TestInstallPreservesTargetSymlink(t *testing.T) {
	if runtime.GOOS == "windows" {
		t.Skip("symlink creation needs privileges on Windows")
	}
	data := []byte("new binary")
	srv := testReleaseServer(t, []testRelease{
		{tag: "v0.4.0", assets: []string{"companion-linux-amd64", "SHA256SUMS.txt"}},
	}, map[string][]byte{
		"companion-linux-amd64": data,
		"SHA256SUMS.txt":        checksums("companion-linux-amd64", data),
	})
	u := newTestUpdater(t, srv, "0.3.0", "linux", "amd64")
	check, err := u.Check(context.Background())
	if err != nil {
		t.Fatalf("Check: %v", err)
	}

	dir := t.TempDir()
	realTarget := filepath.Join(dir, "real-companion")
	link := filepath.Join(dir, "companion")
	if err := os.WriteFile(realTarget, []byte("old"), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.Symlink(realTarget, link); err != nil {
		t.Fatal(err)
	}
	installed, err := u.Install(context.Background(), check, link, false)
	if err != nil {
		t.Fatalf("Install: %v", err)
	}
	if installed.InstallPath != realTarget {
		t.Errorf("InstallPath = %q, want resolved target %q", installed.InstallPath, realTarget)
	}
	if fi, err := os.Lstat(link); err != nil || fi.Mode()&os.ModeSymlink == 0 {
		t.Errorf("symlink was replaced: fi=%v err=%v", fi, err)
	}
	got, err := os.ReadFile(realTarget)
	if err != nil {
		t.Fatal(err)
	}
	if string(got) != string(data) {
		t.Errorf("real target = %q, want %q", got, data)
	}
}

func TestChecksumFor(t *testing.T) {
	sum := strings.Repeat("a", 64)
	data := []byte("# generated\n" + sum + "  companion-linux-amd64\n" +
		strings.Repeat("b", 64) + " *nested/companion-darwin-arm64\n")
	got, err := selfupdate.ChecksumFor(data, "companion-linux-amd64")
	if err != nil || got != sum {
		t.Fatalf("ChecksumFor exact = %q, %v", got, err)
	}
	got, err = selfupdate.ChecksumFor(data, "companion-darwin-arm64")
	if err != nil || got != strings.Repeat("b", 64) {
		t.Fatalf("ChecksumFor basename = %q, %v", got, err)
	}
	if _, err := selfupdate.ChecksumFor(data, "missing"); err == nil {
		t.Fatal("ChecksumFor accepted a missing asset")
	}
	if _, err := selfupdate.ChecksumFor([]byte("not-a-digest  file\n"), "file"); err == nil {
		t.Fatal("ChecksumFor accepted a malformed digest")
	}
	conflict := []byte(sum + "  file\n" + strings.Repeat("c", 64) + "  file\n")
	if _, err := selfupdate.ChecksumFor(conflict, "file"); err == nil {
		t.Fatal("ChecksumFor accepted conflicting digests")
	}
}

func TestCompareVersions(t *testing.T) {
	tests := []struct {
		a, b string
		want int
	}{
		{"0.3.4-alpha", "0.3.4-alpha", 0},
		{"v0.3.4-alpha", "0.3.4-alpha", 0},
		{"0.3.10-alpha", "0.3.9-alpha", 1},
		{"0.4.0", "0.4.0-rc1", 1},
		{"0.4.0-alpha", "0.4.0-beta", -1},
		{"0.4.0-alpha.2", "0.4.0-alpha.10", -1},
		{"0.4.0-alpha.1", "0.4.0-alpha", 1},
		{"1.0.0", "0.3.4-alpha", 1},
		{"0.3.4-alpha+build.5", "0.3.4-alpha", 0},
	}
	for _, tt := range tests {
		if got := selfupdate.CompareVersions(tt.a, tt.b); got != tt.want {
			t.Errorf("CompareVersions(%q, %q) = %d, want %d", tt.a, tt.b, got, tt.want)
		}
	}
}

func TestIsNewer(t *testing.T) {
	tests := []struct {
		latest, current string
		want            bool
	}{
		{"0.4.0", "0.3.4", true},
		{"0.4.0", "0.4.0", false},
		{"0.4.0", "0.5.0", false},
		{"0.4.0", "dev", true},
		{"0.4.0", "unknown-local-build", true},
		{"0.4.0", "", true},
	}
	for _, tt := range tests {
		if got := selfupdate.IsNewer(tt.latest, tt.current); got != tt.want {
			t.Errorf("IsNewer(%q, %q) = %v, want %v", tt.latest, tt.current, got, tt.want)
		}
	}
}

func TestNewRejectsInsecureAPI(t *testing.T) {
	if _, err := selfupdate.New(selfupdate.Options{APIBaseURL: "http://example.com"}); err == nil {
		t.Fatal("New accepted a public plaintext API URL")
	}
	if _, err := selfupdate.New(selfupdate.Options{APIBaseURL: "ftp://example.com"}); err == nil {
		t.Fatal("New accepted an unsupported API scheme")
	}
	if _, err := selfupdate.New(selfupdate.Options{Repo: "owner"}); err == nil {
		t.Fatal("New accepted a repository without a slash")
	}
	if _, err := selfupdate.New(selfupdate.Options{APIBaseURL: "http://localhost:1234"}); err != nil {
		t.Errorf("New rejected a loopback test server: %v", err)
	}
}
