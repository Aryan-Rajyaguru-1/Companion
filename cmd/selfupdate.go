package cmd

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"github.com/companion-ide/companion-cli/internal/selfupdate"
	"github.com/spf13/cobra"
)

// selfUpdateOptions are shared by `companion --update` and
// `companion self-update`. The root flag is an intentional convenience: it is
// the form users remember, while the subcommand is discoverable in help.
type selfUpdateOptions struct {
	Check  bool
	JSON   bool
	Target string
	Force  bool
}

var (
	rootUpdateFlag bool
	rootUpdateOpts selfUpdateOptions
)

func newSelfUpdateCmd() *cobra.Command {
	opts := selfUpdateOptions{}
	cmd := &cobra.Command{
		Use:     "self-update",
		Aliases: []string{"selfupdate"},
		Short:   "Update the Companion CLI from the latest GitHub release",
		Long: `Check the project's GitHub releases and install the newest CLI binary
for this operating system and architecture.

The download is verified against the release's SHA256SUMS.txt and replaced
atomically. If the CLI is bundled inside an IDE installation, use --target to
install to a writable location instead of the read-only app bundle.`,
		RunE: func(cmd *cobra.Command, args []string) error {
			return runSelfUpdate(cmd, opts)
		},
	}
	bindSelfUpdateFlags(cmd, &opts)
	return cmd
}

func bindSelfUpdateFlags(cmd *cobra.Command, opts *selfUpdateOptions) {
	cmd.Flags().BoolVar(&opts.Check, "check", false, "Check for a newer release without installing it")
	cmd.Flags().BoolVar(&opts.JSON, "json", false, "Print a machine-readable JSON result")
	cmd.Flags().StringVar(&opts.Target, "target", "", "Install to this path instead of the running executable")
	cmd.Flags().BoolVar(&opts.Force, "force", false, "Install the selected release even when already current")
}

func runSelfUpdate(cmd *cobra.Command, opts selfUpdateOptions) error {
	updater, err := selfupdate.New(selfupdate.Options{CurrentVersion: CLIVersion})
	if err != nil {
		writeSelfUpdateError(opts.JSON, CLIVersion, err)
		return err
	}

	ctx := cmd.Context()
	if ctx == nil {
		ctx = context.Background()
	}
	result, err := updater.Check(ctx)
	if err != nil {
		writeSelfUpdateError(opts.JSON, CLIVersion, err)
		return err
	}

	if opts.Check {
		writeCheckResult(opts.JSON, result)
		return nil
	}

	if !result.UpdateAvailable && !opts.Force {
		writeCheckResult(opts.JSON, result)
		return nil
	}

	target, err := installTarget(opts.Target)
	if err != nil {
		writeUpdateError(opts.JSON, result, err)
		return err
	}

	if !opts.JSON {
		if result.UpdateAvailable {
			printInfo(fmt.Sprintf("Updating Companion CLI %s → %s…", result.CurrentVersion, result.LatestVersion))
		} else {
			printInfo(fmt.Sprintf("Reinstalling Companion CLI %s…", result.LatestVersion))
		}
		printStep(fmt.Sprintf("Downloading %s from %s", result.AssetName, result.ReleaseURL))
	}

	installed, err := updater.Install(ctx, result, target, opts.Force)
	if err != nil {
		writeUpdateError(opts.JSON, result, err)
		return err
	}
	writeInstallResult(opts.JSON, installed)
	return nil
}

// installTarget chooses the path to replace. The caller may explicitly select
// a path (the IDE does this so it never tries to write into its app bundle).
func installTarget(explicit string) (string, error) {
	if strings.TrimSpace(explicit) != "" {
		target, err := expandHome(explicit)
		if err != nil {
			return "", err
		}
		if !filepath.IsAbs(target) {
			target, err = filepath.Abs(target)
			if err != nil {
				return "", fmt.Errorf("resolving --target %q: %w", explicit, err)
			}
		}
		return target, nil
	}

	exe, err := os.Executable()
	if err != nil {
		return "", fmt.Errorf("locating the running companion executable: %w", err)
	}
	if resolved, err := filepath.EvalSymlinks(exe); err == nil {
		exe = resolved
	}
	exe, err = filepath.Abs(exe)
	if err != nil {
		return "", fmt.Errorf("resolving the running companion executable: %w", err)
	}
	return exe, nil
}

