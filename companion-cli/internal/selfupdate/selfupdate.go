// Package selfupdate checks the published Companion releases and safely
// replaces the companion executable.
//
// The updater is deliberately fail-closed: it only installs an asset that is
// named for the current OS/architecture and whose SHA-256 digest appears in the
// release's SHA256SUMS.txt. The replacement is written beside the destination
// and moved into place, so a failed download never leaves a truncated binary.
package selfupdate

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"runtime"
	"sort"
	"strings"
	"time"
)

const (
	// DefaultRepo is the canonical release repository.
	DefaultRepo = "Aryan-Rajyaguru-1/Companion"
	// DefaultAPIBase is the public GitHub API. It is a variable only through
	// Options so tests and enterprise mirrors can point at another API.
	DefaultAPIBase = "https://api.github.com"
	// ChecksumsAssetName is produced by the release workflow over all assets.
	ChecksumsAssetName = "SHA256SUMS.txt"

	maxReleaseJSON = 8 << 20
	maxChecksums   = 2 << 20
	maxBinary      = 128 << 20
)

// Options configures an Updater. Empty values select production defaults.
type Options struct {
	Repo           string
	APIBaseURL     string
	CurrentVersion string
	GOOS           string
	GOARCH         string
	HTTPClient     *http.Client
}

// Asset is a release asset exposed to the CLI and IDE.
type Asset struct {
	Name   string `json:"name"`
	URL    string `json:"url"`
	Size   int64  `json:"size,omitempty"`
	Digest string `json:"digest,omitempty"`
}

// Release is the release metadata needed by the updater.
type Release struct {
	TagName     string  `json:"tag_name"`
	Name        string  `json:"name,omitempty"`
	URL         string  `json:"html_url,omitempty"`
	PublishedAt string  `json:"published_at,omitempty"`
	Prerelease  bool    `json:"prerelease"`
	Notes       string  `json:"release_notes,omitempty"`
	Assets      []Asset `json:"assets,omitempty"`
}

// CheckResult describes the selected release and whether the current binary is
// older than it. It is also the stable JSON contract consumed by the IDE.
type CheckResult struct {
	CurrentVersion  string  `json:"current_version"`
	LatestVersion   string  `json:"latest_version"`
	UpdateAvailable bool    `json:"update_available"`
	ReleaseName     string  `json:"release_name,omitempty"`
	ReleaseURL      string  `json:"release_url,omitempty"`
	PublishedAt     string  `json:"published_at,omitempty"`
	Prerelease      bool    `json:"prerelease"`
	AssetName       string  `json:"asset_name,omitempty"`
	AssetURL        string  `json:"asset_url,omitempty"`
	AssetSize       int64   `json:"asset_size,omitempty"`
	AssetDigest     string  `json:"asset_digest,omitempty"`
	ChecksumsURL    string  `json:"checksums_url,omitempty"`
	ReleaseNotes    string  `json:"release_notes,omitempty"`
	Assets          []Asset `json:"assets,omitempty"`
}

// InstallResult is the result of applying an update. CheckResult is embedded so
// callers get the release metadata in the same JSON object.
type InstallResult struct {
	CheckResult
	Updated          bool   `json:"updated"`
	InstallPath      string `json:"install_path,omitempty"`
	ChecksumVerified bool   `json:"checksum_verified"`
	RestartRequired  bool   `json:"restart_required,omitempty"`
}

// Updater is a release lookup and installation client.
type Updater struct {
	repo       string
	apiBaseURL string
	current    string
	goos       string
	goarch     string
	client     *http.Client
}

