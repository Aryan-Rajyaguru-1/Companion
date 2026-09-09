// Package boards manages board platforms, package indexes, and FQBN resolution.
// Inspired by arduino-cli's PackageManager — written from scratch.
package boards

import (
	"crypto/sha256"
	"crypto/subtle"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"time"

	"github.com/companion-ide/companion-cli/internal/config"
	"github.com/companion-ide/companion-cli/internal/version"
)

// ── Index types (mirrors package_index.json schema) ──────────────

type PackageIndex struct {
	Packages []Package `json:"packages"`
}

type Package struct {
	Name       string     `json:"name"`
	Maintainer string     `json:"maintainer"`
	WebsiteURL string     `json:"websiteURL"`
	Platforms  []Platform `json:"platforms"`
	Tools      []Tool     `json:"tools"`
}

type Platform struct {
	Name             string      `json:"name"`
	Architecture     string      `json:"architecture"`
	Version          string      `json:"version"`
	Category         string      `json:"category"`
	URL              string      `json:"url"`
	ArchiveFileName  string      `json:"archiveFileName"`
	Checksum         string      `json:"checksum"`
	Size             json.Number `json:"size"`
	Boards           []BoardDef  `json:"boards"`
	ToolDependencies []ToolDep   `json:"toolsDependencies"`
}

type BoardDef struct {
	Name string `json:"name"`
}

type ToolDep struct {
	Packager string `json:"packager"`
	Name     string `json:"name"`
	Version  string `json:"version"`
}

// ── Board represents a resolved board for display ─────────────────

type Board struct {
	Name         string
	FQBN         string
	Platform     string
	Architecture string
	Vendor       string
	Installed    bool
}

// ── BoardPackage represents a package/platform for display ────────

type BoardPackage struct {
	Name         string
	Maintainer   string
	Description  string
	Version      string
	Architecture string
	VendorID     string // e.g. "arduino", "esp32" — used to build vendor:arch install ID
	Installed    bool
}

// ── Manager ───────────────────────────────────────────────────────

type Manager struct {
	cfg     *config.Config
	indexes []*PackageIndex
}

func NewManager(cfg *config.Config) *Manager {
	return &Manager{cfg: cfg}
}

// UpdateIndex downloads all board package indexes from configured URLs.
// Mirrors arduino-cli's core update-index command.
func (m *Manager) UpdateIndex(onProgress func(string)) error {
	urls := append(
		[]string{"https://downloads.arduino.cc/packages/package_index.json"},
		m.cfg.BoardManager.AdditionalURLs...,
	)

	indexDir := m.cfg.IndexesDir()
	if err := os.MkdirAll(indexDir, 0o755); err != nil {
		return err
	}

	client := &http.Client{Timeout: 30 * time.Second}

	for _, url := range urls {
		// Derive filename from URL
		parts := strings.Split(url, "/")
		fname := parts[len(parts)-1]
		if !strings.HasSuffix(fname, ".json") {
			fname = "package_" + fname + "_index.json"
		}
		destPath := filepath.Join(indexDir, fname)

		onProgress(fmt.Sprintf("Downloading %s…", fname))

		resp, err := client.Get(url)
		if err != nil {
			onProgress(fmt.Sprintf("  ⚠ Skip %s: %v", fname, err))
			continue
		}

		data, err := io.ReadAll(resp.Body)
		resp.Body.Close()
		if err != nil {
			onProgress(fmt.Sprintf("  ⚠ Read error %s: %v", fname, err))
			continue
		}

		if resp.StatusCode != 200 {
			onProgress(fmt.Sprintf("  ⚠ HTTP %d for %s", resp.StatusCode, url))
			continue
		}

		if err := os.WriteFile(destPath, data, 0o644); err != nil {
			return fmt.Errorf("writing index %s: %w", fname, err)
		}

		onProgress(fmt.Sprintf("  ✓ %s", fname))
	}

	m.indexes = nil // Invalidate cache
	return nil
}

// loadIndexes parses all JSON index files from disk.
func (m *Manager) loadIndexes() ([]*PackageIndex, error) {
	if m.indexes != nil {
		return m.indexes, nil
	}

	indexDir := m.cfg.IndexesDir()
	entries, err := os.ReadDir(indexDir)
	if err != nil {
		if os.IsNotExist(err) {
			return nil, nil
		}
		return nil, err
	}

	var indexes []*PackageIndex
	for _, e := range entries {
		if !strings.HasSuffix(e.Name(), ".json") {
			continue
		}

		data, err := os.ReadFile(filepath.Join(indexDir, e.Name()))
		if err != nil {
			continue
		}

		var idx PackageIndex
		if err := json.Unmarshal(data, &idx); err != nil {
			continue
		}
		indexes = append(indexes, &idx)
	}

	m.indexes = indexes
	return indexes, nil
}

