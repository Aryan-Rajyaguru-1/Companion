//go:build !windows

package uploader

import (
	"os/exec"
	"syscall"
)

// setPgid puts the tool in its own process group so a timeout kill takes
// down the tool and any children it spawned (helpers that inherit pipes
// would otherwise keep the transfer half-alive).
func setPgid(cmd *exec.Cmd) {
	cmd.SysProcAttr = &syscall.SysProcAttr{Setpgid: true}
}
