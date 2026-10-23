package compiler

import (
	"context"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"

	"github.com/companion-ide/companion-cli/internal/boards"
)

// Exercise the actual subprocess/copy/export flow without requiring a core,
// toolchain or serial device. The Python fixtures stand in for platform tools;
// this verifies orchestration, not the contents of Espressif's image format.
func TestGenerateFlashArtifacts(t *testing.T) {
	if _, err := exec.LookPath(pythonBinName()); err != nil {
		t.Skip("Python required for platform-script fixture")
	}
	for _, addr := range []string{"0x1000", "0x0", "0x2000"} {
		t.Run(addr, func(t *testing.T) {
			root := t.TempDir()
			sketch, build, platform, sdk, tools := filepath.Join(root, "sketch"), filepath.Join(root, "build"), filepath.Join(root, "platform"), filepath.Join(root, "sdk"), filepath.Join(root, "tools")
			write := func(p, s string) {
				t.Helper()
				if err := os.MkdirAll(filepath.Dir(p), 0755); err != nil {
					t.Fatal(err)
				}
				if err := os.WriteFile(p, []byte(s), 0644); err != nil {
					t.Fatal(err)
				}
			}
			write(filepath.Join(sketch, "partitions.csv"), "sketch partitions")
			write(filepath.Join(platform, "tools", "partitions", "default.csv"), "platform partitions")
			write(filepath.Join(platform, "tools", "partitions", "boot_app0.bin"), "ota selector")
			write(filepath.Join(sdk, "bin", "bootloader_qio_80m.elf"), "bootloader elf")
			write(filepath.Join(tools, "esptool_py", "4.8.1", "esptool.py"), `import pathlib, sys
args = sys.argv[1:]
assert args[args.index('--chip') + 1] == 'esp32s3'
assert args[args.index('--flash_freq') + 1] == '40m'
pathlib.Path(args[args.index('-o') + 1]).write_bytes(pathlib.Path(args[-1]).read_bytes())
`)
			write(filepath.Join(platform, "tools", "gen_esp32part.py"), `import pathlib, sys
assert sys.argv[1] == '-q'
pathlib.Path(sys.argv[3]).write_bytes(pathlib.Path(sys.argv[2]).read_bytes())
`)
			app := filepath.Join(build, "Blink.bin")
			write(app, "application")
			rb := &boards.ResolvedBoard{PlatformPath: platform, ToolsDir: tools, BoardProps: map[string]string{
				"build.mcu": "esp32s3", "build.boot": "qio", "build.boot_freq": "80m", "build.flash_mode": "dio", "build.flash_freq": "40m", "build.flash_size": "4MB", "build.partitions": "default", "build.bootloader_addr": addr,
			}}
			c := &Compiler{ctx: context.Background()}
			artifacts, err := c.generateESPFlashArtifacts(rb, sdk, sketch, build, "Blink", app)
			if err != nil {
				t.Fatal(err)
			}
			if len(artifacts) != 5 {
				t.Fatalf("artifacts = %v", artifacts)
			}
			export := filepath.Join(root, "export with spaces")
			if err := exportArtifacts(artifacts, export); err != nil {
				t.Fatal(err)
			}
			// The export must be self-contained after the temporary build is gone.
			if err := os.RemoveAll(build); err != nil {
				t.Fatal(err)
			}
			want := "--flash-mode dio --flash-freq 40m --flash-size 4MB\n" + addr + " Blink.bootloader.bin\n0x8000 Blink.partitions.bin\n0xe000 boot_app0.bin\n0x10000 Blink.bin\n"
			data, err := os.ReadFile(filepath.Join(export, "flash_args"))
			if err != nil || string(data) != want {
				t.Fatalf("manifest = %q, %v; want %q", data, err, want)
			}
			for name, content := range map[string]string{"Blink.bin": "application", "Blink.bootloader.bin": "bootloader elf", "Blink.partitions.bin": "sketch partitions", "boot_app0.bin": "ota selector"} {
				data, err := os.ReadFile(filepath.Join(export, name))
				if err != nil || string(data) != content {
					t.Errorf("%s = %q, %v", name, data, err)
				}
			}
			for _, line := range strings.Split(strings.TrimSpace(want), "\n")[1:] {
				if _, err := os.Stat(filepath.Join(export, strings.Fields(line)[1])); err != nil {
					t.Fatal(err)
				}
			}
		})
	}
}
