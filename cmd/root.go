package cmd

import (
	"fmt"
	"os"

	"github.com/spf13/cobra"
)

const (
	CLIName    = "companion"
	CLIVersion = "1.0.0"
)

// GlobalFlags holds flags shared across all subcommands.
type GlobalFlags struct {
	ConfigFile string
	Verbose    bool
	NoColor    bool
	Portable   bool
}

var globalFlags = &GlobalFlags{}

var rootCmd = &cobra.Command{
	Use:   CLIName,
	Short: "Companion CLI — wireless Arduino programmer",
	Long: `
  ██████╗ ██████╗ ███╗   ███╗██████╗  █████╗ ███╗   ██╗██╗ ██████╗ ███╗   ██╗
 ██╔════╝██╔═══██╗████╗ ████║██╔══██╗██╔══██╗████╗  ██║██║██╔═══██╗████╗  ██║
 ██║     ██║   ██║██╔████╔██║██████╔╝███████║██╔██╗ ██║██║██║   ██║██╔██╗ ██║
 ██║     ██║   ██║██║╚██╔╝██║██╔═══╝ ██╔══██║██║╚██╗██║██║██║   ██║██║╚██╗██║
 ╚██████╗╚██████╔╝██║ ╚═╝ ██║██║     ██║  ██║██║ ╚████║██║╚██████╔╝██║ ╚████║
  ╚═════╝ ╚═════╝ ╚═╝     ╚═╝╚═╝     ╚═╝  ╚═╝╚═╝  ╚═══╝╚═╝ ╚═════╝ ╚═╝  ╚═══╝
                                                                  CLI v` + CLIVersion + `

Companion CLI — compile and upload Arduino sketches wirelessly via ESP32 bridge.
No cable needed. Supports ESP32, STM32, AVR and any UART-bootloadable device.`,

	SilenceUsage:  true,
	SilenceErrors: true,
}

// Execute is the entry point called from main.go.
func Execute() {
	if err := rootCmd.Execute(); err != nil {
		fmt.Fprintln(os.Stderr, colorRed("Error: ")+err.Error())
		os.Exit(1)
	}
}

func init() {
	rootCmd.PersistentFlags().StringVar(
		&globalFlags.ConfigFile, "config-file", "",
		"Config file (default: ~/.companion-cli/config.yaml)",
	)
	rootCmd.PersistentFlags().BoolVarP(
		&globalFlags.Verbose, "verbose", "v", false,
		"Enable verbose output",
	)
	rootCmd.PersistentFlags().BoolVar(
		&globalFlags.NoColor, "no-color", false,
		"Disable colored output",
	)
	rootCmd.PersistentFlags().BoolVar(
		&globalFlags.Portable, "portable", false,
		"Portable mode — store all state next to the executable (USB-stick workflow)",
	)

	// Portable mode must be in effect before any command loads config.
	rootCmd.PersistentPreRun = func(cmd *cobra.Command, args []string) {
		if globalFlags.Portable {
			os.Setenv("COMPANION_PORTABLE", "1")
		}
	}

	// Register all subcommands
	rootCmd.AddCommand(
		newCompileCmd(),
		newUploadCmd(),
		newBoardCmd(),
		newLibCmd(),
		newMonitorCmd(),
		newConfigCmd(),
		newVersionCmd(),
		newDaemonCmd(),  // P2: long-lived daemon for persistent build cache
		newProfileCmd(), // P3: reproducible build profiles (sketch.yaml)
		newOTACommand(), // P4: over-the-air WiFi uploads (ArduinoOTA protocol)
		newPluginsCmd(), // P5: plugin system activation
		newLSPCmd(),     // P6: clangd IntelliSense over compile_commands.json
		newOutdatedCmd(),
		newUpgradeCmd(),
		newFleetCommand(), // device registry + batch OTA push
	)
}

// ── Terminal color helpers ───────────────────────────────────────
func colorGreen(s string) string  { return "\033[32m" + s + "\033[0m" }
func colorRed(s string) string    { return "\033[31m" + s + "\033[0m" }
func colorYellow(s string) string { return "\033[33m" + s + "\033[0m" }
func colorCyan(s string) string   { return "\033[36m" + s + "\033[0m" }
func colorBold(s string) string   { return "\033[1m" + s + "\033[0m" }
func colorDim(s string) string    { return "\033[2m" + s + "\033[0m" }
func colorTeal(s string) string   { return "\033[38;5;37m" + s + "\033[0m" }

func printSuccess(msg string) { fmt.Println(colorGreen("✓ ") + msg) }
func printError(msg string)   { fmt.Fprintln(os.Stderr, colorRed("✗ ")+msg) }
func printInfo(msg string)    { fmt.Println(colorCyan("» ") + msg) }
func printWarn(msg string)    { fmt.Println(colorYellow("⚠ ") + msg) }
func printStep(msg string)    { fmt.Println(colorDim("  · ") + msg) }
