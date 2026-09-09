package cmd

import (
	"fmt"
	"os"
	"path/filepath"

	"github.com/companion-ide/companion-cli/internal/config"
	"github.com/companion-ide/companion-cli/internal/plugins"
	"github.com/spf13/cobra"
)

// newPluginsCmd exposes the plugin registry (built-in + dynamic .so plugins).
func newPluginsCmd() *cobra.Command {
	cmd := &cobra.Command{
		Use:   "plugins",
		Short: "Manage Companion plugins",
		Long: `List registered plugins (built-in first-party extensions and any
Go plugin .so files dropped into <data>/plugins).

Plugin types:
  uploader    custom upload strategies (OTA, JTAG, ...)
  compiler    pre/post-compile hooks
  board       additional board definitions
  diagnostic  custom lint rules on compiler output`,
	}
	cmd.AddCommand(newPluginsListCmd())
	return cmd
}

// pluginRegistry loads the plugin registry for a config (best-effort).
func pluginRegistry(cfg *config.Config) *plugins.Registry {
	reg, errs := plugins.LoadAll(filepath.Join(cfg.Directories.Data, "plugins"))
	for _, e := range errs {
		printWarn("plugin: " + e.Error())
	}
	return reg
}

func newPluginsListCmd() *cobra.Command {
	return &cobra.Command{
		Use:   "list",
		Short: "List registered plugins",
		Args:  cobra.NoArgs,
		RunE: func(cmd *cobra.Command, args []string) error {
			cfg, _, err := config.Load(globalFlags.ConfigFile)
			if err != nil {
				return err
			}
			dir := filepath.Join(cfg.Directories.Data, "plugins")
			reg, errs := plugins.LoadAll(dir)

			entries := reg.Entries()
			if len(entries) == 0 && len(errs) == 0 {
				fmt.Println("No plugins registered.")
				return nil
			}
			for _, e := range entries {
				fmt.Printf("  %-38s %-10s %-28s v%s\n",
					e.Plugin.ID(), e.Kind, e.Plugin.Name(), e.Plugin.Version())
			}
			for _, err := range errs {
				fmt.Fprintln(os.Stderr, "  ⚠", err)
			}
			fmt.Printf("\n%d plugin(s) from %s\n", len(entries), dir)
			return nil
		},
	}
}
