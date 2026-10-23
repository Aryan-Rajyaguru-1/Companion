//go:build windows

package uploader

import "os/exec"

// setPgid is a no-op on Windows — exec.CommandContext's process kill
// already terminates the tool there.
func setPgid(cmd *exec.Cmd) {}
