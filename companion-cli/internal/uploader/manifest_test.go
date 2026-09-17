package uploader

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestReadFlashArgsRejectsIncompleteManifest(t *testing.T) {
	dir := t.TempDir()
	for _, name := range []string{"boot.bin", "part.bin", "ota.bin", "app.bin", "other.bin"} {
		if err := os.WriteFile(filepath.Join(dir, name), []byte{1}, 0644); err != nil {
			t.Fatal(err)
		}
	}
	header := "--flash-mode dio --flash-freq 40m --flash-size 4MB\n"
	valid := "0x0 boot.bin\n0x8000 part.bin\n0xe000 ota.bin\n0x10000 app.bin\n"
	cases := []string{
		"0x10000 app.bin\n",
		strings.Replace(valid, "0x8000 part.bin\n", "malformed line here\n", 1),
		strings.Replace(valid, "0x8000", "not-an-offset", 1),
		strings.Replace(valid, "part.bin", "missing.bin", 1),
		strings.Replace(valid, "app.bin", "other.bin", 1),
		strings.Replace(valid, "0xe000", "0x8000", 1),
	}
	for _, body := range cases {
		if err := os.WriteFile(filepath.Join(dir, "flash_args"), []byte(header+body), 0644); err != nil {
			t.Fatal(err)
		}
		if args, ok := readFlashArgs(filepath.Join(dir, "app.bin")); ok {
			t.Errorf("accepted invalid manifest %q: %v", body, args)
		}
	}
}