// New validates options and returns an updater.
func New(opts Options) (*Updater, error) {
	repo := strings.TrimSpace(opts.Repo)
	if repo == "" {
		repo = DefaultRepo
	}
	if !validRepo(repo) {
		return nil, fmt.Errorf("invalid release repository %q (want owner/repository)", repo)
	}

	apiBase := strings.TrimRight(strings.TrimSpace(opts.APIBaseURL), "/")
	if apiBase == "" {
		apiBase = DefaultAPIBase
	}
	parsed, err := url.Parse(apiBase)
	if err != nil || parsed.Host == "" || (parsed.Scheme != "https" && parsed.Scheme != "http") {
		return nil, fmt.Errorf("invalid release API URL %q", apiBase)
	}
	// Plain HTTP is acceptable only for a loopback test/mirror server. Release
	// metadata and checksums must not travel unencrypted to a public host.
	if parsed.Scheme == "http" && !isLoopbackHost(parsed.Hostname()) {
		return nil, fmt.Errorf("release API URL must use https (or be a loopback test server): %q", apiBase)
	}

	goos := opts.GOOS
	if goos == "" {
		goos = runtime.GOOS
	}
	goarch := opts.GOARCH
	if goarch == "" {
		goarch = runtime.GOARCH
	}
	client := opts.HTTPClient
	if client == nil {
		client = &http.Client{Timeout: 2 * time.Minute}
	}

	current := strings.TrimSpace(opts.CurrentVersion)
	if current == "" {
		current = "dev"
	}

	return &Updater{
		repo:       repo,
		apiBaseURL: apiBase,
		current:    current,
		goos:       goos,
		goarch:     goarch,
		client:     client,
	}, nil
}

// CurrentVersion returns the version supplied at construction.
func (u *Updater) CurrentVersion() string { return u.current }

// AssetName returns the published asset name for a platform.
func AssetName(goos, goarch string) (string, error) {
	if goos != "linux" && goos != "darwin" && goos != "windows" {
		return "", fmt.Errorf("self-update is not supported on %s", goos)
	}
	if goarch != "amd64" && goarch != "arm64" {
		return "", fmt.Errorf("self-update is not supported on %s/%s", goos, goarch)
	}
	ext := ""
	if goos == "windows" {
		ext = ".exe"
	}
	return fmt.Sprintf("companion-%s-%s%s", goos, goarch, ext), nil
}

// Check finds the newest published release containing a binary for the target
// platform. Releases are compared by semantic version (not by the order of the
// API response), and a release whose asset is missing is skipped.
func (u *Updater) Check(ctx context.Context) (*CheckResult, error) {
	rel, err := u.latestRelease(ctx)
	if err != nil {
		return nil, err
	}

	assetName, err := AssetName(u.goos, u.goarch)
	if err != nil {
		return nil, err
	}
	asset, ok := findAsset(rel.Assets, assetName)
	if !ok {
		return nil, fmt.Errorf("release %s has no %s asset", rel.TagName, assetName)
	}
	checksums, _ := findAsset(rel.Assets, ChecksumsAssetName)

	latest := strings.TrimPrefix(strings.TrimSpace(rel.TagName), "v")
	result := &CheckResult{
		CurrentVersion:  u.current,
		LatestVersion:   latest,
		UpdateAvailable: IsNewer(latest, u.current),
		ReleaseName:     rel.Name,
		ReleaseURL:      rel.URL,
		PublishedAt:     rel.PublishedAt,
		Prerelease:      rel.Prerelease,
		AssetName:       asset.Name,
		AssetURL:        asset.URL,
		AssetSize:       asset.Size,
		AssetDigest:     asset.Digest,
		ChecksumsURL:    checksums.URL,
		ReleaseNotes:    rel.Notes,
		Assets:          rel.Assets,
	}
	return result, nil
}

