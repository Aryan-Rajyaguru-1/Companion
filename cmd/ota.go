package cmd

import (
	"fmt"
	"net"
	"path/filepath"
	"strings"
	"time"

	"github.com/companion-ide/companion-cli/internal/boards"
	"github.com/companion-ide/companion-cli/internal/compiler"
	"github.com/companion-ide/companion-cli/internal/config"
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
	var port int
	cmd := &cobra.Command{
		Use:   "upload <device-ip> [sketch-dir-or-binary]",
		Short: "Flash firmware over WiFi via the ArduinoOTA protocol",
		Args:  cobra.RangeArgs(1, 2),
		RunE: func(cmd *cobra.Command, args []string) error {
			deviceIP := args[0]
			target := "."
			if len(args) > 1 {
				target = args[1]
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
			return nil
		},
	}
	cmd.Flags().StringVarP(&password, "auth", "a", "",
		"OTA password (device must call ArduinoOTA.setPassword with the same secret; prefix \"sha256:\" for a pre-hashed value)")
	cmd.Flags().IntVarP(&port, "port", "p", 3232, "Device OTA port")
	return cmd
}

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
