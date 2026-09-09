package cmd

import (
	"fmt"
	"strings"

	"github.com/companion-ide/companion-cli/internal/config"
	"github.com/companion-ide/companion-cli/internal/libraries"
	"github.com/spf13/cobra"
)

func newLibCmd() *cobra.Command {
	cmd := &cobra.Command{
		Use:     "lib",
		Short:   "Manage Arduino libraries",
		Aliases: []string{"library", "libraries"},
		Long:    "Search, install, and list Arduino libraries from the official registry (9,359 libraries).",
	}

	cmd.AddCommand(
		newLibUpdateIndexCmd(),
		newLibSearchCmd(),
		newLibListCmd(),
		newLibInstallCmd(),
		newLibUninstallCmd(),
	)

	return cmd
}

// ── lib update-index ─────────────────────────────────────────────

func newLibUpdateIndexCmd() *cobra.Command {
	return &cobra.Command{
		Use:   "update-index",
		Short: "Download the latest library index",
		Long:  "Downloads library_index.json from downloads.arduino.cc (9,359 libraries).",
		RunE: func(cmd *cobra.Command, args []string) error {
			cfg, _, err := config.Load(globalFlags.ConfigFile)
			if err != nil {
				return err
			}
			config.EnsureDirs(cfg)

			printInfo("Updating library index…")
			lm := libraries.NewManager(cfg)
			if err := lm.UpdateIndex(func(s string) { fmt.Println("  " + s) }); err != nil {
				return err
			}
			printSuccess("Library index updated")
			return nil
		},
	}
}

// ── lib search ───────────────────────────────────────────────────

func newLibSearchCmd() *cobra.Command {
	var limit int

	cmd := &cobra.Command{
		Use:   "search <query>",
		Short: "Search libraries in the index",
		Long:  "Search the local library index by name, category, or author. Run 'lib update-index' first.",
		Args:  cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			cfg, _, err := config.Load(globalFlags.ConfigFile)
			if err != nil {
				return err
			}

			lm := libraries.NewManager(cfg)
			results, err := lm.Search(args[0])
			if err != nil {
				return err
			}

			if len(results) == 0 {
				printWarn(fmt.Sprintf("No libraries found for %q", args[0]))
				printStep("Update the index: companion lib update-index")
				return nil
			}

			if limit > 0 && len(results) > limit {
				results = results[:limit]
			}

			fmt.Printf("\n%-35s %-10s %-20s %s\n",
				colorBold("Name"), colorBold("Version"), colorBold("Author"), colorBold("Description"))
			fmt.Println(strings.Repeat("─", 100))

			for _, lib := range results {
				name := lib.Name
				if len(name) > 33 {
					name = name[:30] + "…"
				}
				author := lib.Author
				if len(author) > 18 {
					author = author[:15] + "…"
				}
				sentence := lib.Sentence
				if len(sentence) > 40 {
					sentence = sentence[:37] + "…"
				}

				fmt.Printf("%-35s %-10s %-20s %s\n",
					colorTeal(name),
					colorCyan(lib.Version),
					colorDim(author),
					sentence,
				)
			}

			fmt.Printf("\n%d result(s)", len(results))
			if limit > 0 {
				fmt.Printf(" (showing first %d)", limit)
			}
			fmt.Println()
			return nil
		},
	}

	cmd.Flags().IntVar(&limit, "limit", 20, "Maximum results to show")
	return cmd
}

// ── lib list ─────────────────────────────────────────────────────

func newLibListCmd() *cobra.Command {
	return &cobra.Command{
		Use:   "list",
		Short: "List installed libraries",
		RunE: func(cmd *cobra.Command, args []string) error {
			cfg, _, err := config.Load(globalFlags.ConfigFile)
			if err != nil {
				return err
			}

			lm := libraries.NewManager(cfg)
			libs, err := lm.ListInstalled()
			if err != nil {
				return err
			}

			if len(libs) == 0 {
				printWarn("No libraries installed.")
				printStep("Install one: companion lib install NeoPixel")
				return nil
			}

			fmt.Printf("\n%-35s %-10s %s\n",
				colorBold("Name"), colorBold("Version"), colorBold("Description"))
			fmt.Println(strings.Repeat("─", 80))

			for _, lib := range libs {
				name := lib.Name
				if len(name) > 33 {
					name = name[:30] + "…"
				}
				sentence := lib.Sentence
				if len(sentence) > 36 {
					sentence = sentence[:33] + "…"
				}
				fmt.Printf("%-35s %-10s %s\n",
					colorTeal(name), colorCyan(lib.Version), colorDim(sentence))
			}

			fmt.Printf("\n%d librar%s installed\n", len(libs),
				map[bool]string{true: "y", false: "ies"}[len(libs) == 1])
			return nil
		},
	}
}

// ── lib install ──────────────────────────────────────────────────

func newLibInstallCmd() *cobra.Command {
	var version string

	cmd := &cobra.Command{
		Use:   "install <library-name> [<library-name>...]",
		Short: "Install one or more libraries",
		Long: `Install Arduino libraries by name. Names are case-sensitive and
must match the library registry. Installs the latest version by default.

Examples:
  companion lib install NeoPixel
  companion lib install "Adafruit GFX Library"
  companion lib install ArduinoJson --version 6.21.3`,

		Args: cobra.MinimumNArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			cfg, _, err := config.Load(globalFlags.ConfigFile)
			if err != nil {
				return err
			}
			config.EnsureDirs(cfg)

			lm := libraries.NewManager(cfg)

			for _, name := range args {
				// Support the Name@1.2.3 shorthand (same as --version).
				libName, ver := name, version
				if idx := strings.LastIndex(name, "@"); idx > 0 {
					libName = name[:idx]
					if ver == "" {
						ver = name[idx+1:]
					}
				}
				printInfo(fmt.Sprintf("Installing %s…", colorTeal(name)))
				if err := lm.Install(libName, ver, func(s string) {
					fmt.Println("  " + s)
				}); err != nil {
					printError(fmt.Sprintf("Failed to install %s: %v", name, err))
					if len(args) == 1 {
						return fmt.Errorf("install failed")
					}
					continue
				}
				printSuccess(fmt.Sprintf("Installed %s", colorTeal(name)))
			}
			return nil
		},
	}

	cmd.Flags().StringVar(&version, "version", "",
		"Specific version to install (default: latest)")
	return cmd
}

// ── lib uninstall ────────────────────────────────────────────────

func newLibUninstallCmd() *cobra.Command {
	return &cobra.Command{
		Use:     "uninstall <library-name>",
		Short:   "Uninstall a library",
		Aliases: []string{"remove"},
		Args:    cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			cfg, _, err := config.Load(globalFlags.ConfigFile)
			if err != nil {
				return err
			}

			name := args[0]
			printInfo(fmt.Sprintf("Uninstalling %s…", colorTeal(name)))

			lm := libraries.NewManager(cfg)
			if err := lm.Uninstall(name); err != nil {
				return err
			}

			printSuccess(fmt.Sprintf("Uninstalled %s", name))
			return nil
		},
	}
}
