// Package libraries manages Arduino library index, search, and installation.
// Inspired by arduino-cli's library management — written from scratch.
package libraries

import (
	"crypto/md5"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"time"

	"github.com/companion-ide/companion-cli/internal/atomicfile"
	"github.com/companion-ide/companion-cli/internal/boards"
	"github.com/companion-ide/companion-cli/internal/config"
	"github.com/companion-ide/companion-cli/internal/safename"
	semver "github.com/companion-ide/companion-cli/internal/version"
)

// ── Index types (mirrors library_index.json schema) ──────────────

const (
	LibraryIndexURL = "https://downloads.arduino.cc/libraries/library_index.json"

	// Index and archive bounds. Both are read from a remote endpoint; the
	// previous code used io.ReadAll / unbounded writes, so a hostile or broken
	// server could exhaust memory or fill the disk.
	maxLibraryIndexBytes   int64 = 64 << 20  // 64 MiB
	maxLibraryArchiveBytes int64 = 512 << 20 // 512 MiB
)

type LibraryIndex struct {
	Libraries []LibraryRelease `json:"libraries"`
}

// LibraryRelease is one version of a library in the index.
type LibraryRelease struct {
	Name            string   `json:"name"`
	Version         string   `json:"version"`
	Author          string   `json:"author"`
	Maintainer      string   `json:"maintainer"`
	Sentence        string   `json:"sentence"`
	Paragraph       string   `json:"paragraph"`
	Website         string   `json:"website"`
	Category        string   `json:"category"`
	Architectures   []string `json:"architectures"`
	Types           []string `json:"types"`
	URL             string   `json:"url"`
	ArchiveFileName string   `json:"archiveFileName"`
	Size            int      `json:"size"`
	Checksum        string   `json:"checksum"`
}

// InstalledLibrary represents a library found on disk.
type InstalledLibrary struct {
	Name     string
	Version  string
	Path     string
	Sentence string
	Author   string
}

// ── Manager ───────────────────────────────────────────────────────

type Manager struct {
	cfg   *config.Config
	index *LibraryIndex
}

func NewManager(cfg *config.Config) *Manager {
	return &Manager{cfg: cfg}
}

