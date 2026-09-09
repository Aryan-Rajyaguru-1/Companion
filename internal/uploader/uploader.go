// Package uploader implements wireless firmware upload strategies.
// Each MCU family has its own Upload() method.
// Inspired by arduino-cli's service_upload.go — written from scratch.
package uploader

import (
	"bytes"
	"fmt"
	"io"
	"os"
	"os/exec"
	"strings"
	"sync"
	"time"

	"github.com/companion-ide/companion-cli/internal/bridge"
	"github.com/companion-ide/companion-cli/internal/config"
)

// Options controls the upload process.
type Options struct {
	BinaryPath string
	MCU        string // esp32 | esp8266 | avr | stm32 | generic
	Host       string // WiFi bridge host (wireless mode)
	Port       int    // WiFi bridge TCP port (wireless mode)
	SerialPort string // LOCAL serial device (e.g. /dev/ttyACM0) — USB mode
	Baud       uint32
	FQBN       string // used for AVR MCU part name resolution
	Verbose    bool
}

type Uploader struct {
	cfg      *config.Config
	onOutput func(string)
}

func New(cfg *config.Config, onOutput func(string)) *Uploader {
	return &Uploader{cfg: cfg, onOutput: onOutput}
}

func (u *Uploader) log(msg string) {
	if u.onOutput != nil {
		u.onOutput(msg)
	}
}

// Upload dispatches to the correct MCU-specific upload method.
func (u *Uploader) Upload(opts Options) error {
	info, err := os.Stat(opts.BinaryPath)
	if err != nil {
		return fmt.Errorf("binary not found: %s", opts.BinaryPath)
	}

	if opts.SerialPort != "" {
		sizeKB := float64(info.Size()) / 1024.0
		u.log(fmt.Sprintf("» Binary: %s (%.1f KB)", info.Name(), sizeKB))
		u.log(fmt.Sprintf("» Target: %s on local port %s  Baud: %d",
			opts.MCU, opts.SerialPort, opts.Baud))
		switch strings.ToLower(opts.MCU) {
		case "esp32", "esp8266":
			return u.uploadESPSerial(opts)
		case "avr", "arduino":
			return u.uploadAVRSerial(opts)
		default:
			return fmt.Errorf("USB upload not yet supported for MCU family %q "+
				"(supported over USB: esp32, esp8266, avr)", opts.MCU)
		}
	}

	sizeKB := float64(info.Size()) / 1024.0
	u.log(fmt.Sprintf("» Binary: %s (%.1f KB)", info.Name(), sizeKB))
	u.log(fmt.Sprintf("» Bridge: %s:%d  MCU: %s  Baud: %d",
		opts.Host, opts.Port, opts.MCU, opts.Baud))

	switch strings.ToLower(opts.MCU) {
	case "esp32", "esp8266":
		return u.uploadESP(opts)
	case "stm32":
		return u.uploadSTM32(opts)
	case "avr", "arduino":
		return u.uploadAVR(opts)
	default:
		return u.uploadGeneric(opts)
	}
}

// ── Local USB / UART serial flashing ──────────────────────────────

// usbFlashOffset returns the app-image flash offset for an ESP family chip.
// ESP32/S2/S3/C-series app images live at 0x10000; bare ESP8266 at 0x0.
// Older ESP32 used 0x1000 in some layouts but 0x10000 is the standard
// app-partition offset for arduino-esp32.
func usbFlashOffset(mcu, fqbn string) string {
	if strings.EqualFold(mcu, "esp8266") {
		return "0x0"
	}
	return "0x10000"
}

