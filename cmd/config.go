package cmd

import (
	"fmt"
	"io"
	"strings"

	"github.com/companion-ide/companion-cli/internal/config"
	"github.com/spf13/cobra"
)

func newConfigCmd() *cobra.Command {
	cmd := &cobra.Command{
		Use:   "config",
		Short: "Manage Companion CLI configuration",
		Long:  "Read, write, and manage the Companion CLI configuration file.",
	}

	cmd.AddCommand(
		newConfigInitCmd(),
		newConfigGetCmd(),
		newConfigSetCmd(),
		newConfigDumpCmd(),
	)

	return cmd
}

// ── config init ──────────────────────────────────────────────────

func newConfigInitCmd() *cobra.Command {
	return &cobra.Command{
		Use:   "init",
		Short: "Create the default config file",
		Long:  "Write a default config.yaml to ~/.companion-cli/config.yaml",
		RunE: func(cmd *cobra.Command, args []string) error {
			path, created, err := config.Init(globalFlags.ConfigFile)
			if err != nil {
				return err
			}

			if created {
				printSuccess(fmt.Sprintf("Config created: %s", colorCyan(path)))
			} else {
				printInfo(fmt.Sprintf("Config already exists: %s", colorCyan(path)))
			}
			return nil
		},
	}
}

// ── config get ───────────────────────────────────────────────────

func newConfigGetCmd() *cobra.Command {
	var reveal bool

	cmd := &cobra.Command{
		Use:   "get <key>",
		Short: "Get a config value",
		Long: `Get a config value by its dot-separated key.

Secret values (bridge.key) print <set>/<unset> unless --reveal is passed.
COMPANION_BRIDGE_KEY overrides bridge.key at runtime.

Available keys:
  bridge.host            bridge.port
  bridge.baud            bridge.mcu            bridge.key
  compiler.warnings      compiler.verbose
  upload.auto_verify
  directories.data       directories.user
  daemon.enabled         daemon.port
  cache.enabled          cache.max_size_mb     cache.max_age_days
  library.enable_unsafe_install

Examples:
  companion config get bridge.host
  companion config get bridge.key            # <set> or <unset>
  companion config get bridge.key --reveal   # prints the secret`,

		Args: cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			cfg, _, err := config.Load(globalFlags.ConfigFile)
			if err != nil {
				return err
			}

			val, err := config.GetValue(cfg, args[0])
			if err != nil {
				return err
			}
			if reveal && args[0] == "bridge.key" {
				val = config.BridgeKey(cfg)
				if val == "" {
					val = "<unset>"
				}
				// This is the machine-consumed disclosure path (the IDE feeds
				// it to the native bridge client). Never wrap the secret in
				// ANSI escapes: a key containing \x1b[36m is not the key.
				fmt.Printf("%s = %s\n", args[0], val)
				return nil
			}

			fmt.Printf("%s = %s\n", colorTeal(args[0]), colorCyan(val))
			return nil
		},
	}

	cmd.Flags().BoolVar(&reveal, "reveal", false, "Reveal secret values (bridge.key)")
	return cmd
}

// ── config set ───────────────────────────────────────────────────

