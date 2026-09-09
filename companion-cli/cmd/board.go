package cmd

import (
	"encoding/json"
	"fmt"
	"os"
	"sort"
	"strings"

	"github.com/companion-ide/companion-cli/internal/boards"
	"github.com/companion-ide/companion-cli/internal/config"
	"github.com/spf13/cobra"
)

func newBoardCmd() *cobra.Command {
	cmd := &cobra.Command{
		Use:   "board",
		Short: "Manage board platforms and indexes",
		Long:  "Search, install, and list board platforms from the Arduino board manager.",
	}

	cmd.AddCommand(
		newBoardUpdateIndexCmd(),
		newBoardSearchCmd(),
		newBoardPackagesCmd(),
		newBoardListCmd(),
		newBoardInstallCmd(),
		newBoardListAllCmd(),
		newBoardDetailsCmd(),
		newBoardListPortsCmd(),
	)

	return cmd
}

// ── board list-ports ─────────────────────────────────────────────

func newBoardListPortsCmd() *cobra.Command {
	var jsonOut bool
	cmd := &cobra.Command{
		Use:   "list-ports",
		Short: "Detect connected USB serial boards",
		Long: `Scans local serial devices, reads their USB identity, and matches
VID/PID against installed platforms to identify the attached board.
Used by the IDE for plug-and-play board detection.`,
		RunE: func(cmd *cobra.Command, args []string) error {
			cfg, _, err := config.Load(globalFlags.ConfigFile)
			if err != nil {
				return err
			}
			config.EnsureDirs(cfg)

			bm := boards.NewManager(cfg)
			ports, err := bm.ListSerialPorts()
			if err != nil {
				return err
			}

			if jsonOut {
				return json.NewEncoder(os.Stdout).Encode(ports)
			}
			if len(ports) == 0 {
				printInfo("No serial devices found")
				return nil
			}
			fmt.Printf("  %-18s %-10s %-24s %s\n", "PORT", "USB ID", "BOARD", "FQBN")
			for _, p := range ports {
				name := p.BoardName
				if name == "" {
					if p.ProductName != "" {
						name = p.ProductName
					} else {
						name = "(unknown)"
					}
				}
				fqbn := p.FQBN
				if fqbn == "" {
					fqbn = colorDim("—")
				}
				usbid := colorDim(p.USBVID + ":" + p.USBPID)
				if usbid == ":" {
					usbid = colorDim("(non-usb)")
				}
				fmt.Printf("  %-18s %-20s %-30s %s\n", colorTeal(p.Port), usbid, name, fqbn)
			}
			return nil
		},
	}
	cmd.Flags().BoolVar(&jsonOut, "json", false, "Emit machine-readable JSON")
	return cmd
}

// ── board listall ─────────────────────────────────────────────────

func newBoardListAllCmd() *cobra.Command {
	var jsonOut bool
	cmd := &cobra.Command{
		Use:   "listall [query]",
		Short: "List every board provided by installed platforms",
		Long: `Lists all boards you can actually build for right now, with their
FQBNs. Optionally filter by a case-insensitive name substring.`,
		Args: cobra.MaximumNArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			cfg, _, err := config.Load(globalFlags.ConfigFile)
			if err != nil {
				return err
			}
			config.EnsureDirs(cfg)

			bm := boards.NewManager(cfg)
			all, err := bm.ListAllBoards()
			if err != nil {
				return err
			}

			query := ""
			if len(args) > 0 {
				query = strings.ToLower(args[0])
			}
			var filtered []boards.BoardEntry
			for _, b := range all {
				if query != "" &&
					!strings.Contains(strings.ToLower(b.Name), query) &&
					!strings.Contains(strings.ToLower(b.FQBN), query) {
					continue
				}
				filtered = append(filtered, b)
			}

			if jsonOut {
				return json.NewEncoder(os.Stdout).Encode(filtered)
			}
			if len(filtered) == 0 {
				printInfo("No installed boards found — install a platform first:")
				fmt.Println("    companion board install arduino:avr")
				return nil
			}
			for _, b := range filtered {
				name := b.Name
				if name == "" {
					name = "(unnamed)"
				}
				fmt.Printf("  %-42s %s\n", colorTeal(b.FQBN), name)
			}
			fmt.Printf("\n%d board(s)\n", len(filtered))
			return nil
		},
	}
	cmd.Flags().BoolVar(&jsonOut, "json", false, "Emit machine-readable JSON")
	return cmd
}

