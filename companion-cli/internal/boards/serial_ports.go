package boards

import (
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
)

// ── USB serial port discovery ────────────────────────────────────
//
// Enumerates local serial devices and identifies attached boards by
// matching USB VID/PID against installed platforms' boards.txt entries.
// Linux sysfs is read directly — no cgo, no external tools.

// SerialPortInfo describes one detected serial device + probable board.
type SerialPortInfo struct {
	Port         string `json:"port"`   // /dev/ttyACM0
	USBVID       string `json:"usbVid"` // "303a" (no 0x)
	USBPID       string `json:"usbPid"` // "1001"
	SerialNumber string `json:"serialNumber,omitempty"`
	Manufacturer string `json:"manufacturer,omitempty"`
	ProductName  string `json:"productName,omitempty"`
	BoardName    string `json:"boardName,omitempty"` // from boards.txt match
	FQBN         string `json:"fqbn,omitempty"`
	MatchSource  string `json:"matchSource,omitempty"` // how FQBN was resolved; see Match* constants
}

// How a port's FQBN was resolved. Used by SerialPortInfo.MatchSource and
// returned by CandidateSource.
const (
	MatchVIDPID   = "vidpid"         // installed platform's boards.txt VID/PID table
	MatchBuiltin  = "builtin"        // Companion's built-in USB identity table
	MatchName     = "name"           // product/manufacturer string heuristic
	MatchFuzzy    = "fuzzy"          // containment match vs installed board names
	MatchJTAG     = "espressif-jtag" // native Espressif USB-JTAG/serial product name
	SourceUnknown = "unknown"        // port could not be identified
)

type vidPidBoard struct {
	fqbn string
	name string
}

// ListSerialPorts scans /dev for ttyACM*/ttyUSB* candidates, resolves their
// USB identity via sysfs, and tries to identify the board against all
// installed platforms' boards.txt VID/PID tables.
func (m *Manager) ListSerialPorts() ([]SerialPortInfo, error) {
	candidates := globPorts("/dev/ttyACM*", "/dev/ttyUSB*")
	if len(candidates) == 0 {
		return nil, nil
	}

	vidPids := m.installedVIDPIDTable() // map "303a:1001" → []vidPidBoard

	out := make([]SerialPortInfo, 0, len(candidates))
	for _, port := range candidates {
		info := SerialPortInfo{Port: port}
		devPath := sysfsDevPath(port)
		if devPath != "" {
			info.USBVID = strings.ToLower(sysfsRead(filepath.Join(devPath, "idVendor")))
			info.USBPID = strings.ToLower(sysfsRead(filepath.Join(devPath, "idProduct")))
			info.SerialNumber = sysfsRead(filepath.Join(devPath, "serial"))
			info.Manufacturer = sysfsRead(filepath.Join(devPath, "manufacturer"))
			info.ProductName = sysfsRead(filepath.Join(devPath, "product"))
		}
		if info.USBVID != "" && info.USBPID != "" {
			// Espressif's generic native-USB CDC is shared by every ESP32
			// variant with USB (S2/S3/C3/C6/P4…) and is claimed by several
			// modules at once, so a table hit names the vendor, not the chip —
			// "first match wins" would hand back an arbitrary board. Leave it
			// unidentified so the boot-ROM probe reads the actual chip.
			if !ambiguousVIDPID(info.USBVID, info.USBPID) {
				key := info.USBVID + ":" + info.USBPID
				for _, b := range vidPids[key] { // first match wins
					info.BoardName = b.name
					info.FQBN = b.fqbn
					info.MatchSource = MatchVIDPID
					break
				}
			}
			// Espressif USB-JTAG/serial has no per-board entry; fall back to
			// guessing from the product string later in UI.
			if info.FQBN == "" &&
				strings.EqualFold(info.USBVID, "303a") &&
				strings.HasPrefix(strings.ToLower(info.ProductName), "esp32") {
				info.BoardName = info.ProductName
				info.MatchSource = MatchJTAG
			}
		}
		// Still unidentified? Try Companion's built-in USB table, then
		// heuristic name matching against installed boards.txt entries.
		if info.FQBN == "" {
			m.identifyFallback(&info)
		}
		out = append(out, info)
	}
	sort.Slice(out, func(i, j int) bool { return out[i].Port < out[j].Port })
	return out, nil
}