// Install downloads and replaces target with the asset selected by check.
// If force is false and check.UpdateAvailable is false, it returns Updated
// false without touching the filesystem.
func (u *Updater) Install(ctx context.Context, check *CheckResult, target string, force bool) (*InstallResult, error) {
	if check == nil {
		return nil, fmt.Errorf("missing update check result")
	}
	result := &InstallResult{CheckResult: *check}
	if !check.UpdateAvailable && !force {
		return result, nil
	}
	if check.AssetURL == "" || check.AssetName == "" {
		return nil, fmt.Errorf("release %s has no usable CLI asset", check.LatestVersion)
	}
	if check.ChecksumsURL == "" {
		return nil, fmt.Errorf("release %s does not publish %s; refusing an unverified update", check.LatestVersion, ChecksumsAssetName)
	}

	target, err := resolveTarget(target)
	if err != nil {
		return nil, err
	}
	result.InstallPath = target

	dir := filepath.Dir(target)
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return nil, fmt.Errorf("creating install directory %s: %w", dir, err)
	}
	if fi, err := os.Stat(dir); err != nil || !fi.IsDir() {
		if err != nil {
			return nil, fmt.Errorf("install directory %s: %w", dir, err)
		}
		return nil, fmt.Errorf("install path %s is not a directory", dir)
	}

	sums, err := u.downloadBytes(ctx, check.ChecksumsURL, maxChecksums)
	if err != nil {
		return nil, fmt.Errorf("downloading checksums: %w", err)
	}
	want, err := ChecksumFor(sums, check.AssetName)
	if err != nil {
		return nil, err
	}

	mode := os.FileMode(0o755)
	if fi, err := os.Stat(target); err == nil {
		if fi.IsDir() {
			return nil, fmt.Errorf("install target %s is a directory", target)
		}
		mode = fi.Mode().Perm()
		if mode&0o111 == 0 {
			mode |= 0o111
		}
	}

	tmp, err := os.CreateTemp(dir, "."+filepath.Base(target)+".update-*")
	if err != nil {
		return nil, fmt.Errorf("creating temporary file beside %s: %w", target, err)
	}
	tmpName := tmp.Name()
	defer os.Remove(tmpName)

	hash := sha256.New()
	written, err := u.downloadTo(ctx, check.AssetURL, io.MultiWriter(tmp, hash), maxBinary)
	if err != nil {
		tmp.Close()
		return nil, fmt.Errorf("downloading %s: %w", check.AssetName, err)
	}
	if written == 0 {
		tmp.Close()
		return nil, fmt.Errorf("download of %s was empty", check.AssetName)
	}
	if err := tmp.Chmod(mode); err != nil {
		tmp.Close()
		return nil, fmt.Errorf("setting executable mode: %w", err)
	}
	if err := tmp.Sync(); err != nil {
		tmp.Close()
		return nil, fmt.Errorf("syncing downloaded binary: %w", err)
	}
	if err := tmp.Close(); err != nil {
		return nil, fmt.Errorf("closing downloaded binary: %w", err)
	}

	got := hex.EncodeToString(hash.Sum(nil))
	if !strings.EqualFold(got, want) {
		return nil, fmt.Errorf("checksum mismatch for %s: got %s, expected %s", check.AssetName, got, want)
	}
	if err := verifyAssetDigest(check.AssetDigest, got); err != nil {
		return nil, err
	}

	if err := replaceFile(tmpName, target); err != nil {
		return nil, fmt.Errorf("replacing %s: %w", target, err)
	}

	result.Updated = true
	result.ChecksumVerified = true
	result.RestartRequired = runningExecutable(target) && runtime.GOOS == "windows"
	return result, nil
}

func (u *Updater) latestRelease(ctx context.Context) (*Release, error) {
	releases, err := u.fetchReleases(ctx)
	if err != nil {
		return nil, err
	}
	assetName, err := AssetName(u.goos, u.goarch)
	if err != nil {
		return nil, err
	}

	// GitHub returns releases newest-first by creation time, but tags can be
	// published out of order. Prefix numeric tags sort correctly; malformed
	// tags stay in API order after the valid ones.
	sort.SliceStable(releases, func(i, j int) bool {
		a := strings.TrimPrefix(releases[i].TagName, "v")
		b := strings.TrimPrefix(releases[j].TagName, "v")
		return CompareVersions(a, b) > 0
	})

	for i := range releases {
		if _, ok := findAsset(releases[i].Assets, assetName); !ok {
			continue
		}
		// A release without the checksum manifest cannot be installed safely.
		// Skip it rather than falling through to an unverified download; an
		// older verified release is still a valid update target.
		if _, ok := findAsset(releases[i].Assets, ChecksumsAssetName); !ok {
			continue
		}
		return &releases[i], nil
	}
	return nil, fmt.Errorf("no published release contains both %s and %s", assetName, ChecksumsAssetName)
}

