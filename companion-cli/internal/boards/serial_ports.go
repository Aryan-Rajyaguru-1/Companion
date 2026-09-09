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
	Port         string `json:"port"`          // /dev/ttyACM0
	USBVID       string `json:"usbVid"`        // "303a" (no 0x)
	USBPID       string `json:"usbPid"`        // "1001"
	SerialNumber string `json:"serialNumber,omitempty"`
	Manufacturer string `json:"manufacturer,omitempty"`
	ProductName  string `json:"productName,omitempty"`
	BoardName    string `json:"boardName,omitempty"` // from boards.txt match
	FQBN         string `json:"fqbn,omitempty"`
}

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
			key := info.USBVID + ":" + info.USBPID
			for _, b := range vidPids[key] { // first match wins
				info.BoardName = b.name
				info.FQBN = b.fqbn
				break
			}
			// Espressif USB-JTAG/serial (303a:1001) has no per-board entry;
			// fall back to guessing from the product string later in UI.
			if info.FQBN == "" &&
				strings.EqualFold(info.USBVID, "303a") &&
				strings.HasPrefix(strings.ToLower(info.ProductName), "esp32") {
				info.BoardName = info.ProductName
			}
		}
		out = append(out, info)
	}
	sort.Slice(out, func(i, j int) bool { return out[i].Port < out[j].Port })
	return out, nil
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

// installedVIDPIDTable builds map["vid:pid"]→boards from every installed
// platform's boards.txt (keys vid.N/pid.N with optional vidN.pidN suffixes).
func (m *Manager) installedVIDPIDTable() map[string][]vidPidBoard {
	table := map[string][]vidPidBoard{}
	bds, err := m.ListAllBoards()
	if err != nil {
		return table
	}
	for _, b := range bds {
		props, err := parseBoardsTxt(
			filepath.Join(m.cfg.PackagesDir(), vendorOf(b.Platform), "hardware",
				archOf(b.Platform), b.Version, "boards.txt"), boardIdOf(b.FQBN))
		if err != nil {
			continue
		}
		type pair struct{ vid, pid string }
		var pairs []pair
		for k, v := range props {
			if !strings.HasPrefix(k, "vid.") {
				continue
			}
			idx := strings.TrimPrefix(k, "vid.")
			pidKey := "pid." + idx
			pidVal, ok := props[pidKey]
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