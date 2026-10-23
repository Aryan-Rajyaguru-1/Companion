//go:build !windows

package atomicfile

import "os"

// Replace moves src over dest. src is expected to be a fully written and
// synced temporary file on the same filesystem as dest. POSIX rename(2)
// replaces an existing file or symlink atomically.
func Replace(src, dest string) error {
	return os.Rename(src, dest)
}
