package cmd

import (
	"fmt"
	"net"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/companion-ide/companion-cli/internal/boards"
	"github.com/companion-ide/companion-cli/internal/compiler"
	"github.com/companion-ide/companion-cli/internal/config"
	"github.com/companion-ide/companion-cli/internal/fleet"
	"github.com/companion-ide/companion-cli/internal/ota"
	"github.com/companion-ide/companion-cli/internal/sketch"
	"github.com/spf13/cobra"
)

// ── OTA command — Phase 4c differentiator ────────────────────────
//
// Flash firmware over WiFi with zero USB cable using the standard ArduinoOTA
// protocol (clean-room implementation in internal/ota), plus the device-side
// switch persisted per-sketch in sketch.yaml.

func newOTACommand() *cobra.Command {
	cmd := &cobra.Command{
		Use:   "ota",
		Short: "Over-the-air (WiFi) upload and device OTA switch",
		Long: `Push firmware over WiFi to any device running the ArduinoOTA library,
and manage the device-side OTA switch persisted in the sketch profile.

  companion ota discover                    — mDNS scan for OTA devices
  companion ota upload <ip> [sketch|bin]    — flash over WiFi (compiles first if needed)
  companion ota enable  [sketch-dir]        — record OTA on in sketch.yaml
  companion ota disable [sketch-dir]        — record OTA off in sketch.yaml`,
	}
	cmd.AddCommand(
		newOTAUploadCmd(),
		newOTAEnableCmd(),
		newOTADisableCmd(),
		newOTAStatusCmd(),
		newOTADiscoverCmd(),
	)
	return cmd
}

// ── ota upload ───────────────────────────────────────────────────

