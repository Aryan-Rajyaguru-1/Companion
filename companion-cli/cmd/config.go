package cmd

import (
	"fmt"
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
	return &cobra.Command{
		Use:   "get <key>",
		Short: "Get a config value",
		Long: `Get a config value by its dot-separated key.

Available keys:
  bridge.host            bridge.port
  bridge.baud            bridge.mcu
  compiler.warnings      compiler.verbose
  upload.auto_verify
  directories.data       directories.user
  daemon.enabled         daemon.port
  cache.enabled          cache.max_size_mb     cache.max_age_days
  library.enable_unsafe_install

Examples:
  companion config get bridge.host
  companion config get compiler.warnings`,

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

			fmt.Printf("%s = %s\n", colorTeal(args[0]), colorCyan(val))
			return nil
		},
	}
}

// ── config set ───────────────────────────────────────────────────

func newConfigSetCmd() *cobra.Command {
	return &cobra.Command{
		Use:   "set <key> <value>",
		Short: "Set a config value",
		Long: `Set a config value and save it to the config file.

Examples:
  companion config set bridge.host 192.168.1.42
  companion config set bridge.mcu esp32
  companion config set compiler.warnings more
  companion config set upload.auto_verify true`,

		Args: cobra.ExactArgs(2),
		RunE: func(cmd *cobra.Command, args []string) error {
			cfgPath := globalFlags.ConfigFile
			if cfgPath == "" {
				cfgPath = config.DefaultPath()
			}

			cfg, _, err := config.Load(cfgPath)
			if err != nil {
				return err
			}

			if err := config.SetValue(cfg, args[0], args[1]); err != nil {
				return err
			}

			if err := config.Save(cfg, cfgPath); err != nil {
				return fmt.Errorf("saving config: %w", err)
			}

			printSuccess(fmt.Sprintf("Set %s = %s", colorTeal(args[0]), colorCyan(args[1])))
			return nil
		},
	}
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
