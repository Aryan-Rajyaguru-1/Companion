package cmd

import (
	"fmt"
	"strings"
	"time"

	"github.com/companion-ide/companion-cli/internal/config"
	"github.com/companion-ide/companion-cli/internal/fleet"
	"github.com/companion-ide/companion-cli/internal/ota"
	"github.com/spf13/cobra"
)

// ── fleet discover ────────────────────────────────────────────────

func newFleetDiscoverCmd() *cobra.Command {
	var wait time.Duration
	var autoRegister bool
	cmd := &cobra.Command{
		Use:   "discover [--register]",
		Short: "mDNS-scan for OTA devices (optionally register them in the fleet)",
		Args:  cobra.NoArgs,
		RunE: func(cmd *cobra.Command, args []string) error {
			cfg, _, err := config.Load(globalFlags.ConfigFile)
			if err != nil {
				return err
			}
			r, err := fleetRegistry(cfg)
			if err != nil {
				return err
			}
			printInfo(fmt.Sprintf("Scanning for OTA devices (%s window)…", wait))
			devs := ota.Discover(cmd.Context(), wait)
			if len(devs) == 0 {
				printInfo("No OTA devices found — are they on the same network with ArduinoOTA.begin() called?")
				return nil
			}
			for _, d := range devs {
				fmt.Printf("  %-16s %-28s port %d\n", d.Host, d.Name, d.Port)
			}
			printSuccess(fmt.Sprintf("%d OTA device(s) found", len(devs)))

			if !autoRegister {
				fmt.Println("\nRe-run with --register to add these to the registry.")
				return nil
			}
			added, updated := 0, 0
			for _, d := range devs {
				if ex := findByHostOrName(r, d.Host, d.Name); ex != nil {
					ex.Host = d.Host
					if d.Name != "" {
						ex.Name = d.Name
					}
					ex.Port = d.Port
					if err := r.Upsert(*ex); err != nil {
						return err
					}
					updated++
					printStep(fmt.Sprintf("updated %s → %s", colorBold(ex.Key()), d.Host))
				} else {
					id := d.Name
					if id == "" {
						id = d.Host
					}
					if err := r.Upsert(fleet.Device{ID: id, Name: d.Name, Host: d.Host, Port: d.Port}); err != nil {
						return err
					}
					added++
					printStep(fmt.Sprintf("registered %s → %s", colorBold(id), d.Host))
				}
			}
			printSuccess(fmt.Sprintf("Registry: %d added, %d updated", added, updated))
			return nil
		},
	}
	cmd.Flags().DurationVar(&wait, "wait", 3*time.Second, "mDNS listen window")
	cmd.Flags().BoolVar(&autoRegister, "register", false, "add found devices to the fleet registry")
	return cmd
}

// findByHostOrName locates an existing registry device matching a host or name.
func findByHostOrName(r *fleet.Registry, host, name string) *fleet.Device {
	for _, d := range r.All() {
		if strings.EqualFold(d.Host, host) {
			cp := d
			return &cp
		}
		if name != "" && strings.EqualFold(d.Name, name) {
			cp := d
			return &cp
		}
	}
	return nil
}
