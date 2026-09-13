package boards

import "testing"

func TestIdentifyFallback(t *testing.T) {
	m := &Manager{} // cases below return before the fuzzy path touches m.cfg

	tests := []struct {
		name     string
		in       SerialPortInfo
		wantFQBN string
		wantName string
		wantSrc  string
	}{
		{
			name:     "built-in table: Arduino Uno VID/PID",
			in:       SerialPortInfo{USBVID: "2341", USBPID: "0043"},
			wantFQBN: "arduino:avr:uno", wantName: "Arduino Uno", wantSrc: MatchBuiltin,
		},
		{
			name:     "heuristic: CH340 bridge carrying ESP32-S3 product string",
			in:       SerialPortInfo{USBVID: "1a86", USBPID: "55d4", ProductName: "USB Single Serial 9C-ESP32-S3"},
			wantFQBN: "esp32:esp32:esp32s3", wantName: "ESP32-S3", wantSrc: MatchName,
		},
		{
			name:     "heuristic: hyphenless product string",
			in:       SerialPortInfo{USBVID: "1a86", USBPID: "55d4", ProductName: "esp32s3 usb modem"},
			wantFQBN: "esp32:esp32:esp32s3", wantName: "ESP32-S3", wantSrc: MatchName,
		},
		{
			name:     "heuristic: NodeMCU over CP210x",
			in:       SerialPortInfo{USBVID: "10c4", USBPID: "ea60", ProductName: "NodeMCU ESP8266"},
			wantFQBN: "esp8266:esp8266:nodemcuv2", wantName: "NodeMCU", wantSrc: MatchName,
		},
		{
			name:     "heuristic falls back to manufacturer string",
			in:       SerialPortInfo{USBVID: "1a86", USBPID: "55d4", Manufacturer: "wemos d1 mini"},
			wantFQBN: "esp8266:esp8266:d1_mini", wantName: "WEMOS D1 mini", wantSrc: MatchName,
		},
		{
			name:     "bare CH340 with generic name stays unidentified",
			in:       SerialPortInfo{USBVID: "1a86", USBPID: "7523", ProductName: "USB2.0-Serial"},
			wantFQBN: "", wantName: "", wantSrc: "",
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			info := tc.in
			m.identifyFallback(&info)
			if info.FQBN != tc.wantFQBN || info.BoardName != tc.wantName || info.MatchSource != tc.wantSrc {
				t.Fatalf("got fqbn=%q name=%q src=%q, want fqbn=%q name=%q src=%q",
					info.FQBN, info.BoardName, info.MatchSource, tc.wantFQBN, tc.wantName, tc.wantSrc)
			}
		})
	}
}

func TestMatchConfidence(t *testing.T) {
	cases := []struct {
		src  string
		want string
	}{
		{MatchVIDPID, "high"},
		{MatchBuiltin, "high"},
		{MatchName, "medium"},
		{MatchJTAG, "medium"},
		{MatchFuzzy, "low"},
		{"", ""},
		{"bogus", ""},
	}
	for _, tc := range cases {
		if got := MatchConfidence(SerialPortInfo{MatchSource: tc.src}); got != tc.want {
			t.Errorf("MatchConfidence(src=%q) = %q, want %q", tc.src, got, tc.want)
		}
	}
}

func TestCandidateSource(t *testing.T) {
	if got := CandidateSource(SerialPortInfo{MatchSource: MatchName}); got != MatchName {
		t.Errorf("CandidateSource passthrough = %q, want %q", got, MatchName)
	}
	if got := CandidateSource(SerialPortInfo{}); got != SourceUnknown {
		t.Errorf("CandidateSource(empty) = %q, want %q", got, SourceUnknown)
	}
}

func TestParseChipToken(t *testing.T) {
	cases := []struct {
		banner string
		want   string
		ok     bool
	}{
		{"ESP-ROM:esp32s3-20210327\n", "s3", true},
		{"ESP-ROM:esp32c3-20200618\n", "c3", true},
		{"ESP-ROM:esp32-20210327\n", "", true},
		{"ESP32-S3 something\n", "s3", true},
		{"ets Jan  8 2013,rst cause:1, boot:3\n", "8266", true},
		{"rst:0x1 (POWERON_RESET),boot:0x13 (SPI_FAST_FLASH_BOOT)\nwaiting for download", "", true},
		{"rst:0x10 (RTCWDT_RTC_RESET),boot:0x13\n", "", true},
		{"no chip signal here\n", "", false},
		{"", "", false},
	}
	for _, tc := range cases {
		chip, ok := parseChipToken(tc.banner)
		if ok != tc.ok || chip != tc.want {
			t.Errorf("parseChipToken(%q) = (%q, %v), want (%q, %v)",
				tc.banner, chip, ok, tc.want, tc.ok)
		}
	}
}

func TestProbeable(t *testing.T) {
	if !probeable(SerialPortInfo{USBVID: "1a86"}) {
		t.Error("unidentified CH340 port should be probeable")
	}
	if probeable(SerialPortInfo{USBVID: "2341", FQBN: "arduino:avr:uno"}) {
		t.Error("already-identified port must never be probed")
	}
	if probeable(SerialPortInfo{USBVID: "0d28"}) {
		t.Error("non-probeable VID must be skipped")
	}
}

func TestKnownUSBBoardsWellformed(t *testing.T) {
	for key, b := range KnownUSBBoards {
		if len(key) != 9 || key[4] != ':' {
			t.Errorf("malformed key %q in KnownUSBBoards", key)
		}
		if b.name == "" {
			t.Errorf("board %q has empty name", key)
		}
		// fqbn is allowed to be empty only for bridge-only entries.
		if b.fqbn == "" && b.name != "CP210x bridge" {
			t.Errorf("board %q (%s) has empty fqbn", key, b.name)
		}
	}
}