// uploadESPSerial flashes an ESP chip connected directly via local USB/UART.
// Works with native UART adapters and with the ESP32-S3/C3 USB-Serial-JTAG
// peripheral (esptool handles entering download mode automatically).
func (u *Uploader) uploadESPSerial(opts Options) error {
	chip := ""
	switch strings.ToLower(opts.MCU) {
	case "esp8266":
		chip = "esp8266"
	default:
		// Let esptool auto-detect (esp32/s3/s2/c3/c6…): passing a wrong
		// --chip value is worse than detecting.
		if strings.Contains(strings.ToLower(opts.FQBN), "esp32s3") {
			chip = "esp32s3"
		} else if strings.Contains(strings.ToLower(opts.FQBN), "esp32c3") {
			chip = "esp32c3"
		} else if strings.Contains(strings.ToLower(opts.FQBN), "esp32s2") {
			chip = "esp32s2"
		} else if strings.Contains(strings.ToLower(opts.FQBN), "esp32c6") {
			chip = "esp32c6"
		}
	}

	python := "python3"
	if _, err := exec.LookPath("python3"); err != nil {
		python = "python"
	}

	args := []string{"-m", "esptool"}
	if chip != "" {
		args = append(args, "--chip", chip)
	}
	args = append(args,
		"--port", opts.SerialPort,
		"--baud", fmt.Sprintf("%d", opts.Baud),
		"--before", "default_reset",
		"--after", "hard_reset",
		"write_flash",
		"--flash_mode", "dio",
		"--flash_size", "detect",
		usbFlashOffset(opts.MCU, opts.FQBN), opts.BinaryPath,
	)

	u.log("» Running esptool over USB…")
	cmd := exec.Command(python, args...)
	var outBuf syncBuffer
	cmd.Stdout = &outBuf
	cmd.Stderr = &outBuf
	runErr := cmd.Run()

	for _, line := range outBuf.allLines() {
		if strings.Contains(line, "%") || strings.Contains(line, "Hash of data") ||
			strings.Contains(line, "Leaving") || strings.Contains(line, "Connecting") {
			u.log("  " + strings.TrimSpace(line))
		}
	}
	if runErr != nil {
		return fmt.Errorf("esptool failed:\n%s\n\nIf the board did not enter download mode, hold BOOT while it resets.", outBuf.string())
	}
	return nil
}

// uploadAVRSerial flashes an AVR board over a local serial port with an
// STK500v2/optiboot-compatible bootloader (avrdude -c arduino).
func (u *Uploader) uploadAVRSerial(opts Options) error {
	avrMCU, err := resolveAVRMCU(opts.FQBN)
	if err != nil {
		return err
	}
	ext := ""
	if idx := strings.LastIndex(opts.BinaryPath, "."); idx >= 0 {
		ext = strings.ToLower(opts.BinaryPath[idx:])
	}
	format := "i" // Intel HEX
	if ext == ".bin" {
		format = "r"
	}

	args := []string{
		"-p", avrMCU,
		"-c", "arduino",
		"-P", opts.SerialPort,
		"-b", fmt.Sprintf("%d", opts.Baud),
		"-D",
		"-U", fmt.Sprintf("flash:w:%s:%s", opts.BinaryPath, format),
	}
	if opts.Verbose {
		args = append(args, "-v")
	}

	u.log("» Running avrdude over USB…")
	cmd := exec.Command("avrdude", args...)
	out, err := cmd.CombinedOutput()
	if err != nil {
		if strings.Contains(err.Error(), "executable file not found") {
			return fmt.Errorf("avrdude not found\nInstall it with: sudo apt install avrdude")
		}
		return fmt.Errorf("avrdude failed:\n%s", string(out))
	}
	for _, line := range strings.Split(string(out), "\n") {
		line = strings.TrimSpace(line)
		if strings.Contains(line, "bytes") || strings.Contains(line, "verified") ||
			strings.Contains(line, "done") {
			u.log("  " + line)
		}
	}
	return nil
}

// syncBuffer captures subprocess output line-by-line for post-run reporting.
type syncBuffer struct {
	mu    sync.Mutex
	buf   []byte
	lines []string
}

func (b *syncBuffer) Write(p []byte) (int, error) {
	b.mu.Lock()
	defer b.mu.Unlock()
	b.buf = append(b.buf, p...)
	for {
		idx := bytes.IndexByte(b.buf, '\n')
		if idx < 0 {
			break
		}
		b.lines = append(b.lines, string(b.buf[:idx]))
		b.buf = b.buf[idx+1:]
	}
	return len(p), nil
}

func (b *syncBuffer) allLines() []string {
	b.mu.Lock()
	defer b.mu.Unlock()
	out := make([]string, len(b.lines), len(b.lines)+1)
	copy(out, b.lines)
	if len(b.buf) > 0 {
		out = append(out, string(b.buf))
	}
	return out
}

func (b *syncBuffer) string() string {
	b.mu.Lock()
	defer b.mu.Unlock()
	all := make([]byte, 0, len(b.buf)+64)
	for _, l := range b.lines {
		all = append(all, l...)
		all = append(all, '\n')
	}
	return string(append(all, b.buf...))
}

