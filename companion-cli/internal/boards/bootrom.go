package boards

import (
	"regexp"
	"strings"
)

// ── Boot-ROM probing ─────────────────────────────────────────────
//
// Some boards expose only a generic USB-serial bridge identity (a bare
// CH340/CH9102/CP210x reports no board name, and the ESP32 cores publish no
// vid.N/pid.N tables). For last-resort identification, the chip's own boot
// ROM banner is the reliable signal — emitted over the UART at every reset:
//
//	ESP-ROM:esp32s3-20210327
//	ESP-ROM:esp32c3-20200618
//
// ProbeBootROM pulses the classic auto-reset circuit (DTR→EN, RTS→IO0 —
// the same dance esptool uses) to trigger a reset into the ROM, then reads
// the banner and maps the chip name to an installed FQBN.
//
// SIDE EFFECT: the attached sketch restarts (the board resets). Ports are
// probed only when table and string matching failed, and only for bridge
// VIDs listed in probeableVIDs. Callers must make probing an explicit,
// user-initiated action (e.g. `companion board detect --probe`), never a
// passive scan.
//
// The actual probing lives in bootrom_linux.go (raw termios + ioctl);
// bootrom_stub.go returns a graceful "unsupported" result elsewhere.

// MatchBootROM marks an FQBN identified from the chip's boot ROM banner.
const MatchBootROM = "bootrom"

// BootProbeResult is the outcome of a single boot-ROM probe.
type BootProbeResult struct {
	OK     bool   // banner read and chip recognized
	Port   string // port path that was probed
	Chip   string // "esp32s3", "esp32c3", "esp32", …
	FQBN   string // canonical FQBN for the chip
	Board  string // display name
	Banner string // raw text captured (for diagnostics)
	Err    string // non-fatal failure reason (port busy, no banner, unsupported OS…)
}

// probeableVIDs lists USB vendor IDs of UART bridges / Espressif native
// USB where a boot-ROM probe adds signal beyond string matching.
var probeableVIDs = map[string]bool{
	"1a86": true, // WCH CH340 / CH9102
	"10c4": true, // Silicon Labs CP210x
	"0403": true, // FTDI FT232
	"303a": true, // Espressif native USB-JTAG/serial or CDC
}

// chipFQBNs maps the boot-ROM chip token to the arduino FQBN board id.
// The empty token is the classic ESP32, whose ROM banner ("rst:0x1
// (POWERON_RESET)…", "waiting for download") names no chip variant.
var chipFQBNs = map[string]struct {
	fqbn, name string
}{
	"":     {"esp32:esp32:esp32", "ESP32 Dev Module"},
	"8266": {"esp8266:esp8266:generic", "ESP8266"},
	"s3":   {"esp32:esp32:esp32s3", "ESP32-S3"},
	"s2":   {"esp32:esp32:esp32s2", "ESP32-S2"},
	"c3":   {"esp32:esp32:esp32c3", "ESP32-C3"},
	"c6":   {"esp32:esp32:esp32c6", "ESP32-C6"},
	"h2":   {"esp32:esp32:esp32h2", "ESP32-H2"},
	"c2":   {"esp32:esp32:esp32c2", "ESP32-C2"},
	"c5":   {"esp32:esp32:esp32c5", "ESP32-C5"},
	"p4":   {"esp32:esp32:esp32p4", "ESP32-P4"},
}

// romBannerRe extracts the chip token from "ESP-ROM:esp32s3-20210327".
var romBannerRe = regexp.MustCompile(`(?i)ESP-ROM:esp32([a-z0-9]*)[-0-9]`)

// bareChipRe catches "ESP32-S3"/"ESP32S3" style names in secondary output.
var bareChipRe = regexp.MustCompile(`(?i)ESP32[- ]?(S3|S2|C3|C6|C2|C5|H2|P4)`)

// classicResetRe matches the classic ESP32 ROM boot lines, which carry no
// chip name: "rst:0x1 (POWERON_RESET)", "rst:0x10 (RTCWDT_RTC_RESET)", …
var classicResetRe = regexp.MustCompile(`(?im)^rst:0x[0-9a-f]+ \(`)

// esp8266Re matches the ESP8266 ROM banner ("ets Jan  8 2013,rst cause:1…").
var esp8266Re = regexp.MustCompile(`ets Jan\s+8 2013`)

// parseChipToken pulls the chip identifier out of a boot banner.
func parseChipToken(banner string) (string, bool) {
	if m := romBannerRe.FindStringSubmatch(banner); m != nil {
		return strings.ToLower(m[1]), true
	}
	if m := bareChipRe.FindStringSubmatch(banner); m != nil {
		return strings.ToLower(m[1]), true
	}
	if esp8266Re.MatchString(banner) {
		return "8266", true
	}
	if classicResetRe.MatchString(banner) {
		return "", true // classic ESP32, unnamed in its banner
	}
	return "", false
}

// probeable reports whether a boot-ROM probe makes sense for this port:
// unidentified so far, and behind a bridge/native USB whose VID is known
// to carry boards worth probing.
func probeable(info SerialPortInfo) bool {
	return info.FQBN == "" && probeableVIDs[strings.ToLower(info.USBVID)]
}

// ProbeUnidentified boot-ROM-probes the unidentified ports a user has
// explicitly agreed to probe (e.g. via `board detect --probe`). Each probe
// resets the attached board — that is the point, the banner only appears on
// boot — so this must never run as part of a passive scan. Successful probes
// fill info.BoardName/FQBN with MatchSource=MatchBootROM; every failure is
// reported in the returned map and never aborts the remaining probes.
func ProbeUnidentified(ports []SerialPortInfo, agreed []string) map[string]BootProbeResult {
	wanted := make(map[string]bool, len(agreed))
	for _, p := range agreed {
		wanted[p] = true
	}
	out := make(map[string]BootProbeResult)
	for _, info := range ports {
		if !wanted[info.Port] || !probeable(info) {
			continue
		}
		res := ProbeBootROM(info.Port)
		if res.OK {
			info.BoardName, info.FQBN = res.Board, res.FQBN
			info.MatchSource = MatchBootROM
		}
		out[info.Port] = res
	}
	return out
}