// Search returns boards matching the query string.
//
// Bug fix: previously when a platform's Boards array was empty (common in
// many package_index.json entries), no results were emitted for that platform.
// This caused "board search avr" to return zero results even when the
// arduino:avr platform exists in the index.
//
// Fix: if Boards is empty, emit one synthetic entry for the platform itself
// so it is discoverable and shows as installed/not-installed.
func (m *Manager) Search(query string) ([]Board, error) {
	indexes, err := m.loadIndexes()
	if err != nil {
		return nil, err
	}

	q := strings.ToLower(strings.TrimSpace(query))
	installed := m.installedPlatforms()
	var results []Board
	seen := make(map[string]bool) // deduplicate by FQBN

	addBoard := func(board Board) {
		if seen[board.FQBN] {
			return
		}
		seen[board.FQBN] = true
		results = append(results, board)
	}

	for _, idx := range indexes {
		for _, pkg := range idx.Packages {
			latest := latestPlatform(pkg.Platforms)
			if latest == nil {
				continue
			}

			platformKey := fmt.Sprintf("%s:%s", pkg.Name, latest.Architecture)
			isInstalled := installed[platformKey]

			// Path 1: platform has an explicit Boards list
			for _, bd := range latest.Boards {
				fqbn := fmt.Sprintf("%s:%s:%s",
					strings.ToLower(pkg.Name),
					latest.Architecture,
					fqbnBoardID(bd.Name),
				)

				board := Board{
					Name:         bd.Name,
					FQBN:         fqbn,
					Platform:     platformKey,
					Architecture: latest.Architecture,
					Vendor:       pkg.Name,
					Installed:    isInstalled,
				}

				// Also search architecture so "avr" finds arduino:avr:* boards
				if q == "" ||
					strings.Contains(strings.ToLower(bd.Name), q) ||
					strings.Contains(strings.ToLower(fqbn), q) ||
					strings.Contains(strings.ToLower(pkg.Name), q) ||
					strings.Contains(strings.ToLower(latest.Architecture), q) {
					addBoard(board)
				}
			}

			// Path 2: platform has NO Boards list — emit one synthetic entry
			// for the platform itself so it appears in search results.
			// This is the main fix: previously these platforms were silently skipped.
			if len(latest.Boards) == 0 {
				syntheticName := fmt.Sprintf("%s (%s)", pkg.Name, latest.Architecture)
				syntheticFQBN := fmt.Sprintf("%s:%s:%s",
					strings.ToLower(pkg.Name),
					latest.Architecture,
					strings.ToLower(latest.Architecture),
				)
				board := Board{
					Name:         syntheticName,
					FQBN:         syntheticFQBN,
					Platform:     platformKey,
					Architecture: latest.Architecture,
					Vendor:       pkg.Name,
					Installed:    isInstalled,
				}

				if q == "" ||
					strings.Contains(strings.ToLower(pkg.Name), q) ||
					strings.Contains(strings.ToLower(latest.Architecture), q) ||
					strings.Contains(strings.ToLower(syntheticFQBN), q) ||
					strings.Contains(strings.ToLower(latest.Name), q) {
					addBoard(board)
				}
			}
		}
	}

	// Merge real board names from INSTALLED platforms' boards.txt. Catalog
	// indexes (including Arduino's own package_index.json) often omit the
	// boards list, which made searches like "uno" return nothing even when
	// the platform providing the Uno was installed.
	if local, err := m.ListAllBoards(); err == nil {
		for _, b := range local {
			if q != "" &&
				!strings.Contains(strings.ToLower(b.Name), q) &&
				!strings.Contains(strings.ToLower(b.FQBN), q) {
				continue
			}
			parts := strings.SplitN(b.Platform, ":", 2)
			addBoard(Board{
				Name:         b.Name,
				FQBN:         b.FQBN,
				Platform:     b.Platform,
				Architecture: b.Platform[strings.LastIndex(b.Platform, ":")+1:],
				Vendor:       parts[0],
				Installed:    true,
			})
		}
	}

	return results, nil
}

