package cmd

import (
	"bufio"
	"context"
	"encoding/json"
	"fmt"
	"io"
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
		password      string
		passwordStdin bool
		concurrency   int
		retries       int
		yes           bool
		skipIfVersion string
		canary        int
		markVersion   string
		dryRun        bool
		jsonOut       bool
		estSeconds    int
		noVerify      bool
		// Remote-OTA (relay hub) transport. Empty hubURL = LAN ArduinoOTA.
		relayHub   string
		relayToken string
	)
	cmd := &cobra.Command{
		Use:   "push <image.bin|sketch-dir> [selectors...]",
		Short: "Flash firmware to many registered devices (bounded concurrency)",
		Args:  cobra.MinimumNArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			// In --json mode stdout carries the JSON document and nothing
			// else, so the whole command's human output (including the
			// helpers that print straight to os.Stdout) is redirected to
			// stderr for the duration. Patching each call site would miss one
			// eventually; swapping the stream cannot.
			jsonw := os.Stdout
			if jsonOut {
				orig := os.Stdout
				os.Stdout = os.Stderr
				defer func() { os.Stdout = orig }()
			}
			target := args[0]
			selectors := args[1:]

			password, err := resolveOTAPassword(cmd, password, "", passwordStdin)
			if err != nil {
				return err
			}

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

			// Build the plan first: a dry run must work with every board
			// offline, and the filters (skip-if-version, canary) have to be
			// applied before anything contacts a device.
			plan := fleet.BuildPlan(r, fleet.PlanOptions{
				Selectors:         selectors,
				SkipIfVersion:     skipIfVersion,
				Canary:            canary,
				Workers:           concurrency,
				EstPushSeconds:    estSeconds,
				ImageBytes:        imageBytes(imagePath),
				DeployVer:         markVersion,
				DeployVerDeclared: markVersion != "",
			})
			devs := plan.Targets
			if len(devs) == 0 {
				if len(plan.Skipped) > 0 {
					fmt.Println()
					fmt.Println(plan.Report())
					printInfo("Nothing to do: every selected device is already current or held back.")
					return nil
				}
				return fmt.Errorf("no registered devices match selectors %v — run 'companion fleet list' and 'companion fleet register <host>'", selectors)
			}
			if dryRun {
				// --json means stdout is JSON and nothing else; the human
				// report goes to stderr so a pipeline can parse the plan.
				if jsonOut {
					if err := emitPlanJSON(jsonw, plan); err != nil {
						return err
					}
					fmt.Fprintln(os.Stderr, plan.Report())
					printStderr("--dry-run: nothing was flashed.")
					return nil
				}
				fmt.Println()
				fmt.Println(plan.Report())
				printInfo("--dry-run: nothing was flashed.")
				return nil
			}

			// Remote push needs a per-device secret for every target; fail
			// before confirmation (not mid-batch) when one is missing.
			if relayHub != "" {
				missing := []string{}
				for _, d := range devs {
					if d.Secret == "" {
						missing = append(missing, d.Key())
					}
				}
				if len(missing) > 0 {
					return fmt.Errorf("remote push needs a stored device secret for: %s — re-register with 'companion fleet register --secret' after copying it from the board's serial output", strings.Join(missing, ", "))
				}
				if relayToken == "" {
					relayToken = os.Getenv("COMPANION_RELAY_AGENTS_TOKEN")
				}
				if relayToken == "" {
					return fmt.Errorf("remote push needs an agent token: --relay-token or COMPANION_RELAY_AGENTS_TOKEN")
				}
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

			// ── The plan: who gets flashed, who is held back, and why ──
			// Everything below runs off this one object, so --dry-run shows
			// exactly what the real run would do — including the skips, which
			// used to be invisible.
			// Human output goes to os.Stdout, which IS stderr while --json has
			// swapped the stream; jsonw is the real stdout reserved for JSON.
			fmt.Fprint(os.Stdout, plan.Report())
			// The preflight already proved the target list, so the plan must
			// not shrink underneath it unnoticed.
			if plan.Waves > 1 && !yes {
				if !confirm(fmt.Sprintf(
					`Type "yes" to flash %d device(s) in %d wave(s) (~%s), or anything else to abort: `,
					len(plan.Targets), plan.Waves, humanSeconds(plan.EstSeconds))) {
					fmt.Println("Aborted — nothing was flashed.")
					return nil
				}
			} else if !yes {
				if !confirm(`Type "yes" to flash the above, or anything else to abort: `) {
					fmt.Println("Aborted — nothing was flashed.")
					return nil
				}
			}

			// The relay path reports what each board is running and where it
			// lives; the LAN path cannot (ArduinoOTA exposes neither), so it
			// keeps the plain PushFunc.
			push := func(ctx context.Context, d fleet.Device) error {
				if relayHub != "" {
					return RelayPushFunc(relayHub, relayToken, imagePath)(ctx, d)
				}
				return ota.Push(ctx, ota.Options{
					ImagePath:  imagePath,
					DeviceIP:   d.Host,
					DevicePort: d.Port,
					Password:   password,
					OnMessage:  func(msg string) { fmt.Fprintf(os.Stdout, "    %s\n", msg) },
				})
			}
			pushInfo := func(ctx context.Context, d fleet.Device) (string, string, error) {
				if relayHub == "" {
					return "", "", push(ctx, d)
				}
				return relayPushOne(ctx, relayHub, relayToken, d, imagePath, nil)
			}

			printInfo("Fleet push started (bounded concurrency)…")
			mode := "LAN ArduinoOTA"
			if relayHub != "" {
				mode = "remote relay (" + relayHub + ")"
			}
			printInfo("Transport: " + mode)
			res := fleet.RunBatch(cmd.Context(), fleet.BatchOptions{
				Devices:      devs,
				Push:         push,
				PushWithInfo: pushInfo,
				Concurrency:  concurrency,
				Retries:      retries,
			})
			recordResults(r, res, markVersion)

			resOut := os.Stdout
			fmt.Fprintln(resOut, "\n── Fleet result table ──")
			for _, row := range res.Summary {
				fmt.Fprintln(resOut, "  "+row)
			}
			if jsonOut {
				if err := emitResultJSON(jsonw, res, plan); err != nil {
					return err
				}
			}
			if res.Failed > 0 {
				printError(fmt.Sprintf("Fleet push finished: %d ok, %d failed", res.OK, res.Failed))
				return fmt.Errorf("fleet push had %d failure(s)", res.Failed)
			}
			printSuccess(fmt.Sprintf("Fleet push complete — %d/%d devices flashed", res.OK, res.Total))
			return nil
		},
	}
	cmd.Flags().StringVar(&password, "ota-password", "", otaPasswordHelp)
	cmd.Flags().BoolVar(&passwordStdin, "ota-password-stdin", false,
		"read the OTA password from stdin (avoids ps/shell-history exposure)")
	cmd.Flags().IntVar(&concurrency, "workers", 4, "bounded worker concurrency")
	cmd.Flags().StringVar(&skipIfVersion, "skip-if-version", "",
		"skip devices already reporting this firmware version (makes a rollout re-runnable)")
	cmd.Flags().IntVar(&canary, "canary", 0,
		"flash only the first N selected devices, hold the rest back for a staged rollout")
	cmd.Flags().StringVar(&markVersion, "mark-version", "",
		"record this version on devices after a successful push (the image carries no version metadata)")
	cmd.Flags().BoolVar(&dryRun, "dry-run", false,
		"print the plan — targets, skips and the time estimate — and flash nothing")
	cmd.Flags().BoolVar(&jsonOut, "json", false, "emit the result summary as JSON (for CI/dashboards)")
	cmd.Flags().IntVar(&estSeconds, "est-push-seconds", 165,
		"assumed seconds per push, used for the time estimate (a 1.2 MB relay push measures ~165s)")
	cmd.Flags().IntVar(&retries, "retries", 1, "automatic retries per failing device")
	cmd.Flags().BoolVarP(&yes, "yes", "y", false, "skip the confirmation prompt")
	cmd.Flags().BoolVar(&noVerify, "no-verify", false, "skip the mDNS identity preflight")
	cmd.Flags().StringVar(&relayHub, "relay-hub", "", "remote OTA via this relay hub (ws:// or wss:// host); empty = LAN ArduinoOTA")
	cmd.Flags().StringVar(&relayToken, "relay-token", "", "relay agent token (prefer COMPANION_RELAY_AGENTS_TOKEN)")
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