func newConfigSetCmd() *cobra.Command {
	var valueFromStdin bool

	cmd := &cobra.Command{
		Use:   "set <key> [value]",
		Short: "Set a config value",
		Long: `Set a config value and save it to the config file.

Use --stdin for secrets: the value is read from standard input instead of
appearing in the process list and shell history.

Examples:
  companion config set bridge.host 192.168.1.42
  companion config set bridge.mcu esp32
  companion config set compiler.warnings more
  companion config set upload.auto_verify true
  companion config set bridge.key --stdin < bridge-key.txt`,

		Args: func(cmd *cobra.Command, args []string) error {
			if valueFromStdin {
				return cobra.ExactArgs(1)(cmd, args)
			}
			return cobra.ExactArgs(2)(cmd, args)
		},
		RunE: func(cmd *cobra.Command, args []string) error {
			value := ""
			if valueFromStdin {
				// Leave room for one optional CRLF after a 4096-byte value.
				raw, err := io.ReadAll(io.LimitReader(cmd.InOrStdin(), 4099))
				if err != nil {
					return fmt.Errorf("reading value from stdin: %w", err)
				}
				if len(raw) > 4098 {
					return fmt.Errorf("value from stdin is too long (max 4096 bytes)")
				}
				// Pipelines normally append one newline. Do not trim arbitrary
				// whitespace: bridge.key validation must reject it.
				value = strings.TrimSuffix(string(raw), "\n")
				value = strings.TrimSuffix(value, "\r")
				if len(value) > 4096 {
					return fmt.Errorf("value from stdin is too long (max 4096 bytes)")
				}
			} else {
				value = args[1]
			}

			cfgPath := globalFlags.ConfigFile
			if cfgPath == "" {
				cfgPath = config.DefaultPath()
			}

			cfg, _, err := config.Load(cfgPath)
			if err != nil {
				return err
			}

			if err := config.SetValue(cfg, args[0], value); err != nil {
				return err
			}

			if err := config.Save(cfg, cfgPath); err != nil {
				return fmt.Errorf("saving config: %w", err)
			}

			shown := value
			if args[0] == "bridge.key" {
				shown = "<redacted>"
				if value == "" {
					shown = "<cleared>"
				}
			}
			printSuccess(fmt.Sprintf("Set %s = %s", colorTeal(args[0]), colorCyan(shown)))
			return nil
		},
	}

	cmd.Flags().BoolVar(&valueFromStdin, "stdin", false, "Read the value from standard input (for secrets)")
	return cmd
}

// ── config dump ──────────────────────────────────────────────────

func newConfigDumpCmd() *cobra.Command {
	return &cobra.Command{
		Use:   "dump",
		Short: "Print the full config file",
		RunE: func(cmd *cobra.Command, args []string) error {
			cfg, cfgPath, err := config.Load(globalFlags.ConfigFile)
			if err != nil {
				return err
			}

			printInfo(fmt.Sprintf("Config file: %s", colorCyan(cfgPath)))
			fmt.Println()

			sections := []struct {
				title  string
				values [][2]string
			}{
				{"Bridge", [][2]string{
					{"host", cfg.Bridge.Host},
					{"port", fmt.Sprintf("%d", cfg.Bridge.Port)},
					{"baud", fmt.Sprintf("%d", cfg.Bridge.Baud)},
					{"mcu", cfg.Bridge.MCU},
					{"key", redactedPresence(config.BridgeKey(cfg))},
				}},
				{"Compiler", [][2]string{
					{"warnings", cfg.Compiler.Warnings},
					{"verbose", fmt.Sprintf("%v", cfg.Compiler.Verbose)},
				}},
				{"Upload", [][2]string{
					{"auto_verify", fmt.Sprintf("%v", cfg.Upload.AutoVerify)},
					{"verbose", fmt.Sprintf("%v", cfg.Upload.Verbose)},
				}},
				{"Directories", [][2]string{
					{"data", cfg.Directories.Data},
					{"user", cfg.Directories.User},
				}},
				{"Board Manager", [][2]string{
					{"additional_urls", strings.Join(cfg.BoardManager.AdditionalURLs, "\n               ")},
				}},
			}

			for _, sec := range sections {
				fmt.Println(colorBold(colorTeal(sec.title + ":")))
				for _, kv := range sec.values {
					fmt.Printf("  %-20s %s\n", colorDim(kv[0]), kv[1])
				}
				fmt.Println()
			}

			return nil
		},
	}
}

// redactedPresence reports whether a secret is configured without printing it.
func redactedPresence(v string) string {
	if strings.TrimSpace(v) == "" {
		return "<unset>"
	}
	return "<set>"
}
