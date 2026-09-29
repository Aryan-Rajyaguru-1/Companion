package fleet

import (
	"fmt"
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
	// Decrypt at rest (see secrets.go). An encrypted file with no key is an
	// error, never a silent empty secret.
	for i := range devs {
		v, err := unprotectSecret(devs[i].Secret)
		if err != nil {
			return nil, fmt.Errorf("%s: %w", devs[i].Key(), err)
		}
		devs[i].Secret = v
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
	out := make([]Device, len(devs))
	copy(out, devs)
	for i := range out {
		v, err := protectSecret(out[i].Secret)
		if err != nil {
			return fmt.Errorf("%s: encrypt secret: %w", out[i].Key(), err)
		}
		out[i].Secret = v
	}
	data, err := yaml.Marshal(out)
	if err != nil {
		return err
	}
	tmp := f.Path + ".tmp"
	if err := os.WriteFile(tmp, data, 0o600); err != nil {
		return err
	}
	return os.Rename(tmp, f.Path)
}