// recordResults writes what the batch learned back into the registry: the
// firmware each board is now running, and when it last accepted a push. This
// is what makes --skip-if-version meaningful on the next run, and it is only
// possible because a relay push reports the device's version.
func recordResults(reg *fleet.Registry, res fleet.BatchResults, markVersion string) {
	now := time.Now()
	for _, r := range res.Results {
		if !r.OK {
			continue
		}
		d := r.Device
		// The device-reported version is what it ran BEFORE this push; a
		// declared --mark-version is what it runs after. Prefer the declared
		// one, and keep the reported value when no version was declared.
		switch {
		case markVersion != "":
			d.Version = markVersion
		case r.Version != "":
			d.Version = r.Version
		}
		if r.IP != "" {
			d.Host = r.IP
		}
		d.LastPushAt = now
		d.SeenAt = now
		if err := reg.Upsert(d); err != nil {
			// A registry write failure must not fail the flash that already
			// happened; it only costs us the version record.
			fmt.Fprintf(os.Stderr, "  (could not record %s in the registry: %v)\n", d.Key(), err)
		}
	}
}

// emitPlanJSON prints the plan (not a result) for --dry-run --json.
func emitPlanJSON(w io.Writer, p fleet.Plan) error {
	type dev struct {
		ID      string `json:"id"`
		Host    string `json:"host,omitempty"`
		Version string `json:"version,omitempty"`
	}
	out := struct {
		Targets  []dev  `json:"targets"`
		Skipped  []dev  `json:"skipped"`
		Workers  int    `json:"workers"`
		Waves    int    `json:"waves"`
		EstSecs  int    `json:"estimated_seconds"`
		DeployTo string `json:"deploying_version,omitempty"`
	}{Workers: p.Workers, Waves: p.Waves, EstSecs: p.EstSeconds, DeployTo: p.DeployVer}
	for _, d := range p.Targets {
		out.Targets = append(out.Targets, dev{ID: d.Key(), Host: d.Host, Version: d.Version})
	}
	for _, s := range p.Skipped {
		out.Skipped = append(out.Skipped, dev{ID: s.Device.Key(), Host: s.Device.Host, Version: s.Device.Version})
	}
	b, err := json.MarshalIndent(out, "", "  ")
	if err != nil {
		return err
	}
	fmt.Fprintln(w, string(b))
	return nil
}

