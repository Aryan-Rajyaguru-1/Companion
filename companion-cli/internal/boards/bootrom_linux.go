//go:build linux

// Boot-ROM probing for Linux: raw termios + modem-bit ioctls, no cgo.
// bootrom_stub.go provides the graceful fallback for every other GOOS.

package boards

import (
	"syscall"
	"time"
	"unsafe"
)

// ProbeBootROM attempts boot-ROM identification on one serial port path.
// It never returns a hard error — failures land in Result.Err so callers
// can degrade gracefully (port busy, permission denied, no banner…).
//
// SIDE EFFECT: pulses the auto-reset circuit, so the attached sketch
// restarts. Only call for ports the user explicitly agreed to probe.
func ProbeBootROM(portPath string) BootProbeResult {
	res := BootProbeResult{Port: portPath}
	fd, closeFn, err := openRawTTY(portPath)
	if err != nil {
		res.Err = "cannot open " + portPath + ": " + err.Error()
		return res
	}
	defer closeFn()

	// Reset into the ROM and give the banner time to arrive.
	if err := pulseAutoReset(fd); err != nil {
		res.Err = "auto-reset failed: " + err.Error()
		return res
	}

	// Read the banner at 115200 (ESP32 native boot rate). If nothing
	// legible arrives, retry once at 74880 — the ESP8266 boot ROM prints
	// there, so its output is garbage at any other rate.
	banner, ok := readBanner(fd, 1500*time.Millisecond)
	if !ok {
		banner, ok = readBanner(fd, 600*time.Millisecond)
	}
	if !ok {
		res.Err = "no boot ROM banner seen"
		res.Banner = banner
		return res
	}
	res.OK, res.Banner = true, banner
	chip, _ := parseChipToken(banner)
	res.Chip = chip
	if def, known := chipFQBNs[chip]; known {
		res.FQBN, res.Board = def.fqbn, def.name
	} else {
		res.FQBN, res.Board = "esp32:esp32:esp32", "ESP32 Dev Module"
	}
	return res
}

// readBanner re-bauds the already-open port to baud, waits briefly for the
// reset tail to pass, then accumulates output until something matches
// parseChipToken or the deadline expires. Returns everything captured.
func readBanner(fd int, wait time.Duration) (string, bool) {
	speed, _ := ttBaud(0)
	switch {
	case wait >= 1200*time.Millisecond: // first pass: ESP32 boot rate
		speed, _ = ttBaud(115200)
	default: // retry pass: ESP8266 boot ROM rate
		speed, _ = ttBaud(74880)
	}
	termios, err := ttGetTermios(fd)
	if err != nil {
		return "", false
	}
	termios.Ispeed = speed
	termios.Ospeed = speed
	if err := ttSetTermios(fd, termios); err != nil {
		return "", false
	}

	// Freshly reset chips print a short burst first; drop it so stale
	// baud-rate garbage cannot pollute the real banner.
	time.Sleep(150 * time.Millisecond)

	deadline := time.Now().Add(wait)
	var sb []byte
	buf := make([]byte, 512)
	for time.Now().Before(deadline) {
		n, err := readTTY(fd, buf)
		if n > 0 {
			sb = append(sb, buf[:n]...)
			if _, ok := parseChipToken(string(sb)); ok {
				return string(sb), true
			}
		}
		if err != nil && !isTTYTimeout(err) {
			return string(sb), false
		}
		// O_NONBLOCK reads return immediately; pace the poll loop so a
		// silent port costs one 25 ms sleep per cycle, not a CPU spin.
		time.Sleep(25 * time.Millisecond)
	}
	return string(sb), false
}

// ── Raw termios serial access (Linux; no cgo) ────────────────────

// openRawTTY opens a serial device in raw 115200 8N1 mode with VMIN=0 and
// VTIME=2 (200 ms) so reads act as poll-with-timeout. It opens O_NONBLOCK
// and clears ICANON: with the line discipline left in canonical mode, read()
// ignores VTIME and blocks until a full newline arrives — which hung probes
// on devices that never send one.
func openRawTTY(path string) (int, func(), error) {
	fd, err := syscall.Open(path, syscall.O_RDWR|syscall.O_NOCTTY|syscall.O_NONBLOCK, 0)
	if err != nil {
		return -1, func() {}, err
	}
	closeFn := func() { syscall.Close(fd) }

	termios, err := ttGetTermios(fd)
	if err != nil {
		syscall.Close(fd)
		return -1, func() {}, err
	}

	speed, _ := ttBaud(115200)
	termios.Cflag = syscall.CREAD | syscall.CLOCAL | syscall.CS8 | speed
	termios.Cflag &^= syscall.PARENB | syscall.CSTOPB
	termios.Iflag &^= syscall.IGNBRK | syscall.BRKINT | syscall.PARMRK |
		syscall.ISTRIP | syscall.INLCR | syscall.IGNCR | syscall.ICRNL | syscall.IXON
	termios.Oflag &^= syscall.OPOST
	termios.Lflag &^= syscall.ICANON | syscall.ECHO | syscall.ECHONL |
		syscall.ISIG | syscall.IEXTEN
	termios.Cc[syscall.VMIN] = 0
	termios.Cc[syscall.VTIME] = 2 // 200 ms read timeout

	if err := ttSetTermios(fd, termios); err != nil {
		syscall.Close(fd)
		return -1, func() {}, err
	}
	return fd, closeFn, nil
}