// ── ESP32 / ESP8266 ───────────────────────────────────────────────
// Delegates to esptool.py (must be installed: pip install esptool)

func (u *Uploader) uploadESP(opts Options) error {
	// Step 1: Enter bootloader via bridge control protocol.
	u.log("» Entering bootloader…")
	bc := bridge.New(opts.Host, opts.Port)
	if err := bc.Connect(); err != nil {
		return err
	}
	bc.SetProfile(opts.MCU)
	bc.SetBaud(opts.Baud)
	bc.EnterBootloader()
	time.Sleep(300 * time.Millisecond) // wait for bootloader to settle
	bc.Close()

	// Step 2: Hand off to esptool
	chip := "esp32"
	if strings.ToLower(opts.MCU) == "esp8266" {
		chip = "esp8266"
	}

	// Flash offset: bare app images produced by our build pipeline belong at
	// 0x10000 on ESP32 (bootloader @0x1000, partition table @0x8000). Writing
	// at 0x0 overwrites the bootloader and bricks the boot layout. ESP8266
	// non-OTA app images start at 0x0.
	flashOffset := "0x10000"
	if chip == "esp8266" {
		flashOffset = "0x0"
	}

	socketURL := fmt.Sprintf("socket://%s:%d", opts.Host, opts.Port)
	args := []string{
		"-m", "esptool",
		"--chip", chip,
		"--port", socketURL,
		"--baud", fmt.Sprintf("%d", opts.Baud),
		"--before", "no_reset",
		"--after", "hard_reset",
		"write_flash",
		"--flash_mode", "dio",
		"--flash_size", "detect",
		"--compress",
		flashOffset, opts.BinaryPath,
	}

	python := "python3"
	if _, err := exec.LookPath("python3"); err != nil {
		python = "python"
	}

	u.log("» Running esptool.py…")
	cmd := exec.Command(python, args...)

	if opts.Verbose {
		cmd.Stdout = os.Stdout
		cmd.Stderr = os.Stderr
		return cmd.Run()
	}

	out, err := cmd.CombinedOutput()
	if err != nil {
		return fmt.Errorf("esptool failed:\n%s\n\nMake sure esptool is installed: pip install esptool", string(out))
	}
	// Print key lines
	for _, line := range strings.Split(string(out), "\n") {
		line = strings.TrimSpace(line)
		if strings.Contains(line, "%") ||
			strings.Contains(line, "Hash") ||
			strings.Contains(line, "Leaving") ||
			strings.Contains(line, "Wrote") ||
			strings.Contains(line, "Connecting") ||
			strings.Contains(line, "WARNING") ||
			strings.Contains(line, "Fatal") {
			u.log("  " + line)
		}
	}
	return nil
}

// ── STM32 — native UART bootloader (AN3155) ────────────────────────

const (
	stm32ACK      = 0x79
	stm32NACK     = 0x1F
	stm32SyncByte = 0x7F
)

func (u *Uploader) uploadSTM32(opts Options) error {
	fw, err := os.ReadFile(opts.BinaryPath)
	if err != nil {
		return err
	}

	bc := bridge.New(opts.Host, opts.Port)
	if err := bc.Connect(); err != nil {
		return err
	}
	defer func() {
		bc.Release()
		time.Sleep(100 * time.Millisecond)
		bc.Reset()
		bc.Close()
	}()

	bc.SetProfile("stm32")
	bc.SetBaud(opts.Baud)
	bc.EnterBootloader()
	time.Sleep(500 * time.Millisecond)

	// Sync
	u.log("» Syncing with STM32 bootloader…")
	if err := stm32Sync(bc); err != nil {
		return err
	}

	// Get bootloader info
	stm32GetInfo(bc, u.onOutput)

	// Mass erase
	u.log("» Erasing flash (mass erase)…")
	if err := stm32MassErase(bc); err != nil {
		return fmt.Errorf("erase: %w", err)
	}

	// Write
	const flashBase = 0x08000000
	const chunkSize = 256
	u.log(fmt.Sprintf("» Writing %d bytes to 0x%08X…", len(fw), flashBase))

	for i := 0; i < len(fw); i += chunkSize {
		end := i + chunkSize
		if end > len(fw) {
			end = len(fw)
		}
		chunk := fw[i:end]

		if err := stm32WriteMemory(bc, uint32(flashBase+i), chunk); err != nil {
			return fmt.Errorf("write at 0x%08X: %w", flashBase+i, err)
		}

		pct := (i + len(chunk)) * 100 / len(fw)
		if pct%10 == 0 || i == 0 {
			u.log(fmt.Sprintf("  %3d%%  [%d/%d bytes]", pct, i+len(chunk), len(fw)))
		}
	}

	u.log("» STM32 flash complete")
	return nil
}