// UpdateIndex downloads the official library index.
func (m *Manager) UpdateIndex(onProgress func(string)) error {
	indexPath := filepath.Join(m.cfg.IndexesDir(), "library_index.json")
	os.MkdirAll(filepath.Dir(indexPath), 0o755)

	onProgress("Downloading library index…")

	client := &http.Client{Timeout: 60 * time.Second}
	resp, err := client.Get(LibraryIndexURL)
	if err != nil {
		return fmt.Errorf("download library index: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		return fmt.Errorf("HTTP %d from library index", resp.StatusCode)
	}

	data, err := readAllLimit(resp.Body, maxLibraryIndexBytes)
	if err != nil {
		return fmt.Errorf("reading library index: %w", err)
	}

	if err := os.WriteFile(indexPath, data, 0o644); err != nil {
		return fmt.Errorf("saving library index: %w", err)
	}

	m.index = nil // Invalidate cache
	onProgress(fmt.Sprintf("✓ Library index updated (%d KB)", len(data)/1024))
	return nil
}

// loadIndex parses the library index from disk.
func (m *Manager) loadIndex() (*LibraryIndex, error) {
	if m.index != nil {
		return m.index, nil
	}

	indexPath := filepath.Join(m.cfg.IndexesDir(), "library_index.json")
	data, err := readFileLimit(indexPath, maxLibraryIndexBytes)
	if err != nil {
		if os.IsNotExist(err) {
			return &LibraryIndex{}, nil
		}
		return nil, err
	}

	var idx LibraryIndex
	if err := json.Unmarshal(data, &idx); err != nil {
		return nil, fmt.Errorf("parsing library index: %w", err)
	}

	m.index = &idx
	return &idx, nil
}

// Search returns library releases matching the query.
// Returns only the latest version of each library.
func (m *Manager) Search(query string) ([]LibraryRelease, error) {
	idx, err := m.loadIndex()
	if err != nil {
		return nil, err
	}

	q := strings.ToLower(strings.TrimSpace(query))

	// Group by name, keep latest version (semver-aware)
	latest := make(map[string]*LibraryRelease)
	for i := range idx.Libraries {
		lib := &idx.Libraries[i]
		if existing, ok := latest[lib.Name]; !ok || semver.Compare(lib.Version, existing.Version) > 0 {
			latest[lib.Name] = lib
		}
	}

	// Collect matches
	var results []LibraryRelease
	for _, lib := range latest {
		if q == "" ||
			strings.Contains(strings.ToLower(lib.Name), q) ||
			strings.Contains(strings.ToLower(lib.Sentence), q) ||
			strings.Contains(strings.ToLower(lib.Author), q) ||
			strings.Contains(strings.ToLower(lib.Category), q) {
			results = append(results, *lib)
		}
	}

	// Sort by name
	sort.Slice(results, func(i, j int) bool {
		return results[i].Name < results[j].Name
	})

	return results, nil
}

// Install downloads and installs a library by name.
// Mirrors arduino-cli's LibraryInstall.
func (m *Manager) Install(name string, version string, onProgress func(string)) error {
	idx, err := m.loadIndex()
	if err != nil {
		return err
	}

	// Find the release
	var found *LibraryRelease
	for i := range idx.Libraries {
		lib := &idx.Libraries[i]
		if !strings.EqualFold(lib.Name, name) {
			continue
		}
		if version == "" || version == "latest" {
			if found == nil || semver.Compare(lib.Version, found.Version) > 0 {
				found = lib
			}
		} else if lib.Version == version {
			found = lib
			break
		}
	}

	if found == nil {
		return fmt.Errorf("library %q not found\nRun: companion lib update-index", name)
	}

	onProgress(fmt.Sprintf("Installing %s v%s…", found.Name, found.Version))

	// Download
	dlDir := m.cfg.Directories.Downloads
	if err := os.MkdirAll(dlDir, 0o755); err != nil {
		return fmt.Errorf("create downloads directory: %w", err)
	}
	archiveName, err := safeArchiveSegment(found.ArchiveFileName)
	if err != nil {
		return fmt.Errorf("library index: invalid archive filename: %w", err)
	}
	archivePath := filepath.Join(dlDir, archiveName)

	if err := downloadLibrary(found.URL, archivePath, onProgress); err != nil {
		return fmt.Errorf("download: %w", err)
	}

	// Verify archive integrity (the index checksum was parsed but never
	// checked). On mismatch, assume a corrupt cached archive, re-download
	// once, and verify again before giving up. A missing checksum is treated
	// like a checksum-less board index: refuse unless the operator explicitly
	// opted into a mirror they control.
	if strings.TrimSpace(found.Checksum) == "" {
		if os.Getenv("COMPANION_ALLOW_UNVERIFIED_INDEX") != "1" {
			return fmt.Errorf("library index publishes no checksum for %s — refusing to install it "+
				"(set COMPANION_ALLOW_UNVERIFIED_INDEX=1 only for a mirror you control)", found.ArchiveFileName)
		}
		onProgress("  ⚠ no checksum in index — verification SKIPPED by COMPANION_ALLOW_UNVERIFIED_INDEX=1")
	} else {
		if err := verifyFileChecksum(archivePath, found.Checksum); err != nil {
			onProgress("Checksum mismatch — re-downloading…")
			os.Remove(archivePath)
			if err2 := downloadLibrary(found.URL, archivePath, onProgress); err2 != nil {
				return fmt.Errorf("download: %w", err2)
			}
			if err := verifyFileChecksum(archivePath, found.Checksum); err != nil {
				return fmt.Errorf("checksum verification failed for %s: %w", found.ArchiveFileName, err)
			}
		}
		onProgress("Checksum OK")
	}

	// Extract to a temporary directory first
	// (boards.ExtractArchive strips top-level dir, which is what we want)
	tempDir, err := os.MkdirTemp(dlDir, ".extract-")
	if err != nil {
		return fmt.Errorf("create extract directory: %w", err)
	}
	defer os.RemoveAll(tempDir)

	onProgress("Extracting…")
	if err := boards.ExtractArchive(archivePath, tempDir); err != nil {
		return fmt.Errorf("extract: %w", err)
	}

	// After extraction, library files are directly in tempDir
	// (top-level dir was stripped by extractZip)
	// Check if library.properties is there
	if _, err := os.Stat(filepath.Join(tempDir, "library.properties")); err == nil {
		// Looks like a valid library, move it to the final location
		libDir := m.cfg.LibrariesDir()
		if err := os.MkdirAll(libDir, 0o755); err != nil {
			return fmt.Errorf("create libraries directory: %w", err)
		}

		libName, err := safeLibrarySegment(found.Name)
		if err != nil {
			return fmt.Errorf("library index: invalid library name: %w", err)
		}
		destPath := filepath.Join(libDir, libName)
		os.RemoveAll(destPath)
		if err := os.Rename(tempDir, destPath); err != nil {
			return fmt.Errorf("move: %w", err)
		}
	} else {
		return fmt.Errorf("invalid library archive: no library.properties found")
	}

	onProgress(fmt.Sprintf("✓ Installed %s v%s", found.Name, found.Version))
	return nil
}

// Uninstall removes an installed library.
func (m *Manager) Uninstall(name string) error {
	libName, err := safeLibrarySegment(name)
	if err != nil {
		return fmt.Errorf("invalid library name: %w", err)
	}
	libPath := filepath.Join(m.cfg.LibrariesDir(), libName)
	if _, err := os.Stat(libPath); os.IsNotExist(err) {
		return fmt.Errorf("library %q is not installed", name)
	}
	return os.RemoveAll(libPath)
}

// ListInstalled returns all libraries installed on disk.
func (m *Manager) ListInstalled() ([]InstalledLibrary, error) {
	libDir := m.cfg.LibrariesDir()
	entries, err := os.ReadDir(libDir)
	if err != nil {
		if os.IsNotExist(err) {
			return nil, nil
		}
		return nil, err
	}

	var libs []InstalledLibrary
	for _, e := range entries {
		if !e.IsDir() {
			continue
		}
		lib := parseInstalledLibrary(filepath.Join(libDir, e.Name()))
		if lib != nil {
			libs = append(libs, *lib)
		}
	}

	sort.Slice(libs, func(i, j int) bool { return libs[i].Name < libs[j].Name })
	return libs, nil
}

// parseInstalledLibrary reads library.properties from an installed library dir.
func parseInstalledLibrary(dir string) *InstalledLibrary {
	propsPath := filepath.Join(dir, "library.properties")
	data, err := os.ReadFile(propsPath)
	if err != nil {
		return nil
	}

	props := make(map[string]string)
	for _, line := range strings.Split(string(data), "\n") {
		line = strings.TrimSpace(line)
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		idx := strings.IndexByte(line, '=')
		if idx < 0 {
			continue
		}
		props[strings.TrimSpace(line[:idx])] = strings.TrimSpace(line[idx+1:])
	}

	return &InstalledLibrary{
		Name:     props["name"],
		Version:  props["version"],
		Path:     dir,
		Sentence: props["sentence"],
		Author:   props["author"],
	}
}

// downloadLibrary downloads a library archive to a temporary file and renames
// it into place only after the complete body has been received. Writing
// directly to dest left a truncated file that the next run treated as a cache
// hit; capping the read prevents a hostile index from filling the disk.
func downloadLibrary(url, dest string, onProgress func(string)) error {
	if info, err := os.Stat(dest); err == nil {
		if info.Size() > maxLibraryArchiveBytes {
			return fmt.Errorf("cached archive %s is larger than the %d byte limit", dest, maxLibraryArchiveBytes)
		}
		if info.Size() > 0 {
			return nil // already cached
		}
	}

	client := &http.Client{Timeout: 60 * time.Second}
	resp, err := client.Get(url)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("HTTP %d", resp.StatusCode)
	}
	if resp.ContentLength > maxLibraryArchiveBytes {
		return fmt.Errorf("archive is %d bytes, over the %d byte limit", resp.ContentLength, maxLibraryArchiveBytes)
	}

	dir := filepath.Dir(dest)
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return err
	}
	tmp, err := os.CreateTemp(dir, ".library-download-*")
	if err != nil {
		return err
	}
	tmpName := tmp.Name()
	defer os.Remove(tmpName)

	total := resp.ContentLength
	var downloaded int64
	buf := make([]byte, 32*1024)

	for {
		n, readErr := resp.Body.Read(buf)
		if n > 0 {
			downloaded += int64(n)
			if downloaded > maxLibraryArchiveBytes {
				tmp.Close()
				return fmt.Errorf("download exceeded the %d byte limit — aborted", maxLibraryArchiveBytes)
			}
			if _, werr := tmp.Write(buf[:n]); werr != nil {
				tmp.Close()
				return werr
			}
			if total > 0 && downloaded%(64*1024) == 0 {
				pct := downloaded * 100 / total
				onProgress(fmt.Sprintf("\r  %d%% (%d/%d KB)", pct, downloaded/1024, total/1024))
			}
		}
		if readErr == io.EOF {
			break
		}
		if readErr != nil {
			tmp.Close()
			return readErr
		}
	}

	if total > 0 && downloaded != total {
		tmp.Close()
		return fmt.Errorf("incomplete download: got %d/%d bytes", downloaded, total)
	}
	if err := tmp.Sync(); err != nil {
		tmp.Close()
		return err
	}
	if err := tmp.Close(); err != nil {
		return err
	}
	if err := atomicfile.Replace(tmpName, dest); err != nil {
		return err
	}
	onProgress("")
	return nil
}

