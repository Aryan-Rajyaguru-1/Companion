// Package safename holds filename rules shared by code that turns untrusted
// index entries into on-disk paths.
package safename

import "strings"

// IsWindowsReservedName reports whether name resolves to a DOS device name on
// Windows, with or without an extension. Windows still treats CON, NUL, COM1,
// LPT1 and friends as devices in every directory, so a downloaded index must
// not be allowed to use them as file or directory names.
func IsWindowsReservedName(name string) bool {
	base := name
	if i := strings.IndexByte(base, '.'); i >= 0 {
		base = base[:i]
	}
	base = strings.ToUpper(strings.TrimSpace(base))
	switch base {
	case "CON", "PRN", "AUX", "NUL":
		return true
	}
	if len(base) == 4 {
		if (strings.HasPrefix(base, "COM") || strings.HasPrefix(base, "LPT")) && base[3] >= '1' && base[3] <= '9' {
			return true
		}
	}
	return false
}
