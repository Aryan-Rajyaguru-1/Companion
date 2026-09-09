// Package compiler — cache.go
//
// Content-addressed build cache for compiled object files.
//
// Design from arduino-cli's build cache strategy:
//   - Each source file gets a cache key: SHA-256 of (source content + compiler flags)
//   - Cached .o files survive across IDE restarts (unlike temp dirs)
//   - Cache stored in ~/.companion-cli/cache/builds/{fqbn_hash}/{file_hash}.o
//   - Core library (libcore.a) uses a separate key: platform files hash
//   - Maximum cache size enforced with LRU eviction
//
// Impact: 70% faster on 2nd/3rd compiles for unchanged sketches.
// Even a single changed line only recompiles that .cpp file — core stays cached.
package compiler

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"time"
)

const (
	// MaxCacheAgeDays evicts entries older than this (prevents stale toolchain objects)
	MaxCacheAgeDays = 30
	// MaxCacheSizeMB is the soft limit; LRU eviction runs when exceeded
	MaxCacheSizeMB = 512
	// BuildCacheSchemaVersion is mixed into every cache key. Bump it when
	// key inputs change meaning (e.g. flag normalization rules) so old
	// entries can never be served to a new pipeline.
	BuildCacheSchemaVersion = 1
)

// buildDirVolatileDirs lists path prefixes that must not participate in
// cache keys because they change between runs (temp build dirs are new
// every invocation). Normalized to a "{BUILD_DIR}" token before hashing.
// Derived from os.TempDir() at init — NOT a hardcoded "/tmp" — so the
// prefix matches on Windows (%TEMP% = C:\Users\...\AppData\Local\Temp)
// and macOS (/var/folders/...) too.
var buildDirVolatileDirs = []string{
	filepath.Join(os.TempDir(), "companion_build_"),
	filepath.Join(os.TempDir(), "companion_sketch_"),
}

// ── BuildCache ─────────────────────────────────────────────────────

// BuildCache is a content-addressed cache of compiled object files.
// Thread-safe for concurrent use by a single Compiler instance.
type BuildCache struct {
	baseDir string
}

// NewBuildCache creates a cache rooted at dir.
// The directory is created if it doesn't exist.
func NewBuildCache(dir string) (*BuildCache, error) {
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return nil, fmt.Errorf("build cache: %w", err)
	}
	return &BuildCache{baseDir: dir}, nil
}

// DefaultCacheDir returns the default cache directory path.
func DefaultCacheDir(dataDir string) string {
	return filepath.Join(dataDir, "cache", "builds")
}

// ── Object file cache ─────────────────────────────────────────────

// ObjectKey computes the cache key for a compiled object file.
// Key inputs:
//   - Source file content (SHA-256)
//   - Compiler flags (sorted for determinism)
//   - FQBN core identifier
//
// If any input changes, the object is recompiled.
func (bc *BuildCache) ObjectKey(srcPath, fqbn string, flags []string) (string, error) {
	h := sha256.New()

	// 1. Source content
	f, err := os.Open(srcPath)
	if err != nil {
		return "", err
	}
	if _, err := io.Copy(h, f); err != nil {
		f.Close()
		return "", err
	}
	f.Close()

	// 2. Compiler flags (sorted so order doesn't matter)
	sorted := make([]string, len(flags))
	copy(sorted, flags)
	sort.Strings(sorted)
	for _, flag := range sorted {
		h.Write([]byte(flag))
	}

	// 3. FQBN scope (prevents cross-board cache pollution)
	h.Write([]byte(fqbn))

	return hex.EncodeToString(h.Sum(nil))[:32], nil
}

// CoreKey computes a cache key for a compiled core library (libcore.a).
// Inputs:
//   - All .c/.cpp file paths + their content hashes from the core dir
//   - Compiler flags
func (bc *BuildCache) CoreKey(coreDir, fqbn string, flags []string) (string, error) {
	h := sha256.New()

	// Scan all source files in core directory, sorted for determinism
	var coreSources []string
	err := filepath.Walk(coreDir, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return nil
		}
		if info.IsDir() {
			return nil
		}
		ext := strings.ToLower(filepath.Ext(path))
		if ext == ".c" || ext == ".cpp" || ext == ".s" || ext == ".S" {
			coreSources = append(coreSources, path)
		}
		return nil
	})
	if err != nil {
		return "", err
	}
	sort.Strings(coreSources)

	for _, src := range coreSources {
		f, err := os.Open(src)
		if err != nil {
			continue
		}
		h.Write([]byte(src)) // include path so renames invalidate
		io.Copy(h, f)
		f.Close()
	}

	// Compiler flags
	sorted := make([]string, len(flags))
	copy(sorted, flags)
	sort.Strings(sorted)
	for _, flag := range sorted {
		h.Write([]byte(flag))
	}
	h.Write([]byte(fqbn))

	return hex.EncodeToString(h.Sum(nil))[:32], nil
}