// validateLibrarySegment rejects values that are path references or path
// separators. Library and archive names come from a downloaded index, so they
// cannot be trusted as filenames.
func validateLibrarySegment(s, field string) (string, error) {
	v := strings.TrimSpace(s)
	if v == "" {
		return "", fmt.Errorf("%s is empty", field)
	}
	if v == "." || v == ".." {
		return "", fmt.Errorf("%s is a path reference (%q)", field, v)
	}
	if strings.ContainsAny(v, `/\`) || strings.ContainsRune(v, 0) || strings.ContainsAny(v, "\r\n") {
		return "", fmt.Errorf("%s must be a plain name, got %q", field, v)
	}
	if strings.HasPrefix(v, "-") {
		return "", fmt.Errorf("%s must not start with '-', got %q", field, v)
	}
	// Keep names portable. ':' is valid on Unix but on Windows opens an
	// alternate data stream ("name:stream"), so a hostile index could write a
	// file that is invisible to a normal directory listing. The same applies to
	// the other Windows metacharacters. Other punctuation is left alone because
	// legitimate registry names use it.
	for _, r := range v {
		if r < 0x20 || r == 0x7f || strings.ContainsRune(`<>:"|?*`, r) {
			return "", fmt.Errorf("%s contains an unsupported character %q in %q", field, r, v)
		}
	}
	if strings.HasSuffix(v, ".") {
		return "", fmt.Errorf("%s must not end with '.', got %q", field, v)
	}
	if safename.IsWindowsReservedName(v) {
		return "", fmt.Errorf("%s is a reserved device name on Windows: %q", field, v)
	}
	return v, nil
}