// SearchPackages returns available board packages/platforms with their metadata.
func (m *Manager) SearchPackages(query string) ([]BoardPackage, error) {
	indexes, err := m.loadIndexes()
	if err != nil {
		return nil, err
	}

	q := strings.ToLower(strings.TrimSpace(query))
	installed := m.installedPlatforms() // keys are "vendor:arch" e.g. "arduino:avr"
	var results []BoardPackage
	seen := make(map[string]bool)

	for _, idx := range indexes {
		for _, pkg := range idx.Packages {
			// Find latest version of each platform
			latest := latestPlatform(pkg.Platforms)
			if latest == nil {
				continue
			}

			// vendorID is the package name lowercased (e.g. "arduino", "esp32")
			// This matches what ListInstalled uses as the vendor directory name.
			vendorID := strings.ToLower(strings.ReplaceAll(pkg.Name, " ", "-"))
			// Use a de-dup key that includes the vendor so two packages with
			// the same architecture but different vendors don't collide.
			dedupeKey := fmt.Sprintf("%s:%s", vendorID, latest.Architecture)
			if seen[dedupeKey] {
				continue
			}
			seen[dedupeKey] = true

			// Check if query matches
			if q != "" &&
				!strings.Contains(strings.ToLower(pkg.Name), q) &&
				!strings.Contains(strings.ToLower(pkg.Maintainer), q) &&
				!strings.Contains(strings.ToLower(latest.Name), q) &&
				!strings.Contains(strings.ToLower(latest.Architecture), q) &&
				!strings.Contains(strings.ToLower(dedupeKey), q) {
				continue
			}

			// Check installed status using the same "vendor:arch" format as ListInstalled.
			// Also try the raw package name as vendor (some packages use full name as dir).
			isInstalled := installed[dedupeKey] ||
				installed[fmt.Sprintf("%s:%s", pkg.Name, latest.Architecture)]

			pkgResult := BoardPackage{
				Name:         pkg.Name,
				Maintainer:   pkg.Maintainer,
				Description:  latest.Name,
				Version:      latest.Version,
				Architecture: latest.Architecture,
				VendorID:     vendorID,
				Installed:    isInstalled,
			}
			results = append(results, pkgResult)
		}
	}

	return results, nil
}

// ListInstalled returns all installed platforms.
func (m *Manager) ListInstalled() ([]InstalledPlatform, error) {
	pkgDir := m.cfg.PackagesDir()
	entries, err := os.ReadDir(pkgDir)
	if err != nil {
		if os.IsNotExist(err) {
			return nil, nil
		}
		return nil, err
	}

	var platforms []InstalledPlatform

	for _, vendor := range entries {
		if !vendor.IsDir() {
			continue
		}
		hwDir := filepath.Join(pkgDir, vendor.Name(), "hardware")
		archs, err := os.ReadDir(hwDir)
		if err != nil {
			continue
		}
		for _, arch := range archs {
			if !arch.IsDir() {
				continue
			}
			versions, err := os.ReadDir(filepath.Join(hwDir, arch.Name()))
			if err != nil {
				continue
			}
			for _, ver := range versions {
				if !ver.IsDir() {
					continue
				}
				platforms = append(platforms, InstalledPlatform{
					ID:      fmt.Sprintf("%s:%s", vendor.Name(), arch.Name()),
					Version: ver.Name(),
					Path:    filepath.Join(hwDir, arch.Name(), ver.Name()),
				})
			}
		}
	}

	return platforms, nil
}

// InstalledPlatform is a platform installed on disk.
type InstalledPlatform struct {
	ID      string // e.g. "arduino:avr"
	Version string
	Path    string
}

