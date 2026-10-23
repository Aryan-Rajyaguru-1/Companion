// Package atomicfile writes files without ever exposing a partially written
// destination.
//
// Several Companion paths handle credentials and downloaded archives: a reader
// must see either the old complete file or the new complete file, never a
// truncated one. The temporary file is created beside the destination (so the
// final rename stays on the same filesystem) with the caller's mode.
package atomicfile

import (
	"io/fs"
	"os"
	"path/filepath"
)

// WriteFile atomically replaces path with data.
//
// The destination's parent directory must already exist. The final rename
// replaces an existing file or symlink atomically; the symlink target is never
// followed.
func WriteFile(path string, data []byte, perm fs.FileMode) error {
	dir := filepath.Dir(path)
	tmp, err := os.CreateTemp(dir, "."+filepath.Base(path)+"-*")
	if err != nil {
		return err
	}
	tmpName := tmp.Name()
	defer os.Remove(tmpName)

	if err := tmp.Chmod(perm); err != nil {
		tmp.Close()
		return err
	}
	if _, err := tmp.Write(data); err != nil {
		tmp.Close()
		return err
	}
	if err := tmp.Sync(); err != nil {
		tmp.Close()
		return err
	}
	if err := tmp.Close(); err != nil {
		return err
	}
	return Replace(tmpName, path)
}