func (u *Updater) fetchReleases(ctx context.Context) ([]Release, error) {
	endpoint := fmt.Sprintf("%s/repos/%s/releases?per_page=100", u.apiBaseURL, u.repo)
	body, err := u.getBytes(ctx, endpoint, maxReleaseJSON, "application/vnd.github+json")
	if err != nil {
		return nil, err
	}

	var raw []struct {
		TagName     string `json:"tag_name"`
		Name        string `json:"name"`
		HTMLURL     string `json:"html_url"`
		PublishedAt string `json:"published_at"`
		Draft       bool   `json:"draft"`
		Prerelease  bool   `json:"prerelease"`
		Body        string `json:"body"`
		Assets      []struct {
			Name               string `json:"name"`
			BrowserDownloadURL string `json:"browser_download_url"`
			Size               int64  `json:"size"`
			Digest             string `json:"digest"`
		} `json:"assets"`
	}
	if err := json.Unmarshal(body, &raw); err != nil {
		return nil, fmt.Errorf("decoding GitHub release list: %w", err)
	}

	out := make([]Release, 0, len(raw))
	for _, r := range raw {
		if r.Draft || strings.TrimSpace(r.TagName) == "" {
			continue
		}
		rel := Release{
			TagName:     r.TagName,
			Name:        r.Name,
			URL:         r.HTMLURL,
			PublishedAt: r.PublishedAt,
			Prerelease:  r.Prerelease,
			Notes:       strings.TrimSpace(r.Body),
		}
		for _, a := range r.Assets {
			rel.Assets = append(rel.Assets, Asset{
				Name:   a.Name,
				URL:    a.BrowserDownloadURL,
				Size:   a.Size,
				Digest: a.Digest,
			})
		}
		out = append(out, rel)
	}
	if len(out) == 0 {
		return nil, fmt.Errorf("no published releases found in %s", u.repo)
	}
	return out, nil
}

func (u *Updater) downloadBytes(ctx context.Context, rawURL string, limit int64) ([]byte, error) {
	return u.getBytes(ctx, rawURL, limit, "")
}

func (u *Updater) getBytes(ctx context.Context, rawURL string, limit int64, accept string) ([]byte, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, rawURL, nil)
	if err != nil {
		return nil, err
	}
	req.Header.Set("User-Agent", "companion-self-update/1")
	if accept != "" {
		req.Header.Set("Accept", accept)
	}
	if strings.Contains(rawURL, "api.github.com") {
		req.Header.Set("X-GitHub-Api-Version", "2022-11-28")
	}

	resp, err := u.client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		msg, _ := readLimited(resp.Body, 4<<10)
		detail := strings.TrimSpace(string(msg))
		if detail != "" {
			detail = ": " + detail
		}
		return nil, fmt.Errorf("HTTP %d from %s%s", resp.StatusCode, rawURL, detail)
	}
	if resp.ContentLength > limit {
		return nil, fmt.Errorf("%s is too large (%d bytes; limit %d)", rawURL, resp.ContentLength, limit)
	}
	data, err := readLimited(resp.Body, limit)
	if err != nil {
		return nil, err
	}
	return data, nil
}

