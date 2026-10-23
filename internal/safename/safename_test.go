package safename

import "testing"

func TestIsWindowsReservedName(t *testing.T) {
	for _, name := range []string{
		"CON", "con", "Con.txt", " PRN ", "AUX", "NUL", "COM1", "com9.log", "LPT1", "lpt9.tar.gz",
	} {
		if !IsWindowsReservedName(name) {
			t.Errorf("%q should be a reserved Windows name", name)
		}
	}
	for _, name := range []string{"COM0", "COM10", "LPT0", "LPT10", "console", "null", "com1x", "lpt9x"} {
		if IsWindowsReservedName(name) {
			t.Errorf("%q should not be a reserved Windows name", name)
		}
	}
}