// ResolveFQBN finds the installed platform directory for a given FQBN.
// FQBN format: vendor:architecture:board_id
// Mirrors arduino-cli's PackageManager.ResolveFQBN()
func (m *Manager) ResolveFQBN(fqbn string) (*ResolvedBoard, error) {
	parts := strings.Split(fqbn, ":")
	if len(parts) < 3 {
		return nil, fmt.Errorf("invalid FQBN %q — expected vendor:arch:board_id", fqbn)
	}

	vendor := parts[0]
	arch := parts[1]
	boardID := parts[2]

	// Vendor directories on disk are lowercased at install time
	// (see Manager.Install), so resolve case-insensitively to match.
	vendorDir := strings.ToLower(vendor)

	// Scan installed packages directory
	pkgDir := m.cfg.PackagesDir()
	hwDir := filepath.Join(pkgDir, vendorDir, "hardware", arch)

	entries, err := os.ReadDir(hwDir)
	if err != nil {
		return nil, fmt.Errorf(
			"platform %s:%s not installed — run: companion board install %s:%s",
			vendor, arch, vendor, arch,
		)
	}

	// Pick latest version (semver-aware so 2.0.0 beats 1.9.9)
	var latestVer string
	for _, e := range entries {
		if e.IsDir() && version.Compare(e.Name(), latestVer) > 0 {
			latestVer = e.Name()
		}
	}
	if latestVer == "" {
		return nil, fmt.Errorf("no version installed for %s:%s", vendor, arch)
	}

	platformPath := filepath.Join(hwDir, latestVer)

	// Parse boards.txt to get board config
	boardsFile := filepath.Join(platformPath, "boards.txt")
	boardProps, err := parseBoardsTxt(boardsFile, boardID)
	if err != nil {
		return nil, fmt.Errorf("reading boards.txt: %w", err)
	}

	// Parse platform.txt for build recipes
	platformFile := filepath.Join(platformPath, "platform.txt")
	platformProps, err := parsePropertiesFile(platformFile)
	if err != nil {
		return nil, fmt.Errorf("reading platform.txt: %w", err)
	}

	return &ResolvedBoard{
		FQBN:          fqbn,
		Vendor:        vendor,
		Architecture:  arch,
		BoardID:       boardID,
		PlatformPath:  platformPath,
		BoardProps:    boardProps,
		PlatformProps: platformProps,
		ToolsDir:      filepath.Join(pkgDir, vendor, "tools"),
	}, nil
}

// ResolvedBoard contains all paths and properties needed for compilation.
type ResolvedBoard struct {
	FQBN          string
	Vendor        string
	Architecture  string
	BoardID       string
	PlatformPath  string
	BoardProps    map[string]string
	PlatformProps map[string]string
	ToolsDir      string
}

// GetProp returns a board or platform property, resolving {placeholder}
// references recursively (mirrors Arduino's property expansion).
// Board properties take priority over platform properties.
func (rb *ResolvedBoard) GetProp(key string) string {
	raw := rb.getRaw(key)
	return rb.expandProps(raw, 0)
}

// getRaw returns the unexpanded value for key, board props first.
func (rb *ResolvedBoard) getRaw(key string) string {
	if v, ok := rb.BoardProps[key]; ok {
		return v
	}
	return rb.PlatformProps[key]
}

// expandProps resolves {key} placeholders in s up to maxDepth levels deep.
// Unresolvable placeholders are left as empty strings so they don't land
// on the compiler command line as literal "{...}" tokens.
func (rb *ResolvedBoard) expandProps(s string, depth int) string {
	if depth > 10 || !strings.Contains(s, "{") {
		return s
	}
	var buf strings.Builder
	rest := s
	for {
		start := strings.Index(rest, "{")
		if start < 0 {
			buf.WriteString(rest)
			break
		}
		buf.WriteString(rest[:start])
		// Find matching closing brace accounting for nested braces
		depthCount := 0
		match := -1
		for j := start; j < len(rest); j++ {
			if rest[j] == '{' {
				depthCount++
			} else if rest[j] == '}' {
				depthCount--
				if depthCount == 0 {
					match = j
					break
				}
			}
		}
		if match < 0 {
			// Unclosed brace — write as-is and stop
			buf.WriteString(rest)
			break
		}
		// placeholder spans from start+1 .. match-1
		placeholder := rest[start+1 : match]
		rest = rest[match+1:]

		// Expand nested placeholders inside the placeholder name first
		placeholder = rb.expandProps(placeholder, depth+1)

		// Look up the placeholder key and expand recursively
		val := rb.expandProps(rb.getRaw(placeholder), depth+1)

		// If the placeholder refers to a runtime tool path and wasn't found in
		// the properties, try resolving it from the installed tools directory
		if val == "" && strings.HasPrefix(placeholder, "runtime.tools.") {
			p := strings.TrimPrefix(placeholder, "runtime.tools.")
			if strings.HasSuffix(p, ".path") {
				p = strings.TrimSuffix(p, ".path")
			}
			if rb.ToolsDir != "" {
				toolParent := filepath.Join(rb.ToolsDir, p)
				if entries, err := os.ReadDir(toolParent); err == nil {
					var latest string
					for _, e := range entries {
						if e.IsDir() && version.Compare(e.Name(), latest) > 0 {
							latest = e.Name()
						}
					}
					if latest != "" {
						val = filepath.Join(toolParent, latest)
					}
				}
			}
		}

		buf.WriteString(val)
	}
	return buf.String()
}