func newOTAUploadCmd() *cobra.Command {
	var password string
	var passwordStdin bool
	var port int
	// Transport toggle — same contract as `upload --ota-mode`: "local" (LAN
	// ArduinoOTA) or "remote" (relay hub over the internet). This is the
	// controller-side switch the user picks; the device firmware and the
	// data-phase engine are identical either way.
	var (
		otaMode     string
		relayHub    string
		relayDevice string
		relaySecret string
		relayToken  string
	)
	cmd := &cobra.Command{
		Use:   "upload <device-ip|device-id> [sketch-dir-or-binary]",
		Short: "Flash firmware over WiFi via the ArduinoOTA protocol",
		Long: `Flash firmware over WiFi using the ArduinoOTA protocol.

Two transports, chosen with --ota-mode (same flag as 'companion upload'):
  local   — LAN ArduinoOTA: this host invites the device over UDP and the
            device dials back to this machine. The positional argument is
            the device's IP address or mDNS hostname.
  remote  — remote OTA: the image is relayed through the Companion relay hub
            to a device that may be anywhere on the internet. The positional
            argument is the device id (e.g. esp32-relaytest-01) and
            --relay-hub + --relay-token (+ --relay-device-secret) are needed.

Both transports speak the same data-phase protocol, so the device firmware
shares one Update state machine.`,
		Args: cobra.RangeArgs(1, 2),
		RunE: func(cmd *cobra.Command, args []string) error {
			deviceIP := args[0]
			target := "."
			if len(args) > 1 {
				target = args[1]
			}

			password, err := resolveOTAPassword(cmd, password, "", passwordStdin)
			if err != nil {
				return err
			}

			cfg, _, err := config.Load(globalFlags.ConfigFile)
			if err != nil {
				return fmt.Errorf("config: %w", err)
			}

			imagePath := target
			if !isBinFile(target) {
				// Treat as a sketch directory: resolve board + profile, compile.
				sketchDir, err := filepath.Abs(target)
				if err != nil {
					return err
				}
				rp, err := applyProfile(cfg, sketchDir, "")
				if err != nil {
					return err
				}
				fqbn := rp.FQBN
				if fqbn == "" {
					fqbn = readSketchFQBN(sketchDir)
				}
				if fqbn == "" {
					return fmt.Errorf("no board configured for %s — set fqbn in sketch.yaml or pass a .bin", sketchDir)
				}
				if err := config.EnsureDirs(cfg); err != nil {
					return err
				}
				bm := boards.NewManager(cfg)
				cmp := compiler.New(cfg, bm, func(s string) { fmt.Println(s) })
				printInfo(fmt.Sprintf("Compiling %s for %s (OTA)",
					colorBold(filepath.Base(sketchDir)), colorTeal(fqbn)))
				result, err := cmp.Build(compiler.Options{
					SketchDir:    sketchDir,
					FQBN:         fqbn,
					Warnings:     cfg.Compiler.Warnings,
					Verbose:      globalFlags.Verbose || cfg.Compiler.Verbose,
					ExportBinary: true,
					LibraryDirs:  profileLibDirs(rp),
				})
				if err != nil {
					printError("Compilation failed — OTA aborted")
					return err
				}
				imagePath = result.BinaryPath
				printSuccess(fmt.Sprintf("Compiled → %s", colorCyan(filepath.Base(imagePath))))
			}

			// mDNS refinement only helps when the user passed a hostname
			// instead of a raw IP; raw IPs skip the wait entirely.
			host := deviceIP
			if net.ParseIP(host) == nil {
				for _, d := range ota.Discover(cmd.Context(), 2*time.Second) {
					if strings.EqualFold(d.Name, host) || strings.HasPrefix(d.Name, host+".") {
						host = d.Host
						break
					}
				}
			}

			// ── Controller-side transport switch ────────────────────
			// Same contract as `upload --ota-mode`: the user chooses the
			// transport here; the device firmware and the shared data-phase
			// engine (ota.PushStream) are identical for both.
			mode := otaMode
			if !cmd.Flags().Changed("ota-mode") && cfg.Upload.OTAMode != "" {
				mode = cfg.Upload.OTAMode
			}
			if mode == "" {
				// A non-IP positional (a device id) plus relay flags means
				// remote; otherwise this command keeps its LAN default.
				if relayHub != "" || relayDevice != "" {
					mode = "remote"
				} else {
					mode = "local"
				}
			}
			if mode != "remote" && mode != "local" {
				return fmt.Errorf("invalid --ota-mode %q: want \"remote\" or \"local\"", mode)
			}

			if mode == "remote" {
				if relayDevice == "" {
					relayDevice = deviceIP // positional arg is the device id
				}
				if relaySecret == "" {
					relaySecret = os.Getenv("COMPANION_RELAY_DEVICE_SECRET")
				}
				if relayToken == "" {
					relayToken = os.Getenv("COMPANION_RELAY_AGENTS_TOKEN")
				}
				if relayHub == "" {
					return fmt.Errorf("remote OTA needs --relay-hub wss://host (or use --ota-mode local for LAN ArduinoOTA)")
				}
				if relayToken == "" {
					return fmt.Errorf("remote OTA needs an agent token: --relay-token or COMPANION_RELAY_AGENTS_TOKEN")
				}
				printInfo(fmt.Sprintf("Remote OTA → %s via %s", colorBold(relayDevice), colorTeal(relayHub)))
				start := time.Now()
				last := time.Now()
				dev := fleet.Device{ID: relayDevice, Name: relayDevice, Secret: relaySecret}
				err := relayPushOne(cmd.Context(), relayHub, relayToken, dev, imagePath, &ota.StreamOptions{
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
					printError(fmt.Sprintf("Remote OTA failed after %s: %s",
						time.Since(start).Round(time.Second), err.Error()))
					return err
				}
				printSuccess(fmt.Sprintf("Remote OTA complete in %s — device is rebooting",
					time.Since(start).Round(time.Second)))
				return nil
			}

			printInfo(fmt.Sprintf("OTA push → %s", colorBold(host)))
			start := time.Now()
			lastPct := -1
			err = ota.Push(cmd.Context(), ota.Options{
				DeviceIP:   host,
				DevicePort: port,
				Password:   password,
				ImagePath:  imagePath,
				OnProgress: func(sent, total int64) {
					pct := int(sent * 100 / total)
					if pct/10 != lastPct/10 {
						lastPct = pct
						fmt.Printf("\r  %3d%% (%d / %d bytes)", pct, sent, total)
					}
				},
				OnMessage: func(s string) { fmt.Println(s) },
			})
			if err != nil {
				printError(fmt.Sprintf("OTA failed after %s", time.Since(start).Round(time.Second)))
				return err
			}
			fmt.Println()
			printSuccess(fmt.Sprintf("OTA complete in %s — device rebooted into new firmware",
				time.Since(start).Round(time.Millisecond)))
			if password == "" {
				printWarn("no OTA password was used — anyone on this network could do the same; " +
					"set OTA_PASSWORD on the device and pass --auth / COMPANION_OTA_PASSWORD / --ota-password-stdin")
			}
			return nil
		},
	}
	cmd.Flags().StringVarP(&password, "auth", "a", "",
		otaPasswordHelp)
	cmd.Flags().BoolVar(&passwordStdin, "ota-password-stdin", false,
		"read the OTA password from stdin (avoids ps/shell-history exposure)")
	cmd.Flags().IntVarP(&port, "port", "p", 3232, "Device OTA port")
	cmd.Flags().StringVar(&otaMode, "ota-mode", "",
		"OTA transport: local (LAN ArduinoOTA) | remote (relay hub); config upload.ota_mode also read")
	cmd.Flags().StringVar(&relayHub, "relay-hub", "",
		"Relay hub base URL for remote OTA (ws:// or wss:// host)")
	cmd.Flags().StringVar(&relayDevice, "relay-device", "",
		"Target device id for remote OTA (defaults to the positional device id)")
	cmd.Flags().StringVar(&relaySecret, "relay-device-secret", "",
		"That device's provisioning secret (prefer COMPANION_RELAY_DEVICE_SECRET)")
	cmd.Flags().StringVar(&relayToken, "relay-token", "",
		"Relay agent token (prefer COMPANION_RELAY_AGENTS_TOKEN)")
	return cmd
}

const otaPasswordHelp = "OTA password (prefer COMPANION_OTA_PASSWORD env or --ota-password-stdin: " +
	"a flag value is visible in ps output and shell history; " +
	"device must call ArduinoOTA.setPassword with the same secret; " +
	"prefix \"sha256:\" for a pre-hashed value)"

// ── ota enable / disable ─────────────────────────────────────────

func newOTAEnableCmd() *cobra.Command {
	return &cobra.Command{
		Use:   "enable [sketch-dir]",
		Short: "Record OTA on for the sketch's default profile (sketch.yaml)",
		Args:  cobra.MaximumNArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			return otaToggle(args, true)
		},
	}
}