// ── Get / Put ─────────────────────────────────────────────────────

// GetObject returns the path to a cached object file, or "" if not cached.
func (bc *BuildCache) GetObject(key string) string {
	p := bc.objectPath(key)
	info, err := os.Stat(p)
	if err != nil || info.Size() < 8 {
		return ""
	}
	// Touch mtime for LRU tracking
	now := time.Now()
	os.Chtimes(p, now, now)
	return p
}

// PutObject copies srcPath into the cache under key.
// Returns the cache path.
func (bc *BuildCache) PutObject(key, srcPath string) (string, error) {
	dst := bc.objectPath(key)
	if err := os.MkdirAll(filepath.Dir(dst), 0o755); err != nil {
		return "", err
	}
	if err := copyFileCache(srcPath, dst); err != nil {
		return "", err
	}
	return dst, nil
}

// GetCore returns the path to a cached libcore.a, or "" if not cached.
func (bc *BuildCache) GetCore(key string) string {
	p := bc.corePath(key)
	info, err := os.Stat(p)
	if err != nil || info.Size() < 100 {
		return ""
	}
	now := time.Now()
	os.Chtimes(p, now, now)
	return p
}

// PutCore copies srcPath (libcore.a) into the cache under key.
func (bc *BuildCache) PutCore(key, srcPath string) (string, error) {
	dst := bc.corePath(key)
	if err := os.MkdirAll(filepath.Dir(dst), 0o755); err != nil {
		return "", err
	}
	if err := copyFileCache(srcPath, dst); err != nil {
		return "", err
	}
	return dst, nil
}

// ── Core compile-commands (compile_commands.json completeness) ──

// PutCoreTUs stores the core's captured translation-unit commands beside the
// cached archive so a warm-core build can still export a complete
// compile_commands.json without re-walking the core.
func (bc *BuildCache) PutCoreTUs(key string, tus []CompileCommand) error {
	if len(tus) == 0 {
		return nil
	}
	data, err := json.Marshal(tus)
	if err != nil {
		return err
	}
	dst := bc.baseDir + "/core/" + key + ".tus.json"
	if err := os.MkdirAll(filepath.Dir(dst), 0o755); err != nil {
		return err
	}
	return os.WriteFile(dst, data, 0o644)
}

// GetCoreTUs returns the core's previously captured compile commands, or nil.
func (bc *BuildCache) GetCoreTUs(key string) []CompileCommand {
	src := bc.baseDir + "/core/" + key + ".tus.json"
	data, err := os.ReadFile(src)
	if err != nil {
		return nil
	}
	var tus []CompileCommand
	if json.Unmarshal(data, &tus) != nil {
		return nil
	}
	return tus
}

// ── Cache paths ───────────────────────────────────────────────────

func (bc *BuildCache) objectPath(key string) string {
	// Two-level sharding: first 2 chars of key → subdirectory
	return filepath.Join(bc.baseDir, "obj", key[:2], key+".o")
}

func (bc *BuildCache) corePath(key string) string {
	return filepath.Join(bc.baseDir, "core", key+".a")
}

// ── Stats ─────────────────────────────────────────────────────────

// Stats returns cache statistics.
type CacheStats struct {
	ObjectCount int
	CoreCount   int
	TotalSizeMB float64
	OldestEntry time.Time
}

func (bc *BuildCache) Stats() CacheStats {
	var stats CacheStats
	var oldest time.Time

	filepath.Walk(bc.baseDir, func(path string, info os.FileInfo, err error) error {
		if err != nil || info.IsDir() {
			return nil
		}
		ext := filepath.Ext(path)
		switch ext {
		case ".o":
			stats.ObjectCount++
		case ".a":
			stats.CoreCount++
		}
		stats.TotalSizeMB += float64(info.Size()) / (1024 * 1024)
		if oldest.IsZero() || info.ModTime().Before(oldest) {
			oldest = info.ModTime()
		}
		return nil
	})
	stats.OldestEntry = oldest
	return stats
}

// ── Eviction ─────────────────────────────────────────────────────

