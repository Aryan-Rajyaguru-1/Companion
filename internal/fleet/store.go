package fleet

import (
	"os"
	"path/filepath"

	"gopkg.in/yaml.v3"
)

// FileStore persists the device catalog to a YAML file.
type FileStore struct {
	Path string
}

// Load reads the catalog file; a missing file is an empty catalog (not an error).
func (f FileStore) Load() ([]Device, error) {
	data, err := os.ReadFile(f.Path)
	if err != nil {
		if os.IsNotExist(err) {
			return nil, nil
		}
		return nil, err
	}
	var devs []Device
	if err := yaml.Unmarshal(data, &devs); err != nil {
		return nil, err
	}
	return devs, nil
}

// Save writes the catalog atomically (tmp + rename) with 0600 perms.
func (f FileStore) Save(devs []Device) error {
	if f.Path == "" {
		return nil
	}
	if err := os.MkdirAll(filepath.Dir(f.Path), 0o755); err != nil {
		return err
	}
	data, err := yaml.Marshal(devs)
	if err != nil {
		return err
	}
	tmp := f.Path + ".tmp"
	if err := os.WriteFile(tmp, data, 0o600); err != nil {
		return err
	}
	return os.Rename(tmp, f.Path)
}
