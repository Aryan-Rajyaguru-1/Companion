package libraries

import "testing"

func TestValidateLibrarySegmentRejectsPathAndWindowsMetacharacters(t *testing.T) {
	bad := []struct{ in, why string }{
		{"", "empty"},
		{"   ", "blank"},
		{".", "current"},
		{"..", "parent"},
		{"../../.ssh/authorized_keys", "traversal"},
		{`..\..\Windows\System32\x.dll`, "windows traversal"},
		{"/etc/passwd", "absolute"},
		{`sub\dir`, "backslash"},
		{"-rf", "option injection"},
		{"name:stream", "windows alternate data stream"},
		{"name*", "windows wildcard"},
		{"name?", "windows wildcard"},
		{"name<1>", "windows redirection"},
		{"name|pipe", "windows pipe"},
		{`name"quote`, "windows quote"},
		{"name\x00", "NUL"},
		{"name\nline", "newline"},
		{"name\ttab", "tab"},
		{"name\x7f", "control"},
		{"trailing.", "windows strips a trailing dot"},
		{"NUL", "reserved device"},
		{"con.txt", "reserved device with extension"},
		{"COM1", "reserved serial device"},
		{"lpt9.log", "reserved printer device"},
	}
	for _, tc := range bad {
		if got, err := validateLibrarySegment(tc.in, "library name"); err == nil {
			t.Errorf("accepted %q (%s) as %q — it must be rejected", tc.in, tc.why, got)
		}
	}

	good := []string{
		"ArduinoJson",
		"Adafruit GFX Library",
		"ESP8266 and ESP32 OLED driver for SSD1306 displays",
		"Foo & Bar",
		"Ladyada's Library",
		"library-1.2.3",
		"a+b~c@d",
	}
	for _, name := range good {
		if _, err := validateLibrarySegment(name, "library name"); err != nil {
			t.Errorf("rejected a legitimate library name %q: %v", name, err)
		}
	}
}

func TestSafeLibrarySegmentReplacesSpacesOnly(t *testing.T) {
	got, err := safeLibrarySegment("Adafruit GFX Library")
	if err != nil {
		t.Fatal(err)
	}
	if got != "Adafruit_GFX_Library" {
		t.Fatalf("safeLibrarySegment = %q, want Adafruit_GFX_Library", got)
	}

	got, err = safeArchiveSegment("Adafruit GFX Library-1.11.11.zip")
	if err != nil {
		t.Fatal(err)
	}
	if got != "Adafruit GFX Library-1.11.11.zip" {
		t.Fatalf("safeArchiveSegment changed a legitimate archive name: %q", got)
	}
}