func expandHome(p string) (string, error) {
	p = strings.TrimSpace(p)
	if p == "~" || strings.HasPrefix(p, "~/") || strings.HasPrefix(p, `~\`) {
		home, err := os.UserHomeDir()
		if err != nil {
			return "", fmt.Errorf("resolving home directory: %w", err)
		}
		if p == "~" {
			return home, nil
		}
		return filepath.Join(home, p[2:]), nil
	}
	return p, nil
}

func writeCheckResult(asJSON bool, result *selfupdate.CheckResult) {
	if asJSON {
		writeJSON(result)
		return
	}
	if !result.UpdateAvailable {
		if compare := selfupdate.CompareVersions(result.CurrentVersion, result.LatestVersion); compare > 0 {
			printSuccess(fmt.Sprintf("Companion CLI %s is newer than the latest release %s", result.CurrentVersion, result.LatestVersion))
		} else {
			printSuccess(fmt.Sprintf("Companion CLI is up to date (%s)", result.LatestVersion))
		}
		if result.ReleaseURL != "" {
			printStep("Release: " + result.ReleaseURL)
		}
		return
	}

	fmt.Printf("\n%s\n", colorBold("Companion CLI update available"))
	printStep(fmt.Sprintf("Current: %s", result.CurrentVersion))
	printStep(fmt.Sprintf("Latest:  %s", result.LatestVersion))
	if result.ReleaseName != "" && result.ReleaseName != result.LatestVersion {
		printStep("Release: " + result.ReleaseName)
	}
	if result.ReleaseURL != "" {
		printStep("Notes:   " + result.ReleaseURL)
	}
	if result.AssetName != "" {
		size := ""
		if result.AssetSize > 0 {
			size = fmt.Sprintf(" (%s)", humanBytes(result.AssetSize))
		}
		printStep("Asset:   " + result.AssetName + size)
	}
	printStep("Install: companion --update")
	fmt.Println()
}

func writeInstallResult(asJSON bool, result *selfupdate.InstallResult) {
	if asJSON {
		writeJSON(result)
		return
	}
	if !result.Updated {
		writeCheckResult(false, &result.CheckResult)
		return
	}
	printSuccess(fmt.Sprintf("Updated Companion CLI to %s", result.LatestVersion))
	printStep("Installed: " + result.InstallPath)
	printStep("SHA-256 verified against " + selfupdate.ChecksumsAssetName)
	if result.RestartRequired {
		printWarn("Restart the IDE (or the terminal that launched the CLI) to use the new binary")
	}
}

func writeUpdateError(asJSON bool, result *selfupdate.CheckResult, err error) {
	if asJSON {
		out := struct {
			selfupdate.CheckResult
			Error string `json:"error"`
		}{CheckResult: *result, Error: err.Error()}
		writeJSON(out)
	}
}

func writeSelfUpdateError(asJSON bool, current string, err error) {
	if asJSON {
		writeJSON(struct {
			CurrentVersion string `json:"current_version"`
			Error          string `json:"error"`
		}{CurrentVersion: current, Error: err.Error()})
	}
}

func writeJSON(v interface{}) {
	enc := json.NewEncoder(os.Stdout)
	enc.SetEscapeHTML(false)
	_ = enc.Encode(v)
}

func humanBytes(n int64) string {
	const (
		kib = 1024
		mib = 1024 * kib
	)
	switch {
	case n >= mib:
		return fmt.Sprintf("%.1f MiB", float64(n)/mib)
	case n >= kib:
		return fmt.Sprintf("%.1f KiB", float64(n)/kib)
	default:
		return fmt.Sprintf("%d B", n)
	}
}