func stm32Sync(bc *bridge.Client) error {
	for attempt := 0; attempt < 5; attempt++ {
		bc.Write([]byte{stm32SyncByte})
		b, err := bc.ReadByteTimeout(800 * time.Millisecond)
		if err == nil && b == stm32ACK {
			return nil
		}
		time.Sleep(200 * time.Millisecond)
	}
	return fmt.Errorf("STM32 sync timeout — check BOOT0 and NRST wiring")
}

func stm32SendCmd(bc *bridge.Client, opcode byte) error {
	bc.Write([]byte{opcode, opcode ^ 0xFF})
	b, err := bc.ReadByteTimeout(2 * time.Second)
	if err != nil {
		return err
	}
	if b != stm32ACK {
		return fmt.Errorf("NACK for command 0x%02X", opcode)
	}
	return nil
}

func stm32GetInfo(bc *bridge.Client, log func(string)) {
	if err := stm32SendCmd(bc, 0x00); err != nil {
		return
	}
	n, _ := bc.ReadByteTimeout(2 * time.Second)
	data := make([]byte, int(n)+2)
	io.ReadFull(bc, data)
	if log != nil {
		log(fmt.Sprintf("  BL version 0x%02X — %d commands", data[0], len(data)-2))
	}
}

func stm32MassErase(bc *bridge.Client) error {
	if err := stm32SendCmd(bc, 0x44); err != nil {
		return err
	}
	// 0xFFFF = mass erase, checksum = 0xFF ^ 0xFF = 0x00
	bc.Write([]byte{0xFF, 0xFF, 0x00})
	b, err := bc.ReadByteTimeout(30 * time.Second)
	if err != nil {
		return err
	}
	if b != stm32ACK {
		return fmt.Errorf("mass erase NACK")
	}
	return nil
}

func stm32WriteMemory(bc *bridge.Client, address uint32, data []byte) error {
	// Copy to avoid aliasing the caller's firmware slice (the chunk is a
	// sub-slice of the whole image); padding must not mutate the source.
	data = append([]byte(nil), data...)
	// Pad to 4-byte boundary with 0xFF
	for len(data)%4 != 0 {
		data = append(data, 0xFF)
	}

	if err := stm32SendCmd(bc, 0x31); err != nil {
		return err
	}

	// Address + XOR checksum
	ab := []byte{
		byte(address >> 24),
		byte(address >> 16),
		byte(address >> 8),
		byte(address),
	}
	checksum := ab[0] ^ ab[1] ^ ab[2] ^ ab[3]
	bc.Write(append(ab, checksum))

	b, err := bc.ReadByteTimeout(2 * time.Second)
	if err != nil || b != stm32ACK {
		return fmt.Errorf("address write NACK")
	}

	// (N-1) + data + XOR checksum of all bytes
	n := len(data) - 1
	xor := byte(n)
	for _, b := range data {
		xor ^= b
	}
	payload := append([]byte{byte(n)}, data...)
	payload = append(payload, xor)
	bc.Write(payload)

	b, err = bc.ReadByteTimeout(5 * time.Second)
	if err != nil || b != stm32ACK {
		return fmt.Errorf("data write NACK")
	}
	return nil
}

// ── AVR / Arduino — avrdude ───────────────────────────────────────