func (u *Updater) downloadTo(ctx context.Context, rawURL string, dst io.Writer, limit int64) (int64, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, rawURL, nil)
	if err != nil {
		return 0, err
	}
	req.Header.Set("User-Agent", "companion-self-update/1")
	resp, err := u.client.Do(req)
	if err != nil {
		return 0, err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		msg, _ := readLimited(resp.Body, 4<<10)
		detail := strings.TrimSpace(string(msg))
		if detail != "" {
			detail = ": " + detail
		}
		return 0, fmt.Errorf("HTTP %d%s", resp.StatusCode, detail)
	}
	if resp.ContentLength > limit {
		return 0, fmt.Errorf("asset is too large (%d bytes; limit %d)", resp.ContentLength, limit)
	}
	n, err := io.Copy(dst, io.LimitReader(resp.Body, limit+1))
	if err != nil {
		return n, err
	}
	if n > limit {
		return n, fmt.Errorf("asset exceeds %d bytes", limit)
	}
	return n, nil
}

func readLimited(r io.Reader, limit int64) ([]byte, error) {
	data, err := io.ReadAll(io.LimitReader(r, limit+1))
	if err != nil {
		return nil, err
	}
	if int64(len(data)) > limit {
		return nil, fmt.Errorf("response exceeds %d bytes", limit)
	}
	return data, nil
}

func findAsset(assets []Asset, name string) (Asset, bool) {
	for _, a := range assets {
		if a.Name == name {
			return a, true
		}
	}
	return Asset{}, false
}

func validRepo(repo string) bool {
	parts := strings.Split(repo, "/")
	if len(parts) != 2 {
		return false
	}
	for _, p := range parts {
		if p == "" || p == "." || p == ".." {
			return false
		}
		for _, r := range p {
			if !(r == '-' || r == '_' || r == '.' ||
				(r >= 'a' && r <= 'z') || (r >= 'A' && r <= 'Z') || (r >= '0' && r <= '9')) {
				return false
			}
		}
	}
	return true
}

func isLoopbackHost(host string) bool {
	if host == "localhost" {
		return true
	}
	ip := net.ParseIP(host)
	return ip != nil && ip.IsLoopback()
}

func resolveTarget(target string) (string, error) {
	target = strings.TrimSpace(target)
	if target == "" {
		return "", fmt.Errorf("install target is empty")
	}
	abs, err := filepath.Abs(target)
	if err != nil {
		return "", fmt.Errorf("resolving install target %q: %w", target, err)
	}
	// Preserve a caller-managed symlink by updating the file it points at. A
	// dangling symlink is an error rather than a reason to replace the link.
	if fi, err := os.Lstat(abs); err == nil && fi.Mode()&os.ModeSymlink != 0 {
		resolved, err := filepath.EvalSymlinks(abs)
		if err != nil {
			return "", fmt.Errorf("resolving install target symlink %s: %w", abs, err)
		}
		abs = resolved
	}
	return abs, nil
}

func runningExecutable(target string) bool {
	exe, err := os.Executable()
	if err != nil {
		return false
	}
	if resolved, err := filepath.EvalSymlinks(exe); err == nil {
		exe = resolved
	}
	exe, _ = filepath.Abs(exe)
	target, _ = filepath.Abs(target)
	return samePath(exe, target)
}

func samePath(a, b string) bool {
	if runtime.GOOS == "windows" {
		return strings.EqualFold(filepath.Clean(a), filepath.Clean(b))
	}
	return filepath.Clean(a) == filepath.Clean(b)
}

func verifyAssetDigest(digest, got string) error {
	digest = strings.TrimSpace(digest)
	if digest == "" {
		return nil
	}
	const prefix = "sha256:"
	if !strings.HasPrefix(strings.ToLower(digest), prefix) {
		return fmt.Errorf("release asset uses unsupported digest %q", digest)
	}
	want := digest[len(prefix):]
	if !strings.EqualFold(want, got) {
		return fmt.Errorf("release metadata digest mismatch: got %s, expected %s", got, want)
	}
	return nil
}