// readTTY reads up to len(buf) bytes with the VTIME timeout applied.
func readTTY(fd int, buf []byte) (int, error) {
	return syscall.Read(fd, buf)
}

// isTTYTimeout reports whether an error is a benign timeout/would-block
// condition rather than a real failure.
func isTTYTimeout(err error) bool {
	if err == nil {
		return false
	}
	return err == syscall.EAGAIN || err == syscall.EWOULDBLOCK || err == syscall.EINTR
}

// Modem-bit ioctl constants (asm-generic termbits for Linux).
const (
	tiocmDTR = 0x002
	tiocmRTS = 0x004
	tiocmbis = 0x5416 // set modem bits
	tiocmbic = 0x5417 // clear modem bits
)

// pulseAutoReset drives the classic EN/IO0 auto-reset circuit so the chip
// reboots into its ROM: assert EN (DTR), then IO0 (RTS), release IO0, then
// release EN. Mirrors esptool's classic reset sequence.
func pulseAutoReset(fd int) error {
	// esptool classic sequence as (DTR, RTS) pairs.
	steps := []struct{ dtr, rts bool }{
		{false, true}, // EN released, IO0 asserted
		{true, false}, // EN asserted (chip held in reset), IO0 released
		{true, true},  // both asserted — IO0 sampled low at EN release
	}
	for _, s := range steps {
		if err := ttModemBits(fd, tiocmDTR, s.dtr); err != nil {
			return err
		}
		if err := ttModemBits(fd, tiocmRTS, s.rts); err != nil {
			return err
		}
		time.Sleep(100 * time.Millisecond)
	}
	// Release both — EN goes high, IO0 is high, ROM boots normally
	// and prints its banner.
	return ttModemBits(fd, tiocmDTR|tiocmRTS, false)
}

// ttModemBits sets or clears TIOCM DTR/RTS bits via TIOCMBIS/TIOCMBIC.
// The kernel expects a pointer to the bitmask (it get_user()s the value),
// not the mask itself — passing it by value fails with EFAULT.
func ttModemBits(fd int, bits uint, set bool) error {
	which := uintptr(tiocmbic)
	if set {
		which = uintptr(tiocmbis)
	}
	var mask uint64 = uint64(bits) // 8 bytes: safe for both 4- and 8-byte kernel reads
	_, _, errno := syscall.Syscall(syscall.SYS_IOCTL, uintptr(fd), which, uintptr(unsafe.Pointer(&mask)))
	if errno != 0 {
		return errno
	}
	return nil
}

// ── termios plumbing ─────────────────────────────────────────────

// ttGetTermios fetches the current termios for fd (TCGETS).
func ttGetTermios(fd int) (*syscall.Termios, error) {
	var t syscall.Termios
	_, _, errno := syscall.Syscall(syscall.SYS_IOCTL, uintptr(fd), syscall.TCGETS, uintptr(unsafe.Pointer(&t)))
	if errno != 0 {
		return nil, errno
	}
	return &t, nil
}

// ttSetTermios applies termios to fd immediately (TCSETS).
func ttSetTermios(fd int, t *syscall.Termios) error {
	_, _, errno := syscall.Syscall(syscall.SYS_IOCTL, uintptr(fd), syscall.TCSETS, uintptr(unsafe.Pointer(t)))
	if errno != 0 {
		return errno
	}
	return nil
}

// ttBaud converts a numeric baud rate to termios speed constants.
// Only rates used by boot ROMs and common sketches are mapped; anything
// else falls back to 115200.
func ttBaud(baud int) (in, out uint32) {
	var b uint32
	switch baud {
	case 9600:
		b = syscall.B9600
	case 19200:
		b = syscall.B19200
	case 38400:
		b = syscall.B38400
	case 57600:
		b = syscall.B57600
	case 230400:
		b = syscall.B230400
	case 460800:
		b = syscall.B460800
	case 921600:
		b = syscall.B921600
	default:
		b = syscall.B115200
	}
	return b, b
}
