package cmd

import (
	"fmt"
	"path/filepath"
	"strings"

	"github.com/companion-ide/companion-cli/internal/config"
	"github.com/companion-ide/companion-cli/internal/fleet"
	"github.com/companion-ide/companion-cli/internal/ota"
	"github.com/spf13/cobra"
)

// fleetStore returns the file-backed device catalog for the active config.
func fleetStore(cfg *config.Config) fleet.Store {
	return fleet.FileStore{Path: filepath.Join(cfg.Directories.Data, "devices.yaml")}
}

// fleetRegistry loads the catalog into memory.
func fleetRegistry(cfg *config.Config) (*fleet.Registry, error) {
	r := fleet.New(fleetStore(cfg))
	if err := r.Load(); err != nil {
		return nil, fmt.Errorf("load device registry: %w", err)
	}
	return r, nil
}

// newFleetCommand — batch OTA push + durable device registry.
func newFleetCommand() *cobra.Command {
	cmd := &cobra.Command{
		Use:   "fleet",
		Short: "Device registry and batch (fleet) OTA upload",
		Long: `Manage a durable registry of OTA-capable boards and push firmware to
many of them at once.

  companion fleet list                      — show registered devices
  companion fleet register <host> [name]    — add/update a device
  companion fleet remove <id>               — forget a device
  companion fleet push <image|sketch> <selectors...>  — flash many boards

Selectors match device id/name/mac/host/mcu (substring) or @tag. Multiple
selectors are ANDed. Always confirms the resolved target list before flashing.`,
	}
	cmd.AddCommand(
		newFleetListCmd(),
		newFleetRegisterCmd(),
		newFleetRemoveCmd(),
		newFleetDiscoverCmd(),
		newFleetPushCmd(),
	)
	return cmd
}

// ── fleet list ─────────────────────────────────────────────────────

func newFleetListCmd() *cobra.Command {
	return &cobra.Command{
		Use:   "list",
		Short: "List registered devices in the fleet registry",
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
			devs := r.All()
			if len(devs) == 0 {
				fmt.Println("No devices registered. Add one with: companion fleet register <host> [name]")
				return nil
			}
			fmt.Printf("%-22s %-18s %-16s %-7s %s\n", "ID", "NAME", "HOST", "MCU", "TAGS")
			for _, d := range devs {
				fmt.Printf("%-22s %-18s %-16s %-7s %s\n",
					d.Key(), d.Name, d.Host, d.MCU, strings.Join(d.Tags, ","))
			}
			fmt.Println()
			printSuccess(fmt.Sprintf("%d device(s) registered", len(devs)))
			return nil
		},
	}
}

// ── fleet register ─────────────────────────────────────────────────

func newFleetRegisterCmd() *cobra.Command {
	var mcu string
	var name string
	var tags string
	var port int
	var probe bool
	cmd := &cobra.Command{
		Use:   "register <host> [name]",
		Short: "Add or update a device in the registry (optional live TCP probe)",
		Args:  cobra.RangeArgs(1, 2),
		RunE: func(cmd *cobra.Command, args []string) error {
			host := args[0]
			if len(args) > 1 && args[1] != "" {
				name = args[1]
			}
			cfg, _, err := config.Load(globalFlags.ConfigFile)
			if err != nil {
				return err
			}
			if err := config.EnsureDirs(cfg); err != nil {
				return err
			}
			if probe {
				printInfo(fmt.Sprintf("Probing %s:%d (OTA)…", host, port))
				if err := ota.Probe(host, port); err != nil {
					return fmt.Errorf("device not reachable: %w", err)
				}
				printSuccess("OTA port reachable")
			}
			id := name
			if id == "" {
				id = host
			}
			var tagList []string
			for _, t := range strings.Split(tags, ",") {
				if t = strings.TrimSpace(t); t != "" {
					tagList = append(tagList, t)
				}
			}
			r, err := fleetRegistry(cfg)
			if err != nil {
				return err
			}
			dev := fleet.Device{ID: id, Name: name, Host: host, Port: port, MCU: mcu, Tags: tagList}
			if err := r.Upsert(dev); err != nil {
				return err
			}
			printSuccess(fmt.Sprintf("Registered %s → %s:%d", colorBold(id), host, port))
			return nil
		},
	}
	cmd.Flags().StringVar(&mcu, "mcu", "", "MCU family: esp32 | esp8266 | avr | stm32 | generic")
	cmd.Flags().StringVar(&tags, "tags", "", "comma-separated tags, e.g. sensors,kitchen")
	cmd.Flags().IntVar(&port, "port", 3232, "OTA port")
	cmd.Flags().BoolVar(&probe, "probe", false, "TCP-check the OTA port before registering")
	return cmd
}

// ── fleet remove ───────────────────────────────────────────────────

func newFleetRemoveCmd() *cobra.Command {
	return &cobra.Command{
		Use:   "remove <id>",
		Short: "Remove a device from the registry",
		Args:  cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			cfg, _, err := config.Load(globalFlags.ConfigFile)
			if err != nil {
				return err
			}
			r, err := fleetRegistry(cfg)
			if err != nil {
				return err
			}
			if _, ok := r.Get(args[0]); !ok {
				return fmt.Errorf("no device with id %q", args[0])
			}
			if err := r.Remove(args[0]); err != nil {
				return err
			}
			printSuccess(fmt.Sprintf("Removed %s", colorBold(args[0])))
			return nil
		},
	}
}
