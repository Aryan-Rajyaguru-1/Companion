package cmd

import (
	"bufio"
	"fmt"
	"os"
	"os/signal"
	"strings"
	"syscall"
	"time"

	"github.com/companion-ide/companion-cli/internal/bridge"
	"github.com/companion-ide/companion-cli/internal/config"
	"github.com/spf13/cobra"
)

func newMonitorCmd() *cobra.Command {
	var (
		host       string
		port       int
		baud       uint32
		lineEnding string
		showTS     bool
	)

	cmd := &cobra.Command{
		Use:   "monitor",
		Short: "Open an interactive serial monitor over the WiFi bridge",
		Long: `Connect to the target device UART via the ESP32 WiFi bridge.

Press Ctrl+C to exit.

Line ending options:  none | nl | cr | crnl

Examples:
  companion monitor
  companion monitor --baud 9600 --host 192.168.1.42
  companion monitor --line-ending crnl --timestamp`,

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
			if baud == 0 {
				baud = uint32(cfg.Bridge.Baud)
			}

			ending := map[string]string{
				"cr": "\r", "crnl": "\r\n", "none": "", "nl": "\n",
			}[lineEnding]
			if lineEnding == "" {
				ending = "\n"
			}

			printInfo(fmt.Sprintf("Serial Monitor → %s:%d @ %d baud",
				colorBold(host), port, baud))
			printStep("Press Ctrl+C to exit")
			fmt.Println()

			bc := bridge.New(host, port)
			if err := bc.Connect(); err != nil {
				return err
			}
			defer bc.Close()

			if err := bc.SetBaud(baud); err != nil {
				printWarn(fmt.Sprintf("Set baud failed: %v", err))
			}

			printSuccess(fmt.Sprintf("Connected to bridge at %s:%d", host, port))
			fmt.Println(strings.Repeat("─", 60))

			sigCh := make(chan os.Signal, 1)
			signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)

			inputCh := make(chan string, 16)
			go func() {
				scanner := bufio.NewScanner(os.Stdin)
				for scanner.Scan() {
					inputCh <- scanner.Text()
				}
				close(inputCh)
			}()

			recvDone := make(chan error, 1)
			go func() {
				buf := make([]byte, 4096)
				for {
					n, err := bc.Read(buf)
					if n > 0 {
						if showTS {
							ts := time.Now().Format("15:04:05.000")
							for _, line := range strings.Split(strings.TrimRight(string(buf[:n]), "\r\n"), "\n") {
								fmt.Printf("%s  %s\n", colorDim(ts), line)
							}
						} else {
							os.Stdout.Write(buf[:n])
						}
					}
					if err != nil {
						recvDone <- err
						return
					}
				}
			}()

			for {
				select {
				case <-sigCh:
					fmt.Printf("\n%s\n", colorDim("Closing monitor…"))
					return nil
				case line, ok := <-inputCh:
					if !ok {
						return nil
					}
					bc.Write([]byte(line + ending))
				case err := <-recvDone:
					if err != nil {
						fmt.Printf("\n%s: %v\n", colorYellow("Connection closed"), err)
					}
					return nil
				}
			}
		},
	}

	cmd.Flags().StringVar(&host, "host", "", "Bridge IP (default from config)")
	cmd.Flags().IntVar(&port, "port", 0, "Bridge TCP port (default from config)")
	cmd.Flags().Uint32Var(&baud, "baud", 0, "Serial baud rate (default from config)")
	cmd.Flags().StringVar(&lineEnding, "line-ending", "nl", "Line ending: none|nl|cr|crnl")
	cmd.Flags().BoolVar(&showTS, "timestamp", false, "Show HH:MM:SS.mmm timestamp per line")

	return cmd
}
