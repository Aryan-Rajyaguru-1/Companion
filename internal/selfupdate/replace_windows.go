//go:build windows

package selfupdate

import (
	"fmt"
	"os"

	"github.com/companion-ide/companion-cli/internal/atomicfile"
)

// replaceFile handles the Windows case where the destination may be the
// currently running executable. MoveFileEx cannot replace an image that is
// still mapped, but Windows does allow the old image to be renamed; after the
// process exits the new path is used on the next launch.
func replaceFile(staged, target string) error {
	if err := atomicfile.Replace(staged, target); err == nil {
		return nil
	}

	old := target + ".old"
	// A previous update may have left this behind while the old process was
	// still running. Removing it is best effort; a failure here only means we
	// need a unique fallback name.
	if err := os.Remove(old); err != nil && !os.IsNotExist(err) {
		old = fmt.Sprintf("%s.old-%d", target, os.Getpid())
	}
	if err := os.Rename(target, old); err != nil {
		return fmt.Errorf("renaming the running executable to %s: %w", old, err)
	}
	if err := os.Rename(staged, target); err != nil {
		// Put the old executable back so the install is not left broken.
		_ = os.Rename(old, target)
		return fmt.Errorf("moving the staged executable into place: %w", err)
	}
	// The old image is usually still locked by this process until exit, so
	// leave it for the next update rather than failing a successful install.
	_ = os.Remove(old)
	return nil
}
