package cmd

import (
	"fmt"
	"os"
	"path/filepath"
	"time"

	"github.com/companion-ide/companion-cli/internal/boards"
	"github.com/companion-ide/companion-cli/internal/compiler"
	"github.com/companion-ide/companion-cli/internal/config"
	fqbnpkg "github.com/companion-ide/companion-cli/internal/fqbn"
	"github.com/companion-ide/companion-cli/internal/ota"
	"github.com/companion-ide/companion-cli/internal/plugins"
	"github.com/companion-ide/companion-cli/internal/uploader"
	"github.com/spf13/cobra"
)

func newUploadCmd() *cobra.Command {
	var (
		fqbn       string
		mcu        string
		host       string
		port       int
		baud       uint32
		binaryPath string
		noVerify   bool
		warnings   string
		profileNam string
		serialPort string
		otaFlag    bool
		otaPass    string
	)
	var rpProfileWantsOTA bool

	cmd := &cobra.Command{
		Use:   "upload [sketch-dir]",
		Short: "Compile and upload a sketch wirelessly via ESP32 bridge",
		Long: `Compile the sketch, then upload it to the target device wirelessly
through the Companion ESP32 bridge over WiFi.

The bridge must be reachable at the specified host:port.
By default the ESP32 bridge runs in AP mode at 192.168.4.1:3333.

If --binary is provided, compilation is skipped and the binary is
uploaded directly.

MCU families supported:
  esp32    — ESP32 / ESP32-S3 / ESP32-C3   (uses esptool.py)
  esp8266  — ESP8266 / NodeMCU             (uses esptool.py)
  avr      — Arduino Uno / Mega / Nano     (uses avrdude)
  stm32    — STM32 UART bootloader         (built-in AN3155)
  generic  — Custom UART bootloader        (raw byte stream)

Examples:
  companion upload --fqbn arduino:avr:uno --mcu avr
  companion upload --fqbn esp32:esp32:esp32 --mcu esp32 --host 192.168.1.42
  companion upload --binary firmware.bin --mcu stm32`,

		Args: cobra.MaximumNArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			cfg, _, err := config.Load(globalFlags.ConfigFile)
			if err != nil {
				return err
			}
			if err := config.EnsureDirs(cfg); err != nil {
				return err
			}

			// ── Profile resolution: contributes board/port/baud/mcu ────
			sketchDir := "."
			if len(args) > 0 {
				sketchDir = args[0]
			}
			if abs, aerr := filepath.Abs(sketchDir); aerr == nil {
				if rp, perr := applyProfile(cfg, abs, profileNam); perr == nil && rp != nil {
					if rp.FQBN != "" && !cmd.Flags().Changed("fqbn") {
						fqbn = rp.FQBN
					}
					if rp.Port != "" && !cmd.Flags().Changed("host") {
						host = rp.Port
					}
					if rp.Baud != 0 && !cmd.Flags().Changed("baud") {
						baud = rp.Baud
					}
					if rp.MCU != "" && !cmd.Flags().Changed("mcu") {
						mcu = rp.MCU
					}
					rpProfileWantsOTA = rp.OTA
				}
			}

			// Apply config defaults for unset flags
			if host == "" {
				host = cfg.Bridge.Host
			}
			if port == 0 {
				port = cfg.Bridge.Port
			}
			if baud == 0 {
				baud = uint32(cfg.Bridge.Baud)
			}
			// MCU family resolution order:
			//   1. explicit --mcu flag (respected as-is)
			//   2. inferred from the FQBN (prevents flashing an ESP32 .bin
			//      with avrdude just because the config default is "avr")
			//   3. config bridge.mcu default
			if !cmd.Flags().Changed("mcu") {
				if f := fqbnpkg.MCUFromFQBN(fqbn); f != "" && f != "generic" {
					mcu = f
				}
			}
			if mcu == "" {
				mcu = cfg.Bridge.MCU
			}
			if warnings == "" {
				warnings = cfg.Compiler.Warnings
			}

			// OTA: explicit flag wins; profile sketch.ota auto-enables.
			useOTA := otaFlag || (rpProfileWantsOTA && !cmd.Flags().Changed("ota"))

			// ── Step 1: Compile if no pre-built binary ──────────
			if binaryPath == "" {
				if fqbn == "" {
					return fmt.Errorf("--fqbn required when uploading from source\n" +
						"Example: companion upload --fqbn arduino:avr:uno --mcu avr")
				}

				sketchDir := "."
				if len(args) > 0 {
					sketchDir = args[0]
				}
				sketchDir, _ = filepath.Abs(sketchDir)

				if !noVerify && !cfg.Upload.AutoVerify {
					noVerify = true
				}

				shouldCompile := !noVerify
				if shouldCompile {
					printInfo(fmt.Sprintf("Compiling %s for %s",
						colorBold(filepath.Base(sketchDir)), colorTeal(fqbn)))

					bm := boards.NewManager(cfg)
					cmp := compiler.New(cfg, bm, func(s string) { fmt.Println(s) })
					cmp.SetPlugins(pluginRegistry(cfg))
					if cfg.Cache.Enabled {
						if bc, err := compiler.NewBuildCache(compiler.DefaultCacheDir(cfg.Directories.Data)); err == nil {
							cmp.SetCache(bc)
							defer bc.Evict()
						}
					}

					result, err := cmp.Build(compiler.Options{
						SketchDir:    sketchDir,
						FQBN:         fqbn,
						Warnings:     warnings,
						Verbose:      globalFlags.Verbose || cfg.Compiler.Verbose,
						ExportBinary: true,
					})
					if err != nil {
						printError("Compilation failed — upload aborted")
						return err
					}
					binaryPath = result.BinaryPath
					printSuccess(fmt.Sprintf("Compiled → %s", colorCyan(filepath.Base(binaryPath))))
				} else {
					// Find pre-exported binary
					binaryPath = findExportedBinary(sketchDir, fqbn)
					if binaryPath == "" {
						return fmt.Errorf("no compiled binary found — run compile first or remove --no-verify")
					}
					printInfo(fmt.Sprintf("Using binary: %s", colorCyan(binaryPath)))
				}
			}

			// ── Step 2: Upload ───────────────────────────────────
			fmt.Println()

			// OTA target resolution: --host / profile port wins; otherwise
			// fall back to mDNS discovery when only the bridge AP default
			// (192.168.4.1) is configured — that address is never an OTA peer.
			if useOTA && (host == "" || host == "192.168.4.1") {
				printInfo("Searching for OTA devices (mDNS)…")
				devs := ota.Discover(cmd.Context(), 3*time.Second)
				switch len(devs) {
				case 0:
					printError("No OTA devices found — pass the device IP with --host")
					return fmt.Errorf("no OTA device discovered")
				case 1:
					host = devs[0].Host
					printInfo(fmt.Sprintf("Found %s at %s", devs[0].Name, devs[0].Host))
				default:
					for _, d := range devs {
						fmt.Printf("  %-16s %s\n", d.Host, d.Name)
					}
					return fmt.Errorf("multiple OTA devices found — pick one with --host <ip>")
				}
			}

			if useOTA {
				// Route through the plugin registry (P5): first-party OTA
				// uploader handles esp32/esp8266; third-party .so plugins can
				// replace it with JTAG/OpenOCD etc.
				upl := pluginRegistry(cfg).UploaderFor(fqbn)
				if upl == nil {
					printInfo(fmt.Sprintf("No OTA-capable plugin for %q — using built-in OTA push", fqbn))
					if err := ota.Probe(host, 3232); err != nil {
						printError(err.Error())
						return fmt.Errorf("OTA probe failed")
					}
					last := time.Now()
					err := ota.Push(cmd.Context(), ota.Options{
						ImagePath:  binaryPath,
						DeviceIP:   host,
						DevicePort: 3232,
						Password:   otaPass,
						OnProgress: func(sent, total int64) {
							if time.Since(last) < 150*time.Millisecond && sent < total {
								return
							}
							last = time.Now()
							fmt.Printf("\r  OTA: %d / %d bytes (%.0f%%)   ",
								sent, total, float64(sent)/float64(total)*100)
						},
						OnMessage: func(s string) { fmt.Printf("  %s\n", s) },
					})
					fmt.Println()
					if err != nil {
						printError("OTA upload failed: " + err.Error())
						return fmt.Errorf("upload failed")
					}
				} else {
					printInfo(fmt.Sprintf("Uploading over the air (%s) → %s",
						upl.Name(), colorBold(host)))
					err := upl.Upload(cmd.Context(), plugins.UploadOptions{
						BinaryPath: binaryPath,
						FQBN:       fqbn,
						MCU:        mcu,
						Host:       host,
						Port:       3232,
						Verbose:    globalFlags.Verbose || cfg.Upload.Verbose,
						ExtraFlags: []string{"ota-password=" + otaPass},
					}, os.Stdout)
					fmt.Println()
					if err != nil {
						printError("OTA upload failed: " + err.Error())
						return fmt.Errorf("upload failed")
					}
				}
				printSuccess("OTA upload complete — device is rebooting")
				return nil
			}

			if serialPort != "" {
				printInfo(fmt.Sprintf("Uploading via USB → %s  [%s]",
					colorBold(serialPort), colorTeal(mcu)))
			} else {
				printInfo(fmt.Sprintf("Uploading wirelessly → %s:%d  [%s]",
					colorBold(host), port, colorTeal(mcu)))
			}

			ul := uploader.New(cfg, func(s string) { fmt.Println(s) })
			if err := ul.Upload(uploader.Options{
				BinaryPath: binaryPath,
				MCU:        mcu,
				Host:       host,
				Port:       port,
				SerialPort: serialPort,
				Baud:       baud,
				FQBN:       fqbn,
				Verbose:    globalFlags.Verbose || cfg.Upload.Verbose,
			}); err != nil {
				printError("Upload failed: " + err.Error())
				return fmt.Errorf("upload failed")
			}

			fmt.Println()
			printSuccess("Upload complete — device is running")
			return nil
		},
	}

	cmd.Flags().StringVar(&fqbn, "fqbn", "",
		"Fully Qualified Board Name (required when uploading from source)")
	cmd.Flags().StringVar(&mcu, "mcu", "",
		"Target MCU family: esp32 | esp8266 | avr | stm32 | generic (default from config)")
	cmd.Flags().StringVar(&host, "host", "",
		"Bridge IP address (default from config: 192.168.4.1)")
	cmd.Flags().IntVar(&port, "port", 0,
		"Bridge TCP port (default from config: 3333)")
	cmd.Flags().Uint32Var(&baud, "baud", 0,
		"UART baud rate for upload (default from config: 115200)")
	cmd.Flags().StringVar(&serialPort, "serial", "",
		"Local serial device for USB upload (e.g. /dev/ttyACM0) — bypasses the WiFi bridge")
	cmd.Flags().StringVar(&binaryPath, "binary", "",
		"Path to pre-compiled binary — skips compilation")
	cmd.Flags().BoolVar(&noVerify, "no-verify", false,
		"Skip compilation, upload previously built binary")
	cmd.Flags().StringVar(&warnings, "warnings", "",
		"Compiler warnings level (only used when compiling)")
	cmd.Flags().StringVar(&profileNam, "profile", "",
		"Upload profile from sketch.yaml (board + bridge target + libraries)")
	cmd.Flags().BoolVar(&otaFlag, "ota", false,
		"Upload over the air via ArduinoOTA (device IP via --host or mDNS discovery)")
	cmd.Flags().StringVar(&otaPass, "ota-password", "",
		"OTA password (prefix \"sha256:\" for a pre-hashed value)")

	return cmd
}

// findExportedBinary searches for a previously exported binary.
func findExportedBinary(sketchDir, fqbn string) string {
	fqbnDir := filepath.Join(sketchDir, "build",
		replaceColons(fqbn))

	entries, err := os.ReadDir(fqbnDir)
	if err != nil {
		return ""
	}

	// Prefer .bin, fall back to .hex
	for _, e := range entries {
		if filepath.Ext(e.Name()) == ".bin" {
			return filepath.Join(fqbnDir, e.Name())
		}
	}
	for _, e := range entries {
		if filepath.Ext(e.Name()) == ".hex" {
			return filepath.Join(fqbnDir, e.Name())
		}
	}
	return ""
}

func replaceColons(s string) string {
	result := make([]byte, len(s))
	for i := 0; i < len(s); i++ {
		if s[i] == ':' {
			result[i] = '.'
		} else {
			result[i] = s[i]
		}
	}
	return string(result)
}
