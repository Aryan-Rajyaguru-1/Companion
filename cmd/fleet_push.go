package cmd

import (
	"bufio"
	"context"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/companion-ide/companion-cli/internal/boards"
	"github.com/companion-ide/companion-cli/internal/compiler"
	"github.com/companion-ide/companion-cli/internal/config"
	"github.com/companion-ide/companion-cli/internal/fleet"
	"github.com/companion-ide/companion-cli/internal/ota"
	"github.com/spf13/cobra"
)

// ── fleet push ─────────────────────────────────────────────────────

func newFleetPushCmd() *cobra.Command {
	var (
		password    string
		concurrency int
		retries     int
		yes         bool
		noVerify    bool
	)
	cmd := &cobra.Command{
		Use:   "push <image.bin|sketch-dir> [selectors...]",
		Short: "Flash firmware to many registered devices (bounded concurrency)",
		Args:  cobra.MinimumNArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			target := args[0]
			selectors := args[1:]

			cfg, _, err := config.Load(globalFlags.ConfigFile)
			if err != nil {
				return err
			}
			if err := config.EnsureDirs(cfg); err != nil {
				return err
			}
			r, err := fleetRegistry(cfg)
			if err != nil {
				return err
			}

			// Resolve the image first (single compile shared by every device).
			imagePath, err := fleetImage(cfg, target)
			if err != nil {
				return err
			}
			printSuccess(fmt.Sprintf("Image: %s", colorCyan(imagePath)))

			devs := r.Select(selectors)
			if len(devs) == 0 {
				return fmt.Errorf("no registered devices match selectors %v — run 'companion fleet list' and 'companion fleet register <host>'", selectors)
			}

			// ── Identity preflight: verify each target against live mDNS ──
			if !noVerify {
				preflights := fleet.VerifyTargets(r, devs, discoverAdvertisements(cmd.Context()))
				fmt.Println("\nIdentity preflight (mDNS):")
				failed := 0
				for _, p := range preflights {
					mark := "✓"
					if p.State == fleet.PreflightWarn {
						mark = "⚠"
					} else if p.State == fleet.PreflightFail {
						mark = "✗"
						failed++
					}
					fmt.Printf("  %s %-22s %s\n", mark, p.Device.Key(), p.Detail)
				}
				if failed > 0 {
					return fmt.Errorf("identity preflight failed for %d device(s) — fix the registry or re-run with --no-verify only if you are certain", failed)
				}
			}

			// ── Mandatory confirmation showing the exact target list ──
			fmt.Println("\nTarget devices to flash:")
			for _, d := range devs {
				fmt.Printf("  %-22s %-16s %-7s %s\n", d.Key(), d.Host, d.MCU, strings.Join(d.Tags, ","))
			}
			fmt.Printf("\n  %d device(s), concurrency=%d, retries=%d\n",
				len(devs), concurrency, retries)
			if !yes {
				if !confirm(`Type "yes" to flash ALL of the above, or anything else to abort: `) {
					fmt.Println("Aborted — nothing was flashed.")
					return nil
				}
			}

			push := func(ctx context.Context, d fleet.Device) error {
				return ota.Push(ctx, ota.Options{
					ImagePath:  imagePath,
					DeviceIP:   d.Host,
					DevicePort: d.Port,
					Password:   password,
					OnMessage:  func(msg string) { fmt.Printf("    %s\n", msg) },
				})
			}

			printInfo("Fleet push started (bounded concurrency)…")
			res := fleet.RunBatch(cmd.Context(), fleet.BatchOptions{
				Devices:     devs,
				Push:        push,
				Concurrency: concurrency,
				Retries:     retries,
			})

			fmt.Println("\n── Fleet result table ──")
			for _, row := range res.Summary {
				fmt.Println("  " + row)
			}
			if res.Failed > 0 {
				printError(fmt.Sprintf("Fleet push finished: %d ok, %d failed", res.OK, res.Failed))
				return fmt.Errorf("fleet push had %d failure(s)", res.Failed)
			}
			printSuccess(fmt.Sprintf("Fleet push complete — %d/%d devices flashed", res.OK, res.Total))
			return nil
		},
	}
	cmd.Flags().StringVar(&password, "ota-password", "", "OTA password (or sha256:… pre-hash)")
	cmd.Flags().IntVar(&concurrency, "workers", 4, "bounded worker concurrency")
	cmd.Flags().IntVar(&retries, "retries", 1, "automatic retries per failing device")
	cmd.Flags().BoolVarP(&yes, "yes", "y", false, "skip the confirmation prompt")
	cmd.Flags().BoolVar(&noVerify, "no-verify", false, "skip the mDNS identity preflight")
	return cmd
}

// discoverAdvertisements runs an mDNS scan and returns host → advertised name.
func discoverAdvertisements(ctx context.Context) map[string]string {
	m := map[string]string{}
	for _, d := range ota.Discover(ctx, 3*time.Second) {
		m[d.Host] = d.Name
	}
	return m
}

// fleetImage compiles a sketch dir (once for the whole batch) or
// validates a .bin/.hex path.
func fleetImage(cfg *config.Config, target string) (string, error) {
	ext := strings.ToLower(filepath.Ext(target))
	if ext == ".bin" || ext == ".hex" {
		if _, err := os.Stat(target); err != nil {
			return "", fmt.Errorf("image not found: %w", err)
		}
		return target, nil
	}
	sketchDir, err := filepath.Abs(target)
	if err != nil {
		return "", err
	}
	rp, err := applyProfile(cfg, sketchDir, "")
	if err != nil {
		return "", err
	}
	fqbn := ""
	if rp != nil {
		fqbn = rp.FQBN
	}
	if fqbn == "" {
		fqbn = readSketchFQBN(sketchDir)
	}
	if fqbn == "" {
		return "", fmt.Errorf("no board configured for %s — set fqbn in sketch.yaml or pass a .bin", sketchDir)
	}
	bm := boards.NewManager(cfg)
	cmp := compiler.New(cfg, bm, func(s string) { fmt.Println(s) })
	printInfo(fmt.Sprintf("Compiling %s for %s (shared by all targets)…",
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
		return "", fmt.Errorf("compile failed: %w", err)
	}
	return result.BinaryPath, nil
}

// confirm prompts until the user types an exact word.
func confirm(prompt string) bool {
	fmt.Print(prompt)
	rd := bufio.NewReader(os.Stdin)
	line, _ := rd.ReadString('\n')
	return strings.TrimSpace(line) == "yes"
}