// KnownUSBBoards maps lowercased "vid:pid" → board FQBN + display name for
// common hobbyist boards whose cores don't publish vid.N/pid.N in boards.txt
// (e.g. Espressif cores). WCH CH340/CH9102 bridges are board-agnostic and are
// intentionally absent here — those resolve via ProductNameHeuristics instead.
// Exported so command-layer code can grade match confidence.
var KnownUSBBoards = map[string]vidPidBoard{
	"2341:0043": {fqbn: "arduino:avr:uno", name: "Arduino Uno"},
	"2341:0001": {fqbn: "arduino:avr:uno", name: "Arduino Uno"},
	"2341:8036": {fqbn: "arduino:avr:leonardo", name: "Arduino Leonardo"},
	"2341:0045": {fqbn: "arduino:avr:mega", name: "Arduino Mega 2560"},
	"2341:8037": {fqbn: "arduino:avr:micro", name: "Arduino Micro"},
	"2341:004e": {fqbn: "arduino:avr:robotMotor", name: "Arduino Robot Control"},
	"1b4f:9206": {fqbn: "SparkFun:avr:pro", name: "SparkFun Pro Micro"},
	"1b4f:9207": {fqbn: "SparkFun:avr:pro", name: "SparkFun Pro Micro"},
	"2341:8058": {fqbn: "arduino:megaavr:uno2018", name: "Arduino Uno WiFi Rev2"},
	"2341:0058": {fqbn: "arduino:samd:mkrzero", name: "Arduino MKR Zero"},
	"2341:8050": {fqbn: "arduino:samd:mkr1000", name: "Arduino MKR1000"},
	"2341:8052": {fqbn: "arduino:samd:mkrwifi1010", name: "Arduino MKR WiFi 1010"},
	"2341:8054": {fqbn: "arduino:samd:nano_33_iot", name: "Arduino Nano 33 IoT"},
	"2341:8057": {fqbn: "arduino:samd:nano_33_ble", name: "Arduino Nano 33 BLE"},
	"2341:0057": {fqbn: "arduino:avr:nano", name: "Arduino Nano"},
	"2c7b:0001": {fqbn: "arduino:avr:nano", name: "Arduino Nano (clone)"},
	"10c4:ea60": {fqbn: "", name: "CP210x bridge"}, // bridge, resolved by name
}

// ProductNameHeuristics maps substrings commonly found in USB product
// strings to their canonical FQBNs. Matched case-insensitively against
// the reported product name (falling back to the manufacturer string).
// IMPORTANT: ordered most-specific first — the scan stops at the first
// containment hit, so "esp32c3" must precede "esp32" and "nodemcu"/
// "d1 mini" must precede "esp8266".
// Exported so command-layer code can grade match confidence.
var ProductNameHeuristics = []struct {
	match string
	fqbn  string
	name  string
}{
	{"esp32s3", "esp32:esp32:esp32s3", "ESP32-S3"},
	{"esp32c3", "esp32:esp32:esp32c3", "ESP32-C3"},
	{"esp32c6", "esp32:esp32:esp32c6", "ESP32-C6"},
	{"esp32h2", "esp32:esp32:esp32h2", "ESP32-H2"},
	{"esp32s2", "esp32:esp32:esp32s2", "ESP32-S2"},
	{"nodemcu", "esp8266:esp8266:nodemcuv2", "NodeMCU"},
	{"wemos", "esp8266:esp8266:d1_mini", "WEMOS D1 mini"},
	{"d1 mini", "esp8266:esp8266:d1_mini", "WEMOS D1 mini"},
	{"esp8266", "esp8266:esp8266:generic", "ESP8266"},
	{"esp32", "esp32:esp32:esp32", "ESP32 Dev Module"},
	{"arduino uno", "arduino:avr:uno", "Arduino Uno"},
	{"uno wifi", "arduino:avr:uno", "Arduino Uno"},
	{"leonardo", "arduino:avr:leonardo", "Arduino Leonardo"},
	{"micro pro", "arduino:avr:micro", "Arduino Pro Micro"},
	{"promicro", "arduino:avr:micro", "Arduino Pro Micro"},
	{"mega 2560", "arduino:avr:mega", "Arduino Mega 2560"},
	{"mega2560", "arduino:avr:mega", "Arduino Mega 2560"},
	{"nano 33", "arduino:samd:nano_33_iot", "Arduino Nano 33"},
	{"nano", "arduino:avr:nano", "Arduino Nano"},
}