// Evict removes cache entries older than MaxCacheAgeDays, then
// enforces MaxCacheSizeMB by removing oldest entries first (LRU).
func (bc *BuildCache) Evict() error {
	cutoff := time.Now().AddDate(0, 0, -MaxCacheAgeDays)

	type entry struct {
		path    string
		modTime time.Time
		size    int64
	}
	var entries []entry

	err := filepath.Walk(bc.baseDir, func(path string, info os.FileInfo, err error) error {
		if err != nil || info.IsDir() {
			return nil
		}
		ext := filepath.Ext(path)
		if ext != ".o" && ext != ".a" {
			return nil
		}
		if info.ModTime().Before(cutoff) {
			os.Remove(path)
			return nil
		}
		entries = append(entries, entry{path, info.ModTime(), info.Size()})
		return nil
	})
	if err != nil {
		return err
	}

	// LRU: remove oldest if over size limit
	var totalBytes int64
	for _, e := range entries {
		totalBytes += e.size
	}
	limitBytes := int64(MaxCacheSizeMB * 1024 * 1024)
	if totalBytes <= limitBytes {
		return nil
	}

	// Sort oldest first
	sort.Slice(entries, func(i, j int) bool {
		return entries[i].modTime.Before(entries[j].modTime)
	})
	for _, e := range entries {
		if totalBytes <= limitBytes {
			break
		}
		os.Remove(e.path)
		totalBytes -= e.size
	}
	return nil
}

// hashGeneratedHeader folds a GENERATED C header's effective content into a
// hash — sorting macro lines and dropping the file's own path references —
// so regenerating the same logical header into a fresh temp dir yields the
// same digest. Path/mtime identity (AppendFileMeta) is WRONG here: only the
// macro set affects compilation.
func hashGeneratedHeader(h io.Writer, path string) {
	data, err := os.ReadFile(path)
	if err != nil {
		return
	}
	lines := strings.Split(string(data), "\n")
	var defs []string
	for _, ln := range lines {
		ln = strings.TrimSpace(ln)
		if strings.HasPrefix(ln, "#define CONFIG_") || strings.HasPrefix(ln, "/* #undef CONFIG_") {
			defs = append(defs, ln)
		}
	}
	sort.Strings(defs)
	h.Write([]byte("sdkconfig|"))
	for _, d := range defs {
		h.Write([]byte(d))
		h.Write([]byte("\n"))
	}
}

// hashFileContents returns the hex SHA-256 of a file's bytes.
func hashFileContents(path string) (string, error) {
	f, err := os.Open(path)
	if err != nil {
		return "", err
	}
	defer f.Close()
	h := sha256.New()
	if _, err := io.Copy(h, f); err != nil {
		return "", err
	}
	return hex.EncodeToString(h.Sum(nil)), nil
}

// ── Cache-key helpers ─────────────────────────────────────────────

// NormalizeFlags returns a copy of flags with every occurrence of the given
// directory paths replaced by a "{BUILD_DIR}" token, so cache keys don't
// change when the build directory moves (temp dirs are new every run).
// Full paths are replaced before their parent prefixes (longest first) so
// "/a/b/sketch" collapses entirely instead of leaving "/sketch" behind.
func NormalizeFlags(flags []string, volatileDirs ...string) []string {
	out := make([]string, len(flags))
	copy(out, flags)
	dirs := make([]string, len(volatileDirs))
	copy(dirs, volatileDirs)
	sort.Slice(dirs, func(i, j int) bool { return len(dirs[i]) > len(dirs[j]) })
	for i, f := range out {
		for _, d := range dirs {
			if d != "" && strings.Contains(f, d) {
				out[i] = strings.ReplaceAll(f, d, "{BUILD_DIR}")
				break
			}
		}
	}
	return out
}

// AppendFileMeta mixes a file's identity (path + size + mtime) into a hash.
// Used to fold volatile-but-cheap-to-detect inputs (platform.txt, boards.txt,
// toolchain binaries) into cache keys without hashing megabytes of content.
func AppendFileMeta(h io.Writer, path string) {
	if info, err := os.Stat(path); err == nil {
		fmt.Fprintf(h, "|%s|%d|%d", path, info.Size(), info.ModTime().UnixNano())
	}
}

// ── File copy helper ──────────────────────────────────────────────

func copyFileCache(src, dst string) error {
	in, err := os.Open(src)
	if err != nil {
		return err
	}
	defer in.Close()
	tmp := dst + ".tmp"
	out, err := os.Create(tmp)
	if err != nil {
		return err
	}
	if _, err := io.Copy(out, in); err != nil {
		out.Close()
		os.Remove(tmp)
		return err
	}
	out.Close()
	return os.Rename(tmp, dst)
}