// ── Install platform ──────────────────────────────────────────────

// Install downloads and extracts a platform by ID (e.g. "arduino:avr" or "esp32:esp32@3.3.7").
// Supports an optional @version suffix to pin a specific version.
func (m *Manager) Install(platformID string, onProgress func(string)) error {
	// Parse optional @version suffix: "esp32:esp32@3.3.7" → vendor="esp32", arch="esp32", wantVersion="3.3.7"
	var wantVersion string
	if idx := strings.LastIndex(platformID, "@"); idx > 0 {
		wantVersion = platformID[idx+1:]
		platformID = platformID[:idx]
	}

	parts := strings.SplitN(platformID, ":", 2)
	if len(parts) != 2 {
		return fmt.Errorf("invalid platform ID %q — expected vendor:architecture[@version]", platformID)
	}
	vendor, arch := parts[0], parts[1]

	indexes, err := m.loadIndexes()
	if err != nil {
		return err
	}

	// Find platform in indexes — if wantVersion is set, match exactly;
	// otherwise pick the latest version.
	var found *Platform
	var foundPkg *Package

	for _, idx := range indexes {
		for i, pkg := range idx.Packages {
			if !strings.EqualFold(pkg.Name, vendor) {
				continue
			}
			for j, p := range pkg.Platforms {
				if !strings.EqualFold(p.Architecture, arch) {
					continue
				}
				if wantVersion != "" {
					if p.Version == wantVersion {
						found = &idx.Packages[i].Platforms[j]
						foundPkg = &idx.Packages[i]
					}
				} else {
					if found == nil || version.Compare(p.Version, found.Version) > 0 {
						found = &idx.Packages[i].Platforms[j]
						foundPkg = &idx.Packages[i]
					}
				}
			}
		}
	}

	if found == nil {
		if wantVersion != "" {
			return fmt.Errorf(
				"platform %q version %s not found in any index\nRun: companion board update-index",
				platformID, wantVersion,
			)
		}
		return fmt.Errorf(
			"platform %q not found in any index\nRun: companion board update-index",
			platformID,
		)
	}

	onProgress(fmt.Sprintf("Installing %s:%s v%s…", foundPkg.Name, found.Architecture, found.Version))

	// Download archive
	dlDir := m.cfg.Directories.Downloads
	os.MkdirAll(dlDir, 0o755)

	archivePath := filepath.Join(dlDir, found.ArchiveFileName)
	if err := downloadFile(found.URL, archivePath, onProgress); err != nil {
		return fmt.Errorf("download: %w", err)
	}
	// Verify the archive against the index SHA-256 checksum (matches what
	// was published, and matches the library-install trust level).
	if err := verifyArchiveChecksum(archivePath, found.Checksum, onProgress); err != nil {
		os.Remove(archivePath)
		return err
	}

	// Extract to packages directory
	destDir := filepath.Join(m.cfg.PackagesDir(), strings.ToLower(foundPkg.Name),
		"hardware", found.Architecture, found.Version)
	os.MkdirAll(destDir, 0o755)

	onProgress("Extracting…")
	if err := extractArchive(archivePath, destDir); err != nil {
		return fmt.Errorf("extract: %w", err)
	}

	// Install required tool dependencies
	for _, dep := range found.ToolDependencies {
		onProgress(fmt.Sprintf("Installing tool %s v%s…", dep.Name, dep.Version))
		if err := m.installTool(dep, indexes, onProgress); err != nil {
			onProgress(fmt.Sprintf("  ⚠ Tool install failed: %v", err))
		}
	}

	m.indexes = nil
	onProgress(fmt.Sprintf("✓ Installed %s:%s v%s", vendor, arch, found.Version))
	return nil
}

