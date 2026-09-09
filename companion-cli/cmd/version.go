package cmd

import (
	"fmt"
	"runtime"

	"github.com/companion-ide/companion-cli/internal/bridge"
	"github.com/companion-ide/companion-cli/internal/config"
	"github.com/spf13/cobra"
)

func newVersionCmd() *cobra.Command {
	cmd := &cobra.Command{
		Use:   "version",
		Short: "Print version information",
		Run: func(cmd *cobra.Command, args []string) {
			fmt.Printf("\n%s\n", colorTeal(colorBold("Companion CLI")))
			fmt.Printf("  Version:   %s\n", colorCyan(CLIVersion))
			fmt.Printf("  Go:        %s\n", colorDim(runtime.Version()))
			fmt.Printf("  OS/Arch:   %s/%s\n", colorDim(runtime.GOOS), colorDim(runtime.GOARCH))
			fmt.Printf("  License:   %s\n", colorDim("MIT — fully open, no GPL obligations"))
			fmt.Println()
		},
	}

	// Attach ping as a subcommand of version for convenience,
	// and also register it at root level via newPingCmd()
	cmd.AddCommand(newPingCmd())
	return cmd
}

func newPingCmd() *cobra.Command {
	var host string
	var port int

	cmd := &cobra.Command{
		Use:   "ping",
		Short: "Ping the ESP32 WiFi bridge and report its status",
		Long: `Send a query command to the ESP32 bridge and display its status.
Useful to verify the bridge is reachable before compiling/uploading.

Examples:
  companion version ping
  companion version ping --host 192.168.1.42`,

		RunE: func(cmd *cobra.Command, args []string) error {
			cfg, _, err := config.Load(globalFlags.ConfigFile)
			if err != nil {
				return err
			}

			if host == "" {
				host = cfg.Bridge.Host
			}
			if port == 0 {
				port = cfg.Bridge.Port
			}

			printInfo(fmt.Sprintf("Pinging bridge at %s:%d…", colorBold(host), port))

			info, err := bridge.Ping(host, port)
			if err != nil {
				printError(fmt.Sprintf("Bridge unreachable: %v", err))
				printStep("Check that the ESP32 bridge is powered and on the same WiFi network.")
				printStep(fmt.Sprintf("AP mode default: SSID=ESP32-OTA  IP=%s  Port=%d", host, port))
				return fmt.Errorf("ping failed")
			}

			printSuccess(fmt.Sprintf("Bridge responded: %s", colorCyan(info)))
			return nil
		},
	}

	cmd.Flags().StringVar(&host, "host", "", "Bridge IP (default from config)")
	cmd.Flags().IntVar(&port, "port", 0, "Bridge TCP port (default from config)")
	return cmd
}
