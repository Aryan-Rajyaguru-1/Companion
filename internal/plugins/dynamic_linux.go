//go:build linux && cgo

package plugins

import (
	"fmt"
	"os"
	"path/filepath"
	"plugin"
)

// loadDynamic loads Go plugins (.so) from dir. A missing dir is fine (returns
// nil); individual broken plugins produce an entry in the error slice so the
// rest of the CLI keeps working.
func loadDynamic(dir string) ([]Plugin, []error) {
	entries, err := os.ReadDir(dir)
	if err != nil {
		return nil, nil // no plugins directory — not an error
	}
	var (
		out  []Plugin
		errs []error
	)
	for _, e := range entries {
		if e.IsDir() || filepath.Ext(e.Name()) != ".so" {
			continue
		}
		p, err := plugin.Open(filepath.Join(dir, e.Name()))
		if err != nil {
			errs = append(errs, fmt.Errorf("%s: %w", e.Name(), err))
			continue
		}
		sym, err := p.Lookup("Plugin")
		if err != nil {
			errs = append(errs, fmt.Errorf("%s: %w", e.Name(), err))
			continue
		}
		plug, ok := sym.(Plugin)
		if !ok {
			errs = append(errs, fmt.Errorf("%s: exported Plugin does not implement plugins.Plugin", e.Name()))
			continue
		}
		out = append(out, plug)
	}
	return out, errs
}