func (u *Uploader) uploadAVR(opts Options) error {
	// Derive MCU part from FQBN (e.g. arduino:avr:uno → atmega328p)
	avrMCU, err := resolveAVRMCU(opts.FQBN)
	if err != nil {
		return err
	}

	// Trigger bootloader window via bridge RST pulse
	u.log("» Triggering AVR bootloader window…")
	bc := bridge.New(opts.Host, opts.Port)
	if err := bc.Connect(); err != nil {
		return err
	}
	bc.SetProfile("avr")
	bc.SetBaud(opts.Baud)
	bc.EnterBootloader()
	time.Sleep(200 * time.Millisecond)
	bc.Close()
	time.Sleep(100 * time.Millisecond)

	ext := ""
	if idx := strings.LastIndex(opts.BinaryPath, "."); idx >= 0 {
		ext = strings.ToLower(opts.BinaryPath[idx:])
	}
	format := "i" // Intel HEX
	if ext == ".bin" {
		format = "r" // raw binary
	}

	// avrdude speaks its own network protocol: "net:host:port" (avrdude 7+,
	// via the avrdude-serjtag/net programmer). "socket://" is esptool syntax
	// and is not understood by avrdude.
	socketURL := fmt.Sprintf("net:%s:%d", opts.Host, opts.Port)
	args := []string{
		"-p", avrMCU,
		"-c", "arduino",
		"-P", socketURL,
		"-b", fmt.Sprintf("%d", opts.Baud),
		"-D",
		"-U", fmt.Sprintf("flash:w:%s:%s", opts.BinaryPath, format),
	}
	if opts.Verbose {
		args = append(args, "-v")
	}

	u.log("» Running avrdude…")
	cmd := exec.Command("avrdude", args...)
	out, err := cmd.CombinedOutput()
	if err != nil {
		if strings.Contains(err.Error(), "executable file not found") {
			return fmt.Errorf("avrdude not found\nInstall it with: sudo apt install avrdude")
		}
		return fmt.Errorf("avrdude failed:\n%s", string(out))
	}

	if opts.Verbose {
		u.log(string(out))
	} else {
		// Print avrdude progress lines only
		for _, line := range strings.Split(string(out), "\n") {
			line = strings.TrimSpace(line)
			if strings.Contains(line, "bytes") || strings.Contains(line, "done") ||
				strings.Contains(line, "verified") {
				u.log("  " + line)
			}
		}
	}
	return nil
}

// resolveAVRMCU maps common FQBNs to avrdude MCU part names. It returns an
// error (rather than silently guessing atmega328p) so the caller can surface
// a clear message instead of flashing the wrong part.
func resolveAVRMCU(fqbn string) (string, error) {
	table := map[string]string{
		"arduino:avr:uno":      "atmega328p",
		"arduino:avr:mega":     "atmega2560",
		"arduino:avr:mega2560": "atmega2560",
		"arduino:avr:nano":     "atmega328p",
		"arduino:avr:leonardo": "atmega32u4",
		"arduino:avr:micro":    "atmega32u4",
		"arduino:avr:pro":      "atmega328p",
		"arduino:avr:ethernet": "atmega328p",
	}
	if mcu, ok := table[strings.ToLower(fqbn)]; ok {
		return mcu, nil
	}
	// Extract board part and guess from well-known third components.
	parts := strings.Split(fqbn, ":")
	if len(parts) >= 3 {
		switch parts[2] {
		case "mega", "mega2560":
			return "atmega2560", nil
		case "leonardo", "micro":
			return "atmega32u4", nil
		}
	}
	return "", fmt.Errorf("unknown AVR board %q — cannot determine MCU part for avrdude", fqbn)
}

// ── Generic — raw binary stream ───────────────────────────────────

func (u *Uploader) uploadGeneric(opts Options) error {
	fw, err := os.ReadFile(opts.BinaryPath)
	if err != nil {
		return err
	}

	bc := bridge.New(opts.Host, opts.Port)
	if err := bc.Connect(); err != nil {
		return err
	}
	defer bc.Close()

	bc.SetBaud(opts.Baud)
	bc.EnterBootloader()
	time.Sleep(500 * time.Millisecond)

	u.log(fmt.Sprintf("» Streaming %d bytes (raw binary)…", len(fw)))

	const chunkSize = 256
	for i := 0; i < len(fw); i += chunkSize {
		end := i + chunkSize
		if end > len(fw) {
			end = len(fw)
		}
		bc.Write(fw[i:end])
		time.Sleep(8 * time.Millisecond)

		pct := end * 100 / len(fw)
		if pct%20 == 0 {
			u.log(fmt.Sprintf("  %3d%%", pct))
		}
	}

	bc.Release()
	time.Sleep(100 * time.Millisecond)
	bc.Reset()
	u.log("» Generic upload complete")
	return nil
}
