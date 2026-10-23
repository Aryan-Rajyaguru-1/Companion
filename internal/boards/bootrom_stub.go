//go:build !linux

package boards

// ProbeBootROM is a graceful no-op off Linux: reading the boot-ROM banner
// needs raw termios/modem-bit access that only the Linux build implements
// (bootrom_linux.go). Callers treat Err as a non-fatal skip.
func ProbeBootROM(portPath string) BootProbeResult {
	return BootProbeResult{
		Port: portPath,
		Err:  "boot-ROM probing is only supported on Linux builds",
	}
}
