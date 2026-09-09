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

	"github.com/companion-ide/companion-cli/internal/boards"
	"github.com/companion-ide/companion-cli/internal/config"
	semver "github.com/companion-ide/companion-cli/internal/version"
)

// ── Index types (mirrors library_index.json schema) ──────────────

const LibraryIndexURL = "https://downloads.arduino.cc/libraries/library_index.json"

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

	data, err := io.ReadAll(resp.Body)
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
	data, err := os.ReadFile(indexPath)
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
	os.MkdirAll(dlDir, 0o755)
	archivePath := filepath.Join(dlDir, found.ArchiveFileName)

	if err := downloadLibrary(found.URL, archivePath, onProgress); err != nil {
		return fmt.Errorf("download: %w", err)
	}

	// Verify archive integrity (the index checksum was parsed but never
	// checked). On mismatch, assume a corrupt cached archive, re-download
	// once, and verify again before giving up.
	if found.Checksum != "" {
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
	tempDir := filepath.Join(m.cfg.Directories.Downloads, ".extract")
	os.RemoveAll(tempDir)
	os.MkdirAll(tempDir, 0o755)

	onProgress("Extracting…")
	if err := boards.ExtractArchive(archivePath, tempDir); err != nil {
		os.RemoveAll(tempDir)
		return fmt.Errorf("extract: %w", err)
	}

	// After extraction, library files are directly in tempDir
	// (top-level dir was stripped by extractZip)
	// Check if library.properties is there
	if _, err := os.Stat(filepath.Join(tempDir, "library.properties")); err == nil {
		// Looks like a valid library, move it to the final location
		libDir := m.cfg.LibrariesDir()
		os.MkdirAll(libDir, 0o755)

		libName := strings.ReplaceAll(found.Name, " ", "_")
		destPath := filepath.Join(libDir, libName)
		os.RemoveAll(destPath)
		if err := os.Rename(tempDir, destPath); err != nil {
			os.RemoveAll(tempDir)
			return fmt.Errorf("move: %w", err)
		}
	} else {
		os.RemoveAll(tempDir)
		return fmt.Errorf("invalid library archive: no library.properties found")
	}

	onProgress(fmt.Sprintf("✓ Installed %s v%s", found.Name, found.Version))
	return nil
}

// Uninstall removes an installed library.
func (m *Manager) Uninstall(name string) error {
	libPath := filepath.Join(m.cfg.LibrariesDir(), strings.ReplaceAll(name, " ", "_"))
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

// downloadLibrary downloads a library archive.
func downloadLibrary(url, dest string, onProgress func(string)) error {
	if _, err := os.Stat(dest); err == nil {
		return nil // already cached
	}

	client := &http.Client{Timeout: 60 * time.Second}
	resp, err := client.Get(url)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		return fmt.Errorf("HTTP %d", resp.StatusCode)
	}

	f, err := os.Create(dest)
	if err != nil {
		return err
	}
	defer f.Close()

	total := resp.ContentLength
	var downloaded int64
	buf := make([]byte, 32*1024)

	for {
		n, err := resp.Body.Read(buf)
		if n > 0 {
			f.Write(buf[:n])
			downloaded += int64(n)
			if total > 0 && downloaded%(64*1024) == 0 {
				pct := downloaded * 100 / total
				onProgress(fmt.Sprintf("\r  %d%% (%d/%d KB)", pct, downloaded/1024, total/1024))
			}
		}
		if err == io.EOF {
			break
		}
		if err != nil {
			return err
		}
	}
	fmt.Println()
	return nil
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