// installTool finds and downloads a tool dependency.
// It first tries an exact match on the host string (e.g. "linux_aarch64"),
// then falls back to a substring match on hostArchKey() (e.g. "aarch64").
// This handles the inconsistency between old-style host strings
// ("x86_64-linux-gnu") and new-style ones ("linux_aarch64") across
// different versions of the Espressif/Arduino package indexes.
func (m *Manager) installTool(dep ToolDep, indexes []*PackageIndex, onProgress func(string)) error {
	sys := toolSystem()
	archKey := hostArchKey()

	for _, idx := range indexes {
		for _, pkg := range idx.Packages {
			if !strings.EqualFold(pkg.Name, dep.Packager) {
				continue
			}
			for _, tool := range pkg.Tools {
				if tool.Name != dep.Name || tool.Version != dep.Version {
					continue
				}

				// Pass 1: exact host string match
				var matched *ToolSystem
				for i := range tool.Systems {
					if tool.Systems[i].Host == sys {
						matched = &tool.Systems[i]
						break
					}
				}

				// Pass 2: fallback — arch substring match
				// Handles cases like index using "linux_aarch64" when sys is
				// "arm-linux-gnueabihf" or vice versa due to index version drift.
				if matched == nil {
					for i := range tool.Systems {
						if strings.Contains(tool.Systems[i].Host, archKey) {
							matched = &tool.Systems[i]
							break
						}
					}
				}

				if matched == nil {
					// No matching system binary for this platform — skip silently
					continue
				}

				// Check if already installed — skip download if present and non-empty
				destDir := filepath.Join(m.cfg.PackagesDir(), strings.ToLower(pkg.Name),
					"tools", dep.Name, dep.Version)
				if info, err := os.Stat(destDir); err == nil && info.IsDir() {
					entries, _ := os.ReadDir(destDir)
					if len(entries) > 0 {
						onProgress(fmt.Sprintf("  ✓ Tool %s v%s already installed", dep.Name, dep.Version))
						return nil
					}
				}

				os.MkdirAll(filepath.Dir(destDir), 0o755)
				archivePath := filepath.Join(m.cfg.Directories.Downloads, matched.ArchiveFileName)
				if err := downloadFile(matched.URL, archivePath, func(s string) {}); err != nil {
					return fmt.Errorf("download tool %s: %w", dep.Name, err)
				}
				if err := verifyArchiveChecksum(archivePath, matched.Checksum, func(s string) {}); err != nil {
					os.Remove(archivePath)
					return fmt.Errorf("tool %s checksum: %w", dep.Name, err)
				}

				// Tool archives keep their internal layout: the single
				// top-level directory IS the version folder. Extract with
				// root preserved into staging, then move it into place.
				tmpExtract := filepath.Join(m.cfg.Directories.Downloads, ".tool-extract")
				os.RemoveAll(tmpExtract)
				os.MkdirAll(tmpExtract, 0o755)
				if err := ExtractArchiveKeepRoot(archivePath, tmpExtract); err != nil {
					os.RemoveAll(tmpExtract)
					return fmt.Errorf("extract tool %s: %w", dep.Name, err)
				}
				if err := moveToDest(tmpExtract, destDir); err != nil {
					os.RemoveAll(tmpExtract)
					return fmt.Errorf("install tool %s: %w", dep.Name, err)
				}
				os.RemoveAll(tmpExtract)
				onProgress(fmt.Sprintf("  ✓ Tool %s v%s installed", dep.Name, dep.Version))
				return nil
			}
		}
	}
	return nil // Tool not found in index — silently skip (may already be installed)
}

// moveToDest moves the extracted archive contents into destDir:
//   - a single top-level directory is renamed to destDir itself
//     (its name — typically the version — is normalized to destDir),
//   - otherwise every entry is moved inside destDir.
//
// Falls back to a recursive copy when src and dst are on different
// filesystems and rename fails with EXDEV.
func moveToDest(srcDir, destDir string) error {
	entries, err := os.ReadDir(srcDir)
	if err != nil {
		return err
	}
	if len(entries) == 0 {
		return fmt.Errorf("archive extracted nothing")
	}

	os.RemoveAll(destDir)
	os.MkdirAll(filepath.Dir(destDir), 0o755)

	if len(entries) == 1 && entries[0].IsDir() {
		if err := os.Rename(filepath.Join(srcDir, entries[0].Name()), destDir); err == nil {
			return nil
		}
		// Cross-device: copy then remove.
		if err := copyTree(filepath.Join(srcDir, entries[0].Name()), destDir); err != nil {
			return err
		}
		return nil
	}

	os.MkdirAll(destDir, 0o755)
	for _, e := range entries {
		from := filepath.Join(srcDir, e.Name())
		to := filepath.Join(destDir, e.Name())
		if err := os.Rename(from, to); err != nil {
			if err := copyTree(from, to); err != nil {
				return err
			}
		}
	}
	return nil
}