// identifyFallback resolves unidentified ports using (1) the built-in USB
// identity table and (2) fuzzy product/manufacturer-name matching against
// known FQBNs and against every installed boards.txt board name.
func (m *Manager) identifyFallback(info *SerialPortInfo) {
	hay := strings.ToLower(info.ProductName)
	if hay == "" {
		hay = strings.ToLower(info.Manufacturer)
	}
	// 1) Exact VID/PID from the built-in table.
	if key := info.USBVID + ":" + info.USBPID; key != ":" {
		if b, ok := KnownUSBBoards[key]; ok && b.fqbn != "" {
			info.BoardName, info.FQBN = b.name, b.fqbn
			info.MatchSource = MatchBuiltin
			return
		}
	}
	// 2) Product-name heuristics (cheap, catches ESP32 devkits on CH340/CP210x).
	// Match against several normalized forms so "esp32-s3" hits "esp32s3"
	// and "d1-mini" hits "d1 mini" alike.
	normSpace := strings.ReplaceAll(hay, "-", " ")
	normCompact := strings.ReplaceAll(hay, "-", "")
	for _, h := range ProductNameHeuristics {
		if strings.Contains(hay, h.match) ||
			strings.Contains(normSpace, h.match) ||
			strings.Contains(normCompact, h.match) {
			info.BoardName, info.FQBN = h.name, h.fqbn
			info.MatchSource = MatchName
			return
		}
	}
	// 3) Fuzzy match against names of boards from installed platforms.
	if hay == "" || m == nil || m.cfg == nil {
		return
	}
	bds, err := m.ListAllBoards()
	if err != nil {
		return
	}
	best, bestLen := -1, 0
	for i, b := range bds {
		lname := strings.ToLower(b.Name)
		if strings.Contains(lname, hay) || strings.Contains(hay, lname) {
			if l := len(lname); l > bestLen {
				best, bestLen = i, l
			}
		}
	}
	if best >= 0 {
		info.BoardName, info.FQBN = bds[best].Name, bds[best].FQBN
		info.MatchSource = MatchFuzzy
	}
}

// MatchConfidence grades how trustworthy a port's identification is:
//   - "high"   — exact VID/PID (installed boards.txt table or built-in table)
//                or a boot-ROM banner match
//   - "medium" — product/manufacturer string hit in the built-in heuristics
//   - "low"    — fuzzy containment match against installed board names
func MatchConfidence(p SerialPortInfo) string {
	switch p.MatchSource {
	case MatchVIDPID, MatchBuiltin, MatchBootROM:
		return "high"
	case MatchName, MatchJTAG:
		return "medium"
	case MatchFuzzy:
		return "low"
	default:
		return ""
	}
}

// CandidateSource reports how a port's FQBN was derived — one of the Match*
// constants, or SourceUnknown for unidentified ports.
func CandidateSource(p SerialPortInfo) string {
	if p.MatchSource != "" {
		return p.MatchSource
	}
	return SourceUnknown
}

func globPorts(patterns ...string) []string {
	var ports []string
	for _, p := range patterns {
		matches, err := filepath.Glob(p)
		if err != nil {
			continue
		}
		ports = append(ports, matches...)
	}
	sort.Strings(ports)
	return ports
}

// sysfsDevPath resolves a /dev node to its USB device directory under
// sysfs by following the class symlink and walking up through interface
// dirs until the device-level idVendor/idProduct pair appears.
func sysfsDevPath(devNode string) string {
	base := filepath.Base(devNode)
	p := fmt.Sprintf("/sys/class/tty/%s/device", base)
	// Resolve the symlink (…/usbX/Y:Z.W interface dir).
	if resolved, err := filepath.EvalSymlinks(p); err == nil {
		p = resolved
	}
	for i := 0; i < 6; i++ {
		if info, err := os.Stat(filepath.Join(p, "idVendor")); err == nil && !info.IsDir() {
			return p
		}
		parent := filepath.Dir(p)
		if parent == p || !strings.HasPrefix(parent, "/sys") {
			break
		}
		p = parent
	}
	return ""
}

