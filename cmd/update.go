package cmd

import (
	"fmt"

	"github.com/companion-ide/companion-cli/internal/boards"
	"github.com/companion-ide/companion-cli/internal/config"
	"github.com/spf13/cobra"
)

// ── outdated / upgrade ───────────────────────────────────────────
//
// One-stop update workflow: see everything stale, then bring it current.

func newOutdatedCmd() *cobra.Command {
	return &cobra.Command{
		Use:   "outdated",
		Short: "List installed platforms with newer releases available",
		RunE: func(cmd *cobra.Command, args []string) error {
			cfg, _, err := config.Load(globalFlags.ConfigFile)
			if err != nil {
				return err
			}
			config.EnsureDirs(cfg)

			bm := boards.NewManager(cfg)
			updates, err := bm.OutdatedPlatforms()
			if err != nil {
				return fmt.Errorf("checking updates (run `companion board update-index` first): %w", err)
			}
			if len(updates) == 0 {
				printSuccess("All installed platforms are up to date")
				return nil
			}
			fmt.Printf("  %-28s %-12s %s\n", "PLATFORM", "INSTALLED", "AVAILABLE")
			for _, u := range updates {
				fmt.Printf("  %-28s %-12s %s\n",
					colorTeal(u.ID), u.InstalledVer, colorCyan(u.AvailableVer))
			}
			fmt.Printf("\n%d platform(s) can be updated — run: companion upgrade\n", len(updates))
			return nil
		},
	}
}

func newUpgradeCmd() *cobra.Command {
	return &cobra.Command{
		Use:   "upgrade",
		Short: "Upgrade all outdated installed platforms to their latest releases",
		RunE: func(cmd *cobra.Command, args []string) error {
			cfg, _, err := config.Load(globalFlags.ConfigFile)
			if err != nil {
				return err
			}
			config.EnsureDirs(cfg)

			bm := boards.NewManager(cfg)
			updates, err := bm.OutdatedPlatforms()
			if err != nil {
				return fmt.Errorf("checking updates (run `companion board update-index` first): %w", err)
			}
			if len(updates) == 0 {
				printSuccess("Nothing to upgrade — all platforms are current")
				return nil
			}

			var failures int
			for _, u := range updates {
				printInfo(fmt.Sprintf("Upgrading %s %s → %s…",
					colorTeal(u.ID), u.InstalledVer, colorCyan(u.AvailableVer)))
				if err := bm.Install(u.ID, func(s string) { fmt.Println(s) }); err != nil {
					printError(fmt.Sprintf("failed to upgrade %s: %v", u.ID, err))
					failures++
				}
			}

			if failures > 0 {
				return fmt.Errorf("%d platform(s) failed to upgrade", failures)
			}
			printSuccess(fmt.Sprintf("Upgraded %d platform(s)", len(updates)))
			return nil
		},
	}
}
