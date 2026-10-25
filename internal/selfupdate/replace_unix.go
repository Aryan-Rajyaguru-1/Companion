//go:build !windows

package selfupdate

import "github.com/companion-ide/companion-cli/internal/atomicfile"

// replaceFile atomically renames the fully written staging file over target.
// POSIX permits this even while the old executable is running.
func replaceFile(staged, target string) error {
	return atomicfile.Replace(staged, target)
}