func sysfsRead(path string) string {
	data, err := os.ReadFile(path)
	if err != nil {
		return ""
	}
	return strings.TrimSpace(string(data))
}

// ambiguousVIDPID reports whether a USB identity is shared by so many boards
// that matching it identifies nothing. 303a:1001 is Espressif's generic
// native-USB CDC/serial: the chip behind it may be any ESP32 variant, and
// multiple module definitions claim the same pair.
func ambiguousVIDPID(vid, pid string) bool {
	return strings.EqualFold(vid, "303a") && pid == "1001"
}

// installedVIDPIDTable builds map["vid:pid"]→boards from every installed
// platform's boards.txt (keys vid.N/pid.N with optional vidN.pidN suffixes).
// Boards are grouped by their boards.txt path so each file is parsed exactly
// once — re-parsing per board made port scans take seconds on large files
// like esp32's 5000-line boards.txt.
func (m *Manager) installedVIDPIDTable() map[string][]vidPidBoard {
	table := map[string][]vidPidBoard{}
	bds, err := m.ListAllBoards()
	if err != nil {
		return table
	}
	byFile := map[string][]BoardEntry{}
	for _, b := range bds {
		path := filepath.Join(m.cfg.PackagesDir(), vendorOf(b.Platform), "hardware",
			archOf(b.Platform), b.Version, "boards.txt")
		byFile[path] = append(byFile[path], b)
	}
	for path, entries := range byFile {
		all, err := parsePropertiesFile(path)
		if err != nil {
			continue
		}
		for _, b := range entries {
			prefix := boardIdOf(b.FQBN) + "."
			// Hidden boards are internal/compat placeholders — the esp32 core's
			// `esp32_family` catch-all, for one — and are never user-selectable.
			// Letting one match a port dresses a placeholder up as real hardware.
			if strings.EqualFold(strings.TrimSpace(all[prefix+"hide"]), "true") {
				continue
			}
			type pair struct{ vid, pid string }
			var pairs []pair
			for k, v := range all {
				if !strings.HasPrefix(k, prefix) {
					continue
				}
				suffix := k[len(prefix):]
				if !strings.HasPrefix(suffix, "vid.") {
					continue
				}
				idx := strings.TrimPrefix(suffix, "vid.")
				pidVal, ok := all[prefix+"pid."+idx]
				if !ok {
					continue
				}
				vid := strings.ToLower(strings.TrimPrefix(strings.TrimPrefix(v, "0x"), "0X"))
				pid := strings.ToLower(strings.TrimPrefix(strings.TrimPrefix(pidVal, "0x"), "0X"))
				if n, err := strconv.ParseUint(vid, 16, 16); err == nil {
					vid = fmt.Sprintf("%04x", n)
				}
				if n, err := strconv.ParseUint(pid, 16, 16); err == nil {
					pid = fmt.Sprintf("%04x", n)
				}
				pairs = append(pairs, pair{vid, pid})
			}
			for _, pr := range pairs {
				key := pr.vid + ":" + pr.pid
				table[key] = append(table[key], vidPidBoard{fqbn: b.FQBN, name: b.Name})
			}
		}
	}
	return table
}

func vendorOf(platform string) string {
	i := indexByteStr(platform, ':')
	if i <= 0 {
		return platform
	}
	return platform[:i]
}

func archOf(platform string) string {
	first := indexByteStr(platform, ':')
	if first < 0 {
		return ""
	}
	rest := platform[first+1:]
	second := indexByteStr(rest, ':')
	if second >= 0 {
		return rest[:second]
	}
	return rest
}

func boardIdOf(fqbn string) string {
	parts := strings.Split(fqbn, ":")
	if len(parts) >= 3 {
		return parts[2]
	}
	return ""
}

func indexByteStr(s string, c byte) int {
	for i := 0; i < len(s); i++ {
		if s[i] == c {
			return i
		}
	}
	return -1
}