func imageBytes(path string) int64 {
	fi, err := os.Stat(path)
	if err != nil {
		return 0
	}
	return fi.Size()
}

func humanSeconds(sec int) string {
	if sec < 60 {
		return fmt.Sprintf("%ds", sec)
	}
	m, s := sec/60, sec%60
	if s == 0 {
		return fmt.Sprintf("%dm", m)
	}
	return fmt.Sprintf("%dm%02ds", m, s)
}

func printStderr(msg string) { fmt.Fprintln(os.Stderr, colorCyan("» ")+msg) }

// emitResultJSON prints the machine-readable outcome of a real push.
func emitResultJSON(w io.Writer, res fleet.BatchResults, plan fleet.Plan) error {
	type dev struct {
		ID       string `json:"id"`
		OK       bool   `json:"ok"`
		Version  string `json:"version,omitempty"`
		IP       string `json:"ip,omitempty"`
		Attempts int    `json:"attempts"`
		Error    string `json:"error,omitempty"`
	}
	out := struct {
		Total   int   `json:"total"`
		OK      int   `json:"ok"`
		Failed  int   `json:"failed"`
		Workers int   `json:"workers"`
		Waves   int   `json:"waves"`
		Skipped int   `json:"skipped"`
		Devices []dev `json:"devices"`
	}{Total: res.Total, OK: res.OK, Failed: res.Failed,
		Workers: plan.Workers, Waves: plan.Waves, Skipped: len(plan.Skipped)}
	for _, r := range res.Results {
		out.Devices = append(out.Devices, dev{
			ID: r.Device.Key(), OK: r.OK, Version: r.Version, IP: r.IP,
			Attempts: r.Attempts, Error: r.Error,
		})
	}
	b, err := json.MarshalIndent(out, "", "  ")
	if err != nil {
		return err
	}
	fmt.Fprintln(w, string(b))
	return nil
}