// ── board details ─────────────────────────────────────────────────

func newBoardDetailsCmd() *cobra.Command {
	return &cobra.Command{
		Use:   "details <fqbn>",
		Short: "Show full details for an installed board (options, memory, platform)",
		Args:  cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			cfg, _, err := config.Load(globalFlags.ConfigFile)
			if err != nil {
				return err
			}
			config.EnsureDirs(cfg)

			bm := boards.NewManager(cfg)
			d, err := bm.BoardDetails(args[0])
			if err != nil {
				return err
			}

			fmt.Printf("  Board:      %s\n", colorBold(d.Name))
			fmt.Printf("  FQBN:       %s\n", colorTeal(d.FQBN))
			fmt.Printf("  Platform:   %s @ %s\n", d.Vendor+":"+d.Arch, colorCyan(d.Version))
			if d.Props != nil {
				if v := d.Props["build.mcu"]; v != "" {
					fmt.Printf("  MCU:        %s\n", v)
				}
				if v := d.Props["build.f_cpu"]; v != "" {
					fmt.Printf("  Clock:      %s Hz\n", v)
				}
				if v := d.Props["upload.maximum_size"]; v != "" {
					fmt.Printf("  Flash:      %s bytes\n", v)
				}
				if v := d.Props["upload.maximum_data_size"]; v != "" {
					fmt.Printf("  RAM:        %s bytes\n", v)
				}
			}
			if len(d.Options) > 0 {
				fmt.Println("  Options:")
				labels := make([]string, 0, len(d.Options))
				for l := range d.Options {
					labels = append(labels, l)
				}
				sort.Strings(labels)
				for _, l := range labels {
					fmt.Printf("    %-14s %s\n", l+":", strings.Join(d.Options[l], ", "))
				}
			}
			return nil
		},
	}
}

// ── board update-index ────────────────────────────────────────────

func newBoardUpdateIndexCmd() *cobra.Command {
	return &cobra.Command{
		Use:   "update-index",
		Short: "Download the latest board package indexes",
		Long:  "Downloads package_index.json and all additional board URLs from config.",
		RunE: func(cmd *cobra.Command, args []string) error {
			cfg, _, err := config.Load(globalFlags.ConfigFile)
			if err != nil {
				return err
			}
			config.EnsureDirs(cfg)

			printInfo("Updating board package indexes…")
			bm := boards.NewManager(cfg)
			if err := bm.UpdateIndex(func(s string) { fmt.Println("  " + s) }); err != nil {
				return err
			}
			printSuccess("Board index updated")
			return nil
		},
	}
}

// ── board search ──────────────────────────────────────────────────

func newBoardSearchCmd() *cobra.Command {
	var showAll bool

	cmd := &cobra.Command{
		Use:   "search [query]",
		Short: "Search for available boards",
		Long:  "Search for boards in the downloaded package index. Run 'board update-index' first.",
		Args:  cobra.MaximumNArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			cfg, _, err := config.Load(globalFlags.ConfigFile)
			if err != nil {
				return err
			}

			query := ""
			if len(args) > 0 {
				query = args[0]
			}

			bm := boards.NewManager(cfg)
			results, err := bm.Search(query)
			if err != nil {
				return err
			}

			if len(results) == 0 {
				printWarn("No boards found — run: companion board update-index")
				return nil
			}

			// Print table header
			fmt.Printf("\n%-40s %-28s %s\n",
				colorBold("Board Name"), colorBold("FQBN"), colorBold("Status"))
			fmt.Println(strings.Repeat("─", 90))

			shown := 0
			for _, b := range results {
				if !showAll && !b.Installed && query == "" {
					continue // Only show installed boards in default view
				}
				status := colorDim("not installed")
				if b.Installed {
					status = colorGreen("installed")
				}
				name := b.Name
				if len(name) > 38 {
					name = name[:35] + "…"
				}
				fqbn := b.FQBN
				if len(fqbn) > 26 {
					fqbn = fqbn[:23] + "…"
				}
				fmt.Printf("%-40s %-28s %s\n", name, colorCyan(fqbn), status)
				shown++
			}

			if shown == 0 && query == "" {
				printInfo("No boards installed yet.")
				printStep("Install a board platform: companion board install arduino:avr")
				printStep("Or search all available: companion board search --all")
			} else {
				fmt.Printf("\n%d board(s) shown\n", shown)
			}
			return nil
		},
	}

	cmd.Flags().BoolVar(&showAll, "all", false,
		"Show all available boards, including uninstalled ones")
	return cmd
}