func safeLibrarySegment(name string) (string, error) {
	v, err := validateLibrarySegment(name, "library name")
	if err != nil {
		return "", err
	}
	return strings.ReplaceAll(v, " ", "_"), nil
}

func safeArchiveSegment(name string) (string, error) {
	return validateLibrarySegment(name, "archive filename")
}

func readAllLimit(r io.Reader, max int64) ([]byte, error) {
	data, err := io.ReadAll(io.LimitReader(r, max+1))
	if err != nil {
		return nil, err
	}
	if int64(len(data)) > max {
		return nil, fmt.Errorf("data is larger than the %d byte limit", max)
	}
	return data, nil
}

func readFileLimit(path string, max int64) ([]byte, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	if info, err := f.Stat(); err == nil && info.Size() > max {
		return nil, fmt.Errorf("%s is larger than the %d byte limit", path, max)
	}
	return readAllLimit(f, max)
}

// verifyFileChecksum checks a downloaded file against an index checksum of
// the form "SHA256:hexdigits" (case-insensitive algorithm prefix).
func verifyFileChecksum(path, expected string) error {
	algo, sum, ok := strings.Cut(expected, ":")
	if !ok {
		return fmt.Errorf("malformed checksum %q (want ALGO:hex)", expected)
	}
	f, err := os.Open(path)
	if err != nil {
		return err
	}
	defer f.Close()

	var actual string
	switch strings.ToUpper(strings.TrimSpace(algo)) {
	case "SHA256":
		h := sha256.New()
		if _, err := io.Copy(h, f); err != nil {
			return err
		}
		actual = hex.EncodeToString(h.Sum(nil))
	case "MD5":
		h := md5.New()
		if _, err := io.Copy(h, f); err != nil {
			return err
		}
		actual = hex.EncodeToString(h.Sum(nil))
	default:
		return fmt.Errorf("unsupported checksum algorithm %q", algo)
	}
	if !strings.EqualFold(actual, strings.TrimSpace(sum)) {
		return fmt.Errorf("checksum mismatch: got %s, want %s", actual, sum)
	}
	return nil
}
