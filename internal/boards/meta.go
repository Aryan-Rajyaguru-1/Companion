package boards

import (
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"github.com/companion-ide/companion-cli/internal/version"
)

// ── Board catalog over installed platforms ───────────────────────

// BoardEntry is one board known from an installed platform's boards.txt.
type BoardEntry struct {
	FQBN     string `json:"fqbn"`
	Name     string `json:"name"`
	Platform string `json:"platform"` // vendor:arch
	Version  string `json:"version"`
}

// ListAllBoards enumerates every board provided by installed platforms,
// mirroring the "show all boards I can actually build for" workflow.
func (m *Manager) ListAllBoards() ([]BoardEntry, error) {
	pkgDir := m.cfg.PackagesDir()
	vendors, err := os.ReadDir(pkgDir)
	if err != nil {
		if os.IsNotExist(err) {
			return nil, nil
		}
		return nil, err
	}

	var out []BoardEntry
	for _, v := range vendors {
		if !v.IsDir() {
			continue
		}
		hwRoot := filepath.Join(pkgDir, v.Name(), "hardware")
		archs, err := os.ReadDir(hwRoot)
		if err != nil {
			continue
		}
		for _, a := range archs {
			if !a.IsDir() {
				continue
			}
			versions, err := os.ReadDir(filepath.Join(hwRoot, a.Name()))
			if err != nil {
				continue
			}
			var latestVer string
			for _, ver := range versions {
				if ver.IsDir() && version.Compare(ver.Name(), latestVer) > 0 {
					latestVer = ver.Name()
				}
			}
			if latestVer == "" {
				continue
			}
			boardsFile := filepath.Join(hwRoot, a.Name(), latestVer, "boards.txt")
			all, err := parsePropertiesFile(boardsFile)
			if err != nil {
				continue // platform without boards.txt — skip silently
			}
			seen := map[string]bool{}
			for key := range all {
				id := key
				if i := strings.IndexByte(key, '.'); i > 0 {
					id = key[:i]
				}
				if id == "" || id == "menu" || seen[id] {
					continue
				}
				seen[id] = true
				out = append(out, BoardEntry{
					FQBN:     fmt.Sprintf("%s:%s:%s", v.Name(), a.Name(), id),
					Name:     all[id+".name"],
					Platform: v.Name() + ":" + a.Name(),
					Version:  latestVer,
				})
			}
		}
	}

	sort.Slice(out, func(i, j int) bool { return out[i].FQBN < out[j].FQBN })
	return out, nil
}

// ── Board details ────────────────────────────────────────────────

// BoardDetails is the rich description returned by `board details`.
type BoardDetails struct {
	FQBN      string              `json:"fqbn"`
	Name      string              `json:"name"`
	Vendor    string              `json:"vendor"`
	Arch      string              `json:"architecture"`
	BoardID   string              `json:"boardId"`
	Version   string              `json:"platformVersion"`
	PlatformP string              `json:"platformPath"`
	Props     map[string]string   `json:"properties,omitempty"`
	Options   map[string][]string `json:"options,omitempty"` // menu label → choices
}

// BoardDetails resolves an installed FQBN into full metadata, including
// configurable menu options (e.g. CPU speed, flash size).
func (m *Manager) BoardDetails(fqbn string) (*BoardDetails, error) {
	rb, err := m.ResolveFQBN(fqbn)
	if err != nil {
		return nil, err
	}

	d := &BoardDetails{
		FQBN:      fqbn,
		Name:      rb.GetProp("name"),
		Vendor:    rb.Vendor,
		Arch:      rb.Architecture,
		BoardID:   rb.BoardID,
		Version:   filepath.Base(rb.PlatformPath),
		PlatformP: rb.PlatformPath,
		Options:   map[string][]string{},
	}

	for _, k := range []string{"build.mcu", "build.f_cpu", "build.core",
		"upload.maximum_size", "upload.maximum_data_size", "upload.speed"} {
		if v := rb.GetProp(k); v != "" {
			if d.Props == nil {
				d.Props = map[string]string{}
			}
			d.Props[k] = v
		}
	}

	// Menu options live as menu.<label>.<choice>=value pairs in boards.txt.
	labels := map[string]bool{}
	for k := range rb.BoardProps {
		if strings.HasPrefix(k, "menu.") {
			parts := strings.SplitN(k, ".", 3)
			if len(parts) >= 2 {
				labels[parts[1]] = true
			}
		}
	}
	for label := range labels {
		prefix := "menu." + label + "."
		for k := range rb.BoardProps {
			if strings.HasPrefix(k, prefix) {
				choice := strings.TrimPrefix(k, prefix)
				if i := strings.IndexByte(choice, '.'); i > 0 {
					choice = choice[:i]
				}
				d.Options[label] = append(d.Options[label], choice)
			}
		}
		sort.Strings(d.Options[label])
	}

	return d, nil
}

// ── Update tracking ──────────────────────────────────────────────

// PlatformUpdate describes an installed platform that has a newer release.
type PlatformUpdate struct {
	ID           string `json:"id"` // vendor:arch
	InstalledVer string `json:"installed"`
	AvailableVer string `json:"available"`
}

// OutdatedPlatforms compares every installed platform against the package
// indexes and returns those with newer releases available.
func (m *Manager) OutdatedPlatforms() ([]PlatformUpdate, error) {
	indexes, err := m.loadIndexes()
	if err != nil {
		return nil, err
	}
	installed, err := m.ListInstalled()
	if err != nil {
		return nil, err
	}

	var out []PlatformUpdate
	for _, p := range installed {
		parts := strings.SplitN(p.ID, ":", 2)
		if len(parts) != 2 {
			continue
		}
		var latest string
		for _, idx := range indexes {
			for _, pkg := range idx.Packages {
				if !strings.EqualFold(pkg.Name, parts[0]) {
					continue
				}
				for _, plat := range pkg.Platforms {
					if !strings.EqualFold(plat.Architecture, parts[1]) {
						continue
					}
					if version.Compare(plat.Version, latest) > 0 {
						latest = plat.Version
					}
				}
			}
		}
		if latest != "" && version.Compare(latest, p.Version) > 0 {
			out = append(out, PlatformUpdate{ID: p.ID, InstalledVer: p.Version, AvailableVer: latest})
		}
	}
	return out, nil
}