// ── board packages ────────────────────────────────────────────────

func newBoardPackagesCmd() *cobra.Command {
	cmd := &cobra.Command{
		Use:   "packages [query]",
		Short: "Search for available board packages",
		Long:  "Search for board packages/platforms in the downloaded package index. Run 'board update-index' first.",
		Args:  cobra.MaximumNArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			cfg, _, err := config.Load(globalFlags.ConfigFile)
			if err != nil {
				return err
			}

			query := ""
			if len(args) > 0 {
				query = args[0]
			}

			bm := boards.NewManager(cfg)
			results, err := bm.SearchPackages(query)
			if err != nil {
				return err
			}

			if len(results) == 0 {
				printWarn("No packages found — run: companion board update-index")
				return nil
			}

			// Print table header
			fmt.Printf("\n%-30s %-20s %-15s %s\n",
				colorBold("Package"), colorBold("Maintainer"), colorBold("Architecture"), colorBold("Status"))
			fmt.Println(strings.Repeat("─", 100))

			for _, pkg := range results {
				status := colorDim("not installed")
				if pkg.Installed {
					status = colorGreen("installed")
				}
				name := pkg.Name
				if len(name) > 28 {
					name = name[:25] + "…"
				}
				maintainer := pkg.Maintainer
				if len(maintainer) > 18 {
					maintainer = maintainer[:15] + "…"
				}
				arch := pkg.Architecture
				if len(arch) > 13 {
					arch = arch[:10] + "…"
				}
				fmt.Printf("%-30s %-20s %-15s %s\n",
					colorCyan(name), maintainer, arch, status)
			}

			fmt.Printf("\n%d package(s) shown\n", len(results))
			return nil
		},
	}

	return cmd
}

// ── board list ────────────────────────────────────────────────────

func newBoardListCmd() *cobra.Command {
	return &cobra.Command{
		Use:   "list",
		Short: "List installed board platforms",
		RunE: func(cmd *cobra.Command, args []string) error {
			cfg, _, err := config.Load(globalFlags.ConfigFile)
			if err != nil {
				return err
			}

			bm := boards.NewManager(cfg)
			platforms, err := bm.ListInstalled()
			if err != nil {
				return err
			}

			if len(platforms) == 0 {
				printWarn("No platforms installed.")
				printStep("Install one: companion board install arduino:avr")
				return nil
			}

			fmt.Printf("\n%-30s %-12s %s\n",
				colorBold("Platform ID"), colorBold("Version"), colorBold("Path"))
			fmt.Println(strings.Repeat("─", 70))

			for _, p := range platforms {
				fmt.Printf("%-30s %-12s %s\n",
					colorTeal(p.ID), colorCyan(p.Version), colorDim(p.Path))
			}
			fmt.Printf("\n%d platform(s) installed\n", len(platforms))
			return nil
		},
	}
}

// ── board install ─────────────────────────────────────────────────

func newBoardInstallCmd() *cobra.Command {
	return &cobra.Command{
		Use:   "install <platform-id>",
		Short: "Install a board platform",
		Long: `Install a board platform by its ID (vendor:architecture).

Examples:
  companion board install arduino:avr
  companion board install esp32:esp32
  companion board install STMicroelectronics:stm32`,

		Args: cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			cfg, _, err := config.Load(globalFlags.ConfigFile)
			if err != nil {
				return err
			}
			config.EnsureDirs(cfg)

			platformID := args[0]
			printInfo(fmt.Sprintf("Installing platform %s…", colorTeal(platformID)))

			bm := boards.NewManager(cfg)
			if err := bm.Install(platformID, func(s string) {
				fmt.Println("  " + s)
			}); err != nil {
				printError(err.Error())
				return fmt.Errorf("install failed")
			}

			printSuccess(fmt.Sprintf("Platform %s installed", colorTeal(platformID)))
			return nil
		},
	}
}
