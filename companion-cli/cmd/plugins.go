package cmd

import (
	"fmt"
	"os"
	"path/filepath"
	"sync"

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

// pluginRegistry returns the cached plugin registry for a config.
//
// Builtins call Init() on load, so rebuilding per request would re-run
// plugin Init for every compile/upload and re-scan for .so files.
// Registries are cached per plugin dir for the life of the process;
// the daemon additionally holds one on daemonServer built at startup.
var (
	registryMu    sync.Mutex
	registryByDir = map[string]*plugins.Registry{}
)

// pluginRegistry loads the plugin registry for a config (best-effort).
func pluginRegistry(cfg *config.Config) *plugins.Registry {
	dir := filepath.Join(cfg.Directories.Data, "plugins")
	registryMu.Lock()
	if reg, ok := registryByDir[dir]; ok {
		registryMu.Unlock()
		return reg
	}
	registryMu.Unlock()
	reg, errs := plugins.LoadAll(dir)
	for _, e := range errs {
		printWarn("plugin: " + e.Error())
	}
	registryMu.Lock()
	registryByDir[dir] = reg
	registryMu.Unlock()
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