// copyTree recursively copies a file or directory tree.
func copyTree(src, dst string) error {
	info, err := os.Stat(src)
	if err != nil {
		return err
	}
	if info.IsDir() {
		if err := os.MkdirAll(dst, info.Mode()); err != nil {
			return err
		}
		entries, err := os.ReadDir(src)
		if err != nil {
			return err
		}
		for _, e := range entries {
			if err := copyTree(filepath.Join(src, e.Name()), filepath.Join(dst, e.Name())); err != nil {
				return err
			}
		}
		return nil
	}
	in, err := os.Open(src)
	if err != nil {
		return err
	}
	defer in.Close()
	out, err := os.OpenFile(dst, os.O_CREATE|os.O_WRONLY|os.O_TRUNC, info.Mode())
	if err != nil {
		return err
	}
	defer out.Close()
	_, err = io.Copy(out, in)
	return err
}

// ── Helpers ───────────────────────────────────────────────────────

type Tool struct {
	Name    string       `json:"name"`
	Version string       `json:"version"`
	Systems []ToolSystem `json:"systems"`
}

type ToolSystem struct {
	Host            string      `json:"host"`
	URL             string      `json:"url"`
	ArchiveFileName string      `json:"archiveFileName"`
	Checksum        string      `json:"checksum"`
	Size            json.Number `json:"size"`
}

// latestPlatform returns the latest version of a platform from a slice
// (semver-aware so 2.0.0 beats 1.9.9).
func latestPlatform(platforms []Platform) *Platform {
	var latest *Platform
	for i := range platforms {
		if latest == nil || version.Compare(platforms[i].Version, latest.Version) > 0 {
			latest = &platforms[i]
		}
	}
	return latest
}

// fqbnBoardID converts a board name to a safe board ID.
func fqbnBoardID(name string) string {
	s := strings.ToLower(name)
	s = strings.ReplaceAll(s, " ", "_")
	s = strings.ReplaceAll(s, "-", "_")
	var out []rune
	for _, r := range s {
		if (r >= 'a' && r <= 'z') || (r >= '0' && r <= '9') || r == '_' {
			out = append(out, r)
		}
	}
	return string(out)
}

// installedPlatforms returns a set of installed platform IDs.
func (m *Manager) installedPlatforms() map[string]bool {
	result := make(map[string]bool)
	pkgs, _ := m.ListInstalled()
	for _, p := range pkgs {
		result[p.ID] = true
	}
	return result
}

// parseBoardsTxt parses boards.txt and returns properties for a specific board ID.
func parseBoardsTxt(path, boardID string) (map[string]string, error) {
	all, err := parsePropertiesFile(path)
	if err != nil {
		return nil, err
	}

	prefix := boardID + "."
	result := make(map[string]string)
	for k, v := range all {
		if strings.HasPrefix(k, prefix) {
			result[strings.TrimPrefix(k, prefix)] = v
		}
	}

	if len(result) == 0 {
		return nil, fmt.Errorf("board %q not found in boards.txt", boardID)
	}
	return result, nil
}

// parsePropertiesFile parses a Java .properties style key=value file.
func parsePropertiesFile(path string) (map[string]string, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}

	result := make(map[string]string)
	for _, line := range strings.Split(string(data), "\n") {
		line = strings.TrimSpace(line)
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		idx := strings.IndexByte(line, '=')
		if idx < 0 {
			continue
		}
		key := strings.TrimSpace(line[:idx])
		val := strings.TrimSpace(line[idx+1:])
		result[key] = val
	}
	return result, nil
}