func newOTADisableCmd() *cobra.Command {
	return &cobra.Command{
		Use:   "disable [sketch-dir]",
		Short: "Record OTA off for the sketch's default profile (sketch.yaml)",
		Args:  cobra.MaximumNArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			return otaToggle(args, false)
		},
	}
}

// otaToggle flips sketch.ota in the sketch's default profile and saves it.
func otaToggle(args []string, enabled bool) error {
	dir := "."
	if len(args) > 0 {
		dir = args[0]
	}
	sf, err := sketch.Load(dir)
	if err != nil {
		return err
	}
	name := sf.DefaultProfile
	if name == "" {
		name = soleProfileName(sf.Profiles) // the single profile when unambiguous
	}
	if name == "" && len(sf.Profiles) == 0 {
		// No profiles at all — create one holding just the OTA flag.
		name = "default"
		sf.Profiles = map[string]sketch.Profile{name: {}}
	}
	if name == "" {
		return fmt.Errorf("sketch.yaml has multiple profiles — set default_profile first (companion profile set-default)")
	}
	p := sf.Profiles[name]
	p.OTA = enabled
	sf.Profiles[name] = p
	sf.DefaultProfile = name
	if err := sf.SaveTo(dir); err != nil {
		return err
	}
	if enabled {
		printSuccess(fmt.Sprintf("OTA enabled for profile %s (sketch.yaml)", colorBold(name)))
	} else {
		printSuccess(fmt.Sprintf("OTA disabled for profile %s (sketch.yaml)", colorBold(name)))
	}
	return nil
}

// ── ota status ───────────────────────────────────────────────────

func newOTAStatusCmd() *cobra.Command {
	return &cobra.Command{
		Use:   "status [sketch-dir]",
		Short: "Show whether OTA is enabled for the sketch's default profile",
		Args:  cobra.MaximumNArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			dir := "."
			if len(args) > 0 {
				dir = args[0]
			}
			sf, err := sketch.Load(dir)
			if err != nil {
				return err
			}
			name := sf.DefaultProfile
			if name == "" {
				name = soleProfileName(sf.Profiles)
			}
			if name == "" {
				fmt.Println("ota: disabled (no profile configured)")
				return nil
			}
			if sf.Profiles[name].OTA {
				printSuccess(fmt.Sprintf("OTA enabled for profile %s", colorBold(name)))
			} else {
				fmt.Printf("ota: disabled for profile %s\n", name)
			}
			return nil
		},
	}
}

// ── ota discover ─────────────────────────────────────────────────

func newOTADiscoverCmd() *cobra.Command {
	var wait time.Duration
	cmd := &cobra.Command{
		Use:   "discover",
		Short: "Scan the network (mDNS) for ArduinoOTA devices",
		Args:  cobra.NoArgs,
		RunE: func(cmd *cobra.Command, args []string) error {
			devs := ota.Discover(cmd.Context(), wait)
			if len(devs) == 0 {
				printInfo("No OTA devices found — is the device on the same network with ArduinoOTA.begin() called?")
				return nil
			}
			for _, d := range devs {
				fmt.Printf("  %-16s %-28s port %d\n", d.Host, d.Name, d.Port)
			}
			printSuccess(fmt.Sprintf("%d OTA device(s) found", len(devs)))
			return nil
		},
	}
	cmd.Flags().DurationVar(&wait, "wait", 3*time.Second, "mDNS listen window")
	return cmd
}

// ── shared helpers ───────────────────────────────────────────────

func isBinFile(path string) bool {
	e := strings.ToLower(filepath.Ext(path))
	return e == ".bin" || e == ".hex"
}

// soleProfileName returns the single key of a one-entry profile map, or "".
func soleProfileName(m map[string]sketch.Profile) string {
	if len(m) == 1 {
		for k := range m {
			return k
		}
	}
	return ""
}