// downloadFile downloads a URL to a destination path with progress reporting.
func downloadFile(url, dest string, onProgress func(string)) error {
	// Check if file exists and has reasonable size (> 1KB)
	// If file is too small, it's likely incomplete and should be re-downloaded
	if info, err := os.Stat(dest); err == nil && info.Size() > 1024 {
		return nil // Already downloaded (and not suspiciously small)
	}

	client := &http.Client{Timeout: 120 * time.Second}
	resp, err := client.Get(url)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		return fmt.Errorf("HTTP %d from %s", resp.StatusCode, url)
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
			if _, werr := f.Write(buf[:n]); werr != nil {
				return werr
			}
			downloaded += int64(n)
			if total > 0 {
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

	// Verify we got all the bytes
	if total > 0 && downloaded < total {
		os.Remove(dest) // Clean up incomplete file
		return fmt.Errorf("incomplete download: got %d/%d bytes", downloaded, total)
	}

	onProgress("")
	return nil
}

// verifyArchiveChecksum checks a downloaded archive against the published
// "<ALGO>:<hex>" checksum from the package index. An empty expected checksum
// (index omits it) logs a warning and passes — some mirrors don't publish
// one. A mismatch is a hard error: the archive may be corrupted or tampered.
func verifyArchiveChecksum(path, expected string, onProgress func(string)) error {
	if strings.TrimSpace(expected) == "" {
		onProgress("  ⚠ no checksum published in index — skipping verification")
		return nil
	}
	algo, sum, ok := strings.Cut(expected, ":")
	if !ok {
		return fmt.Errorf("malformed index checksum %q (want ALGO:hex)", expected)
	}
	if !strings.EqualFold(strings.TrimSpace(algo), "sha-256") {
		onProgress(fmt.Sprintf("  ⚠ unsupported checksum algorithm %q — skipping", algo))
		return nil
	}
	want, err := hex.DecodeString(strings.TrimSpace(sum))
	if err != nil || len(want) != sha256.Size {
		return fmt.Errorf("malformed SHA-256 checksum %q", sum)
	}

	f, err := os.Open(path)
	if err != nil {
		return err
	}
	defer f.Close()
	h := sha256.New()
	if _, err := io.Copy(h, f); err != nil {
		return err
	}
	got := h.Sum(nil)
	if subtle.ConstantTimeCompare(got, want) != 1 {
		return fmt.Errorf("checksum mismatch: got %s, want %s", hex.EncodeToString(got), hex.EncodeToString(want))
	}
	onProgress("  ✓ SHA-256 verified")
	return nil
}

// extractArchive extracts .zip or .tar.bz2/.tar.gz to dest directory,
// stripping the archive's single top-level directory (library layout).
func extractArchive(archivePath, destDir string) error {
	return extractArchiveOpts(archivePath, destDir, true)
}

// extractArchiveKeepRoot extracts preserving the archive's internal
// structure (used for tool archives whose top-level directory is
// meaningful, e.g. the version folder in Arduino package tool archives).
func extractArchiveKeepRoot(archivePath, destDir string) error {
	return extractArchiveOpts(archivePath, destDir, false)
}

func extractArchiveOpts(archivePath, destDir string, stripTop bool) error {
	if strings.HasSuffix(archivePath, ".zip") {
		return extractZipOpts(archivePath, destDir, stripTop)
	}
	if strings.HasSuffix(archivePath, ".tar.bz2") ||
		strings.HasSuffix(archivePath, ".tar.gz") ||
		strings.HasSuffix(archivePath, ".tar.xz") {
		return extractTarOpts(archivePath, destDir, stripTop)
	}
	return fmt.Errorf("unsupported archive format: %s", filepath.Ext(archivePath))
}

// toolSystem returns the arduino-cli system string for the current OS/arch.
// The host strings must match what Espressif/Arduino use in their package indexes:
//   linux_aarch64      — ARM64 Linux (Jetson, RPi 64-bit, Apple M1 cross, etc.)
//   arm-linux-gnueabihf — ARM 32-bit Linux (RPi 32-bit)
//   x86_64-linux-gnu   — 64-bit Linux
//   arm64-apple-darwin — Apple Silicon macOS
//   x86_64-apple-darwin — Intel macOS
//   i686-mingw32       — Windows
func toolSystem() string {
	switch {
	case isLinuxARM64():
		return "linux_aarch64"
	case isLinuxARM():
		return "arm-linux-gnueabihf"
	case isLinux64():
		return "x86_64-linux-gnu"
	case isDarwinARM():
		return "arm64-apple-darwin"
	case isDarwin64():
		return "x86_64-apple-darwin"
	case isWindows64():
		return "i686-mingw32"
	default:
		return "x86_64-linux-gnu"
	}
}

// hostArchKey returns a substring that appears in all host strings for this arch.
// Used as a fallback when the index uses a non-standard host string format.
func hostArchKey() string {
	switch runtime.GOARCH {
	case "arm64":
		return "aarch64"
	case "arm":
		return "arm"
	case "amd64":
		return "x86_64"
	default:
		return "x86_64"
	}
}

func isLinuxARM64() bool { return runtime.GOOS == "linux" && runtime.GOARCH == "arm64" }
func isLinuxARM() bool   { return runtime.GOOS == "linux" && runtime.GOARCH == "arm" }
func isLinux64() bool    { return runtime.GOOS == "linux" && runtime.GOARCH == "amd64" }
func isDarwinARM() bool  { return runtime.GOOS == "darwin" && runtime.GOARCH == "arm64" }
func isDarwin64() bool   { return runtime.GOOS == "darwin" && runtime.GOARCH == "amd64" }
func isWindows64() bool  { return runtime.GOOS == "windows" }
